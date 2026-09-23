import copy
from typing import Any
from app.schemas.parser import ParsedEvent, ParseError


class PublicDatasetAdapter:
    """ParserAdapter for Public Benchmark Dataset events (source_type='public_dataset')."""
    source_type: str = "public_dataset"

    def parse(self, raw: dict[str, Any]) -> ParsedEvent | ParseError:
        if not isinstance(raw, dict):
            return ParseError(reason="Raw event must be a dict", raw_event={})

        raw_copy = copy.deepcopy(raw)

        event_id = raw_copy.get("event_id") or raw_copy.get("id") or raw_copy.get("uuid")
        if event_id is None or not str(event_id).strip():
            return ParseError(
                event_id=None,
                field_name="event_id",
                reason="Public dataset event missing required event_id field",
                raw_event=raw_copy,
            )
        event_id_str = str(event_id).strip()

        timestamp_raw = raw_copy.get("timestamp") or raw_copy.get("time")
        if timestamp_raw is None or not str(timestamp_raw).strip():
            return ParseError(
                event_id=event_id_str,
                field_name="timestamp",
                reason="Public dataset event missing required timestamp field",
                raw_event=raw_copy,
            )

        recognized_keys = {
            "event_id", "id", "uuid",
            "timestamp", "time",
            "event_type", "type", "category",
            "action", "activity",
            "user", "username",
            "source_host", "src_host", "hostname",
            "destination_host", "dst_host", "target_host",
            "source_ip", "src_ip",
            "destination_ip", "dst_ip",
            "process", "process_name",
            "file", "file_path",
            "severity", "level",
        }

        extra_fields = {k: v for k, v in raw_copy.items() if k not in recognized_keys}

        return ParsedEvent(
            event_id=event_id_str,
            source_type=self.source_type,
            timestamp_raw=str(timestamp_raw).strip(),
            event_type=_get_str(raw_copy, ["event_type", "type", "category"]),
            action=_get_str(raw_copy, ["action", "activity"]),
            user=_get_str(raw_copy, ["user", "username"]),
            source_host=_get_str(raw_copy, ["source_host", "src_host", "hostname"]),
            destination_host=_get_str(raw_copy, ["destination_host", "dst_host", "target_host"]),
            source_ip=_get_str(raw_copy, ["source_ip", "src_ip"]),
            destination_ip=_get_str(raw_copy, ["destination_ip", "dst_ip"]),
            process=_get_str(raw_copy, ["process", "process_name"]),
            file=_get_str(raw_copy, ["file", "file_path"]),
            severity=_get_str(raw_copy, ["severity", "level"]),
            extra_fields=extra_fields,
        )


def _get_str(d: dict[str, Any], keys: list[str]) -> str | None:
    for k in keys:
        if k in d and d[k] is not None:
            return str(d[k])
    return None
