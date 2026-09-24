"""PostgreSQL investigation repository.

CRUD operations using parameterized SQLAlchemy async queries (no string
interpolation to prevent SQL injection).

ORM models are imported lazily (inside methods) to avoid a Python 3.14 /
SQLAlchemy 2.0.31 `Union.__getitem__` incompatibility that triggers at class
definition time when models are imported at module level.  This mirrors the
pattern already used in ``app/core/auth.py``.

Requirements covered: 11.1, 11.5, 11.6, 11.7, 15.6
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.investigation import (
    CreateInvestigationPayload,
    InvestigationFilter,
    InvestigationStatus,
    NotePayload,
)


class InvestigationRepository:
    """All DB operations for the investigations and investigation_notes tables.

    All queries use parameterized SQLAlchemy expressions — never string
    interpolation — satisfying Requirement 15.6.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        payload: CreateInvestigationPayload,
        owner_id: str,
    ):
        """Persist a new investigation and return the ORM row."""
        from app.models.investigation import InvestigationModel  # noqa: PLC0415

        now = datetime.now(UTC)
        row = InvestigationModel(
            investigation_id=uuid.uuid4(),
            title=payload.title,
            description=payload.description,
            status=InvestigationStatus.OPEN.value,
            outcome=None,
            created_at=now,
            updated_at=now,
            owner_id=owner_id,
            event_count=0,
        )
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return row

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_id(self, investigation_id: str):
        """Return the investigation row, or None if it doesn't exist."""
        from app.models.investigation import InvestigationModel  # noqa: PLC0415

        result = await self._db.execute(
            select(InvestigationModel).where(
                InvestigationModel.investigation_id == investigation_id  # type: ignore[arg-type]
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        filters: InvestigationFilter,
    ) -> list:
        """Return a paginated slice of investigations matching filters."""
        from app.models.investigation import InvestigationModel  # noqa: PLC0415

        stmt = select(InvestigationModel)

        if filters.owner_id is not None:
            stmt = stmt.where(InvestigationModel.owner_id == filters.owner_id)

        if filters.status is not None:
            stmt = stmt.where(InvestigationModel.status == filters.status.value)

        stmt = (
            stmt.order_by(InvestigationModel.created_at.desc())
            .offset(filters.offset)
            .limit(filters.limit)
        )

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Update status
    # ------------------------------------------------------------------

    async def update_status(
        self,
        investigation_id: str,
        new_status: InvestigationStatus,
    ):
        """Set a new status and bump updated_at. Returns updated row or None."""
        from app.models.investigation import InvestigationModel  # noqa: PLC0415

        now = datetime.now(UTC)
        await self._db.execute(
            update(InvestigationModel)
            .where(
                InvestigationModel.investigation_id == investigation_id  # type: ignore[arg-type]
            )
            .values(status=new_status.value, updated_at=now)
        )
        await self._db.commit()
        return await self.get_by_id(investigation_id)

    # ------------------------------------------------------------------
    # Record outcome
    # ------------------------------------------------------------------

    async def record_outcome(
        self,
        investigation_id: str,
        outcome: str,
    ):
        """Persist the outcome label. Returns updated row or None."""
        from app.models.investigation import InvestigationModel  # noqa: PLC0415

        now = datetime.now(UTC)
        await self._db.execute(
            update(InvestigationModel)
            .where(
                InvestigationModel.investigation_id == investigation_id  # type: ignore[arg-type]
            )
            .values(outcome=outcome, updated_at=now)
        )
        await self._db.commit()
        return await self.get_by_id(investigation_id)

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    async def add_note(
        self,
        investigation_id: str,
        payload: NotePayload,
        author_id: str,
    ):
        """Persist a new analyst note and return the ORM row."""
        from app.models.note import InvestigationNoteModel  # noqa: PLC0415

        row = InvestigationNoteModel(
            note_id=uuid.uuid4(),
            investigation_id=uuid.UUID(investigation_id),
            author_id=author_id,
            body=payload.body,
            created_at=datetime.now(UTC),
        )
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return row

    async def list_notes(
        self,
        investigation_id: str,
    ) -> list:
        """Return all notes for an investigation, oldest first."""
        from app.models.note import InvestigationNoteModel  # noqa: PLC0415

        result = await self._db.execute(
            select(InvestigationNoteModel)
            .where(
                InvestigationNoteModel.investigation_id == investigation_id  # type: ignore[arg-type]
            )
            .order_by(InvestigationNoteModel.created_at.asc())
        )
        return list(result.scalars().all())
