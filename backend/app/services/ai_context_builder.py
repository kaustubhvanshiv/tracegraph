"""AI context builder.

Assembles a bounded, structured InvestigationContext from graph, timeline,
and evidence data. Applies configurable size limits; prioritizes high/critical
severity events and most-connected events when sampling.

Never includes secrets, credentials, or PII beyond normalized event fields.
Produces a fully JSON-serializable context with no circular references.

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7
"""

from __future__ import annotations

import logging
from typing import Sequence

from app.schemas.entity import Entity
from app.schemas.graph import GraphResult
from app.schemas.relationship import CorrelatedRelationship
from app.schemas.security_event import SecurityEvent
from app.schemas.summary import InvestigationContext
from app.schemas.timeline import TimelineEvent, TimelineResult

logger = logging.getLogger(__name__)

SEVERITY_WEIGHTS: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


class AIContextBuilder:
    """Service to construct a bounded InvestigationContext for AI summary generation."""

    def build_context(
        self,
        investigation_id: str,
        graph: GraphResult,
        timeline: TimelineResult | Sequence[SecurityEvent] | Sequence[TimelineEvent],
        max_events: int = 50,
    ) -> InvestigationContext:
        """Build a bounded, structured InvestigationContext.

        Parameters
        ----------
        investigation_id:
            ID of the investigation.
        graph:
            GraphResult containing nodes and edges for the investigation.
        timeline:
            TimelineResult or sequence of SecurityEvent / TimelineEvent objects.
        max_events:
            Maximum number of sampled events to include (default: 50).

        Returns
        -------
        InvestigationContext:
            Bounded context containing entities, evidence relationships, and sampled events.
        """
        # 1. Extract events list and total event count
        if isinstance(timeline, TimelineResult):
            events_list = timeline.events
            total_events = getattr(timeline, "total", getattr(timeline, "total_count", len(timeline.events)))
        else:
            events_list = list(timeline)
            total_events = len(events_list)

        # Convert TimelineEvent objects to SecurityEvent if needed
        normalized_events: list[SecurityEvent] = []
        for item in events_list:
            if isinstance(item, TimelineEvent):
                normalized_events.append(item.event)
            elif isinstance(item, SecurityEvent):
                normalized_events.append(item)

        # 2. Filter entities: include only entities present in the investigation graph
        entities: list[Entity] = list(graph.nodes)

        # 3. Filter relationships: include only relationships with at least one evidence reference
        relationships: list[CorrelatedRelationship] = [
            rel for rel in graph.edges if len(rel.event_ids) >= 1
        ]

        # 4. Compute event connectivity (how many graph relationships reference each event_id)
        event_connectivity: dict[str, int] = {}
        for rel in relationships:
            for eid in rel.event_ids:
                event_connectivity[eid] = event_connectivity.get(eid, 0) + 1

        # 5. Prioritize and sample events:
        # High/critical severity first, then most-connected events, then by timestamp
        def sort_key(event: SecurityEvent) -> tuple[int, int, str]:
            sev_w = SEVERITY_WEIGHTS.get(
                event.severity.lower() if event.severity else "low", 1
            )
            conn_cnt = event_connectivity.get(event.event_id, 0)
            ts_str = event.timestamp.isoformat() if event.timestamp else ""
            return (-sev_w, -conn_cnt, ts_str)

        sorted_events = sorted(normalized_events, key=sort_key)
        seen_ids: set[str] = set()
        sampled_events: list[SecurityEvent] = []

        for evt in sorted_events:
            if evt.event_id not in seen_ids:
                seen_ids.add(evt.event_id)
                sampled_events.append(evt)
                if len(sampled_events) >= max_events:
                    break

        return InvestigationContext(
            investigation_id=investigation_id,
            total_events=total_events,
            entities=entities,
            relationships=relationships,
            sampled_events=sampled_events,
        )
