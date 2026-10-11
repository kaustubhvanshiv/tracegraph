"""Full streaming coverage audit against report-derived review indicators.

Produces aggregate coverage and bounded event references, never attack labels.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re

from fastavro import reader
from fastavro.schema import to_parsing_canonical_form

from research.ml.data_prep.inspect_fivedirections import natural_key, utc_nanos, uuid_text


def time_nanos(value: str) -> int:
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(instant.timestamp()) * 1_000_000_000


def audit_file(path: Path, candidates: dict, schema: dict | None = None) -> dict:
    types, actions, host_counts, matches = Counter(), Counter(), Counter(), Counter()
    host_records, references, intervals = {}, [], Counter()
    minimum = maximum = None
    count = 0
    indicators = {indicator.lower(): incident["incident_id"]
                  for incident in candidates["incidents"] for indicator in incident["indicators"]}
    pattern = re.compile("|".join(re.escape(i) for i in indicators), re.IGNORECASE) if indicators else None
    windows = [(incident["incident_id"], time_nanos(incident["candidate_start_utc"]),
                time_nanos(incident["candidate_end_utc"])) for incident in candidates["incidents"]]
    with gzip.open(path, "rb") as stream:
        avro = reader(stream)
        canonical = to_parsing_canonical_form(avro.writer_schema)
        agrees = None if schema is None else canonical == to_parsing_canonical_form(schema)
        for record in avro:
            count += 1
            if count % 250_000 == 0:
                print(f"{path.name}: {count:,} records", flush=True)
            kind, datum = record.get("type"), record.get("datum") or {}
            types[kind] += 1
            if kind == "RECORD_HOST":
                host_records[uuid_text(datum.get("uuid"))] = {
                    "hostname": datum.get("hostName"), "host_type": datum.get("hostType")}
            if kind != "RECORD_EVENT":
                continue
            host = uuid_text(record.get("hostId"))
            host_counts[host] += 1
            actions[datum.get("type")] += 1
            timestamp = datum.get("timestampNanos")
            if isinstance(timestamp, int):
                minimum = timestamp if minimum is None else min(minimum, timestamp)
                maximum = timestamp if maximum is None else max(maximum, timestamp)
                for incident_id, start, end in windows:
                    if start <= timestamp <= end:
                        intervals[incident_id] += 1
            # Match only descriptive string fields, not UUIDs or bytes.
            fields = {k: v for k, v in datum.items() if isinstance(v, str)}
            fields.update({f"properties.{k}": v for k, v in (datum.get("properties") or {}).items() if isinstance(v, str)})
            found = {m.group().lower() for m in pattern.finditer("\n".join(fields.values()))} if pattern else set()
            for indicator in sorted(found):
                incident_id = indicators[indicator]
                matched_fields = [k for k, v in fields.items() if indicator in v.lower()]
                if not matched_fields:
                    continue
                matches[indicator] += 1
                if matches[indicator] <= 10:
                    references.append({
                        "incident_id": incident_id, "indicator": indicator,
                        "matched_fields": matched_fields, "event_uuid": uuid_text(datum.get("uuid")),
                        "host_uuid": host, "timestamp_nanos": timestamp,
                        "timestamp_utc": utc_nanos(timestamp), "cdm_event_type": datum.get("type"),
                        "subject_uuid": uuid_text(datum.get("subject")),
                        "record_index_1based": count, "label": None,
                    })
    return {
        "path": str(path.resolve()), "compressed_bytes": path.stat().st_size,
        "complete_scan": True, "records": count, "record_type_counts": dict(types),
        "event_count": sum(actions.values()), "event_type_counts": dict(actions),
        "min_event_time_utc": utc_nanos(minimum), "max_event_time_utc": utc_nanos(maximum),
        "host_event_counts": dict(host_counts), "host_definitions": host_records,
        "schema_canonical_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "downloaded_schema_matches": agrees,
        "candidate_interval_event_counts": dict(intervals),
        "indicator_event_counts": dict(matches), "review_event_references": references,
        "labels_assigned": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="Reuse completed files from this same audit output")
    parser.add_argument("--filename", help="Audit one exact filename instead of every discovered segment")
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.source.resolve()):
        parser.error("Output must be outside the raw source directory")
    paths = sorted(args.source.rglob("*.bin*.gz"), key=natural_key)
    if not paths:
        parser.error("No gzip Avro files found")
    discovered_file_count = len(paths)
    if args.filename:
        paths = [p for p in paths if p.name == args.filename]
        if len(paths) != 1:
            parser.error("--filename must match exactly one discovered source file")
    # Investigate the most relevant late segment first; saved results retain order.
    paths.sort(key=lambda p: (not p.name.endswith(".121.gz"), natural_key(p)))
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8")) if args.schema else None
    report = {"source_path": str(args.source.resolve()), "candidates_path": str(args.candidates.resolve()),
              "label_status": "review candidates only; all labels unknown", "files": [], "errors": []}
    config_sha256 = hashlib.sha256(json.dumps({"candidates": candidates, "schema": schema}, sort_keys=True).encode()).hexdigest()
    report["config_sha256"] = config_sha256
    if args.resume and args.output.exists():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        if previous["source_path"] != report["source_path"] or previous["candidates_path"] != report["candidates_path"]:
            parser.error("Resume source and candidate configuration must match the previous audit")
        if previous.get("config_sha256") != config_sha256:
            parser.error("Resume requires identical incident/schema content and a recorded configuration hash")
        selected_paths = {str(path.resolve()) for path in paths}
        report["files"] = [f for f in previous["files"] if f["path"] in selected_paths]
    report["expected_file_count"] = len(paths)
    report["discovered_file_count"] = discovered_file_count
    report["selected_file_count"] = len(paths)
    report["all_files_fully_scanned"] = False
    completed = {f["path"]: f for f in report["files"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for path in paths:
        prior = completed.get(str(path.resolve()))
        if prior is not None:
            if (not prior.get("complete_scan") or prior["compressed_bytes"] != path.stat().st_size
                    or prior.get("source_modified_time_ns") != path.stat().st_mtime_ns):
                parser.error(f"Resume file has changed or is incomplete: {path}")
            print(f"Reusing complete audit: {path.name}", flush=True)
            continue
        try:
            result = audit_file(path, candidates, schema)
            result["source_modified_time_ns"] = path.stat().st_mtime_ns
            report["files"].append(result)
            print(f"Completed {path.name}: {result['records']:,} records; {result['min_event_time_utc']} to {result['max_event_time_utc']}", flush=True)
        except Exception as exc:
            report["errors"].append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["all_files_fully_scanned"] = not report["errors"] and len(report["files"]) == len(paths)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
