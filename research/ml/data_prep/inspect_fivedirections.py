"""Profile bounded prefixes of gzip-wrapped DARPA CDM Avro containers.

No raw records are exported. Counts and reference availability describe ONLY
the inspected prefixes. Pass --records-per-file 0 for a full streaming scan.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import re
from typing import Any

from fastavro import reader

EVENT_FIELDS = (
    "uuid", "timestampNanos", "subject", "predicateObject",
    "predicateObject2", "predicateObjectPath", "predicateObject2Path",
)
LABEL_KEYS = {"label", "attack", "attack_label", "is_malicious", "malicious", "attack_category"}


def natural_key(path: Path) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", str(path))]


def utc_nanos(value: int | None) -> str | None:
    """Preserve all nine fractional digits without float rounding."""
    if value is None:
        return None
    seconds, nanos = divmod(value, 1_000_000_000)
    instant = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return instant.strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos:09d}Z"


def uuid_text(value: Any) -> str | None:
    if value is None:
        return None
    return value.hex() if isinstance(value, bytes) else str(value)


def schema_records(schema: dict) -> dict:
    """Describe record fields, without copying record payloads."""
    result = {}

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                visit(child)
        elif isinstance(node, dict):
            if node.get("type") == "record":
                result[node["name"]] = [
                    {"name": f["name"], "type": f["type"]} for f in node["fields"]
                ]
            for child in node.values():
                visit(child)

    visit(schema)
    return result


def inspect_file(path: Path, records_per_file: int) -> tuple[dict, dict]:
    if records_per_file < 0:
        raise ValueError("records_per_file must be nonnegative")
    types, actions, names, versions, sources, hosts = (Counter() for _ in range(6))
    populated, property_keys, label_keys = Counter(), Counter(), Counter()
    sessions, minimum, maximum, previous, regressions, events = set(), None, None, None, 0, 0
    field_names: dict[str, set[str]] = {}
    count = 0
    with gzip.open(path, "rb") as stream:
        avro = reader(stream)
        schema, codec = avro.writer_schema, avro.codec
        # One lookahead distinguishes a complete small file from a bounded prefix.
        records = avro if not records_per_file else itertools.islice(avro, records_per_file)
        for record in records:
            count += 1
            kind = record.get("type", "UNKNOWN")
            datum = record.get("datum") or {}
            if not isinstance(datum, dict):
                raise ValueError(f"Unexpected datum shape at record {count} in {path.name}")
            types[kind] += 1
            versions[str(record.get("CDMVersion"))] += 1
            sources[str(record.get("source"))] += 1
            hosts[uuid_text(record.get("hostId")) or "UNKNOWN"] += 1
            sessions.add(record.get("sessionNumber"))
            field_names.setdefault(kind, set()).update(datum)
            properties = datum.get("properties") or {}
            if isinstance(properties, dict):
                property_keys.update(properties.keys())
                label_keys.update(k for k in properties if k.lower() in LABEL_KEYS)
            label_keys.update(k for k in datum if k.lower() in LABEL_KEYS)
            if kind != "RECORD_EVENT":
                continue
            events += 1
            actions[str(datum.get("type"))] += 1
            names.update(datum.get("names") or [])
            for field in EVENT_FIELDS:
                if datum.get(field) is not None:
                    populated[field] += 1
            timestamp = datum.get("timestampNanos")
            if isinstance(timestamp, int):
                minimum = timestamp if minimum is None else min(minimum, timestamp)
                maximum = timestamp if maximum is None else max(maximum, timestamp)
                if previous is not None and timestamp < previous:
                    regressions += 1
                previous = timestamp
        complete = not records_per_file or next(avro, None) is None
    schema_digest = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    report = {
        "path": str(path.resolve()), "compressed_bytes": path.stat().st_size,
        "format": "gzip-wrapped Avro object container", "avro_codec": codec,
        "schema_name": schema.get("name"), "schema_sha256": schema_digest,
        "records_inspected": count, "complete_scan": complete,
        "record_type_counts": dict(sorted(types.items())),
        "event_count": events, "event_type_counts": dict(sorted(actions.items())),
        "event_name_counts": dict(sorted(names.items())),
        "event_fields_populated": {field: populated[field] for field in EVENT_FIELDS},
        "event_time_min_nanos": minimum, "event_time_max_nanos": maximum,
        "event_time_min_utc": utc_nanos(minimum), "event_time_max_utc": utc_nanos(maximum),
        "event_timestamp_regressions": regressions,
        "cdm_version_counts": dict(versions), "instrumentation_source_counts": dict(sources),
        "host_uuid_counts": dict(hosts), "session_numbers": sorted(sessions, key=str),
        "datum_fields_observed": {k: sorted(v) for k, v in sorted(field_names.items())},
        "property_key_counts": dict(sorted(property_keys.items())),
        "candidate_label_key_counts": dict(label_keys),
    }
    return report, schema


def inspect_dataset(source: Path, records_per_file: int = 20_000) -> dict:
    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source}")
    paths = sorted(source.rglob("*.bin*.gz"), key=natural_key)
    if not paths:
        raise ValueError(f"No .bin*.gz files found in {source}")
    files, failures, schemas = [], [], {}
    for path in paths:
        try:
            profile, schema = inspect_file(path, records_per_file)
            files.append(profile)
            schemas.setdefault(profile["schema_sha256"], schema_records(schema))
            print(f"Inspected {path.name}: {profile['records_inspected']:,} records", flush=True)
        except Exception as exc:
            failures.append({"path": str(path.resolve()), "error": f"{type(exc).__name__}: {exc}"})
    all_files = sorted((p for p in source.rglob("*") if p.is_file()), key=natural_key)
    return {
        "source_path": str(source.resolve()),
        "records_per_file_limit": records_per_file,
        "sampling_method": "prefix of each file; not random or representative of the full release",
        "file_count": len(paths), "total_compressed_bytes": sum(p.stat().st_size for p in paths),
        "records_inspected": sum(f["records_inspected"] for f in files),
        "events_inspected": sum(f["event_count"] for f in files),
        "all_files_fully_scanned": not failures and all(f["complete_scan"] for f in files),
        "ground_truth_status": "unverified; missing annotations do not imply benign activity",
        "other_local_files": [str(p.resolve()) for p in all_files if p not in paths],
        "schema_record_fields": schemas, "files": files, "errors": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--records-per-file", type=int, default=20_000)
    args = parser.parse_args()
    if args.records_per_file < 0:
        parser.error("--records-per-file must be >= 0")
    # Inspection must never write into the source download directory.
    if args.output.resolve().is_relative_to(args.source.resolve()):
        parser.error("--output must be outside the raw source directory")
    try:
        report = inspect_dataset(args.source, args.records_per_file)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {args.output}; {len(report['errors'])} file errors", flush=True)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
