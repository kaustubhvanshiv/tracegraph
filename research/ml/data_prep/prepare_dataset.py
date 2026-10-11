"""Prepare reviewed CDM events and refuse unsupported supervised splits.

Raw telemetry, entity index and prepared events stay in an ignored local run.
This is an offline research adapter, not a production ingestion registration.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from fastavro import reader

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from app.schemas.parser import ParsedEvent, ParseError
from app.schemas.security_event import SecurityEvent
from app.services.parser_registry import AdapterRegistry
from research.ml.data_prep.inspect_fivedirections import utc_nanos, uuid_text


def json_safe(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


class CDMReviewAdapter:
    source_type = "darpa_cdm"

    def parse(self, raw):
        try:
            datum = raw["datum"]
            if raw["type"] != "RECORD_EVENT" or not isinstance(datum["timestampNanos"], int):
                raise ValueError("Expected a timestamped CDM Event")
            event_id = uuid_text(datum["uuid"])
            if not event_id:
                raise ValueError("Missing Event UUID")
            # Preserve CDM semantics; OPEN alone does not establish a file object.
            return ParsedEvent(event_id=event_id, source_type=self.source_type,
                               timestamp_raw=utc_nanos(datum["timestampNanos"]),
                               event_type="cdm_event", action=datum["type"],
                               extra_fields={"cdm": json_safe(raw)})
        except (KeyError, TypeError, ValueError) as error:
            return ParseError(reason=str(error), raw_event=json_safe(raw))


def reviewed_label(annotation, raw):
    """Accept labels only with exact identity/time/action and reviewed evidence."""
    datum = raw["datum"]
    expected = (annotation["event_uuid"], annotation["host_uuid"],
                annotation["timestamp_nanos"], annotation["cdm_event_type"])
    actual = (uuid_text(datum.get("uuid")), uuid_text(raw.get("hostId")),
              datum.get("timestampNanos"), datum.get("type"))
    if actual != expected:
        raise ValueError("Annotation identity/time/action mismatch")
    label = annotation.get("label")
    if label is not None:
        if type(label) is not int or label not in (0, 1):
            raise ValueError("Label must be integer 0, 1, or null")
        if annotation.get("review_status") != "verified" or not annotation.get("evidence") or not annotation.get("group_id"):
            raise ValueError("Binary label requires verified evidence and a group ID")
        if label == 1 and not annotation.get("incident_id"):
            raise ValueError("Positive label requires an incident ID")
    return label


def make_splits(samples, context_nanos=0):
    """Chronological whole-group split; reject missing classes/overlapping context."""
    if context_nanos < 0:
        raise ValueError("Context window must be nonnegative")
    known = [s for s in samples if s["label"] is not None]
    incident_groups = {}
    for sample in known:
        incident = sample.get("incident_id")
        if sample["label"] == 1 and incident:
            incident_groups.setdefault(incident, set()).add(sample.get("group_id"))
    if any(len(ids) > 1 for ids in incident_groups.values()):
        return None, ["A positive incident is assigned to multiple split groups"]
    if len({s["event_uuid"] for s in samples}) != len(samples):
        return None, ["Duplicate sample identities"]
    groups = {}
    for sample in known:
        group = sample.get("group_id")
        if not group:
            return None, ["Labeled sample lacks group ID"]
        groups.setdefault(group, []).append(sample)
    if len(groups) < 3:
        return None, ["At least three independent labeled groups required", "Verified benign and attack samples required in every partition"]
    ordered = sorted(groups, key=lambda g: (min(s["timestamp_nanos"] for s in groups[g]), g))
    first = max(1, min(len(ordered) - 2, int(len(ordered) * .6)))
    second = max(first + 1, min(len(ordered) - 1, int(len(ordered) * .8)))
    partitions = {"train": ordered[:first], "validation": ordered[first:second], "test": ordered[second:]}
    splits = {name: sorted([s for g in ids for s in groups[g]], key=lambda s: (s["timestamp_nanos"], s["event_uuid"])) for name, ids in partitions.items()}
    reasons = []
    for name, rows in splits.items():
        if {s["label"] for s in rows} != {0, 1}:
            reasons.append(f"{name} lacks both verified classes")
    for left, right in (("train", "validation"), ("validation", "test")):
        if max(s["timestamp_nanos"] for s in splits[left]) >= min(s["timestamp_nanos"] for s in splits[right]) - context_nanos:
            reasons.append(f"{left}/{right} temporal or context overlap")
    return (None, reasons) if reasons else (splits, [])


def resolve_subject(db, subject_id):
    chain, seen = [], set()
    while subject_id and subject_id not in seen:
        seen.add(subject_id)
        row = db.execute("SELECT payload FROM entities WHERE uuid=?", (subject_id,)).fetchone()
        if row is None:
            return {"chain": chain, "unresolved_uuid": subject_id, "process_resolved": False}
        entity = json.loads(row[0])
        chain.append({"uuid": subject_id, "type": entity.get("type"), "cid": entity.get("cid")})
        if entity.get("type") == "SUBJECT_PROCESS":
            return {"chain": chain, "unresolved_uuid": None, "process_resolved": True}
        subject_id = entity.get("parentSubject")
    return {"chain": chain, "unresolved_uuid": subject_id, "process_resolved": False}


def prepare(source, annotations_path, output, limit, context_nanos=0, split_output=None):
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents:
        raise ValueError("Output must be outside the raw source")
    if output.exists():
        raise ValueError("Use a fresh output directory; previous results are preserved")
    if limit < 0:
        raise ValueError("Record limit must be nonnegative")
    if context_nanos < 0:
        raise ValueError("Context window must be nonnegative")
    split_directory = Path(split_output).resolve() if split_output is not None else output / "splits"
    if split_directory == source or source in split_directory.parents:
        raise ValueError("Split output must be outside raw source")
    if split_directory.exists() or split_directory == output or split_directory in output.parents:
        raise ValueError("Use a fresh, separate split directory")
    annotations = json.loads(annotations_path.read_text(encoding="utf-8"))["events"]
    wanted = {a["event_uuid"]: a for a in annotations}
    if len(wanted) != len(annotations):
        raise ValueError("Duplicate annotation identities")
    output.mkdir(parents=True)
    registry = AdapterRegistry()
    registry.register(CDMReviewAdapter())
    counts, matches, fingerprints, conflicts, files = Counter(), {}, {}, set(), []
    with closing(sqlite3.connect(output / "entities.sqlite")) as db:
        db.execute("CREATE TABLE entities(uuid TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        filenames = sorted({a["source_file"] for a in annotations})
        for filename in filenames:
            if Path(filename).name != filename or not filename.endswith(".gz"):
                raise ValueError("Annotation source_file must be a gzip basename")
            candidates = list(source.rglob(filename))
            if len(candidates) != 1:
                raise ValueError(f"Expected one source file: {filename}")
            path, count, complete = candidates[0], 0, True
            with gzip.open(path, "rb") as stream:
                for raw in reader(stream):
                    if limit and count >= limit:
                        complete = False
                        break
                    count += 1
                    counts[raw.get("type")] += 1
                    datum = raw.get("datum") or {}
                    uid = uuid_text(datum.get("uuid"))
                    if raw.get("type") == "RECORD_SUBJECT" and uid:
                        payload = json.dumps(json_safe(datum), sort_keys=True)
                        old = db.execute("SELECT payload FROM entities WHERE uuid=?", (uid,)).fetchone()
                        if old and old[0] != payload:
                            # Ambiguous entity definitions cannot supply process features.
                            db.execute("UPDATE entities SET payload=? WHERE uuid=?", ('{}', uid))
                        elif not old:
                            db.execute("INSERT INTO entities VALUES (?,?)", (uid, payload))
                    if raw.get("type") == "RECORD_EVENT" and uid in wanted:
                        annotation = wanted[uid]
                        if annotation["source_file"] != filename:
                            raise ValueError("Annotation file mismatch")
                        fingerprint = hashlib.sha256(json.dumps(json_safe(raw), sort_keys=True).encode()).hexdigest()
                        if uid in fingerprints and fingerprints[uid] != fingerprint:
                            conflicts.add(uid)
                        fingerprints[uid] = fingerprint
                        label = reviewed_label(annotation, raw)
                        parsed = registry.dispatch("darpa_cdm", raw)
                        if isinstance(parsed, ParseError):
                            raise ValueError(parsed.reason)
                        normalized = SecurityEvent(event_id=parsed.event_id, source_type=parsed.source_type,
                            timestamp=parsed.timestamp_raw, event_type=parsed.event_type, action=parsed.action,
                            raw_data=parsed.extra_fields)
                        matches[uid] = {**annotation, "label": label,
                            "subject_uuid": uuid_text(datum.get("subject")),
                            "record_index_1based": count, "security_event": normalized.model_dump(mode="json")}
                    if count % 250_000 == 0:
                        db.commit()
                        print(f"{filename}: {count:,} records", flush=True)
            files.append({"filename": filename, "records": count, "complete_scan": complete,
                          "compressed_bytes": path.stat().st_size, "modified_time_ns": path.stat().st_mtime_ns})
        samples = []
        for uid, sample in sorted(matches.items()):
            if uid not in conflicts:
                sample["subject_resolution"] = resolve_subject(db, sample["subject_uuid"])
                samples.append(sample)
        db.commit()
    splits, reasons = make_splits(samples, context_nanos)
    missing = sorted(set(wanted) - set(matches))
    if missing or conflicts:
        splits = None
        reasons.append("Missing or conflicting reviewed events")
    # Indexed references are audit metadata only; no process features or graphs
    # are constructed until event-time-valid entity semantics are established.
    with (output / "review_events.jsonl").open("w", encoding="utf-8") as stream:
        for sample in samples:
            stream.write(json.dumps(sample) + "\n")
    if splits:
        directory = split_directory
        directory.mkdir(parents=True)
        for name, rows in splits.items():
            (directory / f"{name}.json").write_text(json.dumps([r["event_uuid"] for r in rows], indent=2), encoding="utf-8")
    manifest = {"status": "split_ready" if splits else "blocked_for_training", "selection": "annotation-listed events only; not representative sampling",
        "files": files, "record_type_counts": dict(counts), "annotation_sha256": hashlib.sha256(annotations_path.read_bytes()).hexdigest(),
        "sample_count": len(samples), "label_counts": dict(Counter(str(s["label"]) for s in samples)),
        "missing_event_uuids": missing, "conflicting_event_uuids": sorted(conflicts),
        "resolved_process_count": sum(s["subject_resolution"]["process_resolved"] for s in samples),
        "context_nanos": context_nanos, "blocking_reasons": reasons,
        "feature_status": "no model features; references for audit only"}
    manifest["split_output"] = str(split_directory) if splits else None
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--records-per-file", type=int, default=2_000_000)
    parser.add_argument("--context-nanos", type=int, default=0)
    parser.add_argument("--split-output", type=Path,
                        default=Path(__file__).resolve().parents[3] / "data/ml/splits",
                        help="Fresh directory for validated split IDs (created only when gates pass)")
    args = parser.parse_args()
    manifest = prepare(args.source, args.annotations, args.output, args.records_per_file, args.context_nanos, args.split_output)
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["status"] == "split_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
