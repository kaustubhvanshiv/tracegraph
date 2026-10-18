"""Search documented activities without converting matches into attack labels.

Full scans retain complete Host/Principal/Subject definitions locally.
Candidate events must be reread in full and
reviewed before entering review_annotations.json. No negative labels are inferred
from uncovered windows or a lack of indicator matches.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from fastavro import reader

from research.ml.data_prep.audit_attack_coverage import time_nanos
from research.ml.data_prep.inspect_fivedirections import natural_key, utc_nanos, uuid_text
from research.ml.data_prep.resolve_references import clean


def compiled_activities(configuration):
    result, seen = [], set()
    for activity in configuration["activities"]:
        identifier = activity["activity_id"]
        if identifier in seen:
            raise ValueError("Duplicate activity ID")
        seen.add(identifier)
        start, end = time_nanos(activity["start_utc"]), time_nanos(activity["end_utc"])
        if start >= end or not activity.get("host_uuid") or not activity.get("evidence"):
            raise ValueError("Activity requires a host, evidence and an increasing time window")
        result.append({**activity, "start": start, "end": end,
                       "pattern": re.compile(activity["search_regex"], re.IGNORECASE)})
    return result


def audit(source, configuration_path, output, file_pattern="*.gz", candidate_cap=30):
    source, output = source.resolve(), output.resolve()
    if output == source or source in output.parents or output.exists():
        raise ValueError("Use a fresh output directory outside the raw source")
    if candidate_cap < 1 or Path(file_pattern).name != file_pattern or not file_pattern.endswith(".gz"):
        raise ValueError("Use a positive candidate cap and a gzip basename pattern")
    paths = sorted(source.rglob(file_pattern), key=lambda p: natural_key(Path(p.name.replace(".bin.gz", ".bin.0.gz"))))
    if not paths or len({p.name for p in paths}) != len(paths):
        raise ValueError("Expected source files with unique basenames")
    configuration_text = configuration_path.read_text(encoding="utf-8")
    configuration = json.loads(configuration_text)
    activities = compiled_activities(configuration)
    by_host = {}
    for item in activities:
        by_host.setdefault(item["host_uuid"], []).append(item)
    matches = {item["activity_id"]: {"window_event_count": 0, "subject_match_count": 0,
               "path_match_count": 0, "known_subject_event_count": 0,
               "subject_candidates": [], "event_candidates": []} for item in activities}
    known_subjects = {item["activity_id"]: set() for item in activities}
    output.mkdir(parents=True)
    files = []
    with closing(sqlite3.connect(output / "references.sqlite")) as db:
        db.execute("CREATE TABLE entities(uuid TEXT,kind TEXT,payload TEXT,filename TEXT,record_index INTEGER,host TEXT)")
        for path in paths:
            before = path.stat()
            with gzip.open(path, "rb") as stream:
                records = reader(stream)
                types, host_ranges = Counter(), {}
                count = 0
                for raw in records:
                    count += 1
                    kind, datum = raw["type"], raw.get("datum") or {}
                    types[kind] += 1
                    host, uid = uuid_text(raw.get("hostId")), uuid_text(datum.get("uuid"))
                    if kind in {"RECORD_SUBJECT", "RECORD_HOST", "RECORD_PRINCIPAL"} and uid:
                        db.execute("INSERT INTO entities VALUES (?,?,?,?,?,?)", (uid, kind,
                            json.dumps(clean(datum), sort_keys=True), path.name, count, host))
                    timestamp = datum.get("timestampNanos") if kind == "RECORD_EVENT" else datum.get("startTimestampNanos")
                    if kind == "RECORD_EVENT" and isinstance(timestamp, int):
                        limits = host_ranges.setdefault(host, [timestamp, timestamp])
                        limits[0], limits[1] = min(limits[0], timestamp), max(limits[1], timestamp)
                    for activity in by_host.get(host, ()):
                        if not isinstance(timestamp, int) or not activity["start"] <= timestamp < activity["end"]:
                            continue
                        entry = matches[activity["activity_id"]]
                        if kind == "RECORD_SUBJECT" and activity["pattern"].search(datum.get("cmdLine") or ""):
                            entry["subject_match_count"] += 1
                            known_subjects[activity["activity_id"]].add(uid)
                            if len(entry["subject_candidates"]) < candidate_cap:
                                entry["subject_candidates"].append({"source_file": path.name, "record_index_1based": count,
                                    "host_uuid": host, "subject_uuid": uid, "start_utc": utc_nanos(timestamp),
                                    "subject_type": datum.get("type"), "cid": datum.get("cid"), "label": None})
                        elif kind == "RECORD_EVENT":
                            entry["window_event_count"] += 1
                            fields = [] if activity.get("subject_only") else [field
                                      for field in ("predicateObjectPath", "predicateObject2Path")
                                      if activity["pattern"].search(datum.get(field) or "")]
                            actors = known_subjects[activity["activity_id"]]
                            subject_match = bool(actors) and any(uuid_text(datum.get(field)) in actors
                                                for field in ("subject", "predicateObject", "predicateObject2"))
                            entry["path_match_count"] += bool(fields)
                            entry["known_subject_event_count"] += bool(subject_match)
                            if (fields or subject_match) and len(entry["event_candidates"]) < candidate_cap:
                                entry["event_candidates"].append({"source_file": path.name, "record_index_1based": count,
                                    "event_uuid": uid, "host_uuid": host, "timestamp_nanos": timestamp,
                                    "timestamp_utc": utc_nanos(timestamp), "cdm_event_type": datum.get("type"),
                                    "subject_uuid": uuid_text(datum.get("subject")), "matched_path_fields": fields,
                                    "already_seen_subject_match": subject_match, "label": None})
                    if count % 1_000_000 == 0:
                        db.commit()
                        print(f"{path.name}: {count:,} records", flush=True)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError(f"Source changed while scanning: {path.name}")
            db.commit()
            all_ranges = list(host_ranges.values())
            files.append({"filename": path.name, "records": count, "complete_scan": True,
                "compressed_bytes": after.st_size, "modified_time_ns": after.st_mtime_ns,
                "record_type_counts": dict(types),
                "min_event_utc": utc_nanos(min(r[0] for r in all_ranges)) if all_ranges else None,
                "max_event_utc": utc_nanos(max(r[1] for r in all_ranges)) if all_ranges else None,
                "host_event_ranges": {h: {"min_utc": utc_nanos(r[0]), "max_utc": utc_nanos(r[1])} for h, r in host_ranges.items()}})
            (output / "scan_progress.json").write_text(json.dumps(files, indent=2), encoding="utf-8")
        db.execute("CREATE INDEX entity_host_uuid ON entities(host,uuid)")
        db.commit()
    report = {"files": files, "file_pattern": file_pattern, "all_files_fully_scanned": True,
              "activity_configuration_sha256": hashlib.sha256(configuration_text.encode("utf-8")).hexdigest(),
              "activity_matches": matches, "labels_assigned": 0, "review_events": [],
              "scope": "Full record/time scan; complete identity metadata retained locally; candidate string search covers Subject cmdLine and Event paths only",
              "candidate_caveat": "Known-subject event matching sees only preceding definitions; zero matches does not prove absence. All candidates need full-record reread and source review."}
    (output / "reference_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--activities", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--file-pattern", default="*.gz")
    args = parser.parse_args()
    audit(args.source, args.activities, args.output, args.file_pattern)


if __name__ == "__main__":
    main()
