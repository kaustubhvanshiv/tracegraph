import copy
from typing import Any
from app.schemas.parser import ParsedEvent, ParseError


class SysmonAdapter:
    """ParserAdapter for Sysmon Windows events (source_type='sysmon')."""
    source_type: str = "sysmon"

    def parse(self, raw: dict[str, Any]) -> ParsedEvent | ParseError:
        if not isinstance(raw, dict):
            return ParseError(reason="Raw event must be a dict", raw_event={})

        raw_copy = copy.deepcopy(raw)

        event_id = raw_copy.get("event_id") or raw_copy.get("RecordID") or raw_copy.get("id") or raw_copy.get("EventID")
        if event_id is None or not str(event_id).strip():
            return ParseError(
                event_id=None,
                field_name="event_id",
                reason="Sysmon event missing required event_id / RecordID field",
                raw_event=raw_copy,
            )
        event_id_str = str(event_id).strip()

        timestamp_raw = raw_copy.get("UtcTime") or raw_copy.get("timestamp") or raw_copy.get("TimeCreated") or raw_copy.get("time")
        if timestamp_raw is None or not str(timestamp_raw).strip():
            return ParseError(
                event_id=event_id_str,
                field_name="timestamp",
                reason="Sysmon event missing required UtcTime / timestamp field",
                raw_event=raw_copy,
            )

        recognized_keys = {
            "EventID", "event_id", "RecordID", "id",
            "UtcTime", "timestamp", "TimeCreated", "time",
            "EventDescription", "event_type", "Task",
            "Action", "action", "Opcode",
            "User", "user", "Account",
            "Computer", "source_host", "Hostname",
            "DestinationHostname", "destination_host", "TargetHostname",
            "SourceIp", "source_ip", "SrcIp",
            "DestinationIp", "destination_ip", "DestIp",
            "Image", "process", "ParentImage",
            "TargetFilename", "file", "FileName",
            "Level", "severity",
        }

        extra_fields = {k: v for k, v in raw_copy.items() if k not in recognized_keys}

        return ParsedEvent(
            event_id=event_id_str,
            source_type=self.source_type,
            timestamp_raw=str(timestamp_raw).strip(),
            event_type=_get_str(raw_copy, ["EventDescription", "event_type", "Task"]),
            action=_get_str(raw_copy, ["Action", "action", "Opcode"]),
            user=_get_str(raw_copy, ["User", "user", "Account"]),
            source_host=_get_str(raw_copy, ["Computer", "source_host", "Hostname"]),
            destination_host=_get_str(raw_copy, ["DestinationHostname", "destination_host", "TargetHostname"]),
            source_ip=_get_str(raw_copy, ["SourceIp", "source_ip", "SrcIp"]),
            destination_ip=_get_str(raw_copy, ["DestinationIp", "destination_ip", "DestIp"]),
            process=_get_str(raw_copy, ["Image", "process", "ParentImage"]),
            file=_get_str(raw_copy, ["TargetFilename", "file", "FileName"]),
            severity=_get_str(raw_copy, ["Level", "severity"]),
            extra_fields=extra_fields,
        )


def _get_str(d: dict[str, Any], keys: list[str]) -> str | None:
    for k in keys:
        if k in d and d[k] is not None:
            return str(d[k])
    return None
