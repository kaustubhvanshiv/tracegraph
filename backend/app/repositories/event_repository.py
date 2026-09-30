"""PostgreSQL event repository.

Stores normalized SecurityEvent objects and the event→entity mapping used by
the Timeline service to cross-link events and graph nodes.

Design decisions:
  - ON CONFLICT DO NOTHING on the (event_id, investigation_id) unique key
    makes re-ingestion idempotent (Req 8.1, 8.2).
  - ON CONFLICT DO NOTHING on event_entity_map's unique key is similarly safe.
  - All queries use parameterized SQLAlchemy — no string interpolation (Req 15.6).
  - ORM models are imported lazily inside methods to avoid the Python 3.14 /
    SQLAlchemy 2.0.31 Union.__getitem__ incompatibility at class-definition time
    (same pattern as investigation_repository.py).

Requirements: 15.6
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.security_event import SecurityEvent

logger = logging.getLogger(__name__)


class EventRepository:
    """PostgreSQL persistence for security events and their entity associations."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # store
    # ------------------------------------------------------------------

    async def store(
        self,
        events: list[SecurityEvent],
        investigation_id: str,
        entity_map: dict[str, list[str]],
    ) -> None:
        """Persist *events* and their entity associations.

        Parameters
        ----------
        events:
            Normalized SecurityEvent objects to persist.
        investigation_id:
            UUID string scoping these events.
        entity_map:
            Mapping of event_id → list of entity_ids extracted from that event.
            Used to populate the ``event_entity_map`` table.

        Notes
        -----
        - Uses ``INSERT … ON CONFLICT DO NOTHING`` for idempotent re-ingestion.
        - All values go through parameterized SQLAlchemy — never interpolated.
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: PLC0415

        from app.models.event_entity_map import EventEntityMapModel  # noqa: PLC0415
        from app.models.security_event import SecurityEventModel  # noqa: PLC0415

        inv_uuid = _to_uuid(investigation_id)

        for event in events:
            # ---- security_events row ----
            stmt = (
                pg_insert(SecurityEventModel)
                .values(
                    event_id=event.event_id,
                    investigation_id=inv_uuid,
                    source_type=event.source_type,
                    timestamp=event.timestamp,
                    event_type=event.event_type,
                    action=event.action,
                    user=event.user,
                    source_host=event.source_host,
                    destination_host=event.destination_host,
                    source_ip=event.source_ip,
                    destination_ip=event.destination_ip,
                    process=event.process,
                    file=event.file,
                    severity=event.severity,
                    raw_data=event.raw_data,
                )
                .on_conflict_do_nothing(
                    index_elements=["event_id", "investigation_id"]
                )
            )
            await self._db.execute(stmt)

            # ---- event_entity_map rows ----
            entity_ids = entity_map.get(event.event_id, [])
            for entity_id in entity_ids:
                map_stmt = (
                    pg_insert(EventEntityMapModel)
                    .values(
                        event_id=event.event_id,
                        investigation_id=inv_uuid,
                        entity_id=entity_id,
                    )
                    .on_conflict_do_nothing(
                        index_elements=["event_id", "investigation_id", "entity_id"]
                    )
                )
                await self._db.execute(map_stmt)

        await self._db.commit()

        logger.debug(
            "Stored %d events for investigation %s",
            len(events),
            investigation_id,
        )

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------

    async def get(
        self,
        event_id: str,
        investigation_id: str,
    ) -> SecurityEvent | None:
        """Retrieve a single SecurityEvent by (event_id, investigation_id).

        Returns ``None`` if not found.  The returned ``SecurityEvent``
        is reconstructed from the stored row — the ``raw_data`` field
        preserves the original parsed representation.
        """
        from sqlalchemy import select  # noqa: PLC0415

        from app.models.security_event import SecurityEventModel  # noqa: PLC0415

        inv_uuid = _to_uuid(investigation_id)

        result = await self._db.execute(
            select(SecurityEventModel).where(
                SecurityEventModel.event_id == event_id,
                SecurityEventModel.investigation_id == inv_uuid,  # type: ignore[arg-type]
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        return _row_to_security_event(row)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_uuid(value: str) -> uuid.UUID:
    """Convert a UUID string to a ``uuid.UUID`` object.

    Falls back to treating the value as a literal UUID if already valid,
    otherwise wraps in a new UUID via the uuid5 namespace to avoid crashes
    on non-UUID investigation IDs used in tests.
    """
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        # Test fixtures sometimes use short strings; hash to a stable UUID.
        return uuid.uuid5(uuid.NAMESPACE_DNS, value)


def _row_to_security_event(row: Any) -> SecurityEvent:
    """Convert a ``SecurityEventModel`` ORM row to a ``SecurityEvent`` schema."""
    return SecurityEvent(
        event_id=row.event_id,
        source_type=row.source_type,
        timestamp=row.timestamp,
        event_type=row.event_type,
        action=row.action,
        user=row.user,
        source_host=row.source_host,
        destination_host=row.destination_host,
        source_ip=row.source_ip,
        destination_ip=row.destination_ip,
        process=row.process,
        file=row.file,
        severity=row.severity,
        raw_data=row.raw_data,
    )
