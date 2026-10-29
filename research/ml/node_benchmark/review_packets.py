"""Attach native evidence to a frozen unknown-label draw; never assign labels.

The packet is for offline human evidence review, not predictive features or a
benign cohort. Full telemetry and command lines remain in ignored local files.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import gzip
import hashlib
import html
import json
from pathlib import Path
import sqlite3

from fastavro import reader

from research.ml.data_prep.inspect_fivedirections import natural_key, utc_nanos, uuid_text
from research.ml.data_prep.resolve_references import clean, reusable_files, validate_cached_index
from research.ml.node_benchmark.background_review import canonical, rank_candidates
from research.ml.node_benchmark.build_graphs import OBJECT_KINDS, text_hash
from research.ml.node_benchmark.audit_protocol import file_hash


def read_frozen_pool(pool, plan_path):
    manifest = json.loads((pool / "manifest.json").read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (manifest.get("status") != "complete_unknown_label_review_pool"
            or manifest.get("reference_membership_used") is not False
            or manifest.get("candidate_labels_assigned") is not False
            or manifest.get("frozen_before_reference_join") is not True
            or manifest.get("plan_sha256_utf8_lf") != text_hash(plan_path)
            or plan["candidate_label"] is not None):
        raise ValueError("Require the pinned, frozen unknown-label review pool")
    for name, key in (("universe.jsonl", "universe_sha256"),
                      ("review_candidates.jsonl", "candidate_file_sha256")):
        if file_hash(pool / name) != manifest[key]:
            raise ValueError("Frozen pool file digest changed")
    window = manifest["window"]
    universe = [json.loads(line) for line in (pool / "universe.jsonl").read_text(encoding="utf-8").splitlines()]
    if (len(universe) != manifest["pool_node_count"]
            or len({tuple(row) for row in universe}) != len(universe)
            or any(len(row) != 3 or row[0] != window["host_uuid"]
                   or row[2] != window["end_nanos"] - 1 for row in universe)):
        raise ValueError("Invalid frozen review universe")
    rows = [json.loads(line) for line in (pool / "review_candidates.jsonl").read_text(encoding="utf-8").splitlines()]
    draw = rank_candidates({uid: dict(host_uuid=host, node_uuid=uid, anchor_nanos=anchor)
                            for host, uid, anchor in universe}, window, plan["seed"], plan["limit"])
    if (len(rows) != manifest["candidate_count"] or len(rows) != len(draw)
            or (manifest["seed"], manifest["limit"]) != (plan["seed"], plan["limit"])):
        raise ValueError("Frozen draw count or seed changed")
    for row, expected in zip(rows, draw):
        if (row["label"] is not None
                or any(row[key] != expected[key] for key in ("host_uuid", "node_uuid", "anchor_nanos", "selection_sha256"))
                or row["witness_role"] not in ("subject", "predicateObject", "predicateObject2")
                or type(row["witness_record_index_1based"]) is not int
                or row["witness_record_index_1based"] < 1):
            raise ValueError("Candidate labels, identity, ordering or witness changed")
    return manifest, rows


def verified_witness(raw, candidate, window):
    datum = raw["datum"]
    timestamp = datum.get("timestampNanos")
    if (raw["type"] != "RECORD_EVENT"
            or uuid_text(raw.get("hostId")) != candidate["host_uuid"]
            or uuid_text(datum.get("uuid")) != candidate["witness_event_uuid"]
            or uuid_text(datum.get(candidate["witness_role"])) != candidate["node_uuid"]
            or type(timestamp) is not int or not window["start_nanos"] <= timestamp < window["end_nanos"]
            or timestamp != candidate["first_event_nanos"]
            or hashlib.sha256(canonical(clean(raw))).hexdigest() != candidate["witness_raw_sha256"]):
        raise ValueError("Native witness does not match the frozen candidate")
    return dict(raw_record=clean(raw), timestamp_utc=utc_nanos(timestamp),
                source_file=candidate["witness_source_file"],
                record_index_1based=candidate["witness_record_index_1based"],
                raw_sha256=candidate["witness_raw_sha256"])


class NativeDefinitions:
    """Retain conflicting payload variants and exact first source positions."""

    def __init__(self, db):
        self.db = db
        self.local = defaultdict(dict)
        self.cached = {}

    def add_object(self, raw, filename, index):
        key = (uuid_text(raw["hostId"]), uuid_text(raw["datum"].get("uuid")))
        payload = clean(raw["datum"])
        digest = hashlib.sha256(canonical([raw["type"], payload])).hexdigest()
        variants = self.local[key]
        if digest not in variants:
            variants[digest] = dict(kind=raw["type"], payload=payload,
                definition_sha256=digest, fingerprint_scope="canonical_kind_and_clean_datum",
                source_file=filename, record_index_1based=index,
                raw_sha256=hashlib.sha256(canonical(clean(raw))).hexdigest(), occurrences=0)
        variants[digest]["occurrences"] += 1

    def get(self, host, uid):
        if not uid:
            return dict(status="no_native_reference", variants=[])
        key = (host, uid)
        if key not in self.cached:
            variants = dict(self.local.get(key, {}))
            for kind, text, name, index in self.db.execute(
                    "SELECT kind,payload,filename,record_index FROM entities WHERE host=? AND uuid=? ORDER BY filename,record_index",
                    key):
                payload = json.loads(text)
                digest = hashlib.sha256(canonical([kind, payload])).hexdigest()
                if digest not in variants:
                    variants[digest] = dict(kind=kind, payload=payload, definition_sha256=digest,
                        fingerprint_scope="canonical_kind_and_clean_datum", source_file=name,
                        record_index_1based=index, raw_sha256=None, occurrences=0)
                variants[digest]["occurrences"] += 1
            status = "one_payload_in_review_sources" if len(variants) == 1 else (
                "conflicting_payloads_in_review_sources" if variants else "not_found_in_review_sources")
            self.cached[key] = dict(host_uuid=host, node_uuid=uid, status=status,
                variants=[variants[d] for d in sorted(variants)],
                offline_only=True, arrival_time_availability_proven=False)
        return self.cached[key]


def actor_chain(definitions, host, actor, timestamp, max_depth=32):
    chain, seen = [], set()
    while actor:
        if actor in seen:
            return dict(status="cycle", nodes=chain)
        if len(chain) >= max_depth:
            return dict(status="depth_limit", nodes=chain)
        seen.add(actor)
        definition = definitions.get(host, actor)
        node = dict(definition=definition, started_at_or_before_witness=None)
        chain.append(node)
        if definition["status"] != "one_payload_in_review_sources":
            return dict(status="unresolved_or_conflicting", nodes=chain)
        variant = definition["variants"][0]
        if variant["kind"] != "RECORD_SUBJECT":
            return dict(status="non_subject_native_reference", nodes=chain)
        datum = variant["payload"]
        start = datum.get("startTimestampNanos")
        node["started_at_or_before_witness"] = start <= timestamp if type(start) is int else None
        principal = datum.get("localPrincipal")
        node["principal"] = definitions.get(host, principal) if principal else None
        actor = datum.get("parentSubject")
    if not chain:
        status = "no_native_actor"
    elif any(n["started_at_or_before_witness"] is False for n in chain):
        status = "future_start_in_chain"
    elif any(n["started_at_or_before_witness"] is None for n in chain):
        status = "missing_start_in_chain"
    else:
        status = "native_starts_at_or_before_witness"
    return dict(status=status, nodes=chain)


def write_viewer(path, packets):
    # Source strings are text, never executable markup or browser JavaScript.
    entries = []
    for number, packet in enumerate(packets, 1):
        candidate = packet["candidate"]
        title = f"{number}. {candidate['node_uuid']} | unknown | {packet['node_definition']['status']}"
        if packet["pilot_overlap"]:
            title += " | overlaps pilot"
        entries.append("<details><summary>" + html.escape(title) + "</summary><pre>" +
                       html.escape(json.dumps(packet, indent=2, ensure_ascii=True)) + "</pre></details>")
    page = ("<!doctype html><html lang=en><meta charset=utf-8><title>DARPA evidence review</title>"
            "<meta http-equiv=Content-Security-Policy content=\"default-src 'none'; style-src 'unsafe-inline'\">"
            "<style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 16px}"
            "details{border:1px solid #aaa;padding:12px;margin:10px 0}summary{cursor:pointer}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}</style>"
            "<h1>DARPA native evidence review</h1><p>All candidates are unknown. These offline evidence "
            "packets do not establish benign intent, training labels or arrival-time availability. "
            "Find a UUID with your browser's search, then expand its record. "
            "Pilot overlap means shared native identity, not shared attack intent.</p>" +
            "".join(entries) + "</html>")
    path.write_text(page, encoding="utf-8")


def build(source, pool, plan_path, reference_audit, pilot_graph, group_review, annotations, output):
    source, output = source.resolve(), output.resolve()
    if output.exists() or source == output or source in output.parents:
        raise ValueError("Use a fresh output directory outside raw data")
    frozen, candidates = read_frozen_pool(pool, plan_path)
    if text_hash(reference_audit / "reference_report.json") != frozen["source_reference_report_sha256_utf8_lf"]:
        raise ValueError("Reference audit snapshot changed")
    paths = list(source.rglob("*.gz"))
    files = reusable_files(paths, reference_audit)
    if len({p.name for p in paths}) != len(paths) or {p.name for p in paths} != {f["filename"] for f in files}:
        raise ValueError("Raw source inventory differs from the audited subset")
    by_name, expected = {p.name: p for p in paths}, {f["filename"]: f for f in files}
    scans = {s["filename"]: s for s in frozen["scans"]}
    if not scans or any(s.get("complete_scan") is not True for s in scans.values()):
        raise ValueError("Review source scans must be complete")
    witness_positions = defaultdict(list)
    for row in candidates:
        name, index = row["witness_source_file"], row["witness_record_index_1based"]
        if name not in scans or index > expected[name]["records"]:
            raise ValueError("Witness outside reviewed source bounds")
        witness_positions[(name, index)].append(row)
    group = json.loads(group_review.read_text(encoding="utf-8"))
    graph_sha = file_hash(pilot_graph)
    if group.get("status") != "accepted_conservative_single_holdout" or group["graph_sha256"] != graph_sha:
        raise ValueError("Pilot graph does not match the reviewed group manifest")
    annotation_sha = text_hash(annotations)
    index_path = reference_audit / "references.sqlite"
    index_sha = file_hash(index_path)
    report = dict(status="building_review_packets", producer_sha256_utf8_lf=text_hash(Path(__file__)),
        pool_manifest_sha256_utf8_lf=text_hash(pool / "manifest.json"),
        plan_sha256_utf8_lf=text_hash(plan_path), candidate_file_sha256=frozen["candidate_file_sha256"],
        universe_sha256=frozen["universe_sha256"], source_reference_report_sha256_utf8_lf=text_hash(reference_audit / "reference_report.json"),
        native_index_sha256=index_sha, pilot_graph_sha256=graph_sha,
        group_review_sha256_utf8_lf=text_hash(group_review), event_annotations_sha256_utf8_lf=annotation_sha,
        candidate_count=len(candidates), new_verified_benign_labels=0, new_verified_attack_labels=0,
        candidate_labels_assigned=False, feature_vectors_created=False, partitions_created=False,
        models_trained=False, ready_for_training=False,
        object_metadata_scope="All frozen candidates searched equally in complete original review-window source streams only",
        subject_metadata_scope="Host-scoped exact UUID lookup in the completed 37-file Host/Principal/Subject index; includes offline later definitions",
        definition_conflict_scope="Complete kind and cleaned datum payloads in these review sources only",
        source_authenticity="Local counts, fingerprints and size/mtime guards; no publisher authenticity claim",
        scans=[])
    output.mkdir(parents=True)
    save = lambda: (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    save()
    try:
        with closing(sqlite3.connect(index_path.resolve().as_uri() + "?mode=ro", uri=True)) as db, closing(
                sqlite3.connect(pilot_graph.resolve().as_uri() + "?mode=ro", uri=True)) as graph:
            validate_cached_index(db, files)
            definitions = NativeDefinitions(db)
            targets = {(r["host_uuid"], r["node_uuid"]) for r in candidates}
            witnesses = {}
            for name in sorted(scans, key=lambda name: natural_key(Path(name))):
                kinds, index = Counter(), 0
                with gzip.open(by_name[name], "rb") as stream:
                    for index, raw in enumerate(reader(stream), 1):
                        kinds[raw["type"]] += 1
                        if raw["type"] in OBJECT_KINDS and (uuid_text(raw.get("hostId")), uuid_text(raw["datum"].get("uuid"))) in targets:
                            definitions.add_object(raw, name, index)
                        for row in witness_positions.get((name, index), []):
                            witnesses[row["node_uuid"]] = verified_witness(raw, row, frozen["window"])
                        if index % 2_000_000 == 0:
                            print(json.dumps(dict(filename=name, records=index, candidate_witnesses_verified=len(witnesses))), flush=True)
                    if stream.read(1):
                        raise ValueError("Unexpected trailing Avro bytes")
                if index != expected[name]["records"] or dict(kinds) != expected[name]["record_type_counts"]:
                    raise ValueError("Complete source record/type counts changed")
                report["scans"].append(dict(filename=name, records=index, complete_scan=True,
                    record_type_counts=dict(kinds), gzip_exhaustion_verified=True))
                save()
            if len(witnesses) != len(candidates):
                raise ValueError("A frozen candidate has no verified native witness")
            packets, statuses, chain_statuses = [], Counter(), Counter()
            for row in candidates:
                witness = witnesses[row["node_uuid"]]
                datum = witness["raw_record"]["datum"]
                definition = definitions.get(row["host_uuid"], row["node_uuid"])
                context = actor_chain(definitions, row["host_uuid"], datum.get("subject"), datum["timestampNanos"])
                overlaps = [dict(case_id=case, observed=bool(observed), evaluation_group=group["assignments"][case])
                    for case, observed in graph.execute("SELECT c.case_id,c.observed FROM nodes n JOIN case_nodes c ON c.node_id=n.id "
                        "WHERE n.host_uuid=? AND n.uuid=? ORDER BY c.case_id", (row["host_uuid"], row["node_uuid"]))]
                packets.append(dict(candidate=row, witness=witness, node_definition=definition,
                    witness_actor_context=context, pilot_overlap=overlaps, label=None,
                    review_status="needs_independent_action_intent_evidence"))
                statuses[definition["status"]] += 1
                chain_statuses[context["status"]] += 1
        reusable_files(paths, reference_audit)
        if (file_hash(index_path) != index_sha or file_hash(pilot_graph) != graph_sha
                or text_hash(annotations) != annotation_sha):
            raise ValueError("An input database or Event annotation changed during review")
        packet_file = output / "packets.jsonl"
        packet_file.write_bytes(b"".join(canonical(p) + b"\n" for p in packets))
        packet_sha = file_hash(packet_file)
        worksheet = dict(packet_file_sha256=packet_sha, purpose="Human evidence review only; never consumed as training labels",
            decisions=[dict(host_uuid=r["host_uuid"], node_uuid=r["node_uuid"], anchor_nanos=r["anchor_nanos"],
                label=None, reviewer=None, action_intent_evidence=[], rationale="") for r in candidates])
        (output / "review_worksheet.json").write_text(json.dumps(worksheet, indent=2) + "\n", encoding="utf-8")
        write_viewer(output / "review.html", packets)
        report.update(status="complete_native_evidence_packets_unknown_labels", verified_candidate_witnesses=len(witnesses),
            distinct_witness_events=len(witness_positions), node_definition_status_counts=dict(statuses),
            witness_actor_chain_status_counts=dict(chain_statuses), candidates_overlapping_pilot=sum(bool(p["pilot_overlap"]) for p in packets),
            unknown_labels=len(packets), packet_file_sha256=packet_sha, packet_bytes=packet_file.stat().st_size,
            viewer_sha256=file_hash(output / "review.html"), worksheet_sha256=file_hash(output / "review_worksheet.json"),
            input_databases_and_event_annotations_unchanged=True)
        save()
        return report
    except BaseException as error:
        report.update(status="incomplete_failed", error=str(error))
        save()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "pool", "plan", "reference-audit", "pilot-graph", "group-review", "annotations", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = build(args.source, args.pool, args.plan, args.reference_audit, args.pilot_graph,
                   args.group_review, args.annotations, args.output)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
