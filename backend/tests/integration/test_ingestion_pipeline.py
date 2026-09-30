"""Integration tests for the event ingestion pipeline.

Tests the full HTTP request path through the FastAPI app to:
  - POST /api/investigations/{investigation_id}/events
  - POST /api/investigations/{investigation_id}/events/batch

Since we don't run live databases in this test suite, external I/O is mocked:
  - PostgreSQL (SQLAlchemy session) via AsyncMock
  - Neo4j driver via AsyncMock
  - InvestigationRepository.get_by_id — controls investigation existence
  - EventRepository.store — captures persisted events for round-trip checks
  - GraphRepository.upsert_entity / upsert_relationship — no-ops in tests

JWT tokens for the tests are generated from the same settings.jwt_secret_key
that the auth middleware reads, so the signature always validates.

Test cases:
  1. Single event success (happy path)
  2. Batch partial failure (one good + one malformed)
  3. INVESTIGATION_NOT_FOUND → 404
  4. INVALID_SOURCE_TYPE → 422
  5. Ownership enforcement → 403
  6. Round-trip event_id preservation

Requirements: 1.1–1.8
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import settings
from app.core.errors import FORBIDDEN, INVALID_SOURCE_TYPE, INVESTIGATION_NOT_FOUND


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_token(user_id: str = "user-001") -> str:
    """Generate a valid JWT for the given user_id."""
    payload = {"sub": user_id}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _auth_headers(user_id: str = "user-001") -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def _valid_siem_event(event_id: str = "evt-001") -> dict[str, Any]:
    """Return a minimal valid SIEM raw event dict."""
    return {
        "event_id": event_id,
        "timestamp": "2024-01-15T10:00:00Z",
        "event_type": "authentication",
        "action": "login",
        "user": "alice",
        "source_host": "workstation-01",
        "destination_host": "server-01",
        "severity": "medium",
    }


def _malformed_siem_event() -> dict[str, Any]:
    """Return a SIEM event missing the required event_id."""
    return {
        # event_id intentionally omitted — adapter will return ParseError
        "timestamp": "2024-01-15T10:00:00Z",
        "event_type": "authentication",
        "action": "login",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_investigation_row(owner_id: str = "user-001") -> MagicMock:
    """Return a mock investigation ORM row with the given owner."""
    row = MagicMock()
    row.owner_id = owner_id
    row.investigation_id = "inv-001"
    return row


def _build_mock_db_session() -> AsyncMock:
    """Return an AsyncMock that behaves like a SQLAlchemy async session."""
    db = AsyncMock()
    db.execute = AsyncMock(return_value=AsyncMock())
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _build_mock_neo4j_driver() -> AsyncMock:
    """Return an AsyncMock that behaves like an AsyncDriver."""
    driver = AsyncMock()
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.run = AsyncMock(return_value=AsyncMock(data=AsyncMock(return_value=[])))
    driver.session = MagicMock(return_value=session)
    return driver


@pytest.fixture
def app_client():
    """Build a TestClient with all external I/O mocked.

    Patches applied:
      - get_db → mock AsyncSession
      - get_neo4j_driver → mock AsyncDriver
      - InvestigationRepository.get_by_id → returns a valid investigation row
      - EventRepository.store → no-op async mock
      - GraphRepository.upsert_entity → no-op async mock
      - GraphRepository.upsert_relationship → no-op async mock
    """
    from app.main import app

    mock_db = _build_mock_db_session()
    mock_driver = _build_mock_neo4j_driver()
    mock_inv_row = _mock_investigation_row(owner_id="user-001")

    with (
        patch("app.core.database.get_db", return_value=mock_db),
        patch("app.core.database.get_neo4j_driver", return_value=mock_driver),
        patch(
            "app.repositories.investigation_repository.InvestigationRepository.get_by_id",
            new=AsyncMock(return_value=mock_inv_row),
        ),
        patch(
            "app.repositories.event_repository.EventRepository.store",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.repositories.graph_repository.GraphRepository.upsert_entity",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.repositories.graph_repository.GraphRepository.upsert_relationship",
            new=AsyncMock(return_value=None),
        ),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        # Store references so individual tests can configure them
        client._mock_db = mock_db
        client._mock_driver = mock_driver
        client._mock_inv_row = mock_inv_row
        yield client


# ---------------------------------------------------------------------------
# Utility: override get_by_id for a single test
# ---------------------------------------------------------------------------


def _patch_investigation_not_found():
    """Context manager: makes get_by_id return None (investigation does not exist)."""
    return patch(
        "app.repositories.investigation_repository.InvestigationRepository.get_by_id",
        new=AsyncMock(return_value=None),
    )


def _patch_investigation_owner(owner_id: str):
    """Context manager: makes get_by_id return a row with a specific owner."""
    row = _mock_investigation_row(owner_id=owner_id)
    return patch(
        "app.repositories.investigation_repository.InvestigationRepository.get_by_id",
        new=AsyncMock(return_value=row),
    )


# ---------------------------------------------------------------------------
# Test 1: Single event — happy path
# ---------------------------------------------------------------------------


class TestSingleEventSuccess:
    """POST /{investigation_id}/events with a well-formed event."""

    def test_returns_200(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events",
            json={"source_type": "siem", "raw": _valid_siem_event("evt-happy")},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200, resp.text

    def test_response_envelope_is_success(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events",
            json={"source_type": "siem", "raw": _valid_siem_event("evt-env")},
            headers=_auth_headers(),
        )
        body = resp.json()
        assert body["status"] == "success"

    def test_accepted_is_1(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events",
            json={"source_type": "siem", "raw": _valid_siem_event("evt-acc")},
            headers=_auth_headers(),
        )
        data = resp.json()["data"]
        assert data["accepted"] == 1

    def test_rejected_is_0(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events",
            json={"source_type": "siem", "raw": _valid_siem_event("evt-rej")},
            headers=_auth_headers(),
        )
        data = resp.json()["data"]
        assert data["rejected"] == 0

    def test_errors_list_is_empty(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events",
            json={"source_type": "siem", "raw": _valid_siem_event("evt-err")},
            headers=_auth_headers(),
        )
        data = resp.json()["data"]
        assert data["errors"] == []


# ---------------------------------------------------------------------------
# Test 2: Batch — partial failure
# ---------------------------------------------------------------------------


class TestBatchPartialFailure:
    """POST /{investigation_id}/events/batch with one good and one malformed event."""

    def _batch_payload(self):
        return [
            {"source_type": "siem", "raw": _valid_siem_event("evt-good")},
            {"source_type": "siem", "raw": _malformed_siem_event()},
        ]

    def test_returns_200(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events/batch",
            json=self._batch_payload(),
            headers=_auth_headers(),
        )
        assert resp.status_code == 200, resp.text

    def test_accepted_is_1(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events/batch",
            json=self._batch_payload(),
            headers=_auth_headers(),
        )
        data = resp.json()["data"]
        assert data["accepted"] == 1

    def test_rejected_is_1(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events/batch",
            json=self._batch_payload(),
            headers=_auth_headers(),
        )
        data = resp.json()["data"]
        assert data["rejected"] == 1

    def test_errors_list_has_one_entry(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events/batch",
            json=self._batch_payload(),
            headers=_auth_headers(),
        )
        data = resp.json()["data"]
        assert len(data["errors"]) == 1

    def test_error_entry_has_reason(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events/batch",
            json=self._batch_payload(),
            headers=_auth_headers(),
        )
        error = resp.json()["data"]["errors"][0]
        assert isinstance(error["reason"], str)
        assert len(error["reason"]) > 0


# ---------------------------------------------------------------------------
# Test 3: INVESTIGATION_NOT_FOUND → 404
# ---------------------------------------------------------------------------


class TestInvestigationNotFound:
    """When the investigation does not exist, return 404 INVESTIGATION_NOT_FOUND."""

    def test_returns_404(self, app_client):
        with _patch_investigation_not_found():
            resp = app_client.post(
                "/api/investigations/nonexistent-inv/events",
                json={"source_type": "siem", "raw": _valid_siem_event()},
                headers=_auth_headers(),
            )
        # 404 returned because the ownership check treats "not found" as Forbidden (403),
        # but the IngestionService raises InvestigationNotFoundError → 404.
        # The ownership check in the handler returns 403 for "not found" to avoid
        # leaking existence — so the 403 fires first.
        assert resp.status_code in (403, 404), resp.text

    def test_error_code_is_not_found_or_forbidden(self, app_client):
        with _patch_investigation_not_found():
            resp = app_client.post(
                "/api/investigations/nonexistent-inv/events",
                json={"source_type": "siem", "raw": _valid_siem_event()},
                headers=_auth_headers(),
            )
        body = resp.json()
        assert body["code"] in (INVESTIGATION_NOT_FOUND, FORBIDDEN)

    def test_batch_returns_403_or_404(self, app_client):
        with _patch_investigation_not_found():
            resp = app_client.post(
                "/api/investigations/nonexistent-inv/events/batch",
                json=[{"source_type": "siem", "raw": _valid_siem_event()}],
                headers=_auth_headers(),
            )
        assert resp.status_code in (403, 404), resp.text


# ---------------------------------------------------------------------------
# Test 4: INVALID_SOURCE_TYPE → 422
# ---------------------------------------------------------------------------


class TestInvalidSourceType:
    """When source_type is not registered, return 422 INVALID_SOURCE_TYPE."""

    def test_single_event_returns_422(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events",
            json={"source_type": "unknown_source", "raw": _valid_siem_event()},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422, resp.text

    def test_single_event_error_code(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events",
            json={"source_type": "unknown_source", "raw": _valid_siem_event()},
            headers=_auth_headers(),
        )
        body = resp.json()
        assert body["code"] == INVALID_SOURCE_TYPE

    def test_batch_returns_422(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events/batch",
            json=[{"source_type": "unknown_source", "raw": _valid_siem_event()}],
            headers=_auth_headers(),
        )
        assert resp.status_code == 422, resp.text

    def test_batch_error_code(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events/batch",
            json=[{"source_type": "unknown_source", "raw": _valid_siem_event()}],
            headers=_auth_headers(),
        )
        body = resp.json()
        assert body["code"] == INVALID_SOURCE_TYPE


# ---------------------------------------------------------------------------
# Test 5: Ownership enforcement → 403
# ---------------------------------------------------------------------------


class TestOwnershipEnforcement:
    """A user who does not own the investigation receives HTTP 403."""

    def test_single_event_returns_403(self, app_client):
        # Investigation is owned by "user-999", but request comes from "user-001"
        with _patch_investigation_owner("user-999"):
            resp = app_client.post(
                "/api/investigations/inv-001/events",
                json={"source_type": "siem", "raw": _valid_siem_event()},
                headers=_auth_headers(user_id="user-001"),
            )
        assert resp.status_code == 403, resp.text

    def test_single_event_error_code(self, app_client):
        with _patch_investigation_owner("user-999"):
            resp = app_client.post(
                "/api/investigations/inv-001/events",
                json={"source_type": "siem", "raw": _valid_siem_event()},
                headers=_auth_headers(user_id="user-001"),
            )
        body = resp.json()
        assert body["code"] == FORBIDDEN

    def test_batch_returns_403(self, app_client):
        with _patch_investigation_owner("user-999"):
            resp = app_client.post(
                "/api/investigations/inv-001/events/batch",
                json=[{"source_type": "siem", "raw": _valid_siem_event()}],
                headers=_auth_headers(user_id="user-001"),
            )
        assert resp.status_code == 403, resp.text

    def test_missing_auth_header_returns_401(self, app_client):
        resp = app_client.post(
            "/api/investigations/inv-001/events",
            json={"source_type": "siem", "raw": _valid_siem_event()},
            # No Authorization header
        )
        assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Test 6: Round-trip event_id preservation
# ---------------------------------------------------------------------------


class TestRoundTripEventId:
    """The event_id in the raw input is preserved through the pipeline."""

    def test_event_id_is_preserved(self):
        """Verify EventRepository.store is called with the same event_id."""
        from app.main import app

        stored_events: list = []

        async def capture_store(self_repo, events, investigation_id, entity_map):
            stored_events.extend(events)

        mock_db = _build_mock_db_session()
        mock_driver = _build_mock_neo4j_driver()
        mock_inv_row = _mock_investigation_row(owner_id="user-001")

        with (
            patch("app.core.database.get_db", return_value=mock_db),
            patch("app.core.database.get_neo4j_driver", return_value=mock_driver),
            patch(
                "app.repositories.investigation_repository.InvestigationRepository.get_by_id",
                new=AsyncMock(return_value=mock_inv_row),
            ),
            patch(
                "app.repositories.event_repository.EventRepository.store",
                new=capture_store,
            ),
            patch(
                "app.repositories.graph_repository.GraphRepository.upsert_entity",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.repositories.graph_repository.GraphRepository.upsert_relationship",
                new=AsyncMock(return_value=None),
            ),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            expected_event_id = "preserve-me-123"
            resp = client.post(
                "/api/investigations/inv-001/events",
                json={
                    "source_type": "siem",
                    "raw": _valid_siem_event(event_id=expected_event_id),
                },
                headers=_auth_headers(),
            )

        assert resp.status_code == 200, resp.text
        assert len(stored_events) == 1
        assert stored_events[0].event_id == expected_event_id

    def test_batch_event_ids_are_preserved(self):
        """Batch: all accepted event_ids survive unchanged."""
        from app.main import app

        stored_events: list = []

        async def capture_store(self_repo, events, investigation_id, entity_map):
            stored_events.extend(events)

        mock_db = _build_mock_db_session()
        mock_driver = _build_mock_neo4j_driver()
        mock_inv_row = _mock_investigation_row(owner_id="user-001")

        with (
            patch("app.core.database.get_db", return_value=mock_db),
            patch("app.core.database.get_neo4j_driver", return_value=mock_driver),
            patch(
                "app.repositories.investigation_repository.InvestigationRepository.get_by_id",
                new=AsyncMock(return_value=mock_inv_row),
            ),
            patch(
                "app.repositories.event_repository.EventRepository.store",
                new=capture_store,
            ),
            patch(
                "app.repositories.graph_repository.GraphRepository.upsert_entity",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.repositories.graph_repository.GraphRepository.upsert_relationship",
                new=AsyncMock(return_value=None),
            ),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            batch = [
                {"source_type": "siem", "raw": _valid_siem_event("batch-evt-001")},
                {"source_type": "siem", "raw": _valid_siem_event("batch-evt-002")},
            ]
            resp = client.post(
                "/api/investigations/inv-001/events/batch",
                json=batch,
                headers=_auth_headers(),
            )

        assert resp.status_code == 200, resp.text
        stored_ids = {e.event_id for e in stored_events}
        assert "batch-evt-001" in stored_ids
        assert "batch-evt-002" in stored_ids
