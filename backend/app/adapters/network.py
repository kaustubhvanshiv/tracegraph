import copy
from typing import Any
from app.schemas.parser import ParsedEvent, ParseError


class NetworkAdapter:
    """ParserAdapter for Network flow / PCAP events (source_type='network')."""
    source_type: str = "network"

    def parse(self, raw: dict[str, Any]) -> ParsedEvent | ParseError:
        if not isinstance(raw, dict):
            return ParseError(reason="Raw event must be a dict", raw_event={})

        raw_copy = copy.deepcopy(raw)

        event_id = raw_copy.get("flow_id") or raw_copy.get("event_id") or raw_copy.get("id") or raw_copy.get("uuid")
        if event_id is None or not str(event_id).strip():
            return ParseError(
                event_id=None,
                field_name="event_id",
                reason="Network event missing required flow_id / event_id field",
                raw_event=raw_copy,
            )
        event_id_str = str(event_id).strip()

        timestamp_raw = raw_copy.get("timestamp") or raw_copy.get("start_time") or raw_copy.get("time")
        if timestamp_raw is None or not str(timestamp_raw).strip():
            return ParseError(
                event_id=event_id_str,
                field_name="timestamp",
                reason="Network event missing required timestamp field",
                raw_event=raw_copy,
            )

        recognized_keys = {
            "flow_id", "event_id", "id", "uuid",
            "timestamp", "start_time", "time",
            "protocol", "event_type", "traffic_type",
            "action", "status", "connection_state",
            "user", "username",
            "src_host", "source_host", "src_name",
            "dst_host", "destination_host", "dst_name",
            "src_ip", "source_ip", "src_address",
            "dst_ip", "destination_ip", "dst_address",
            "process", "app",
            "file", "uri",
            "severity", "priority",
        }

        extra_fields = {k: v for k, v in raw_copy.items() if k not in recognized_keys}

        return ParsedEvent(
            event_id=event_id_str,
            source_type=self.source_type,
            timestamp_raw=str(timestamp_raw).strip(),
            event_type=_get_str(raw_copy, ["protocol", "event_type", "traffic_type"]),
            action=_get_str(raw_copy, ["action", "status", "connection_state"]),
            user=_get_str(raw_copy, ["user", "username"]),
            source_host=_get_str(raw_copy, ["src_host", "source_host", "src_name"]),
            destination_host=_get_str(raw_copy, ["dst_host", "destination_host", "dst_name"]),
            source_ip=_get_str(raw_copy, ["src_ip", "source_ip", "src_address"]),
            destination_ip=_get_str(raw_copy, ["dst_ip", "destination_ip", "dst_address"]),
            process=_get_str(raw_copy, ["process", "app"]),
            file=_get_str(raw_copy, ["file", "uri"]),
            severity=_get_str(raw_copy, ["severity", "priority"]),
            extra_fields=extra_fields,
        )


def _get_str(d: dict[str, Any], keys: list[str]) -> str | None:
    for k in keys:
        if k in d and d[k] is not None:
            return str(d[k])
    return None
