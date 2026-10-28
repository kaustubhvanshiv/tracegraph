"""Recover native types for unresolved published UUIDs without changing Events.

Only exact publishing-host/UUID definitions supply metadata. Annotation paths,
PIDs and Event actions are never used to infer an object type or benign label.
The input graph is preserved; a separate enriched graph is produced locally.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

from fastavro import block_reader

from research.ml.data_prep.inspect_fivedirections import natural_key, uuid_text
from research.ml.data_prep.resolve_references import clean, reusable_files, validate_cached_index
from research.ml.node_benchmark.build_graphs import GraphStore, META_KINDS, OBJECT_KINDS, text_hash

DEFINITION_NAMES = {
    "Host", "Principal", "Subject", "FileObject", "IpcObject",
    "RegistryKeyObject", "NetFlowObject", "MemoryObject", "SrcSinkObject",
}
NATIVE_TABLES = ("events", "event_sources", "edges", "nodes", "case_nodes",
                 "paths", "node_paths", "metadata_links", "published_nodes")


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def definition_prefixes(schema, uuids):
    """Validate CDM's fixed UUID layout before filtering single-record blocks.

    A fixed UUID is stored as 16 unchanged bytes after the datum union tag.
    Multi-record blocks use a conservative byte-presence filter instead.
    A byte match only selects a block for normal Avro decoding, never evidence.
    """
    if schema["fields"][0]["name"] != "datum":
        raise ValueError("Expected the native datum union as the first field")
    union = schema["fields"][0]["type"]
    if not isinstance(union, list):
        raise ValueError("Expected a native CDM datum union")
    named = {}

    def names(value):
        if isinstance(value, dict):
            if value.get("type") in ("record", "fixed", "enum"):
                named[value["name"]] = value
            for child in value.values():
                names(child)
        elif isinstance(value, list):
            for child in value:
                names(child)

    names(schema)
    tags = set()
    seen = set()
    for index, branch in enumerate(union):
        if not isinstance(branch, dict) or branch.get("name", "").split(".")[-1] not in DEFINITION_NAMES:
            continue
        fields = branch["fields"]
        if not fields or fields[0]["name"] != "uuid":
            raise ValueError("Definition UUID must be its first field")
        uuid_schema = fields[0]["type"]
        if isinstance(uuid_schema, str):
            uuid_schema = named.get(uuid_schema, {})
        if uuid_schema.get("type") != "fixed" or uuid_schema.get("size") != 16 or index >= 64:
            raise ValueError("Unsupported native UUID or union-tag layout")
        tags.add(index * 2)  # Avro nonnegative union index, zigzag encoded.
        seen.add(branch["name"].split(".")[-1])
    if not {"FileObject", "Subject"} <= seen:
        raise ValueError("Missing expected native definition branches")
    return {bytes([tag]) + uid for tag in tags for uid in uuids}


def scan_archive(path, targets, expected_records=None, progress=None):
    """Read the entire gzip/Avro stream; decode candidate blocks exactly."""
    wanted = {(host, uid) for host, uid in targets}
    binary = {bytes.fromhex(uid) for _, uid in wanted}
    if any(len(uid) != 16 for uid in binary):
        raise ValueError("Only native 16-byte UUIDs are supported")
    result = {"filename": path.name, "records": 0, "blocks": 0,
              "candidate_blocks": 0, "decoded_records": 0, "definitions": []}
    with gzip.open(path, "rb") as stream:
        avro = block_reader(stream)
        prefixes = definition_prefixes(avro.writer_schema, binary)
        result["writer_schema_sha256"] = hashlib.sha256(
            json.dumps(avro.writer_schema, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        next_progress = 2_000_000
        for block in avro:
            count = block.num_records
            data = block.bytes_.getvalue()
            candidate = data[:17] in prefixes if count == 1 else any(uid in data for uid in binary)
            result["blocks"] += 1
            if candidate:
                result["candidate_blocks"] += 1
                decoded = 0
                for offset, raw in enumerate(block, 1):
                    decoded += 1
                    kind, datum = raw["type"], raw["datum"]
                    key = (uuid_text(raw.get("hostId")), uuid_text(datum.get("uuid")))
                    if kind in META_KINDS | OBJECT_KINDS and key in wanted:
                        payload = clean(raw)
                        result["definitions"].append({
                            "host_uuid": key[0], "uuid": key[1], "kind": kind,
                            "subtype": datum.get("type"), "filename": path.name,
                            "record_index": result["records"] + offset,
                            "raw_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True,
                                separators=(",", ":")).encode()).hexdigest(),
                            "datum": payload["datum"],
                        })
                if decoded != count:
                    raise ValueError("Avro block count disagrees with decoded records")
                result["decoded_records"] += decoded
            result["records"] += count
            if progress and result["records"] >= next_progress:
                progress({k: result[k] for k in ("filename", "records", "decoded_records")})
                next_progress = result["records"] + 2_000_000
        # fastavro treats EOFError as Avro exhaustion; force gzip footer/CRC
        # validation separately so a missing gzip trailer cannot look complete.
        if stream.read(1):
            raise ValueError("Unexpected trailing bytes after Avro exhaustion")
    if expected_records is not None and result["records"] != expected_records:
        raise ValueError("Complete Avro block record count differs from the source audit")
    result["complete_stream_read"] = True
    return result


def apply_definitions(db, targets, definitions):
    """Resolve retained type fields; preserve all conflicting evidence."""
    db.execute("CREATE TABLE metadata_recovery_evidence(node_id INTEGER,kind TEXT,subtype TEXT,"
               "source_file TEXT,record_index INTEGER,raw_sha256 TEXT,datum_json TEXT,"
               "PRIMARY KEY(node_id,source_file,record_index))")
    store = GraphStore(db, initialize=False)
    outcomes = []
    for target in targets:
        hits = [r for r in definitions if (r["host_uuid"], r["uuid"]) == (target["host_uuid"], target["uuid"])]
        signatures = {(r["kind"], r["subtype"]) for r in hits}
        for hit in hits:
            db.execute("INSERT INTO metadata_recovery_evidence VALUES (?,?,?,?,?,?,?)", (
                target["node_id"], hit["kind"], hit["subtype"], hit["filename"],
                hit["record_index"], hit["raw_sha256"], json.dumps(hit["datum"], sort_keys=True)))
        if len(signatures) > 1:
            store.apply_metadata(target["node_id"], None, {}, "recovery-conflict", conflict=True)
            status = "conflicting_native_types"
        elif hits:
            first = hits[0]
            store.apply_metadata(target["node_id"], first["kind"], first["datum"],
                                 first["filename"], first["record_index"])
            status = "typed_uuid_match" if first["kind"] == target["expected_kind"] else "native_type_mismatch"
        else:
            status = "no_native_definition_in_reviewed_local_sources"
        outcomes.append({**target, "outcome": status, "definition_records": len(hits),
            "native_type_signatures": [list(s) for s in sorted(signatures, key=str)],
            "evidence": [{k: r[k] for k in ("filename", "record_index", "raw_sha256")} for r in hits]})
    db.execute("DELETE FROM reference_matches")
    store.match_references()
    store.finish_context()
    return outcomes


def recover(source, graph, pilot_report, reference_audit, output):
    source, graph, output = source.resolve(), graph.resolve(), output.resolve()
    if output.exists() or source == output or source in output.parents or output in graph.parents:
        raise ValueError("Use a fresh output directory outside the source and input graph")
    pilot = json.loads(pilot_report.read_text(encoding="utf-8"))
    if pilot["status"] != "complete_pilot_not_training_ready" or file_hash(graph) != pilot["database_sha256"]:
        raise ValueError("Input graph must match the completed pinned pilot")
    paths = list(source.rglob("*.gz"))
    files = reusable_files(paths, reference_audit)
    if len({p.name for p in paths}) != len(paths):
        raise ValueError("Ambiguous source filenames")
    paths = {p.name: p for p in paths}
    with closing(sqlite3.connect(graph.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        targets = [dict(r) for r in db.execute("SELECT r.case_id,n.id AS node_id,n.host_uuid,n.uuid,"
            "p.expected_kind FROM reference_matches r JOIN nodes n ON n.id=r.node_id "
            "JOIN published_nodes p ON p.case_id=r.case_id AND p.uuid=r.uuid "
            "WHERE r.status='uuid_present_unresolved' ORDER BY r.case_id,n.uuid")]
        native_before = {t: db.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in NATIVE_TABLES}
    if not targets:
        raise ValueError("No unresolved published references in this pilot")
    with closing(sqlite3.connect((reference_audit/"references.sqlite").resolve().as_uri()+"?mode=ro", uri=True)) as refs:
        validate_cached_index(refs, files)
        for target in targets:
            if refs.execute("SELECT 1 FROM entities WHERE host=? AND uuid=? LIMIT 1",
                            (target["host_uuid"], target["uuid"])).fetchone():
                raise ValueError("Target has an unused cached Subject/Principal/Host definition; review cache join first")
    reused = {f["filename"] for f in pilot["scans"]}
    expected = {f["filename"]: f for f in files}
    for scan in pilot["scans"]:
        current = expected[scan["filename"]]
        if not scan["complete_scan"] or any(scan[k] != current[k] for k in ("records", "compressed_bytes", "modified_time_ns")):
            raise ValueError("Pinned pilot scan does not match the complete source audit")
    # Prefixes identify the same native publishing-host streams used by the pilot.
    prefixes = {f['filename'].split('e5-official-')[0] for f in pilot['scans']}
    selected = [f for f in files if f["filename"] not in reused and any(f["filename"].startswith(p) for p in prefixes)]
    if shutil.disk_usage(output.parent).free < graph.stat().st_size + 2 * 2**30:
        raise ValueError("Insufficient room for a separate enriched graph and reserve")
    output.mkdir(parents=True)
    report = {"status": "scanning", "recovery_code_sha256_utf8_lf": text_hash(Path(__file__)),
        "input_graph_sha256": pilot["database_sha256"], "pilot_report_sha256_utf8_lf": text_hash(pilot_report),
        "reference_report_sha256_utf8_lf": text_hash(reference_audit/"reference_report.json"),
        "source_files_validated": len(files), "target_count": len(targets),
        "cached_definition_absence": "Complete validated Host/Principal/Subject index has no exact host/UUID definitions for these targets",
        "reused_complete_pilot_scans": pilot["scans"], "new_scans": [],
        "ready_for_training": False, "models_trained": False, "splits_created": False}
    save = lambda: (output/"manifest.json").write_bytes((json.dumps(report, indent=2)+"\n").encode())
    save()
    definitions = []
    try:
        for item in sorted(selected, key=lambda f: natural_key(f["filename"])):
            scan = scan_archive(paths[item["filename"]], [(t["host_uuid"], t["uuid"]) for t in targets],
                                item["records"], lambda x: print(json.dumps(x), flush=True))
            definitions.extend(scan.pop("definitions"))
            scan.update({k: item[k] for k in ("compressed_bytes", "modified_time_ns")})
            report["new_scans"].append(scan)
            save()
            print(json.dumps({"completed_file": item["filename"], "definition_records_so_far": len(definitions)}), flush=True)
        reusable_files(list(paths.values()), reference_audit)
        if any(r["kind"] in META_KINDS for r in definitions):
            raise ValueError("Fresh metadata contradicts the complete cached definition index")
        (output/"definitions.json").write_bytes((json.dumps(definitions, indent=2)+"\n").encode())
        report["definitions_sha256_utf8_lf"] = text_hash(output/"definitions.json")
        destination = output/"graph.sqlite"
        shutil.copyfile(graph, destination)
        with closing(sqlite3.connect(destination)) as db:
            with db:
                report["targets"] = apply_definitions(db, targets, definitions)
                native_after = {t: db.execute("SELECT COUNT(*) FROM " + t).fetchone()[0] for t in NATIVE_TABLES}
                if native_after != native_before:
                    raise ValueError("Metadata recovery altered native graph selection/counts")
                report["native_table_counts_unchanged"] = native_after
                report["reference_status_counts"] = dict(db.execute("SELECT status,COUNT(*) FROM reference_matches GROUP BY status"))
                report["node_metadata_status_counts"] = dict(db.execute("SELECT metadata_status,COUNT(*) FROM nodes GROUP BY metadata_status"))
                report["usable_event_relations"] = db.execute("SELECT COUNT(*) FROM usable_event_relations").fetchone()[0]
                report["process_context_counts"] = dict(db.execute("SELECT process_context_status,COUNT(*) FROM events GROUP BY process_context_status"))
                report["zero_node_labels"] = db.execute("SELECT COUNT(*) FROM node_reference_labels WHERE published_reference_label=0").fetchone()[0]
                if report["zero_node_labels"]:
                    raise ValueError("Unexpected fabricated benign node label")
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Enriched graph integrity check failed")
        if file_hash(graph) != report["input_graph_sha256"]:
            raise ValueError("The input graph changed during recovery")
        report.update(status="complete_metadata_review_not_training_ready", input_graph_unchanged=True,
            outcome_counts=dict(Counter(t["outcome"] for t in report["targets"])),
            database_bytes=destination.stat().st_size, database_sha256=file_hash(destination),
            new_records_streamed=sum(s["records"] for s in report["new_scans"]))
        save()
        return report
    except BaseException as error:
        report.update(status="incomplete_failed", error=str(error))
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "graph", "pilot-report", "reference-audit", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    report = recover(args.source, args.graph, args.pilot_report, args.reference_audit, args.output)
    print(json.dumps({k: report[k] for k in ("status", "target_count", "outcome_counts", "database_bytes")}), flush=True)


if __name__ == "__main__":
    main()
