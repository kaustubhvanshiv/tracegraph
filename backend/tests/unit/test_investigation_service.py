"""Unit tests for InvestigationService.

Tests the state machine, outcome recording, paginated list, and note
persistence without a live database — repository calls are mocked with
simple in-memory fakes.

Requirements covered: 11.2, 11.3, 11.4, 11.7
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.errors import (
    ForbiddenError,
    InvestigationNotFoundError,
    ValidationError,
)
from app.schemas.investigation import (
    CreateInvestigationPayload,
    InvestigationStatus,
    NotePayload,
)
from app.services.investigation import InvestigationService, _VALID_TRANSITIONS


# ---------------------------------------------------------------------------
# Helpers — build lightweight ORM-row-alike objects
# ---------------------------------------------------------------------------


def _make_investigation_row(
    *,
    status: str = "OPEN",
    owner_id: str = "user-1",
    outcome: str | None = None,
    investigation_id: str | None = None,
) -> MagicMock:
    """Return a MagicMock that looks like an InvestigationModel row."""
    row = MagicMock()
    row.investigation_id = uuid.UUID(investigation_id) if investigation_id else uuid.uuid4()
    row.title = "Test Investigation"
    row.description = None
    row.status = status
    row.outcome = outcome
    row.owner_id = owner_id
    row.event_count = 0
    row.created_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)
    return row


def _make_note_row(
    *,
    investigation_id: str | None = None,
    author_id: str = "user-1",
    body: str = "test note",
) -> MagicMock:
    """Return a MagicMock that looks like an InvestigationNoteModel row."""
    row = MagicMock()
    row.note_id = uuid.uuid4()
    row.investigation_id = uuid.UUID(investigation_id) if investigation_id else uuid.uuid4()
    row.author_id = author_id
    row.body = body
    row.created_at = datetime.now(UTC)
    return row


def _make_service(repo_mock: Any) -> InvestigationService:
    """Return an InvestigationService whose _repo is the supplied mock."""
    svc = InvestigationService.__new__(InvestigationService)
    svc._repo = repo_mock
    return svc


# ---------------------------------------------------------------------------
# State machine — valid transitions
# ---------------------------------------------------------------------------


class TestStateMachineValidTransitions:
    """All valid transitions must succeed (Requirement 11.2)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "from_status, to_status",
        [
            ("OPEN", "UNDER_REVIEW"),
            ("UNDER_REVIEW", "OPEN"),
            ("UNDER_REVIEW", "CLOSED"),
        ],
    )
    async def test_valid_transition(self, from_status: str, to_status: str) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(status=from_status, owner_id="user-1", investigation_id=inv_id)
        updated_row = _make_investigation_row(
            status=to_status, owner_id="user-1", investigation_id=inv_id
        )

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)
        repo.update_status = AsyncMock(return_value=updated_row)

        svc = _make_service(repo)
        result = await svc.update_status(
            inv_id, InvestigationStatus(to_status), caller_id="user-1"
        )

        assert result.status == InvestigationStatus(to_status)
        repo.update_status.assert_awaited_once_with(inv_id, InvestigationStatus(to_status))


# ---------------------------------------------------------------------------
# State machine — invalid transitions
# ---------------------------------------------------------------------------


