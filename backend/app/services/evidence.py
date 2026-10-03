"""Evidence detail service.

Returns the full evidence record for a single event:
  - Normalized SecurityEvent fields
  - Original raw_data
  - All extracted entities
  - All relationships referencing the event_id
  - Correlation metadata (signals, score, explanation)

Enforces investigation isolation — never returns data from a different
investigation.

Full implementation is covered by task 16.1.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_event import SecurityEventModel
from app.models.event_entity_map import EventEntityMapModel
from app.repositories.graph_repository import GraphRepository
from app.schemas.entity import Entity
from app.schemas.graph import EntityDetail, GraphFilter
from app.schemas.relationship import CorrelatedRelationship
from app.schemas.security_event import SecurityEvent
from app.schemas.summary import EvidenceDetail

logger = logging.getLogger(__name__)


class EvidenceDetailService:
    """Service for retrieving full evidence detail for a single event."""

    def __init__(
        self,
        db: AsyncSession,
        neo4j_driver,
    ) -> None:
        self._db = db
        self._graph_repo = GraphRepository(neo4j_driver)

    async def get_evidence(
        self,
        event_id: str,
        investigation_id: str,
    ) -> EvidenceDetail:
        """Retrieve the full evidence record for an event.

        Args:
            event_id: The event ID to retrieve.
            investigation_id: The investigation ID for isolation.

        Returns:
            EvidenceDetail with normalized event, raw_data, entities,
            relationships, and correlation metadata.

        Raises:
            KeyError: If event_id not found in investigation.
        """
        # 1. Fetch the normalized event from PostgreSQL
        stmt = select(SecurityEventModel).where(
            SecurityEventModel.event_id == event_id,
            SecurityEventModel.investigation_id == investigation_id,
        )
        result = await self._db.execute(stmt)
        event_row = result.scalar_one_or_none()

        if event_row is None:
            raise KeyError(
                f"Event {event_id!r} not found in investigation {investigation_id!r}"
            )

        # Convert to SecurityEvent schema
        security_event = SecurityEvent(
            event_id=event_row.event_id,
            investigation_id=event_row.investigation_id,
            source_type=event_row.source_type,
            timestamp=event_row.timestamp,
            event_type=event_row.event_type,
            action=event_row.action,
            user=event_row.user,
            source_host=event_row.source_host,
            destination_host=event_row.destination_host,
            source_ip=event_row.source_ip,
            destination_ip=event_row.destination_ip,
            process=event_row.process,
            file=event_row.file,
            severity=event_row.severity,
            raw_data=event_row.raw_data,
        )

        # 2. Fetch entities linked to this event from event_entity_map
        entity_stmt = select(EventEntityMapModel).where(
            EventEntityMapModel.event_id == event_id,
            EventEntityMapModel.investigation_id == investigation_id,
        )
        entity_result = await self._db.execute(entity_stmt)
        entity_map_rows = entity_result.scalars().all()

        entity_ids = [row.entity_id for row in entity_map_rows]

        # 3. Fetch entity details from Neo4j
        entities: list[Entity] = []
        for eid in entity_ids:
            try:
                entity_detail: EntityDetail = await self._graph_repo.get_entity(
                    eid, investigation_id
                )
                entities.append(entity_detail.entity)
            except KeyError:
                # Entity not in graph (shouldn't happen but be defensive)
                logger.warning(
                    "Entity %s from event_entity_map not found in graph",
                    eid,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch entity %s from graph: %s", eid, exc)

        # 4. Fetch all relationships referencing this event_id from Neo4j
        # We need to query all relationships in the investigation and filter
        # by event_id. This is a limitation of the current schema - we could
        # optimize with a direct index on event_ids in Neo4j later.
        graph_result = await self._graph_repo.get_graph(
            investigation_id,
            GraphFilter(),
        )

        # Filter relationships that reference this event_id
        relationships: list[CorrelatedRelationship] = []
        correlation_metadata: list[dict[str, Any]] = []

        for rel in graph_result.edges:
            if event_id in rel.event_ids:
                relationships.append(rel)
                correlation_metadata.append(
                    {
                        "relationship_id": rel.relationship_id,
                        "signal_names": rel.signal_names,
                        "signal_scores": rel.signal_scores,
                        "combined_score": rel.combined_score,
                        "explanation": rel.explanation,
                    }
                )

        return EvidenceDetail(
            event=security_event,
            raw_data=security_event.raw_data,
            entities=entities,
            relationships=relationships,
            correlation_metadata=correlation_metadata,
        )