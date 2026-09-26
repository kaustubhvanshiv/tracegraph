"""Unit tests for NormalizationEngine.

Covers:
  - Timestamp parsing for multiple formats and timezones (Requirements 3.1, 3.3)
  - Hostname lowercasing (Requirement 3.4)
  - Domain-prefix stripping from usernames (Requirement 3.5)
  - IP address canonicalization (Requirement 3.6)
  - Severity validation (Requirement 3.8)
  - raw_data preservation (Requirement 3.9)
  - event_id passthrough unchanged (Requirement 3.7)
  - source_type passthrough (Requirement 2.5)
  - ValidationError on unparseable timestamps (Requirement 3.1)

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.errors import ValidationError
from app.schemas.parser import ParsedEvent
from app.services.normalization import NormalizationEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parsed(
    event_id: str = "evt-001",
    source_type: str = "siem",
    timestamp_raw: str = "2024-06-15T10:00:00Z",
    event_type: str | None = "authentication",
    action: str | None = "login",
    user: str | None = None,
    source_host: str | None = None,
    destination_host: str | None = None,
    source_ip: str | None = None,
    destination_ip: str | None = None,
    process: str | None = None,
    file: str | None = None,
    severity: str | None = None,
    extra_fields: dict | None = None,
) -> ParsedEvent:
    return ParsedEvent(
        event_id=event_id,
        source_type=source_type,
        timestamp_raw=timestamp_raw,
        event_type=event_type,
        action=action,
        user=user,
        source_host=source_host,
        destination_host=destination_host,
        source_ip=source_ip,
        destination_ip=destination_ip,
        process=process,
        file=file,
        severity=severity,
        extra_fields=extra_fields or {},
    )


@pytest.fixture()
def engine() -> NormalizationEngine:
    return NormalizationEngine()


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------


class TestTimestampParsing:
    """Various timestamp formats must all produce UTC-aware datetimes."""

    @pytest.mark.parametrize(
        "raw_ts",
        [
            "2024-06-15T10:00:00Z",                # ISO-8601 with Z
            "2024-06-15T10:00:00+00:00",            # ISO-8601 explicit UTC offset
            "2024-06-15T10:00:00+05:30",            # ISO-8601 non-UTC offset → converted to UTC
            "2024-06-15T10:00:00",                  # ISO-8601 naive → treat as UTC
            "2024-06-15T10:00:00.123456Z",          # ISO-8601 with microseconds
            "2024-06-15 10:00:00",                  # space-separated naive
            "2024-06-15 10:00:00.123456",           # space-separated with microseconds
            "15/06/2024 10:00:00",                  # DD/MM/YYYY
            "06/15/2024 10:00:00",                  # MM/DD/YYYY
            "1718445600.0",                         # Unix epoch float string
            "1718445600",                           # Unix epoch int string
        ],
    )
    def test_timestamp_parsed_to_utc_aware(self, engine, raw_ts):
        parsed = _parsed(timestamp_raw=raw_ts)
        result = engine.normalize(parsed)
        assert result.timestamp.tzinfo is not None, f"No tzinfo for {raw_ts!r}"
        offset = result.timestamp.utcoffset()
        assert offset.total_seconds() == 0.0, f"Not UTC for {raw_ts!r}: {result.timestamp}"

    def test_iso8601_with_offset_converts_to_correct_utc(self, engine):
        """An event at UTC+05:30 10:00 equals UTC 04:30."""
        parsed = _parsed(timestamp_raw="2024-06-15T10:00:00+05:30")
        result = engine.normalize(parsed)
        assert result.timestamp.hour == 4
        assert result.timestamp.minute == 30

    def test_unparseable_timestamp_raises_validation_error(self, engine):
        parsed = _parsed(timestamp_raw="not-a-date-at-all")
        with pytest.raises(ValidationError):
            engine.normalize(parsed)

    def test_empty_timestamp_raises_validation_error(self, engine):
        parsed = _parsed(timestamp_raw="")
        with pytest.raises(ValidationError):
            engine.normalize(parsed)

    def test_whitespace_only_timestamp_raises_validation_error(self, engine):
        parsed = _parsed(timestamp_raw="   ")
        with pytest.raises(ValidationError):
            engine.normalize(parsed)


# ---------------------------------------------------------------------------
# Hostname lowercasing
# ---------------------------------------------------------------------------


class TestHostnameLowercasing:
    """source_host and destination_host are lowercased (Requirement 3.4)."""

    def test_source_host_is_lowercased(self, engine):
        parsed = _parsed(source_host="WorkStation-01")
        result = engine.normalize(parsed)
        assert result.source_host == "workstation-01"

    def test_destination_host_is_lowercased(self, engine):
        parsed = _parsed(destination_host="DC01.CORP.LOCAL")
        result = engine.normalize(parsed)
        assert result.destination_host == "dc01.corp.local"

    def test_already_lowercase_host_unchanged(self, engine):
        parsed = _parsed(source_host="host-abc")
        result = engine.normalize(parsed)
        assert result.source_host == "host-abc"

    def test_none_source_host_stays_none(self, engine):
        parsed = _parsed(source_host=None)
        result = engine.normalize(parsed)
        assert result.source_host is None

    def test_mixed_case_hostname_fully_lowercased(self, engine):
        parsed = _parsed(source_host="SRV-PROD-01")
        result = engine.normalize(parsed)
        assert result.source_host == "srv-prod-01"


# ---------------------------------------------------------------------------
# Username domain-prefix stripping
# ---------------------------------------------------------------------------


class TestUsernameDomainPrefixStripping:
    """Domain prefixes are stripped from usernames (Requirement 3.5)."""

    def test_domain_backslash_user_stripped(self, engine):
        parsed = _parsed(user="DOMAIN\\alice")
        result = engine.normalize(parsed)
        assert result.user == "alice"

    def test_user_at_domain_stripped(self, engine):
        parsed = _parsed(user="bob@example.com")
        result = engine.normalize(parsed)
        assert result.user == "bob"

    def test_bare_user_unchanged(self, engine):
        parsed = _parsed(user="carol")
        result = engine.normalize(parsed)
        assert result.user == "carol"

    def test_none_user_stays_none(self, engine):
        parsed = _parsed(user=None)
        result = engine.normalize(parsed)
        assert result.user is None

    def test_nested_domain_backslash_takes_rightmost_part(self, engine):
        """CORP\\CHILD\\user → user (last segment after all backslashes)."""
        parsed = _parsed(user="CORP\\CHILD\\user")
        result = engine.normalize(parsed)
        assert result.user == "user"

    def test_user_with_at_takes_leftmost_part(self, engine):
        """user@sub.domain.com → user"""
        parsed = _parsed(user="admin@sub.corp.local")
        result = engine.normalize(parsed)
        assert result.user == "admin"


# ---------------------------------------------------------------------------
# IP address canonicalization
# ---------------------------------------------------------------------------


class TestIPCanonicalization:
    """IPs are normalized to canonical dotted-decimal or compressed IPv6 (Requirement 3.6)."""

    def test_valid_ipv4_unchanged(self, engine):
        parsed = _parsed(source_ip="192.168.1.100")
        result = engine.normalize(parsed)
        assert result.source_ip == "192.168.1.100"

    def test_ipv4_leading_zeros_preserved_unchanged(self, engine):
        """Python's ipaddress module rejects leading-zero octets (ambiguous with octal).
        The engine preserves such values unchanged rather than raising."""
        parsed = _parsed(source_ip="192.168.001.001")
        result = engine.normalize(parsed)
        # Not a valid IP per Python ipaddress — preserved as-is
        assert result.source_ip == "192.168.001.001"

    def test_ipv6_full_form_compressed(self, engine):
        """Full-form IPv6 address is compressed."""
        parsed = _parsed(source_ip="2001:0db8:0000:0000:0000:0000:0000:0001")
        result = engine.normalize(parsed)
        assert result.source_ip == "2001:db8::1"

    def test_invalid_ip_preserved_unchanged(self, engine):
        """Non-IP strings are preserved as-is (no exception raised)."""
        parsed = _parsed(source_ip="not-an-ip")
        result = engine.normalize(parsed)
        assert result.source_ip == "not-an-ip"

    def test_destination_ip_also_canonicalized(self, engine):
        parsed = _parsed(destination_ip="10.0.0.1")
        result = engine.normalize(parsed)
        assert result.destination_ip == "10.0.0.1"

    def test_none_ip_stays_none(self, engine):
        parsed = _parsed(source_ip=None)
        result = engine.normalize(parsed)
        assert result.source_ip is None


# ---------------------------------------------------------------------------
# Severity validation
# ---------------------------------------------------------------------------


class TestSeverityValidation:
    """Only lowercase valid severities are accepted; invalid ones cause ValidationError."""

    @pytest.mark.parametrize("severity", ["low", "medium", "high", "critical"])
    def test_valid_severity_accepted(self, engine, severity):
        parsed = _parsed(severity=severity)
        result = engine.normalize(parsed)
        assert result.severity == severity

    @pytest.mark.parametrize("severity_raw", ["LOW", "HIGH", "Medium", "CRITICAL"])
    def test_severity_uppercased_in_parsed_is_lowercased(self, engine, severity_raw):
        """The engine lowercases severity before passing to SecurityEvent."""
        parsed = _parsed(severity=severity_raw)
        result = engine.normalize(parsed)
        assert result.severity == severity_raw.lower()

    def test_none_severity_is_accepted(self, engine):
        parsed = _parsed(severity=None)
        result = engine.normalize(parsed)
        assert result.severity is None

    def test_invalid_severity_raises_validation_error(self, engine):
        parsed = _parsed(severity="unknown_severity")
        with pytest.raises(ValidationError):
            engine.normalize(parsed)


# ---------------------------------------------------------------------------
# raw_data preservation
# ---------------------------------------------------------------------------


class TestRawDataPreservation:
    """All parsed fields survive in SecurityEvent.raw_data (Requirement 3.9)."""

    def test_raw_data_contains_original_event_id(self, engine):
        parsed = _parsed(event_id="EVT-XYZ-789")
        result = engine.normalize(parsed)
        assert result.raw_data is not None
        assert result.raw_data.get("event_id") == "EVT-XYZ-789"

    def test_raw_data_contains_original_timestamp_raw(self, engine):
        ts = "2024-06-15T10:00:00Z"
        parsed = _parsed(timestamp_raw=ts)
        result = engine.normalize(parsed)
        assert result.raw_data.get("timestamp_raw") == ts

    def test_raw_data_contains_extra_fields(self, engine):
        parsed = _parsed(extra_fields={"pid": 1234, "custom_key": "custom_value"})
        result = engine.normalize(parsed)
        # extra_fields should be accessible; raw_data is the full model dump
        assert "extra_fields" in result.raw_data
        assert result.raw_data["extra_fields"].get("pid") == 1234

    def test_raw_data_not_mutated_by_normalization(self, engine):
        """Canonical field changes must NOT propagate back into raw_data."""
        parsed = _parsed(source_host="UPPERCASE-HOST", user="DOMAIN\\alice")
        result = engine.normalize(parsed)
        # raw_data should hold the pre-normalization values
        assert result.raw_data.get("source_host") == "UPPERCASE-HOST"
        assert result.raw_data.get("user") == "DOMAIN\\alice"


# ---------------------------------------------------------------------------
# event_id and source_type passthrough
# ---------------------------------------------------------------------------


class TestEventIdPassthrough:
    """event_id and source_type are never modified by normalization (Requirements 3.7, 2.5)."""

    def test_event_id_unchanged(self, engine):
        parsed = _parsed(event_id="unique-evt-12345")
        result = engine.normalize(parsed)
        assert result.event_id == "unique-evt-12345"

    def test_source_type_unchanged(self, engine):
        parsed = _parsed(source_type="edr")
        result = engine.normalize(parsed)
        assert result.source_type == "edr"

    @pytest.mark.parametrize(
        "event_id",
        ["a", "ABC-123", "evt_hyphen-dot.slash", "00000000-0000-0000-0000-000000000000"],
    )
    def test_various_event_ids_preserved(self, engine, event_id):
        parsed = _parsed(event_id=event_id)
        result = engine.normalize(parsed)
        assert result.event_id == event_id


# ---------------------------------------------------------------------------
# Full round-trip
# ---------------------------------------------------------------------------


class TestFullRoundTrip:
    """A complete ParsedEvent normalizes to a fully populated SecurityEvent."""

    def test_fully_populated_parsed_event(self, engine):
        parsed = _parsed(
            event_id="full-evt-001",
            source_type="sysmon",
            timestamp_raw="2024-03-01T08:30:00Z",
            event_type="process_creation",
            action="execute",
            user="CORP\\Administrator",
            source_host="WORKSTATION-1",
            destination_host="DC01.CORP",
            source_ip="192.168.1.10",
            destination_ip="10.0.0.1",
            process="cmd.exe",
            file="C:\\temp\\payload.exe",
            severity="HIGH",
        )
        result = engine.normalize(parsed)

        assert result.event_id == "full-evt-001"
        assert result.source_type == "sysmon"
        assert result.timestamp.tzinfo is not None
        assert result.user == "Administrator"         # domain prefix stripped
        assert result.source_host == "workstation-1"  # lowercased
        assert result.destination_host == "dc01.corp" # lowercased
        assert result.source_ip == "192.168.1.10"
        assert result.destination_ip == "10.0.0.1"
        assert result.process == "cmd.exe"
        assert result.file == "C:\\temp\\payload.exe"
        assert result.severity == "high"              # lowercased
        assert result.raw_data is not None