class TestStateMachineInvalidTransitions:
    """All invalid transitions must raise ValidationError (Requirement 11.3)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "from_status, to_status",
        [
            ("OPEN", "CLOSED"),        # Cannot skip UNDER_REVIEW
            ("CLOSED", "OPEN"),        # Terminal state
            ("CLOSED", "UNDER_REVIEW"),  # Terminal state
        ],
    )
    async def test_invalid_transition_raises_validation_error(
        self, from_status: str, to_status: str
    ) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(status=from_status, owner_id="user-1", investigation_id=inv_id)

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)
        repo.update_status = AsyncMock()

        svc = _make_service(repo)

        with pytest.raises(ValidationError) as exc_info:
            await svc.update_status(
                inv_id, InvestigationStatus(to_status), caller_id="user-1"
            )

        assert exc_info.value.http_status == 422
        # Confirm the DB update was never called
        repo.update_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_closed_investigation_transition_message_mentions_closed(self) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(status="CLOSED", owner_id="user-1", investigation_id=inv_id)

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)

        svc = _make_service(repo)

        with pytest.raises(ValidationError) as exc_info:
            await svc.update_status(
                inv_id, InvestigationStatus.OPEN, caller_id="user-1"
            )

        assert "CLOSED" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_transition_error_message_mentions_current_status(self) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(status="OPEN", owner_id="user-1", investigation_id=inv_id)

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)

        svc = _make_service(repo)

        with pytest.raises(ValidationError) as exc_info:
            await svc.update_status(
                inv_id, InvestigationStatus.CLOSED, caller_id="user-1"
            )

        assert "OPEN" in str(exc_info.value)
        assert "CLOSED" in str(exc_info.value)


# ---------------------------------------------------------------------------
# State machine — authorization
# ---------------------------------------------------------------------------


class TestStateMachineAuthorization:
    """Ownership is enforced on status updates (Requirement 11.8)."""

    @pytest.mark.asyncio
    async def test_non_owner_cannot_update_status(self) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(status="OPEN", owner_id="user-1", investigation_id=inv_id)

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)

        svc = _make_service(repo)

        with pytest.raises(ForbiddenError):
            await svc.update_status(
                inv_id, InvestigationStatus.UNDER_REVIEW, caller_id="user-2"
            )

    @pytest.mark.asyncio
    async def test_missing_investigation_raises_not_found(self) -> None:
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=None)

        svc = _make_service(repo)

        with pytest.raises(InvestigationNotFoundError):
            await svc.update_status(
                "nonexistent-id", InvestigationStatus.UNDER_REVIEW, caller_id="user-1"
            )


# ---------------------------------------------------------------------------
# Outcome recording
# ---------------------------------------------------------------------------


class TestOutcomeRecording:
    """Valid outcomes are persisted; invalid outcomes are rejected (Requirement 11.4)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "outcome",
        ["TRUE_POSITIVE", "FALSE_POSITIVE", "INCONCLUSIVE", "ESCALATED"],
    )
    async def test_valid_outcome_is_recorded(self, outcome: str) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(owner_id="user-1", investigation_id=inv_id)
        updated_row = _make_investigation_row(
            owner_id="user-1", outcome=outcome, investigation_id=inv_id
        )

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)
        repo.record_outcome = AsyncMock(return_value=updated_row)

        svc = _make_service(repo)
        result = await svc.record_outcome(inv_id, outcome, caller_id="user-1")

        assert result.outcome == outcome
        repo.record_outcome.assert_awaited_once_with(inv_id, outcome)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_outcome",
        ["UNKNOWN", "POSITIVE", "", "true_positive"],
    )
    async def test_invalid_outcome_raises_validation_error(self, bad_outcome: str) -> None:
        inv_id = str(uuid.uuid4())

        repo = MagicMock()
        repo.get_by_id = AsyncMock()  # should not even be called for bad outcomes

        svc = _make_service(repo)

        with pytest.raises(ValidationError) as exc_info:
            await svc.record_outcome(inv_id, bad_outcome, caller_id="user-1")

        assert exc_info.value.http_status == 422

    @pytest.mark.asyncio
    async def test_non_owner_cannot_record_outcome(self) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(owner_id="user-1", investigation_id=inv_id)

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)

        svc = _make_service(repo)

        with pytest.raises(ForbiddenError):
            await svc.record_outcome(inv_id, "TRUE_POSITIVE", caller_id="user-2")


# ---------------------------------------------------------------------------
# Paginated list
# ---------------------------------------------------------------------------


class TestPaginatedList:
    """list() returns only the caller's own investigations (Requirement 11.6, 11.8)."""

    @pytest.mark.asyncio
    async def test_list_scopes_to_caller(self) -> None:
        from app.schemas.investigation import InvestigationFilter

        rows = [
            _make_investigation_row(owner_id="user-1"),
            _make_investigation_row(owner_id="user-1"),
        ]

        repo = MagicMock()
        repo.list_paginated = AsyncMock(return_value=rows)

        svc = _make_service(repo)
        filters = InvestigationFilter(limit=10, offset=0)
        result = await svc.list(filters, caller_id="user-1")

        assert len(result) == 2
        # The filters passed to the repo must have owner_id == caller_id
        call_args = repo.list_paginated.call_args
        used_filters = call_args[0][0]
        assert used_filters.owner_id == "user-1"

    @pytest.mark.asyncio
    async def test_list_returns_empty_when_no_investigations(self) -> None:
        from app.schemas.investigation import InvestigationFilter

        repo = MagicMock()
        repo.list_paginated = AsyncMock(return_value=[])

        svc = _make_service(repo)
        filters = InvestigationFilter(limit=10, offset=0)
        result = await svc.list(filters, caller_id="user-1")

        assert result == []

    @pytest.mark.asyncio
    async def test_list_overrides_owner_id_in_filter(self) -> None:
        """Even if filters.owner_id is explicitly set to another user, the
        service must override it with caller_id (security invariant)."""
        from app.schemas.investigation import InvestigationFilter

        repo = MagicMock()
        repo.list_paginated = AsyncMock(return_value=[])

        svc = _make_service(repo)
        # Caller passes a different owner_id; service must ignore it
        filters = InvestigationFilter(owner_id="attacker-id", limit=10, offset=0)
        await svc.list(filters, caller_id="user-1")

        call_args = repo.list_paginated.call_args
        used_filters = call_args[0][0]
        assert used_filters.owner_id == "user-1"


