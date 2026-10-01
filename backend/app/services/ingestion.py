"""Ingestion pipeline orchestration service.

Implements the full process_event_batch algorithm from the design:

  validate investigation → check source_type → parse (per-event)
  → normalize → collect accepted events
  → extract entities → extract relationships
  → sort by timestamp → retrieve candidates → correlate
  → upsert graph (entities + relationships)
  → store events + event_entity_map
  → return IngestionResponse

Partial-batch semantics:
  - Each event in the batch is processed independently.
  - A parse failure or normalization failure adds to the rejected list
    but does NOT stop the rest of the batch.
  - A GraphUnavailableError (Neo4j down) is re-raised immediately because
    it indicates the persistence layer is unavailable for the whole batch.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 16.3
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any

from neo4j import AsyncDriver  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    GraphUnavailableError,
    InvestigationNotFoundError,
    InvalidSourceTypeError,
    ValidationError as AppValidationError,
)
from app.repositories.graph_repository import GraphRepository
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.ingestion import IngestionResponse, RejectedEvent
from app.schemas.parser import ParseError
from app.schemas.security_event import SecurityEvent
from app.services.candidate_retrieval import CandidateRetrieval
from app.services.correlation import TemporalCorrelationEngine
from app.services.entity_extractor import EntityExtractor
from app.services.normalization import NormalizationEngine
from app.services.parser_registry import default_registry
from app.services.relationship_extractor import RelationshipExtractor

logger = logging.getLogger(__name__)


@contextmanager
def StageTimer(stage_name: str, metrics_dict: dict[str, float]):
    """Context manager to record elapsed time (in ms) for a pipeline stage."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        metrics_dict[stage_name] = round(elapsed_ms, 2)


