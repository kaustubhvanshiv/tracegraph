"""Audit CDM entity definitions across downloaded segments without labeling events."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import gzip
import json
from pathlib import Path
import sqlite3

from fastavro import reader
from research.ml.data_prep.inspect_fivedirections import natural_key, utc_nanos, uuid_text


def clean(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def lookup(db, uid):
    rows = db.execute("SELECT kind,payload,filename,record_index,host FROM entities WHERE uuid=?", (uid,)).fetchall()
    definitions = {r[1] for r in rows}
    if len(definitions) > 1:
        return {"uuid": uid, "status": "conflicting_definitions", "definition_count": len(definitions)}
    if not rows:
        return {"uuid": uid, "status": "missing"}
    kind, payload, filename, index, host = rows[0]
    datum = json.loads(payload)
    result = {"uuid": uid, "status": "resolved", "kind": kind, "definition_host_uuid": host,
              "source_file": filename, "record_index_1based": index}
    # Deliberately exclude complete command lines and principal names from reports.
    for key in ("type", "cid", "parentSubject", "localPrincipal", "startTimestampNanos", "hostName", "hostType"):
        if datum.get(key) is not None:
            result[key] = datum[key]
    command = datum.get("cmdLine") or ""
    result["firefox_command_line"] = "firefox.exe" in command.lower()
    return result


def resolve_chain(db, uid, timestamp):
    chain, seen = [], set()
    while uid and uid not in seen:
        seen.add(uid)
        entity = lookup(db, uid)
        chain.append(entity)
        if entity["status"] != "resolved":
            break
        start = entity.get("startTimestampNanos")
        entity["started_at_or_before_event"] = None if start is None else start <= timestamp
        if entity.get("type") == "SUBJECT_PROCESS":
            principal = entity.get("localPrincipal")
            entity["principal_resolution"] = lookup(db, principal) if principal else None
            break
        uid = entity.get("parentSubject")
    return chain


def audit(source, annotations, output, records_per_file=0):
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents:
        raise ValueError("Output must be outside raw source")
    if output.exists() or records_per_file < 0:
        raise ValueError("Use a fresh output directory and a nonnegative limit")
    paths = sorted(source.rglob("*.gz"), key=natural_key)
    if not paths:
        raise ValueError("No gzip source files")
    output.mkdir(parents=True)
    events = json.loads(annotations.read_text(encoding="utf-8"))["events"]
    files = []
    with closing(sqlite3.connect(output / "references.sqlite")) as db:
        db.execute("CREATE TABLE entities(uuid TEXT,kind TEXT,payload TEXT,filename TEXT,record_index INTEGER,host TEXT)")
        for path in paths:
            count, complete, types = 0, True, Counter()
            minimum = maximum = None
            with gzip.open(path, "rb") as stream:
                for raw in reader(stream):
                    if records_per_file and count >= records_per_file:
                        complete = False
                        break
                    count += 1
                    kind, datum = raw.get("type"), raw.get("datum") or {}
                    types[kind] += 1
                    if kind in {"RECORD_SUBJECT", "RECORD_HOST", "RECORD_PRINCIPAL"}:
                        uid = uuid_text(datum.get("uuid"))
                        if uid:
                            db.execute("INSERT INTO entities VALUES (?,?,?,?,?,?)", (uid, kind,
                                json.dumps(clean(datum), sort_keys=True), path.name, count, uuid_text(raw.get("hostId"))))
                    if kind == "RECORD_EVENT" and isinstance(datum.get("timestampNanos"), int):
                        timestamp = datum["timestampNanos"]
                        minimum = timestamp if minimum is None else min(minimum, timestamp)
                        maximum = timestamp if maximum is None else max(maximum, timestamp)
                    if count % 1_000_000 == 0:
                        db.commit()
                        print(f"{path.name}: {count:,} records", flush=True)
            db.commit()
            files.append({"filename": path.name, "records": count, "complete_scan": complete,
                "compressed_bytes": path.stat().st_size, "modified_time_ns": path.stat().st_mtime_ns,
                "record_type_counts": dict(types), "min_event_utc": utc_nanos(minimum), "max_event_utc": utc_nanos(maximum)})
            (output / "scan_progress.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
        db.execute("CREATE INDEX entity_uuid ON entities(uuid)")
        db.commit()
        reviews = [{"event_uuid": event["event_uuid"], "timestamp_nanos": event["timestamp_nanos"],
                    "host_resolution": lookup(db, event["host_uuid"]),
                    "subject_chain": resolve_chain(db, event["subject_uuid"], event["timestamp_nanos"]),
                    "label": None} for event in events]
    report = {"files": files, "all_files_fully_scanned": all(f["complete_scan"] for f in files),
              "review_events": reviews, "labels_assigned": 0,
              "scope": "Downloaded subset only; entity definitions are audit metadata, not model features"}
    (output / "reference_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--records-per-file", type=int, default=0)
    args = parser.parse_args()
    report = audit(args.source, args.annotations, args.output, args.records_per_file)
    print(f"Reviewed {len(report['review_events'])} events; no labels assigned", flush=True)


if __name__ == "__main__":
    main()