# ---------------------------------------------------------------------------
# Note persistence
# ---------------------------------------------------------------------------


class TestNotePersistence:
    """Notes are persisted with author_id, timestamp, and body (Requirement 11.7)."""

    @pytest.mark.asyncio
    async def test_add_note_persists_with_correct_fields(self) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(owner_id="user-1", investigation_id=inv_id)
        note_row = _make_note_row(
            investigation_id=inv_id, author_id="user-1", body="suspicious activity"
        )

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)
        repo.add_note = AsyncMock(return_value=note_row)

        svc = _make_service(repo)
        payload = NotePayload(body="suspicious activity")
        result = await svc.add_note(inv_id, payload, author_id="user-1")

        assert result.body == "suspicious activity"
        assert result.author_id == "user-1"
        assert result.investigation_id == str(note_row.investigation_id)
        repo.add_note.assert_awaited_once_with(inv_id, payload, "user-1")

    @pytest.mark.asyncio
    async def test_add_note_non_owner_raises_forbidden(self) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(owner_id="user-1", investigation_id=inv_id)

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)

        svc = _make_service(repo)
        with pytest.raises(ForbiddenError):
            await svc.add_note(inv_id, NotePayload(body="note"), author_id="user-2")

    @pytest.mark.asyncio
    async def test_add_note_missing_investigation_raises_not_found(self) -> None:
        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=None)

        svc = _make_service(repo)
        with pytest.raises(InvestigationNotFoundError):
            await svc.add_note(
                "nonexistent", NotePayload(body="note"), author_id="user-1"
            )

    @pytest.mark.asyncio
    async def test_list_notes_returns_notes_for_owner(self) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(owner_id="user-1", investigation_id=inv_id)
        note_rows = [
            _make_note_row(investigation_id=inv_id, author_id="user-1", body="note 1"),
            _make_note_row(investigation_id=inv_id, author_id="user-1", body="note 2"),
        ]

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)
        repo.list_notes = AsyncMock(return_value=note_rows)

        svc = _make_service(repo)
        result = await svc.list_notes(inv_id, caller_id="user-1")

        assert len(result) == 2
        assert result[0].body == "note 1"
        assert result[1].body == "note 2"

    @pytest.mark.asyncio
    async def test_list_notes_non_owner_raises_forbidden(self) -> None:
        inv_id = str(uuid.uuid4())
        row = _make_investigation_row(owner_id="user-1", investigation_id=inv_id)

        repo = MagicMock()
        repo.get_by_id = AsyncMock(return_value=row)

        svc = _make_service(repo)
        with pytest.raises(ForbiddenError):
            await svc.list_notes(inv_id, caller_id="user-2")


# ---------------------------------------------------------------------------
# State machine constant validation
# ---------------------------------------------------------------------------


class TestStateMachineConstants:
    """Verify the _VALID_TRANSITIONS table is complete and correct."""

    def test_all_statuses_have_a_transition_entry(self) -> None:
        for status in InvestigationStatus:
            assert status in _VALID_TRANSITIONS, f"{status} missing from _VALID_TRANSITIONS"

    def test_open_can_only_go_to_under_review(self) -> None:
        allowed = _VALID_TRANSITIONS[InvestigationStatus.OPEN]
        assert allowed == {InvestigationStatus.UNDER_REVIEW}

    def test_under_review_can_go_to_open_or_closed(self) -> None:
        allowed = _VALID_TRANSITIONS[InvestigationStatus.UNDER_REVIEW]
        assert InvestigationStatus.OPEN in allowed
        assert InvestigationStatus.CLOSED in allowed

    def test_closed_is_terminal(self) -> None:
        assert _VALID_TRANSITIONS[InvestigationStatus.CLOSED] == set()
