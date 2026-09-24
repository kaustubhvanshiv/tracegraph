"""Investigation management service.

Implements lifecycle state machine:
  OPEN → UNDER_REVIEW
  UNDER_REVIEW → OPEN (revert)
  UNDER_REVIEW → CLOSED

Valid outcomes: TRUE_POSITIVE, FALSE_POSITIVE, INCONCLUSIVE, ESCALATED

Requirements covered: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 15.6
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, InvestigationNotFoundError, ValidationError
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.investigation import (
    CreateInvestigationPayload,
    Investigation,
    InvestigationFilter,
    InvestigationOutcome,
    InvestigationStatus,
    Note,
    NotePayload,
)

# ---------------------------------------------------------------------------
# Lifecycle state machine — valid transitions
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[InvestigationStatus, set[InvestigationStatus]] = {
    InvestigationStatus.OPEN: {InvestigationStatus.UNDER_REVIEW},
    InvestigationStatus.UNDER_REVIEW: {
        InvestigationStatus.OPEN,
        InvestigationStatus.CLOSED,
    },
    InvestigationStatus.CLOSED: set(),  # terminal state
}

_VALID_OUTCOMES = {o.value for o in InvestigationOutcome}


# ---------------------------------------------------------------------------
# Helper: ORM → Pydantic
# ---------------------------------------------------------------------------


def _to_investigation(row) -> Investigation:
    """Convert an InvestigationModel ORM row to the Investigation Pydantic schema."""
    return Investigation(
        investigation_id=str(row.investigation_id),
        title=row.title,
        description=row.description,
        status=row.status,
        outcome=row.outcome,
        created_at=row.created_at,
        updated_at=row.updated_at,
        owner_id=row.owner_id,
        event_count=row.event_count,
    )


def _to_note(row) -> Note:
    """Convert an InvestigationNoteModel ORM row to the Note Pydantic schema."""
    return Note(
        note_id=str(row.note_id),
        investigation_id=str(row.investigation_id),
        author_id=row.author_id,
        body=row.body,
        created_at=row.created_at,
    )


# ---------------------------------------------------------------------------
# InvestigationService
# ---------------------------------------------------------------------------


class InvestigationService:
    """Business logic layer for investigation lifecycle management.

    All database access is delegated to InvestigationRepository; this class
    only enforces authorization, state-machine rules, and schema conversion.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._repo = InvestigationRepository(db)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        payload: CreateInvestigationPayload,
        owner_id: str,
    ) -> Investigation:
        """Create a new investigation with status=OPEN and event_count=0.

        Requirements: 11.1
        """
        row = await self._repo.create(payload, owner_id)
        return _to_investigation(row)

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    async def get(
        self,
        investigation_id: str,
        caller_id: str,
    ) -> Investigation:
        """Retrieve a single investigation.

        Raises:
            InvestigationNotFoundError: if the investigation does not exist.
            ForbiddenError: if the caller does not own the investigation.

        Requirements: 11.8
        """
        row = await self._repo.get_by_id(investigation_id)
        if row is None:
            raise InvestigationNotFoundError(
                f"Investigation '{investigation_id}' does not exist."
            )
        if row.owner_id != caller_id:
            raise ForbiddenError(
                "You do not have permission to access this investigation."
            )
        return _to_investigation(row)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list(
        self,
        filters: InvestigationFilter,
        caller_id: str,
    ) -> list[Investigation]:
        """Return a paginated list of investigations owned by *caller_id*.

        The filter's owner_id is overridden with caller_id to prevent
        analysts from listing other users' investigations.

        Requirements: 11.6, 11.8
        """
        # Force owner scoping — callers only see their own investigations
        scoped_filters = filters.model_copy(update={"owner_id": caller_id})
        rows = await self._repo.list_paginated(scoped_filters)
        return [_to_investigation(r) for r in rows]

    # ------------------------------------------------------------------
    # Update status
    # ------------------------------------------------------------------

    async def update_status(
        self,
        investigation_id: str,
        new_status: InvestigationStatus,
        caller_id: str,
    ) -> Investigation:
        """Apply a status transition, enforcing the lifecycle state machine.

        Valid transitions:
          OPEN → UNDER_REVIEW
          UNDER_REVIEW → OPEN
          UNDER_REVIEW → CLOSED

        Raises:
            InvestigationNotFoundError: if the investigation does not exist.
            ForbiddenError: if the caller does not own the investigation.
            ValidationError: if the transition is not valid.

        Requirements: 11.2, 11.3, 11.8
        """
        row = await self._repo.get_by_id(investigation_id)
        if row is None:
            raise InvestigationNotFoundError(
                f"Investigation '{investigation_id}' does not exist."
            )
        if row.owner_id != caller_id:
            raise ForbiddenError(
                "You do not have permission to modify this investigation."
            )

        current_status = InvestigationStatus(row.status)
        allowed = _VALID_TRANSITIONS[current_status]

        if new_status not in allowed:
            if not allowed:
                raise ValidationError(
                    f"Investigation is CLOSED and cannot be transitioned to any "
                    f"other status."
                )
            allowed_names = ", ".join(s.value for s in sorted(allowed, key=lambda s: s.value))
            raise ValidationError(
                f"Invalid status transition: {current_status.value} → {new_status.value}. "
                f"Allowed transitions from {current_status.value}: {allowed_names}."
            )

        updated = await self._repo.update_status(investigation_id, new_status)
        assert updated is not None  # just committed
        return _to_investigation(updated)

    # ------------------------------------------------------------------
    # Record outcome
    # ------------------------------------------------------------------

    async def record_outcome(
        self,
        investigation_id: str,
        outcome: str,
        caller_id: str,
    ) -> Investigation:
        """Persist an outcome label on the investigation.

        Raises:
            InvestigationNotFoundError: if the investigation does not exist.
            ForbiddenError: if the caller does not own the investigation.
            ValidationError: if the outcome is not one of the four valid values.

        Requirements: 11.4, 11.8
        """
        if outcome not in _VALID_OUTCOMES:
            raise ValidationError(
                f"Invalid outcome {outcome!r}. Must be one of: "
                f"{', '.join(sorted(_VALID_OUTCOMES))}."
            )

        row = await self._repo.get_by_id(investigation_id)
        if row is None:
            raise InvestigationNotFoundError(
                f"Investigation '{investigation_id}' does not exist."
            )
        if row.owner_id != caller_id:
            raise ForbiddenError(
                "You do not have permission to modify this investigation."
            )

        updated = await self._repo.record_outcome(investigation_id, outcome)
        assert updated is not None
        return _to_investigation(updated)

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    async def add_note(
        self,
        investigation_id: str,
        note: NotePayload,
        author_id: str,
    ) -> Note:
        """Append an analyst note to the investigation.

        Raises:
            InvestigationNotFoundError: if the investigation does not exist.
            ForbiddenError: if the caller does not own the investigation.

        Requirements: 11.7, 11.8
        """
        row = await self._repo.get_by_id(investigation_id)
        if row is None:
            raise InvestigationNotFoundError(
                f"Investigation '{investigation_id}' does not exist."
            )
        if row.owner_id != author_id:
            raise ForbiddenError(
                "You do not have permission to add notes to this investigation."
            )

        note_row = await self._repo.add_note(investigation_id, note, author_id)
        return _to_note(note_row)

    async def list_notes(
        self,
        investigation_id: str,
        caller_id: str,
    ) -> list[Note]:
        """Return all notes for an investigation.

        Raises:
            InvestigationNotFoundError: if the investigation does not exist.
            ForbiddenError: if the caller does not own the investigation.

        Requirements: 11.8
        """
        row = await self._repo.get_by_id(investigation_id)
        if row is None:
            raise InvestigationNotFoundError(
                f"Investigation '{investigation_id}' does not exist."
            )
        if row.owner_id != caller_id:
            raise ForbiddenError(
                "You do not have permission to view notes for this investigation."
            )

        note_rows = await self._repo.list_notes(investigation_id)
        return [_to_note(r) for r in note_rows]
