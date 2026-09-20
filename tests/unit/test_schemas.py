from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.common import ErrorResponse, SuccessResponse
from app.schemas.entity import EntityType, generate_entity_id
from app.schemas.investigation import OutcomePayload
from app.schemas.security_event import SecurityEvent


def test_security_event_valid():
    """Test creating a valid SecurityEvent."""
    event = SecurityEvent(
        event_id="evt-101",
        source_type="sysmon",
        timestamp="2026-09-20T12:00:00Z",
        event_type="authentication",
        action="login",
        user="john_doe",
        source_host="workstation1",
        severity="HIGH",
    )
    assert event.event_id == "evt-101"
    assert event.severity == "high"
    assert event.timestamp.tzinfo == timezone.utc
    assert event.timestamp.year == 2026


def test_security_event_empty_event_id():
    """Test event_id validator rejects empty or whitespace-only values."""
    with pytest.raises(ValidationError) as excinfo:
        SecurityEvent(
            event_id="   ",
            source_type="sysmon",
            timestamp="2026-09-20T12:00:00Z",
            event_type="authentication",
            action="login",
        )
    assert "event_id must be non-empty" in str(excinfo.value)


def test_security_event_invalid_severity():
    """Test severity validator rejects invalid enum strings."""
    with pytest.raises(ValidationError) as excinfo:
        SecurityEvent(
            event_id="evt-102",
            source_type="sysmon",
            timestamp="2026-09-20T12:00:00Z",
            event_type="authentication",
            action="login",
            severity="super_critical",
        )
    assert "severity must be one of low/medium/high/critical" in str(excinfo.value)


def test_security_event_utc_timestamp_coercion():
    """Test timestamp validator coerces naive and non-UTC datetimes to UTC."""
    # Naive string
    event1 = SecurityEvent(
        event_id="evt-103",
        source_type="sysmon",
        timestamp="2026-09-20T12:00:00",
        event_type="authentication",
        action="login",
    )
    assert event1.timestamp.tzinfo == timezone.utc

    # Timezone offset string (+05:30)
    event2 = SecurityEvent(
        event_id="evt-104",
        source_type="sysmon",
        timestamp="2026-09-20T17:30:00+05:30",
        event_type="authentication",
        action="login",
    )
    assert event2.timestamp.tzinfo == timezone.utc
    assert event2.timestamp.hour == 12


def test_success_response_envelope():
    """Test SuccessResponse serialization envelope."""
    resp = SuccessResponse[dict](data={"message": "ok"})
    dump = resp.model_dump()
    assert dump["status"] == "success"
    assert dump["data"] == {"message": "ok"}


def test_error_response_envelope():
    """Test ErrorResponse serialization envelope."""
    resp = ErrorResponse(
        code="VALIDATION_ERROR",
        message="Invalid input field",
        details={"field": "event_id"},
    )
    dump = resp.model_dump()
    assert dump["status"] == "error"
    assert dump["code"] == "VALIDATION_ERROR"
    assert dump["message"] == "Invalid input field"
    assert dump["details"] == {"field": "event_id"}


def test_outcome_payload_validator():
    """Test OutcomePayload accepts valid outcomes and rejects invalid ones."""
    payload = OutcomePayload(outcome="TRUE_POSITIVE")
    assert payload.outcome == "TRUE_POSITIVE"

    with pytest.raises(ValidationError) as excinfo:
        OutcomePayload(outcome="INVALID_OUTCOME")
    assert "outcome must be one of" in str(excinfo.value)


def test_generate_entity_id():
    """Test deterministic entity_id generation."""
    id1 = generate_entity_id(EntityType.USER, "alice")
    id2 = generate_entity_id("User", "alice")
    id3 = generate_entity_id(EntityType.HOST, "alice")
    assert id1 == id2
    assert id1 != id3
    assert len(id1) == 16
