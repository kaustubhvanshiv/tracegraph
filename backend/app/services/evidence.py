"""Evidence detail service.

Returns the full evidence record for a single event:
  - Normalized SecurityEvent fields
  - Original raw_data
  - All extracted entities
  - All relationships referencing the event_id
  - Correlation metadata (signals, score, explanation)

Enforces investigation isolation — never returns data belonging to a different
investigation.

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.errors import EventNotFoundError
from app.repositories.event_repository import EventRepository
from app.repositories.graph_repository import GraphRepository
from app.schemas.summary import EvidenceDetail

logger = logging.getLogger(__name__)


class EvidenceDetailService:
    """Service retrieving comprehensive evidence detail for a single security event."""

    def __init__(
        self,
        event_repo: EventRepository | None = None,
        graph_repo: GraphRepository | None = None,
        db=None,
        neo4j_driver=None,
    ) -> None:
        if event_repo is not None and graph_repo is not None:
            self._event_repo = event_repo
            self._graph_repo = graph_repo
        else:
            self._event_repo = EventRepository(db) if db is not None else event_repo
            self._graph_repo = GraphRepository(neo4j_driver) if neo4j_driver is not None else graph_repo

    async def get_evidence(
        self,
        event_id: str,
        investigation_id: str,
    ) -> EvidenceDetail:
        """Return full evidence detail for *event_id* within *investigation_id*.

        Parameters
        ----------
        event_id:
            Target event identifier.
        investigation_id:
            Investigation identifier scoping the lookup.

        Returns
        -------
        EvidenceDetail:
            Envelope containing the event, raw_data, entities, relationships,
            and correlation metadata.

        Raises
        ------
        EventNotFoundError (HTTP 404):
            If the event does not exist in this investigation.
        """
        # 1. Fetch normalized event from PostgreSQL
        event = await self._event_repo.get(event_id, investigation_id)
        if event is None:
            logger.warning(
                "Event %s not found in investigation %s",
                event_id,
                investigation_id,
            )
            raise EventNotFoundError(
                f"Event {event_id!r} not found in investigation {investigation_id!r}"
            )

        # 2. Fetch extracted entities from Neo4j
        entities = await self._graph_repo.get_entities_for_event(
            event_id, investigation_id
        )

        # 3. Fetch correlated relationships referencing event_id from Neo4j
        relationships = await self._graph_repo.get_relationships_for_event(
            event_id, investigation_id
        )

        # 4. Extract correlation metadata for relationships
        correlation_metadata: list[dict[str, Any]] = []
        for rel in relationships:
            correlation_metadata.append(
                {
                    "relationship_id": rel.relationship_id,
                    "relationship_type": rel.relationship_type.value,
                    "source_entity_id": rel.source_entity_id,
                    "target_entity_id": rel.target_entity_id,
                    "signal_names": rel.signal_names,
                    "signal_scores": rel.signal_scores,
                    "combined_score": rel.combined_score,
                    "explanation": rel.explanation,
                }
            )

        return EvidenceDetail(
            event=event,
            raw_data=event.raw_data,
            entities=entities,
            relationships=relationships,
            correlation_metadata=correlation_metadata,
        )
