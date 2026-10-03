"""AI context builder.

Assembles a bounded, structured InvestigationContext from graph, timeline,
and evidence data.  Applies configurable size limits; prioritizes high/critical
severity events and most-connected events when sampling.

Never includes secrets, credentials, or PII beyond normalized event fields.
Produces a fully JSON-serializable context with no circular references.

Full implementation is covered by task 19.1.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.repositories.graph_repository import GraphRepository
from app.schemas.entity import Entity
from app.schemas.graph import EntityDetail, GraphFilter
from app.schemas.relationship import CorrelatedRelationship
from app.schemas.security_event import SecurityEvent
from app.schemas.summary import InvestigationContext
from app.services.timeline import TimelineService
from app.services.evidence import EvidenceDetailService

logger = logging.getLogger(__name__)


@dataclass
class _EventWithScore:
    """Internal helper for event scoring during sampling."""
    event: SecurityEvent
    score: float
    connections: int


class AIContextBuilder:
    """Builds a bounded InvestigationContext for AI summary generation."""

    def __init__(
        self,
        db,
        neo4j_driver,
    ) -> None:
        self._db = db
        self._neo4j_driver = neo4j_driver
        self._graph_repo = GraphRepository(neo4j_driver)
        self._timeline_service = TimelineService(db=db)
        self._evidence_service = EvidenceDetailService(db=db, neo4j_driver=neo4j_driver)

    async def build_context(
        self,
        investigation_id: str,
        max_events: int | None = None,
    ) -> InvestigationContext:
        """Build a bounded InvestigationContext for an investigation.

        Args:
            investigation_id: Target investigation.
            max_events: Maximum events to include (default from config).

        Returns:
            InvestigationContext with entities, relationships, and sampled events.
            Total events count is the actual total, not the sampled count.
        """
        if max_events is None:
            max_events = settings.ai_context_max_events

        # 1. Get full graph (all entities and relationships)
        graph_result = await self._graph_repo.get_graph(
            investigation_id, GraphFilter()
        )
        all_entities = graph_result.nodes
        all_relationships = graph_result.edges

        # 2. Get full timeline to count total events and get all events
        timeline_result = await self._timeline_service.get_timeline(
            investigation_id, filters=None
        )
        total_events = len(timeline_result.events)
        all_events = timeline_result.events

        # 3. Score events for sampling priority
        scored_events = await self._score_events(
            all_events, all_relationships, all_entities
        )

        # 4. Sample events: high/critical severity first, then most connected
        sampled_events = self._sample_events(scored_events, max_events)

        # 5. Filter entities to only those present in sampled events
        # (entities that appear in at least one sampled event)
        sampled_entity_ids = set()
        for event in sampled_events:
            sampled_entity_ids.update(event.entity_ids)
        # Also include entities that are endpoints of relationships in sampled events
        for rel in all_relationships:
            if rel.event_ids & {e.event_id for e in sampled_events}:
                sampled_entity_ids.add(rel.source_entity_id)
                sampled_entity_ids.add(rel.target_entity_id)

        filtered_entities = [
            e for e in all_entities if e.entity_id in sampled_entity_ids
        ]

        # 6. Filter relationships to only those with at least one evidence reference
        # in the sampled events (and between filtered entities)
        sampled_event_ids = {e.event_id for e in sampled_events}
        filtered_relationships = [
            rel
            for rel in all_relationships
            if rel.event_ids & sampled_event_ids
            and rel.source_entity_id in sampled_entity_ids
            and rel.target_entity_id in sampled_entity_ids
        ]

        # 7. Build context hash for caching
        context_hash = self._compute_context_hash(
            investigation_id, filtered_entities, filtered_relationships, sampled_events
        )

        return InvestigationContext(
            investigation_id=investigation_id,
            total_events=total_events,
            entities=filtered_entities,
            relationships=filtered_relationships,
            sampled_events=sampled_events,
        )

    async def _score_events(
        self,
        events: list[SecurityEvent],
        relationships: list[CorrelatedRelationship],
        entities: list[Entity],
    ) -> list[_EventWithScore]:
        """Score events for sampling priority.

        Priority factors:
        - Severity (high/critical = higher score)
        - Number of connections (entity degree in graph)
        """
        # Build entity connection count from relationships
        entity_connections: Counter[str] = Counter()
        for rel in relationships:
            entity_connections[rel.source_entity_id] += 1
            entity_connections[rel.target_entity_id] += 1

        # Map event_id -> event for quick lookup
        event_map = {e.event_id: e for e in events}

        # Score each event
        scored: list[_EventWithScore] = []
        for event in events:
            # Severity score: critical=4, high=3, medium=2, low=1, none=0
            severity_scores = {
                "critical": 4,
                "high": 3,
                "medium": 2,
                "low": 1,
                None: 0,
            }
            severity_score = severity_scores.get(event.severity, 0)

            # Connection score: sum of connections of entities in this event
            connection_score = sum(
                entity_connections.get(eid, 0) for eid in event.entity_ids
            )

            # Combined score: severity is primary, connections secondary
            # Multiply severity by 100 to prioritize over connections
            total_score = severity_score * 100 + connection_score

            scored.append(
                _EventWithScore(
                    event=event,
                    score=total_score,
                    connections=connection_score,
                )
            )

        # Sort by score descending
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored

    def _sample_events(
        self,
        scored_events: list[_EventWithScore],
        max_events: int,
    ) -> list[SecurityEvent]:
        """Sample events up to max_events, preserving priority order."""
        if len(scored_events) <= max_events:
            return [s.event for s in scored_events]
        return [s.event for s in scored_events[:max_events]]

    def _compute_context_hash(
        self,
        investigation_id: str,
        entities: list[Entity],
        relationships: list[CorrelatedRelationship],
        events: list[SecurityEvent],
    ) -> str:
        """Compute a deterministic hash of the context for caching."""
        # Create a string representation of the key data
        parts = [investigation_id]
        for e in sorted(entities, key=lambda x: x.entity_id):
            parts.append(f"E:{e.entity_id}:{e.entity_type.value}:{e.canonical_key}")
        for r in sorted(relationships, key=lambda x: x.relationship_id):
            parts.append(
                f"R:{r.relationship_id}:{r.source_entity_id}:"
                f"{r.target_entity_id}:{r.relationship_type.value}"
            )
        for e in sorted(events, key=lambda x: x.event_id):
            parts.append(f"V:{e.event_id}:{e.timestamp.isoformat()}:{e.severity or ''}")

        context_str = "|".join(parts)
        return hashlib.sha256(context_str.encode()).hexdigest()[:16]