"""Recover native object types for a frozen, annotation-independent pilot universe.

Starts from the original graph, never the reference-targeted repair. Every node
receives the same source search; references are refreshed only after recovery.
This remains a case-conditioned offline preparation artifact, not training data.
"""
from __future__ import annotations

import argparse
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
from research.ml.node_benchmark.build_graphs import GraphStore, OBJECT_KINDS, text_hash
from research.ml.node_benchmark.recover_metadata import definition_prefixes, file_hash, NATIVE_TABLES

SCOPE = "all_frozen_graph_nodes_without_reference_join"
OBJECT_NAMES = {"FileObject", "IpcObject", "RegistryKeyObject", "NetFlowObject", "MemoryObject", "SrcSinkObject"}


def freeze_universe(db, output=None):
    """Hash identities only; never consult annotations, types or repair status."""
    digest, count, targets = hashlib.sha256(), 0, {}
    stream = output.open("wb") if output else None
    try:
        for node_id, host, uid in db.execute("SELECT id,host_uuid,uuid FROM nodes ORDER BY host_uuid,uuid"):
            if len(bytes.fromhex(uid)) != 16:
                raise ValueError("Invalid native UUID in frozen universe")
            line = (json.dumps([host, uid], separators=(",", ":"))+"\n").encode()
            digest.update(line)
            if stream:
                stream.write(line)
            targets[(host, uid)] = node_id
            count += 1
    finally:
        if stream:
            stream.close()
    return targets, digest.hexdigest(), count


def create_spool(db):
    db.execute("CREATE TABLE uniform_object_definitions(node_id INTEGER PRIMARY KEY,kind TEXT,subtype TEXT,"
        "source_file TEXT,record_index INTEGER,raw_sha256 TEXT,definition_records INTEGER,conflict INTEGER)")


def store_batch(db, batch):
    db.executemany("INSERT INTO uniform_object_definitions VALUES (?,?,?,?,?,?,1,0) "
        "ON CONFLICT(node_id) DO UPDATE SET definition_records=definition_records+1,conflict=CASE "
        "WHEN kind<>excluded.kind OR subtype IS NOT excluded.subtype THEN 1 ELSE conflict END", batch)


def scan_objects(path, targets, db, expected_records, progress=None):
    """Bound memory by spooling definitions; skip decoding unrelated single records."""
    binary = {bytes.fromhex(uid) for _, uid in targets}
    result = dict(filename=path.name, records=0, blocks=0, decoded_records=0, matching_object_definitions=0)
    batch = []
    with gzip.open(path, "rb") as stream:
        avro = block_reader(stream)
        # Validate the native fixed-UUID layout without constructing millions of
        # tag/UUID prefix combinations. A small tag set and one UUID set suffice.
        definition_prefixes(avro.writer_schema, {b"\0"*16})
        branches = avro.writer_schema["fields"][0]["type"]
        tags = {i*2 for i, b in enumerate(branches) if isinstance(b, dict)
                and b.get("name", "").split(".")[-1] in OBJECT_NAMES}
        result["writer_schema_sha256"] = hashlib.sha256(json.dumps(avro.writer_schema,sort_keys=True,separators=(",", ":")).encode()).hexdigest()
        next_progress = 2_000_000
        for block in avro:
            data, count = block.bytes_.getvalue(), block.num_records
            # Multi-record blocks are decoded entirely: scanning for hundreds
            # of thousands of byte patterns would be slower and unnecessary.
            candidate = count != 1 or (data and data[0] in tags and data[1:17] in binary)
            result["blocks"] += 1
            if candidate:
                decoded = 0
                for offset, raw in enumerate(block, 1):
                    decoded += 1
                    if raw["type"] not in OBJECT_KINDS:
                        continue
                    key = (uuid_text(raw.get("hostId")), uuid_text(raw["datum"].get("uuid")))
                    node_id = targets.get(key)
                    if node_id is None:
                        continue
                    fingerprint = hashlib.sha256(json.dumps(clean(raw),sort_keys=True,separators=(",", ":")).encode()).hexdigest()
                    batch.append((node_id, raw["type"], raw["datum"].get("type"), path.name,
                                  result["records"]+offset, fingerprint))
                    result["matching_object_definitions"] += 1
                    if len(batch) >= 2000:
                        store_batch(db,batch); batch.clear()
                if decoded != count:
                    raise ValueError("Decoded Avro block count mismatch")
                result["decoded_records"] += decoded
            result["records"] += count
            if result["records"] >= next_progress:
                store_batch(db,batch); batch.clear(); db.commit()
                if progress:
                    progress({k:result[k] for k in ("filename","records","matching_object_definitions")})
                next_progress = result["records"]+2_000_000
        if stream.read(1):
            raise ValueError("Unexpected trailing Avro bytes")
    store_batch(db,batch)
    if result["records"] != expected_records:
        raise ValueError("Complete stream record total differs from the audited source")
    db.commit()
    result["complete_stream_read"] = True
    return result


