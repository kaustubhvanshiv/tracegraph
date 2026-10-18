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
from app.schemas.parser import ParseError
from app.schemas.security_event import SecurityEvent
from app.services.parser_registry import AdapterRegistry
from research.ml.data_prep.inspect_fivedirections import uuid_text
from research.ml.data_prep.cdm_adapter import CDMReviewAdapter, EntityResolver, ENTITY_KINDS, json_safe
from research.ml.data_prep.resolve_references import reusable_files, validate_cached_index


def index_entity(db, host, uid, kind, payload):
    old = db.execute("SELECT kind,payload FROM entities WHERE host=? AND uuid=?", (host, uid)).fetchone()
    if old and old != (kind, payload):
        db.execute("UPDATE entities SET conflict=1 WHERE host=? AND uuid=?", (host, uid))
    elif not old:
        db.execute("INSERT INTO entities(host,uuid,kind,payload) VALUES (?,?,?,?)", (host, uid, kind, payload))


def import_reference_audit(db, source, previous):
    """Seed metadata only; labels and selected events still come from annotations.

    Raw metadata remain local. Future-starting processes are still rejected by
    EntityResolver, and definitions are never borrowed from another host.
    """
    paths = list(source.rglob("*.gz"))
    if len({p.name for p in paths}) != len(paths):
        raise ValueError("Source contains duplicate basenames")
    previous = Path(previous).resolve()
    files = reusable_files(paths, previous)
    count = 0
    with closing(sqlite3.connect((previous / "references.sqlite").as_uri() + "?mode=ro", uri=True)) as reference:
        validate_cached_index(reference, files)
        for uid, kind, payload, host in reference.execute("SELECT uuid,kind,payload,host FROM entities"):
            if uid and host:
                index_entity(db, host, uid, kind, payload)
                count += 1
    return {"files": [item["filename"] for item in files], "definitions_imported": count,
            "report_sha256": hashlib.sha256((previous / "reference_report.json").read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
            "report_hash_format": "SHA-256 of UTF-8 text with LF newlines"}


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
    if type(annotation.get("split_eligible", True)) is not bool:
        raise ValueError("split_eligible must be a boolean")
    if annotation.get("split_eligible") is False and not annotation.get("split_exclusion_reason"):
        raise ValueError("Excluded sample requires a split exclusion reason")
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
    # A reviewed action label does not repair uncertain event chronology.
    # Keep such samples in the review output, outside training/evaluation.
    known = [s for s in known if s.get("split_eligible", True) is True]
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


def prepare(source, annotations_path, output, limit, context_nanos=0, split_output=None, reference_audit=None):
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
    annotation_text = annotations_path.read_text(encoding="utf-8")
    annotations = json.loads(annotation_text)["events"]
    wanted = {a["event_uuid"]: a for a in annotations}
    if len(wanted) != len(annotations):
        raise ValueError("Duplicate annotation identities")
    output.mkdir(parents=True)
    registry = AdapterRegistry()
    counts, matches, fingerprints, conflicts, files = Counter(), {}, {}, set(), []
    with closing(sqlite3.connect(output / "entities.sqlite")) as db:
        db.execute("CREATE TABLE entities(host TEXT,uuid TEXT,kind TEXT,payload TEXT,conflict INTEGER DEFAULT 0,PRIMARY KEY(host,uuid))")
        references = import_reference_audit(db, source, reference_audit) if reference_audit else None
        resolver = EntityResolver(db)
        registry.register(CDMReviewAdapter(resolver))
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
                    host = uuid_text(raw.get("hostId"))
                    if raw.get("type") in ENTITY_KINDS and uid and host:
                        payload = json.dumps(json_safe(datum), sort_keys=True)
                        index_entity(db, host, uid, raw.get("type"), payload)
                    if raw.get("type") == "RECORD_EVENT" and uid in wanted:
                        annotation = wanted[uid]
                        if annotation["source_file"] != filename:
                            raise ValueError("Annotation file mismatch")
                        fingerprint = hashlib.sha256(json.dumps(json_safe(raw), sort_keys=True).encode()).hexdigest()
                        if uid in fingerprints and fingerprints[uid] != fingerprint:
                            conflicts.add(uid)
                        fingerprints[uid] = fingerprint
                        label = reviewed_label(annotation, raw)
                        matches[uid] = {**annotation, "label": label,
                            "subject_uuid": uuid_text(datum.get("subject")),
                            "record_index_1based": count, "_raw": raw}
                    if count % 250_000 == 0:
                        db.commit()
                        print(f"{filename}: {count:,} records", flush=True)
            files.append({"filename": filename, "records": count, "complete_scan": complete,
                          "compressed_bytes": path.stat().st_size, "modified_time_ns": path.stat().st_mtime_ns})
        samples = []
        for uid, sample in sorted(matches.items()):
            if uid not in conflicts:
                parsed = registry.dispatch("darpa_cdm", sample.pop("_raw"))
                if isinstance(parsed, ParseError):
                    raise ValueError(parsed.reason)
                values = parsed.model_dump(exclude={"timestamp_raw", "extra_fields"})
                normalized = SecurityEvent(**values, timestamp=parsed.timestamp_raw, raw_data=parsed.extra_fields)
                sample["security_event"] = normalized.model_dump(mode="json")
                sample["subject_resolution"] = parsed.extra_fields["subject_resolution"]
                samples.append(sample)
        db.commit()
    splits, reasons = make_splits(samples, context_nanos)
    missing = sorted(set(wanted) - set(matches))
    if missing or conflicts:
        splits = None
        reasons.append("Missing or conflicting reviewed events")
    # Canonical event fields are evidence-grounded; no ML feature vectors or
    # graphs are constructed here. Missing/conflicting definitions stay unknown.
    with (output / "review_events.jsonl").open("w", encoding="utf-8") as stream:
        for sample in samples:
            stream.write(json.dumps(sample) + "\n")
    if splits:
        directory = split_directory
        directory.mkdir(parents=True)
        for name, rows in splits.items():
            (directory / f"{name}.json").write_text(json.dumps([r["event_uuid"] for r in rows], indent=2), encoding="utf-8")
    manifest = {"status": "split_ready" if splits else "blocked_for_training", "selection": "annotation-listed events only; not representative sampling",
        "files": files, "record_type_counts": dict(counts), "annotation_sha256": hashlib.sha256(annotation_text.encode("utf-8")).hexdigest(),
        "annotation_hash_format": "SHA-256 of UTF-8 text with LF newlines",
        "sample_count": len(samples), "label_counts": dict(Counter(str(s["label"]) for s in samples)),
        "label_group_counts": {str(label): len({s.get("group_id") for s in samples
                                              if s["label"] == label and s.get("group_id")}) for label in (0, 1)},
        "eligible_label_counts": dict(Counter(str(s["label"]) for s in samples
                                             if s["label"] is not None and s.get("split_eligible", True) is True)),
        "eligible_label_group_counts": {str(label): len({s.get("group_id") for s in samples
                    if s["label"] == label and s.get("group_id") and s.get("split_eligible", True) is True}) for label in (0, 1)},
        "split_excluded_events": [{"event_uuid": s["event_uuid"], "reason": s["split_exclusion_reason"]}
                                  for s in samples if s.get("split_eligible") is False],
        "positive_incident_count": len({s.get("incident_id") for s in samples
                                        if s["label"] == 1 and s.get("incident_id")}),
        "missing_event_uuids": missing, "conflicting_event_uuids": sorted(conflicts),
        "resolved_process_count": sum(s["subject_resolution"]["process_resolved"] for s in samples),
        "context_nanos": context_nanos, "blocking_reasons": reasons,
        "feature_status": "canonical event fields only; no model vectors or graphs",
        "semantic_mapping_version": 1,
        "reference_audit": references,
        "normalized_event_type_counts": dict(Counter(s["security_event"]["event_type"] for s in samples)),
        "normalized_field_counts": {field: sum(s["security_event"].get(field) is not None for s in samples)
                                    for field in ("process", "file", "user", "source_host", "source_ip", "destination_ip")}}
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
    parser.add_argument("--reference-audit", type=Path,
                        help="Completed reference audit to supply host-scoped metadata from other segments")
    parser.add_argument("--split-output", type=Path,
                        default=Path(__file__).resolve().parents[3] / "data/ml/splits",
                        help="Fresh directory for validated split IDs (created only when gates pass)")
    args = parser.parse_args()
    manifest = prepare(args.source, args.annotations, args.output, args.records_per_file, args.context_nanos, args.split_output, args.reference_audit)
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["status"] == "split_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
