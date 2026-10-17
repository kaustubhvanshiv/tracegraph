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


def lookup(db, uid, host=None, kind=None):
    query, parameters = "SELECT kind,payload,filename,record_index,host FROM entities WHERE uuid=?", [uid]
    if host is not None:
        query += " AND host=?"
        parameters.append(host)
    if kind is not None:
        query += " AND kind=?"
        parameters.append(kind)
    rows = db.execute(query, parameters).fetchall()
    definitions = {(r[0], r[1], r[4]) for r in rows}
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


def resolve_chain(db, uid, timestamp, host=None):
    chain, seen = [], set()
    while uid and uid not in seen:
        seen.add(uid)
        entity = lookup(db, uid, host, "RECORD_SUBJECT")
        chain.append(entity)
        if entity["status"] != "resolved":
            break
        start = entity.get("startTimestampNanos")
        entity["started_at_or_before_event"] = None if start is None else start <= timestamp
        if entity.get("type") == "SUBJECT_PROCESS":
            principal = entity.get("localPrincipal")
            entity["principal_resolution"] = lookup(db, principal, host, "RECORD_PRINCIPAL") if principal else None
            break
        uid = entity.get("parentSubject")
    return chain


def reusable_files(source_paths, previous):
    """Validate a completed local cache before reusing its entity index.

    Size and modification time guard cache identity; checksum verification of
    downloaded archives is a separate acquisition step, not authenticity proof.
    """
    report = json.loads((previous / "reference_report.json").read_text(encoding="utf-8"))
    if not report.get("all_files_fully_scanned") or not (previous / "references.sqlite").is_file():
        raise ValueError("Reuse requires a completed reference audit and its SQLite index")
    by_name = {p.name: p for p in source_paths}
    files = report["files"]
    if len({f["filename"] for f in files}) != len(files):
        raise ValueError("Duplicate cached filenames")
    for item in files:
        path = by_name.get(item["filename"])
        if path is None or not item.get("complete_scan"):
            raise ValueError("Cached file is outside the selected complete scan")
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (item["compressed_bytes"], item["modified_time_ns"]):
            raise ValueError(f"Cached source changed: {path.name}")
    return files


def validate_cached_index(db, files):
    expected = Counter()
    for item in files:
        for kind in ("RECORD_SUBJECT", "RECORD_HOST", "RECORD_PRINCIPAL"):
            expected[(item["filename"], kind)] = item["record_type_counts"].get(kind, 0)
    actual = Counter({(name, kind): n for name, kind, n in db.execute(
        "SELECT filename,kind,COUNT(*) FROM entities GROUP BY filename,kind")})
    if actual != +expected:
        raise ValueError("Cached index does not match the completed report")


def audit(source, annotations, output, records_per_file=0, file_pattern="*.gz", reuse_audit=None):
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents:
        raise ValueError("Output must be outside raw source")
    if output.exists() or records_per_file < 0:
        raise ValueError("Use a fresh output directory and a nonnegative limit")
    if Path(file_pattern).name != file_pattern or not file_pattern.endswith(".gz"):
        raise ValueError("File pattern must be a gzip basename pattern")
    paths = sorted(source.rglob(file_pattern), key=natural_key)
    if not paths:
        raise ValueError("No gzip source files")
    if len({p.name for p in paths}) != len(paths):
        raise ValueError("Source contains duplicate basenames")
    events = json.loads(annotations.read_text(encoding="utf-8"))["events"]
    if reuse_audit is not None and records_per_file:
        raise ValueError("A reused full audit requires a full scan of the new files")
    files = reusable_files(paths, Path(reuse_audit)) if reuse_audit is not None else []
    reused = {f["filename"] for f in files}
    output.mkdir(parents=True)
    with closing(sqlite3.connect(output / "references.sqlite")) as db:
        if reuse_audit is not None:
            with closing(sqlite3.connect((Path(reuse_audit).resolve() / "references.sqlite").as_uri() + "?mode=ro", uri=True)) as old:
                validate_cached_index(old, files)
                old.backup(db)
        else:
            db.execute("CREATE TABLE entities(uuid TEXT,kind TEXT,payload TEXT,filename TEXT,record_index INTEGER,host TEXT)")
        for path in paths:
            if path.name in reused:
                print(f"Reused completed scan: {path.name}", flush=True)
                continue
            count, complete, types = 0, True, Counter()
            minimum = maximum = None
            before = path.stat()
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
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError(f"Source changed while scanning: {path.name}")
            files.append({"filename": path.name, "records": count, "complete_scan": complete,
                "compressed_bytes": path.stat().st_size, "modified_time_ns": path.stat().st_mtime_ns,
                "record_type_counts": dict(types), "min_event_utc": utc_nanos(minimum), "max_event_utc": utc_nanos(maximum)})
            (output / "scan_progress.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
        db.execute("CREATE INDEX IF NOT EXISTS entity_uuid ON entities(uuid)")
        db.execute("CREATE INDEX IF NOT EXISTS entity_host_uuid ON entities(host,uuid)")
        db.commit()
        reviews = [{"event_uuid": event["event_uuid"], "timestamp_nanos": event["timestamp_nanos"],
                    "host_resolution": lookup(db, event["host_uuid"], event["host_uuid"], "RECORD_HOST"),
                    "subject_chain": resolve_chain(db, event["subject_uuid"], event["timestamp_nanos"], event["host_uuid"]),
                    "label": None} for event in events]
    report = {"files": sorted(files, key=lambda f: natural_key(Path(f["filename"]))),
              "file_pattern": file_pattern, "reused_file_count": len(reused),
              "newly_scanned_file_count": len(paths) - len(reused),
              "all_files_fully_scanned": all(f["complete_scan"] for f in files),
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
    parser.add_argument("--file-pattern", default="*.gz", help="Select gzip basenames within the source")
    parser.add_argument("--reuse-audit", type=Path, help="Completed local full audit with unchanged source files")
    args = parser.parse_args()
    report = audit(args.source, args.annotations, args.output, args.records_per_file, args.file_pattern, args.reuse_audit)
    print(f"Reviewed {len(report['review_events'])} events; no labels assigned", flush=True)


if __name__ == "__main__":
    main()