def apply_types(db):
    store = GraphStore(db,initialize=False)
    resolved = conflicts = 0
    for row in db.execute("SELECT d.node_id,d.kind,d.subtype,d.source_file,d.record_index,d.conflict,"
        "n.kind,n.subtype,n.metadata_status FROM uniform_object_definitions d JOIN nodes n ON n.id=d.node_id").fetchall():
        node_id, kind, subtype, source, index, conflict, old_kind, old_subtype, old_status = row
        conflict = bool(conflict) or old_status == "conflicting" or (
            old_kind is not None and (old_kind,old_subtype) != (kind,subtype))
        if conflict:
            store.apply_metadata(node_id,None,{},"uniform-native-conflict",conflict=True)
            conflicts += 1
        elif old_status != "resolved":
            store.apply_metadata(node_id,kind,{"type":subtype},source,index)
            resolved += 1
    db.commit()
    # Reference membership has no role in universe selection or the scan above.
    db.execute("DELETE FROM reference_matches")
    store.match_references()
    store.finish_context()
    db.commit()
    return {"newly_resolved_nodes":resolved,"conflicting_object_nodes":conflicts}


def recover(source, graph, pilot_report, reference_audit, output, max_gib=4):
    source, graph, output = source.resolve(), graph.resolve(), output.resolve()
    if output.exists() or output == source or source in output.parents or output in graph.parents:
        raise ValueError("Use a fresh output directory outside the source and input graph")
    pilot = json.loads(pilot_report.read_text(encoding="utf-8"))
    if pilot["status"] != "complete_pilot_not_training_ready" or file_hash(graph) != pilot["database_sha256"]:
        raise ValueError("Use the pinned original pilot graph, not the targeted repair")
    paths = list(source.rglob("*.gz"))
    files = reusable_files(paths,reference_audit)
    if len({p.name for p in paths}) != len(paths) or {p.name for p in paths} != {f["filename"] for f in files}:
        raise ValueError("Raw file inventory differs from the audited snapshot")
    paths = {p.name:p for p in paths}
    expected = {f["filename"]:f for f in files}
    for scan in pilot["scans"]:
        item = expected[scan["filename"]]
        if not scan["complete_scan"] or any(scan[k]!=item[k] for k in ("records","compressed_bytes","modified_time_ns")):
            raise ValueError("Cached complete pilot scan provenance mismatch")
    prefixes = {f["filename"].split("e5-official-")[0] for f in pilot["scans"]}
    reused = {f["filename"] for f in pilot["scans"]}
    selected = [f for f in files if f["filename"] not in reused and any(f["filename"].startswith(p) for p in prefixes)]
    with closing(sqlite3.connect((reference_audit/"references.sqlite").resolve().as_uri()+"?mode=ro",uri=True)) as refs:
        validate_cached_index(refs,files)
    budget = int(max_gib*2**30)
    if budget < graph.stat().st_size or shutil.disk_usage(output.parent).free < budget+512*2**20:
        raise ValueError("Insufficient room for the bounded graph and reserve")
    output.mkdir(parents=True)
    report = dict(status="freezing",scope=SCOPE,input_graph_sha256=pilot["database_sha256"],
        pilot_report_sha256_utf8_lf=text_hash(pilot_report),recovery_code_sha256_utf8_lf=text_hash(Path(__file__)),
        reference_report_sha256_utf8_lf=text_hash(reference_audit/"reference_report.json"),
        source_files_validated=len(files),reused_complete_pilot_scans=pilot["scans"],new_scans=[],
        storage_budget_bytes=budget,models_trained=False,splits_created=False,ready_for_training=False,
        label_selection_used=False,metadata_availability_claim="offline native types only; not online availability proof")
    save = lambda: (output/"manifest.json").write_bytes((json.dumps(report,indent=2)+"\n").encode())
    save()
    destination = output/"graph.sqlite"
    shutil.copyfile(graph,destination)
    try:
        with closing(sqlite3.connect(destination)) as db:
            db.execute("PRAGMA max_page_count="+str(budget//4096))
            db.execute("PRAGMA cache_size=-65536")
            targets,digest,count = freeze_universe(db,output/"universe.jsonl")
            report.update(universe_sha256=digest,universe_count=count,universe_frozen_before_reference_join=True,
                target_count=count,status="scanning")
            before = {t:db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in NATIVE_TABLES}
            report["original_metadata_status_counts"] = dict(db.execute("SELECT metadata_status,COUNT(*) FROM nodes GROUP BY metadata_status"))
            create_spool(db);db.commit();save()
            for item in sorted(selected,key=lambda f:natural_key(f["filename"])):
                scan = scan_objects(paths[item["filename"]],targets,db,item["records"],
                                    lambda x:print(json.dumps(x),flush=True))
                scan.update({k:item[k] for k in ("compressed_bytes","modified_time_ns")})
                report["new_scans"].append(scan);save()
                print(json.dumps({"completed_file":item["filename"],"matching_objects":scan["matching_object_definitions"]}),flush=True)
            reusable_files(list(paths.values()),reference_audit)
            report.update(apply_types(db))
            after = {t:db.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in NATIVE_TABLES}
            if before != after or freeze_universe(db)[1:] != (digest,count):
                raise ValueError("Uniform recovery changed the frozen graph universe/selection")
            report["native_table_counts_unchanged"] = after
            report["node_metadata_status_counts"] = dict(db.execute("SELECT metadata_status,COUNT(*) FROM nodes GROUP BY metadata_status"))
            report["reference_status_counts"] = dict(db.execute("SELECT status,COUNT(*) FROM reference_matches GROUP BY status"))
            report["usable_event_relations"] = db.execute("SELECT COUNT(*) FROM usable_event_relations").fetchone()[0]
            report["process_context_counts"] = dict(db.execute("SELECT process_context_status,COUNT(*) FROM events GROUP BY process_context_status"))
            report["unique_object_nodes_with_fresh_evidence"] = db.execute("SELECT COUNT(*) FROM uniform_object_definitions").fetchone()[0]
            report["zero_node_labels"] = db.execute("SELECT COUNT(*) FROM node_reference_labels WHERE published_reference_label=0").fetchone()[0]
            if report["zero_node_labels"] or db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Graph integrity/label check failed")
            report["sqlite_quick_check"] = "ok"
            db.commit()
        if file_hash(graph) != report["input_graph_sha256"]:
            raise ValueError("Original graph changed during recovery")
        report.update(status="complete_uniform_metadata_not_training_ready",input_graph_unchanged=True,
            database_bytes=destination.stat().st_size,database_sha256=file_hash(destination),
            new_records_streamed=sum(s["records"] for s in report["new_scans"]))
        save()
        return report
    except BaseException as error:
        report.update(status="incomplete_failed",error=str(error));save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source","graph","pilot-report","reference-audit","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--max-gib",type=float,default=4)
    args = parser.parse_args()
    report = recover(args.source,args.graph,args.pilot_report,args.reference_audit,args.output,args.max_gib)
    print(json.dumps({k:report[k] for k in ("status","universe_count","newly_resolved_nodes","database_bytes")}),flush=True)


if __name__ == "__main__":
    main()
