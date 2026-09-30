"""Timeline service.

Returns events sorted ascending by timestamp from PostgreSQL security_events
table, with entity_ids cross-linked via event_entity_map.

Supports filters: time range, entity_id, event_type, severity.

Design decisions:
  - All queries use parameterized SQLAlchemy expressions — no string
    interpolation (Req 15.6).
  - When entity_id filter is active, a subquery on event_entity_map restricts
    the event set before pagination — no post-filter step (Req 9.6).
  - entity_ids for each page are loaded in a single batch query (not N+1).
  - ORM models are lazily imported inside methods to avoid the Python 3.14 /
    SQLAlchemy 2.0.31 Union.__getitem__ incompatibility at class-definition
    time.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.timeline import TimelineEvent, TimelineFilter, TimelineResult

logger = logging.getLogger(__name__)


def _to_uuid(value: str) -> uuid.UUID:
    """Convert a UUID string to a ``uuid.UUID`` object.

    Non-UUID strings (e.g. in tests) are hashed to a stable UUID via uuid5.
    """
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(value))


class TimelineService:
    """Retrieve a chronologically sorted, filtered timeline for an investigation.

    Requirements: 9.1–9.7
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_timeline(
        self,
        investigation_id: str,
        filters: TimelineFilter,
    ) -> TimelineResult:
        """Return a paginated, filtered timeline for the investigation.

        Parameters
        ----------
        investigation_id:
            UUID string of the investigation.
        filters:
            Optional time range, entity_id, event_type, severity, limit,
            offset.  All filter fields that are ``None`` are ignored (no
            narrowing applied).

        Returns
        -------
        TimelineResult:
            Contains events sorted ascending by timestamp, each decorated with
            entity_ids from event_entity_map, plus the total count of matching
            events (before pagination).
        """
        # Lazy imports to avoid SQLAlchemy 2.0 Union.__getitem__ issue.
        from sqlalchemy import func, select  # noqa: PLC0415

        from app.models.event_entity_map import EventEntityMapModel  # noqa: PLC0415
        from app.models.security_event import SecurityEventModel  # noqa: PLC0415

        inv_uuid = _to_uuid(investigation_id)

        # ------------------------------------------------------------------
        # Build base WHERE conditions
        # ------------------------------------------------------------------
        conditions: list[Any] = [
            SecurityEventModel.investigation_id == inv_uuid,  # type: ignore[arg-type]
        ]

        if filters.start_time is not None:
            conditions.append(SecurityEventModel.timestamp >= filters.start_time)

        if filters.end_time is not None:
            conditions.append(SecurityEventModel.timestamp <= filters.end_time)

        if filters.event_type is not None:
            conditions.append(SecurityEventModel.event_type == filters.event_type)

        if filters.severity is not None:
            conditions.append(SecurityEventModel.severity == filters.severity)

        # entity_id filter — use a subquery so only events linked to the
        # given entity survive, satisfying the filter-is-subset invariant.
        if filters.entity_id is not None:
            entity_subq = (
                select(EventEntityMapModel.event_id)
                .where(
                    EventEntityMapModel.investigation_id == inv_uuid,  # type: ignore[arg-type]
                    EventEntityMapModel.entity_id == filters.entity_id,
                )
                .scalar_subquery()
            )
            conditions.append(SecurityEventModel.event_id.in_(entity_subq))

        # ------------------------------------------------------------------
        # Count total matching rows (before pagination)
        # ------------------------------------------------------------------
        count_stmt = select(func.count()).select_from(SecurityEventModel)
        for cond in conditions:
            count_stmt = count_stmt.where(cond)

        total_result = await self._db.execute(count_stmt)
        total: int = total_result.scalar_one()

        # ------------------------------------------------------------------
        # Fetch the page of events sorted by timestamp ASC
        # ------------------------------------------------------------------
        events_stmt = select(SecurityEventModel)
        for cond in conditions:
            events_stmt = events_stmt.where(cond)
        events_stmt = (
            events_stmt.order_by(SecurityEventModel.timestamp.asc())
            .offset(filters.offset)
            .limit(filters.limit)
        )

        rows_result = await self._db.execute(events_stmt)
        event_rows = list(rows_result.scalars().all())

        if not event_rows:
            return TimelineResult(
                investigation_id=investigation_id,
                events=[],
                total=total,
            )

        # ------------------------------------------------------------------
        # Batch-fetch entity_ids for all events on this page (avoids N+1)
        # ------------------------------------------------------------------
        page_event_ids = [row.event_id for row in event_rows]

        entity_map_stmt = select(
            EventEntityMapModel.event_id,
            EventEntityMapModel.entity_id,
        ).where(
            EventEntityMapModel.investigation_id == inv_uuid,  # type: ignore[arg-type]
            EventEntityMapModel.event_id.in_(page_event_ids),
        )

        entity_rows_result = await self._db.execute(entity_map_stmt)
        entity_rows = entity_rows_result.all()

        # Build a mapping: event_id → [entity_id, ...]
        entity_id_map: dict[str, list[str]] = {}
        for eid, entity_id in entity_rows:
            entity_id_map.setdefault(eid, []).append(entity_id)

        # ------------------------------------------------------------------
        # Assemble TimelineEvent objects
        # ------------------------------------------------------------------
        from app.repositories.event_repository import _row_to_security_event  # noqa: PLC0415

        timeline_events: list[TimelineEvent] = []
        for row in event_rows:
            security_event = _row_to_security_event(row)
            timeline_events.append(
                TimelineEvent(
                    event=security_event,
                    entity_ids=entity_id_map.get(row.event_id, []),
                )
            )

        logger.debug(
            "Timeline query returned %d/%d events for investigation %s",
            len(timeline_events),
            total,
            investigation_id,
        )

        return TimelineResult(
            investigation_id=investigation_id,
            events=timeline_events,
            total=total,
        )
