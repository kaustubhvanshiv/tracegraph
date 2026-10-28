"""Build deterministic, unknown-label review IDs from a declared raw-CDM window.

No node-reference CSV, metadata completeness, inferred object kind or security
label participates in selection. Output is evidence triage, not training data.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

from fastavro import reader

from research.ml.data_prep.inspect_fivedirections import natural_key, uuid_text
from research.ml.data_prep.resolve_references import clean, reusable_files
from research.ml.node_benchmark.build_graphs import iso_nanos, select_sources, text_hash


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",", ":")).encode()


def candidate_pool(events, window):
    pool = {}
    for uid,event in sorted(events.items(),key=lambda item:(item[1]["timestamp_nanos"],item[0])):
        for entity,role in event["references"]:
            if not entity:
                continue
            row = pool.get(entity)
            if row is None:
                row = pool[entity] = dict(host_uuid=window["host_uuid"],node_uuid=entity,
                    anchor_nanos=window["end_nanos"]-1,first_event_nanos=event["timestamp_nanos"],
                    last_event_nanos=event["timestamp_nanos"],witness_event_uuid=uid,
                    witness_role=role,witness_source_file=event["source_file"],
                    witness_record_index_1based=event["record_index"],witness_raw_sha256=event["raw_sha256"],label=None)
            row["last_event_nanos"] = max(row["last_event_nanos"],event["timestamp_nanos"])
    return pool


def rank_candidates(pool, window, seed, limit):
    if limit < 1:
        raise ValueError("Use a positive review budget")
    def rank(row):
        fields = [seed,row["host_uuid"],window["start_nanos"],window["end_nanos"],row["node_uuid"],row["anchor_nanos"]]
        return hashlib.sha256(canonical(fields)).hexdigest(),row["host_uuid"],row["node_uuid"],row["anchor_nanos"]
    return [dict(row,selection_sha256=rank(row)[0]) for row in sorted(pool.values(),key=rank)[:limit]]


def build(source, plan_path, reference_audit, support, output):
    source,output = source.resolve(),output.resolve()
    if output.exists() or output==source or source in output.parents:
        raise ValueError("Use a fresh output directory outside raw data")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan["candidate_label"] is not None or plan["sample_role"]!="unknown_label_review_candidate_only":
        raise ValueError("Review candidates must remain unknown, not benign")
    if text_hash(reference_audit/"reference_report.json") != plan["source_reference_report_sha256_utf8_lf"]:
        raise ValueError("Reference source snapshot changed")
    with zipfile.ZipFile(support/plan["act_report"]["archive"]) as archive:
        if hashlib.sha256(archive.read(plan["act_report"]["member"])).hexdigest()!=plan["act_report"]["sha256"]:
            raise ValueError("ACT report hash mismatch")
    if text_hash(support/plan["operational_log"]["filename"])!=plan["operational_log"]["sha256_utf8_lf"]:
        raise ValueError("Operational-log hash mismatch")
    window = dict(plan["window"],case_id=plan["window"]["window_id"],
        start_nanos=iso_nanos(plan["window"]["start_utc"]),end_nanos=iso_nanos(plan["window"]["end_utc"]))
    if not 0 < window["end_nanos"]-window["start_nanos"] <= 300*10**9:
        raise ValueError("This bounded review requires a window of at most five minutes")
    paths = list(source.rglob("*.gz")); files = reusable_files(paths,reference_audit)
    if len({p.name for p in paths})!=len(paths) or {p.name for p in paths}!={f["filename"] for f in files}:
        raise ValueError("Raw inventory differs from the completed audit")
    paths = {p.name:p for p in paths}; expected = {f["filename"]:f for f in files}
    selected = select_sources(files,[window])
    if not selected:
        raise ValueError("No audited local source overlaps the review window")
    output.mkdir(parents=True)
    report = dict(status="scanning",plan_id=plan["plan_id"],plan_sha256_utf8_lf=text_hash(plan_path),
        producer_sha256_utf8_lf=text_hash(Path(__file__)),window=window,seed=plan["seed"],limit=plan["limit"],
        source_reference_report_sha256_utf8_lf=text_hash(reference_audit/"reference_report.json"),
        support_sources=dict(act_pdf_sha256=plan["act_report"]["sha256"],operational_log_sha256_utf8_lf=plan["operational_log"]["sha256_utf8_lf"]),
        scans=[],reference_membership_used=False,candidate_labels_assigned=False,verified_benign_labels=0,
        clock_review=plan["clock_review"],coverage_contract=plan["coverage_contract"],
        feature_vectors_created=False,partitions_created=False,models_trained=False)
    save = lambda:(output/"manifest.json").write_bytes((json.dumps(report,indent=2)+"\n").encode())
    save();events={};conflicts=set();minute_counts=Counter();raw_window_records=0
    try:
        for name in sorted(selected,key=natural_key):
            kinds,index = Counter(),0
            with gzip.open(paths[name],"rb") as stream:
                for index,raw in enumerate(reader(stream),1):
                    kinds[raw["type"]]+=1
                    if index%2_000_000==0:
                        print(json.dumps(dict(filename=name,records=index,review_window_raw_events=raw_window_records)),flush=True)
                    if raw["type"]!="RECORD_EVENT" or uuid_text(raw.get("hostId"))!=window["host_uuid"]:
                        continue
                    datum=raw["datum"];ts=datum.get("timestampNanos")
                    if not isinstance(ts,int) or not window["start_nanos"]<=ts<window["end_nanos"]:
                        continue
                    raw_window_records+=1;minute_counts[(ts-window["start_nanos"])//(60*10**9)]+=1
                    uid=uuid_text(datum.get("uuid"))
                    if not uid:
                        raise ValueError("Selected native Event has no UUID")
                    fingerprint=hashlib.sha256(canonical(clean(raw))).hexdigest()
                    if uid in events:
                        if events[uid]["raw_sha256"]!=fingerprint: conflicts.add(uid)
                        continue
                    events[uid]=dict(timestamp_nanos=ts,source_file=name,record_index=index,raw_sha256=fingerprint,
                        references=[(uuid_text(datum.get(field)),field) for field in ("subject","predicateObject","predicateObject2")])
                if stream.read(1):
                    raise ValueError("Unexpected trailing Avro bytes")
            item=expected[name]
            if index!=item["records"] or dict(kinds)!=item["record_type_counts"]:
                raise ValueError("Fresh complete stream counts differ from source audit")
            report["scans"].append(dict(filename=name,records=index,complete_scan=True,
                compressed_bytes=item["compressed_bytes"],modified_time_ns=item["modified_time_ns"]))
            save()
        reusable_files(list(paths.values()),reference_audit)
        for uid in conflicts: events.pop(uid,None)
        pool=candidate_pool(events,window)
        if not pool:
            raise ValueError("No nonconflicting observed nodes in the selected window")
        universe=output/"universe.jsonl"
        with universe.open("wb") as stream:
            for row in sorted(pool.values(),key=lambda r:(r["host_uuid"],r["node_uuid"],r["anchor_nanos"])):
                stream.write(canonical([row["host_uuid"],row["node_uuid"],row["anchor_nanos"]])+b"\n")
        selected_rows=rank_candidates(pool,window,plan["seed"],plan["limit"])
        candidates=output/"review_candidates.jsonl"
        with candidates.open("wb") as stream:
            for row in selected_rows: stream.write(canonical(row)+b"\n")
        report.update(status="complete_unknown_label_review_pool",raw_event_records_in_window=raw_window_records,
            unique_nonconflicting_events=len(events),conflicting_event_uuids=sorted(conflicts),
            conflict_check_scope="Selected window in available audited files only",pool_node_count=len(pool),
            universe_sha256=hashlib.sha256(universe.read_bytes()).hexdigest(),
            candidate_file_sha256=hashlib.sha256(candidates.read_bytes()).hexdigest(),
            candidate_count=len(selected_rows),unknown_candidate_labels=len(selected_rows),
            minute_raw_event_counts=[minute_counts[i] for i in range(5)],
            frozen_before_reference_join=True,ready_for_training=False)
        save();return report
    except BaseException as error:
        report.update(status="incomplete_failed",error=str(error));save();raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("source","plan","reference-audit","support","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args()
    result=build(args.source,args.plan,args.reference_audit,args.support,args.output)
    print(json.dumps({k:result[k] for k in ("status","pool_node_count","candidate_count","verified_benign_labels")}),flush=True)


if __name__=="__main__":
    main()
