"""Normalization engine: maps parsed fields to the Common Security Event Model.

Responsibilities:
  - Configurable field-name mapping tables (loaded from settings, not hardcoded)
  - Timestamp normalization to UTC-aware datetime
  - Identifier canonicalization (hostname lowercase, IP notation, domain-strip)
  - Raw data preservation in SecurityEvent.raw_data
"""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.errors import ValidationError
from app.schemas.parser import ParsedEvent
from app.schemas.security_event import SecurityEvent

# Canonical SecurityEvent field names that can be supplied via extra_fields mapping
_CANONICAL_FIELDS = frozenset(
    {
        "event_type",
        "action",
        "user",
        "source_host",
        "destination_host",
        "source_ip",
        "destination_ip",
        "process",
        "file",
        "severity",
    }
)


class NormalizationEngine:
    """Converts a ParsedEvent (intermediate representation) into a normalized SecurityEvent.

    Applies:
    - Configurable field-name mapping (loaded from settings, not hardcoded)
    - Timestamp normalization to UTC-aware datetime
    - Hostname lowercasing
    - Username domain-prefix stripping
    - IP address canonicalization (dotted-decimal IPv4 / compressed IPv6)
    - Raw data preservation in SecurityEvent.raw_data
    """

    # Timestamp formats to try in order (after ISO-8601 / epoch attempts)
    _TIMESTAMP_FORMATS = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize(self, parsed: ParsedEvent) -> SecurityEvent:
        """Convert *parsed* to a fully normalized SecurityEvent.

        Raises:
            ValidationError: if the timestamp cannot be parsed or severity is invalid.
        """
        # 1. Preserve raw data before any mutation
        raw_data: dict[str, Any] = parsed.model_dump()

        # 2. Parse timestamp to UTC-aware datetime
        timestamp = self._parse_timestamp(parsed.timestamp_raw)

        # 3. Apply field-name mapping from extra_fields → canonical field overrides
        mapped = self._apply_field_map(parsed)

        # 4. Resolve required fields (event_type, action) with "unknown" fallback
        event_type = parsed.event_type or mapped.get("event_type") or "unknown"
        action = parsed.action or mapped.get("action") or "unknown"

        # 5. Resolve optional fields — parsed direct fields take precedence over mapped
        user = parsed.user or mapped.get("user")
        source_host = parsed.source_host or mapped.get("source_host")
        destination_host = parsed.destination_host or mapped.get("destination_host")
        source_ip = parsed.source_ip or mapped.get("source_ip")
        destination_ip = parsed.destination_ip or mapped.get("destination_ip")
        process = parsed.process or mapped.get("process")
        file_ = parsed.file or mapped.get("file")
        severity = parsed.severity or mapped.get("severity")

        # 6. Canonicalize identifiers
        source_host = self._canonicalize_hostname(source_host)
        destination_host = self._canonicalize_hostname(destination_host)
        user = self._canonicalize_username(user)
        source_ip = self._canonicalize_ip(source_ip)
        destination_ip = self._canonicalize_ip(destination_ip)

        # 7. Normalize severity casing (let SecurityEvent's validator do the validation)
        if severity is not None:
            severity = severity.strip().lower()

        # 8. Build SecurityEvent — Pydantic validators run here (e.g. severity check)
        try:
            return SecurityEvent(
                event_id=parsed.event_id,
                source_type=parsed.source_type,
                timestamp=timestamp,
                event_type=event_type,
                action=action,
                user=user,
                source_host=source_host,
                destination_host=destination_host,
                source_ip=source_ip,
                destination_ip=destination_ip,
                process=process,
                file=file_,
                severity=severity,
                raw_data=raw_data,
            )
        except Exception as exc:
            # Wrap Pydantic ValidationError (the Pydantic one, not our AppError) as ours
            raise ValidationError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_timestamp(self, raw: str) -> datetime:
        """Parse *raw* into a UTC-aware datetime.

        Tries in order:
          1. ISO-8601 (handles trailing Z or UTC offset)
          2. Each format in _TIMESTAMP_FORMATS via strptime
          3. Unix epoch (float or int string)

        Raises:
            ValidationError: if none of the above succeeds.
        """
        if not raw or not raw.strip():
            raise ValidationError(f"timestamp_raw is empty or blank: {raw!r}")

        raw = raw.strip()

        # --- Attempt 1: ISO-8601 (Z → +00:00, handles offsets natively) ---
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return self._ensure_utc(dt)
        except (ValueError, TypeError):
            pass

        # --- Attempt 2: strptime formats ---
        for fmt in self._TIMESTAMP_FORMATS:
            try:
                dt = datetime.strptime(raw, fmt)
                return self._ensure_utc(dt)
            except (ValueError, TypeError):
                continue

        # --- Attempt 3: Unix epoch (float / int string) ---
        try:
            epoch = float(raw)
            return datetime.fromtimestamp(epoch, tz=timezone.utc)
        except (ValueError, TypeError):
            pass

        raise ValidationError(
            f"Unable to parse timestamp: {raw!r}. "
            "Expected ISO-8601, common datetime formats, or Unix epoch."
        )

    @staticmethod
    def _ensure_utc(dt: datetime) -> datetime:
        """Attach UTC tzinfo if naive, otherwise convert to UTC."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _canonicalize_hostname(hostname: str | None) -> str | None:
        """Lowercase *hostname*. Returns None if falsy."""
        if not hostname:
            return hostname
        return hostname.lower()

    @staticmethod
    def _canonicalize_username(username: str | None) -> str | None:
        """Strip domain prefix from *username*.

        Handles:
          - ``DOMAIN\\user``  → ``user``
          - ``user@domain``   → ``user``
          - bare ``user``     → ``user`` (unchanged)
        """
        if not username:
            return username

        # DOMAIN\user  (backslash form — take everything after last backslash)
        if "\\" in username:
            return username.rsplit("\\", 1)[-1]

        # user@domain  (at-sign form — take everything before the @)
        if "@" in username:
            return username.split("@", 1)[0]

        return username

    @staticmethod
    def _canonicalize_ip(ip: str | None) -> str | None:
        """Canonicalize IP to dotted-decimal IPv4 or compressed IPv6.

        Uses Python's ipaddress module. If *ip* is not a valid address,
        returns it unchanged (no exception raised).
        """
        if not ip:
            return ip

        try:
            addr = ipaddress.ip_address(ip.strip())
            return str(addr)
        except ValueError:
            # Not a valid IP — preserve as-is
            return ip

    def _apply_field_map(self, parsed: ParsedEvent) -> dict[str, Any]:
        """Apply source-type field-name mapping from settings.normalization_field_map.

        Looks up the mapping for *parsed.source_type* and remaps any matching
        keys in *parsed.extra_fields* to their canonical SecurityEvent field names.

        Returns a dict of {canonical_field: value} for fields found in extra_fields.
        """
        field_map: dict[str, str] = settings.normalization_field_map.get(
            parsed.source_type, {}
        )

        result: dict[str, Any] = {}
        for raw_field, canonical_field in field_map.items():
            if canonical_field not in _CANONICAL_FIELDS:
                # Safety guard: skip unknown canonical targets
                continue
            if raw_field in parsed.extra_fields:
                value = parsed.extra_fields[raw_field]
                # Only set if the parsed model field is not already populated
                result[canonical_field] = value

        return result
