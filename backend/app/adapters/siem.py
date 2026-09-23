import copy
from typing import Any
from app.schemas.parser import ParsedEvent, ParseError


class SIEMAdapter:
    """ParserAdapter for SIEM / Log Aggregator events (source_type='siem')."""
    source_type: str = "siem"

    def parse(self, raw: dict[str, Any]) -> ParsedEvent | ParseError:
        if not isinstance(raw, dict):
            return ParseError(reason="Raw event must be a dict", raw_event={})

        # Deep copy raw dict to enforce non-mutation requirement
        raw_copy = copy.deepcopy(raw)

        # Extract event_id
        event_id = raw_copy.get("event_id") or raw_copy.get("@id") or raw_copy.get("id") or raw_copy.get("uuid")
        if event_id is None or not str(event_id).strip():
            return ParseError(
                event_id=None,
                field_name="event_id",
                reason="SIEM event missing required event_id field",
                raw_event=raw_copy,
            )
        event_id_str = str(event_id).strip()

        # Extract timestamp_raw
        timestamp_raw = raw_copy.get("@timestamp") or raw_copy.get("timestamp") or raw_copy.get("time") or raw_copy.get("EventTime")
        if timestamp_raw is None or not str(timestamp_raw).strip():
            return ParseError(
                event_id=event_id_str,
                field_name="timestamp",
                reason="SIEM event missing required timestamp field",
                raw_event=raw_copy,
            )

        # Field mapping helpers
        recognized_keys = {
            "event_id", "@id", "id", "uuid",
            "@timestamp", "timestamp", "time", "EventTime",
            "event_type", "event_category", "category", "log_type",
            "action", "event_action", "activity",
            "user", "username", "account", "user_id", "src_user",
            "source_host", "src_host", "hostname", "host", "computer_name",
            "destination_host", "dst_host", "target_host", "dest_host",
            "source_ip", "src_ip", "client_ip", "source_address",
            "destination_ip", "dst_ip", "target_ip", "destination_address",
            "process", "process_name", "process_path", "image",
            "file", "file_path", "target_filename", "filename",
            "severity", "level", "log_level", "priority",
        }

        extra_fields = {k: v for k, v in raw_copy.items() if k not in recognized_keys}

        return ParsedEvent(
            event_id=event_id_str,
            source_type=self.source_type,
            timestamp_raw=str(timestamp_raw).strip(),
            event_type=_get_str(raw_copy, ["event_type", "event_category", "category", "log_type"]),
            action=_get_str(raw_copy, ["action", "event_action", "activity"]),
            user=_get_str(raw_copy, ["user", "username", "account", "user_id", "src_user"]),
            source_host=_get_str(raw_copy, ["source_host", "src_host", "hostname", "host", "computer_name"]),
            destination_host=_get_str(raw_copy, ["destination_host", "dst_host", "target_host", "dest_host"]),
            source_ip=_get_str(raw_copy, ["source_ip", "src_ip", "client_ip", "source_address"]),
            destination_ip=_get_str(raw_copy, ["destination_ip", "dst_ip", "target_ip", "destination_address"]),
            process=_get_str(raw_copy, ["process", "process_name", "process_path", "image"]),
            file=_get_str(raw_copy, ["file", "file_path", "target_filename", "filename"]),
            severity=_get_str(raw_copy, ["severity", "level", "log_level", "priority"]),
            extra_fields=extra_fields,
        )


def _get_str(d: dict[str, Any], keys: list[str]) -> str | None:
    for k in keys:
        if k in d and d[k] is not None:
            return str(d[k])
    return None
