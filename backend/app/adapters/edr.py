import copy
from typing import Any
from app.schemas.parser import ParsedEvent, ParseError


class EDRAdapter:
    """ParserAdapter for EDR / Endpoint Telemetry events (source_type='edr')."""
    source_type: str = "edr"

    def parse(self, raw: dict[str, Any]) -> ParsedEvent | ParseError:
        if not isinstance(raw, dict):
            return ParseError(reason="Raw event must be a dict", raw_event={})

        raw_copy = copy.deepcopy(raw)

        event_id = raw_copy.get("event_id") or raw_copy.get("alert_id") or raw_copy.get("id") or raw_copy.get("uuid")
        if event_id is None or not str(event_id).strip():
            return ParseError(
                event_id=None,
                field_name="event_id",
                reason="EDR event missing required event_id field",
                raw_event=raw_copy,
            )
        event_id_str = str(event_id).strip()

        timestamp_raw = raw_copy.get("timestamp") or raw_copy.get("event_timestamp") or raw_copy.get("time")
        if timestamp_raw is None or not str(timestamp_raw).strip():
            return ParseError(
                event_id=event_id_str,
                field_name="timestamp",
                reason="EDR event missing required timestamp field",
                raw_event=raw_copy,
            )

        recognized_keys = {
            "event_id", "alert_id", "id", "uuid",
            "timestamp", "event_timestamp", "time",
            "event_category", "event_type", "detection_type",
            "action_taken", "action", "operation",
            "account_name", "user_name", "user",
            "endpoint_name", "agent_hostname", "source_host", "hostname",
            "target_host", "destination_host", "remote_host",
            "src_ip", "source_ip", "local_ip",
            "dest_ip", "destination_ip", "remote_ip",
            "process_path", "process_name", "process",
            "file_path", "target_path", "file",
            "severity_level", "severity", "threat_level",
        }

        extra_fields = {k: v for k, v in raw_copy.items() if k not in recognized_keys}

        return ParsedEvent(
            event_id=event_id_str,
            source_type=self.source_type,
            timestamp_raw=str(timestamp_raw).strip(),
            event_type=_get_str(raw_copy, ["event_category", "event_type", "detection_type"]),
            action=_get_str(raw_copy, ["action_taken", "action", "operation"]),
            user=_get_str(raw_copy, ["account_name", "user_name", "user"]),
            source_host=_get_str(raw_copy, ["endpoint_name", "agent_hostname", "source_host", "hostname"]),
            destination_host=_get_str(raw_copy, ["target_host", "destination_host", "remote_host"]),
            source_ip=_get_str(raw_copy, ["src_ip", "source_ip", "local_ip"]),
            destination_ip=_get_str(raw_copy, ["dest_ip", "destination_ip", "remote_ip"]),
            process=_get_str(raw_copy, ["process_path", "process_name", "process"]),
            file=_get_str(raw_copy, ["file_path", "target_path", "file"]),
            severity=_get_str(raw_copy, ["severity_level", "severity", "threat_level"]),
            extra_fields=extra_fields,
        )


def _get_str(d: dict[str, Any], keys: list[str]) -> str | None:
    for k in keys:
        if k in d and d[k] is not None:
            return str(d[k])
    return None