class IngestionService:
    """Orchestrates the full event ingestion pipeline for a single batch.

    All database/driver I/O is injected at construction time so the service
    remains testable with mock dependencies.
    """

    def __init__(self, db: AsyncSession, neo4j_driver: AsyncDriver) -> None:
        self._db = db
        self._neo4j_driver = neo4j_driver

    async def process_event_batch(
        self,
        raw_events: list[dict[str, Any]],
        investigation_id: str,
        source_type: str,
    ) -> IngestionResponse:
        """Process a batch of raw events through the full pipeline.

        Preconditions:
          - investigation_id references an existing investigation owned by the
            calling user (ownership check is the API layer's responsibility).
          - raw_events is a non-empty list of raw event dicts.

        Postconditions:
          - Accepted events are persisted in PostgreSQL and Neo4j.
          - Rejected events are listed in IngestionResponse.errors with reasons.
          - Re-ingesting the same batch is idempotent (ON CONFLICT DO NOTHING).

        Raises:
          InvestigationNotFoundError: if investigation_id does not exist.
          InvalidSourceTypeError: if source_type is not registered.
          GraphUnavailableError: if Neo4j is unreachable during persistence.
        """
        # ------------------------------------------------------------------
        # 1. Validate investigation existence
        # ------------------------------------------------------------------
        inv_repo = InvestigationRepository(self._db)
        row = await inv_repo.get_by_id(investigation_id)
        if row is None:
            raise InvestigationNotFoundError(
                f"Investigation {investigation_id!r} does not exist."
            )

        # ------------------------------------------------------------------
        # 2. Validate source_type is registered
        # ------------------------------------------------------------------
        if not default_registry.is_registered(source_type):
            raise InvalidSourceTypeError(
                f"No parser adapter registered for source_type: {source_type!r}. "
                f"Registered types: {default_registry.list_source_types()}"
            )

        # ------------------------------------------------------------------
        # 3. Parse + normalize each event independently
        # ------------------------------------------------------------------
        metrics: dict[str, float] = {}
        accepted_events: list[SecurityEvent] = []
        rejected_events: list[RejectedEvent] = []
        normalizer = NormalizationEngine()

        with StageTimer("parse_and_normalize", metrics):
            for raw in raw_events:
                # a. Parse
                parse_result = default_registry.dispatch(source_type, raw)
                if isinstance(parse_result, ParseError):
                    logger.debug(
                        "Parse failure for event",
                        extra={
                            "event_id": parse_result.event_id,
                            "field": parse_result.field_name,
                            "reason": parse_result.reason,
                            "investigation_id": investigation_id,
                        },
                    )
                    rejected_events.append(
                        RejectedEvent(
                            event_id=parse_result.event_id,
                            reason=parse_result.reason,
                            field=parse_result.field_name,
                        )
                    )
                    continue

                # b. Normalize (validate timestamps, canonicalize identifiers, etc.)
                try:
                    security_event = normalizer.normalize(parse_result)
                except (AppValidationError, Exception) as exc:
                    logger.debug(
                        "Normalization failure for event",
                        extra={
                            "event_id": parse_result.event_id,
                            "reason": str(exc),
                            "investigation_id": investigation_id,
                        },
                    )
                    rejected_events.append(
                        RejectedEvent(
                            event_id=parse_result.event_id,
                            reason=str(exc),
                        )
                    )
                    continue

                accepted_events.append(security_event)

        if not accepted_events:
            # Nothing made it through — return early with the rejection list.
            return IngestionResponse(
                accepted=0,
                rejected=len(rejected_events),
                errors=rejected_events,
            )

        # Log only event_ids (never raw data) at INFO level (Req 15.5).
        accepted_ids = [e.event_id for e in accepted_events]
        logger.info(
            "Batch parse+normalize complete",
            extra={
                "investigation_id": investigation_id,
                "accepted": len(accepted_events),
                "rejected": len(rejected_events),
                "event_ids": accepted_ids,
            },
        )

        # ------------------------------------------------------------------
        # 4. Entity extraction
        # ------------------------------------------------------------------
        with StageTimer("entity_extraction", metrics):
            extractor = EntityExtractor()
            entities = extractor.extract(accepted_events, investigation_id=investigation_id)

            # Build event_id → [entity_id, ...] map for EventRepository
            entity_map: dict[str, list[str]] = {}
            for entity in entities:
                for eid in entity.event_ids:
                    entity_map.setdefault(eid, []).append(entity.entity_id)

        # ------------------------------------------------------------------
        # 5. Relationship extraction
        # ------------------------------------------------------------------
        with StageTimer("relationship_extraction", metrics):
            rel_extractor = RelationshipExtractor()
            raw_rels = rel_extractor.extract(
                accepted_events,
                entities,
                investigation_id=investigation_id,
            )

        # ------------------------------------------------------------------
        # 6. Candidate retrieval (requires ascending timestamp order)
        # ------------------------------------------------------------------
        with StageTimer("candidate_retrieval", metrics):
            sorted_events = sorted(accepted_events, key=lambda e: e.timestamp)

            candidate_retrieval = CandidateRetrieval()
            candidates = candidate_retrieval.retrieve(
                sorted_events,
                window_minutes=10,
                investigation_id=investigation_id,
            )

        # ------------------------------------------------------------------
        # 7. Temporal correlation
        # ------------------------------------------------------------------
        with StageTimer("correlation", metrics):
            corr_engine = TemporalCorrelationEngine()
            correlated_rels = corr_engine.correlate(candidates)

        # ------------------------------------------------------------------
        # 8. Persist graph: entities + relationships (Neo4j)
        # ------------------------------------------------------------------
        with StageTimer("graph_persistence", metrics):
            graph_repo = GraphRepository(self._neo4j_driver)

            # Upsert all entities
            for entity in entities:
                await graph_repo.upsert_entity(entity)  # raises GraphUnavailableError on failure

            # Build a set of (source, target, type) keys for correlated rels to
            # detect which raw_rels have no correlated counterpart.
            corr_keys: set[tuple[str, str, str]] = {
                (r.source_entity_id, r.target_entity_id, r.relationship_type.value)
                for r in correlated_rels
            }

            # Upsert correlated relationships (carry signal metadata)
            for rel in correlated_rels:
                await graph_repo.upsert_relationship(rel)

            # Upsert raw relationships that were NOT enriched by correlation
            # (single-event evidence with no temporal pairing partner).
            # Convert RawRelationship → CorrelatedRelationship with zero signal metadata.
            from app.schemas.relationship import CorrelatedRelationship  # noqa: PLC0415

            for raw_rel in raw_rels:
                key = (
                    raw_rel.source_entity_id,
                    raw_rel.target_entity_id,
                    raw_rel.relationship_type.value,
                )
                if key not in corr_keys:
                    # Promote to CorrelatedRelationship with no signal data
                    promoted = CorrelatedRelationship(
                        relationship_id=raw_rel.relationship_id,
                        source_entity_id=raw_rel.source_entity_id,
                        target_entity_id=raw_rel.target_entity_id,
                        relationship_type=raw_rel.relationship_type,
                        investigation_id=raw_rel.investigation_id,
                        timestamp=raw_rel.timestamp,
                        event_ids=raw_rel.event_ids,
                        source=raw_rel.source,
                        signal_names=[],
                        signal_scores={},
                        combined_score=0.0,
                        explanation="Directly extracted relationship (no temporal correlation).",
                    )
                    await graph_repo.upsert_relationship(promoted)

        # ------------------------------------------------------------------
        # 9. Store events + entity map in PostgreSQL
        # ------------------------------------------------------------------
        with StageTimer("pg_persistence", metrics):
            from app.repositories.event_repository import EventRepository  # noqa: PLC0415

            ev_repo = EventRepository(self._db)
            await ev_repo.store(
                accepted_events,
                investigation_id=investigation_id,
                entity_map=entity_map,
            )

        logger.info(
            "Ingestion pipeline complete",
            extra={
                "investigation_id": investigation_id,
                "accepted": len(accepted_events),
                "entities": len(entities),
                "correlated_relationships": len(correlated_rels),
                "timing_metrics": metrics,
            },
        )

        return IngestionResponse(
            accepted=len(accepted_events),
            rejected=len(rejected_events),
            errors=rejected_events,
            timing_metrics=metrics,
        )
