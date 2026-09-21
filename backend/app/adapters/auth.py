import copy
from typing import Any
from app.schemas.parser import ParsedEvent, ParseError


class AuthAdapter:
    """ParserAdapter for Authentication log events (source_type='auth')."""
    source_type: str = "auth"

    def parse(self, raw: dict[str, Any]) -> ParsedEvent | ParseError:
        if not isinstance(raw, dict):
            return ParseError(reason="Raw event must be a dict", raw_event={})

        raw_copy = copy.deepcopy(raw)

        event_id = raw_copy.get("event_id") or raw_copy.get("auth_id") or raw_copy.get("id") or raw_copy.get("uuid")
        if event_id is None or not str(event_id).strip():
            return ParseError(
                event_id=None,
                field_name="event_id",
                reason="Auth event missing required event_id field",
                raw_event=raw_copy,
            )
        event_id_str = str(event_id).strip()

        timestamp_raw = raw_copy.get("timestamp") or raw_copy.get("event_time") or raw_copy.get("time")
        if timestamp_raw is None or not str(timestamp_raw).strip():
            return ParseError(
                event_id=event_id_str,
                field_name="timestamp",
                reason="Auth event missing required timestamp field",
                raw_event=raw_copy,
            )

        recognized_keys = {
            "event_id", "auth_id", "id", "uuid",
            "timestamp", "event_time", "time",
            "auth_event", "event_type", "type",
            "auth_action", "action", "outcome",
            "user_id", "username", "user", "account",
            "hostname", "source_host", "client_host",
            "target_host", "destination_host", "server_host",
            "client_ip", "source_ip", "src_ip",
            "server_ip", "destination_ip", "dst_ip",
            "process", "service",
            "file",
            "severity", "level",
        }

        extra_fields = {k: v for k, v in raw_copy.items() if k not in recognized_keys}

        return ParsedEvent(
            event_id=event_id_str,
            source_type=self.source_type,
            timestamp_raw=str(timestamp_raw).strip(),
            event_type=_get_str(raw_copy, ["auth_event", "event_type", "type"]),
            action=_get_str(raw_copy, ["auth_action", "action", "outcome"]),
            user=_get_str(raw_copy, ["user_id", "username", "user", "account"]),
            source_host=_get_str(raw_copy, ["hostname", "source_host", "client_host"]),
            destination_host=_get_str(raw_copy, ["target_host", "destination_host", "server_host"]),
            source_ip=_get_str(raw_copy, ["client_ip", "source_ip", "src_ip"]),
            destination_ip=_get_str(raw_copy, ["server_ip", "destination_ip", "dst_ip"]),
            process=_get_str(raw_copy, ["process", "service"]),
            file=_get_str(raw_copy, ["file"]),
            severity=_get_str(raw_copy, ["severity", "level"]),
            extra_fields=extra_fields,
        )


def _get_str(d: dict[str, Any], keys: list[str]) -> str | None:
    for k in keys:
        if k in d and d[k] is not None:
            return str(d[k])
    return None
