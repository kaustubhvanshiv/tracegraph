"""Check the DARPA preparation contract against pinned local graph artifacts.

Reads SQLite in read-only mode. Produces diagnostics only: no samples, labels,
features or partitions are exported, even if necessary conditions later pass.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

from research.ml.node_benchmark.input_contract import validate_input_contract


def text_hash(path):
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


UNIFORM_SCOPE = "all_frozen_graph_nodes_without_reference_join"


def universe_identity_hash(db):
    digest, count = hashlib.sha256(), 0
    for host, uid in db.execute("SELECT host_uuid,uuid FROM nodes ORDER BY host_uuid,uuid"):
        digest.update((json.dumps([host,uid],separators=(",", ":"))+"\n").encode())
        count += 1
    return digest.hexdigest(), count


def validate_uniform_scope(recovery, db):
    if recovery["status"] != "complete_uniform_metadata_not_training_ready":
        if recovery.get("scope") == UNIFORM_SCOPE:
            raise ValueError("Uniform metadata scope does not cover the exact frozen graph universe")
        return
    digest,count = universe_identity_hash(db)
    if (recovery.get("scope") != UNIFORM_SCOPE
            or recovery.get("label_selection_used") is not False
            or recovery.get("universe_frozen_before_reference_join") is not True
            or (recovery.get("universe_sha256"),recovery.get("universe_count")) != (digest,count)
            or recovery.get("target_count") != count
            or not all(s.get("complete_stream_read") for s in recovery.get("new_scans",[]))
            or not all(s.get("complete_scan") for s in recovery.get("reused_complete_pilot_scans",[]))):
        raise ValueError("Uniform metadata scope does not cover the exact frozen graph universe")


def validate_policy(policy):
    """Refuse contracts that silently turn unknown/reference data into truth."""
    if policy["version"] not in (1,2):
        raise ValueError("Unsupported preparation protocol")
    labels, metadata, sampling, split = [policy[k] for k in ("label_contract", "metadata", "sampling", "split")]
    safe = (labels["unlisted_missing_conflicting_or_mismatched"] is None
        and labels["unlisted_is_benign"] is False
        and labels["published_reference_is_verified_event_attack"] is False
        and metadata["recovery_scope"] == "all_selected_nodes_before_reference_join"
        and metadata["join_key"] == ["publishing_host_uuid", "native_entity_uuid"]
        and metadata["annotation_directed_graph_role"] == "review_only"
        and sampling["background_candidate_label"] is None
        and sampling["background_window_or_missing_annotation_proves_benign"] is False
        and sampling["select_windows_before_node_reference_join"] is True
        and split["random_row_splitting"] is False
        and split["minimum_distinct_groups"] >= 3
        and split["separate_partition_graphs"] is True
        and split["purge_gap_at_least_history_horizon"] is True
        and split["require_known_classes_each_partition"] == [0, 1]
        and split["training_only_vocabularies_scalers_and_sampling_statistics"] is True
        and split["target_proportions"] == {"train": 0.6, "validation": 0.2, "test": 0.2})
    if not safe:
        raise ValueError("Preparation protocol weakens the evidence or split contract")
    if any(v is not False for k, v in policy["execution"].items() if k != "audit_only") or policy["execution"]["audit_only"] is not True:
        raise ValueError("This command is audit-only; it never authorizes exports or models")
    if sampling["max_review_candidates_per_host_window"] < 1 or not isinstance(sampling["seed"], int):
        raise ValueError("Use a positive review budget and an integer seed")
    horizon = split["history_horizon_nanos"]
    if horizon is not None and (not isinstance(horizon, int) or horizon <= 0):
        raise ValueError("A frozen history horizon must be a positive integer number of nanoseconds")


def profile(db):
    cases = [dict(zip(("case_id", "host_uuid", "start_nanos", "end_nanos"), r))
             for r in db.execute("SELECT case_id,host_uuid,start_ns,end_ns FROM cases ORDER BY start_ns,case_id")]
    for case in cases:
        case["events"] = db.execute("SELECT COUNT(*) FROM events WHERE case_id=?", (case["case_id"],)).fetchone()[0]
        case["typed_reference_matches"] = db.execute("SELECT COUNT(*) FROM reference_matches WHERE case_id=? AND status='typed_uuid_match'", (case["case_id"],)).fetchone()[0]
    metadata = [dict(zip(("listed_uuid", "metadata_status", "nodes"), r)) for r in db.execute("""
        SELECT EXISTS(SELECT 1 FROM published_nodes p WHERE p.case_id=c.case_id AND p.uuid=n.uuid),
               n.metadata_status,COUNT(*) FROM case_nodes c JOIN nodes n ON n.id=c.node_id
        GROUP BY 1,2 ORDER BY 1,2""")]
    return {"cases": cases, "case_group_upper_bound_before_campaign_review": len(cases),
        "nodes": db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0],
        "events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "event_relations": db.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
        "reference_label_counts": [[v, n] for v, n in db.execute("SELECT published_reference_label,COUNT(*) FROM node_reference_labels GROUP BY published_reference_label")],
        "metadata_by_reference_membership": metadata,
        "unresolved_reference_uuids": [r[0] for r in db.execute("SELECT DISTINCT uuid FROM reference_matches WHERE status<>'typed_uuid_match' ORDER BY uuid")],
        "usable_relations_review_only": db.execute("SELECT COUNT(*) FROM usable_event_relations").fetchone()[0],
        "exact_uuid_shared_across_cases": db.execute("SELECT COUNT(*) FROM (SELECT n.uuid FROM case_nodes c JOIN nodes n ON n.id=c.node_id GROUP BY n.uuid HAVING COUNT(DISTINCT c.case_id)>1)").fetchone()[0]}


def validate_review_inputs(policy, db, inventory, recovery, graph_sha, background_path, group_path):
    if policy["version"] == 1:
        return {}
    if background_path is None or group_path is None:
        raise ValueError("Protocol v2 requires background and group review manifests")
    group = json.loads(group_path.read_text(encoding="utf-8"))
    cases = {c["case_id"] for c in inventory["cases"]}
    assignments = group.get("assignments",{})
    if (group.get("status") != "accepted_conservative_single_holdout" or set(assignments) != cases
            or len(set(assignments.values())) != 1 or not all(assignments.values())
            or group.get("independence_claim") is not False or group.get("common_actor_or_campaign_claim") is not False
            or group.get("graph_sha256") != graph_sha or not policy["split"]["campaign_group_review_complete"]):
        raise ValueError("Group review must conservatively cover every current case without asserting independence")
    background = json.loads(background_path.read_text(encoding="utf-8"))
    if (background.get("status") != "complete_unknown_label_review_pool"
            or background.get("reference_membership_used") is not False
            or background.get("frozen_before_reference_join") is not True
            or background.get("verified_benign_labels") != 0
            or background.get("plan_sha256_utf8_lf") != policy["sampling"]["review_pool_plan_sha256_utf8_lf"]
            or background.get("source_reference_report_sha256_utf8_lf") != recovery.get("reference_report_sha256_utf8_lf")
            or background.get("seed") != policy["sampling"]["seed"]
            or background.get("limit") != policy["sampling"]["max_review_candidates_per_host_window"]
            or not background.get("scans") or not all(s.get("complete_scan") for s in background["scans"])):
        raise ValueError("Background review provenance/scope does not match protocol v2")
    support = background["support_sources"]
    if (support["act_pdf_sha256"] != group["sources"]["act_report_sha256"]
            or support["operational_log_sha256_utf8_lf"] != group["sources"]["operational_log_sha256_utf8_lf"]):
        raise ValueError("Group and background reviews use different source evidence")
    window = background["window"]
    for case in inventory["cases"]:
        if case["host_uuid"]==window["host_uuid"] and max(case["start_nanos"],window["start_nanos"])<min(case["end_nanos"],window["end_nanos"]):
            raise ValueError("Background review window overlaps a current attack-case slice")
    candidate_file = background_path.parent/"review_candidates.jsonl"
    universe_file = background_path.parent/"universe.jsonl"
    if file_hash(candidate_file)!=background["candidate_file_sha256"] or file_hash(universe_file)!=background["universe_sha256"]:
        raise ValueError("Background review files changed")
    candidates = [json.loads(line) for line in candidate_file.read_text(encoding="utf-8").splitlines()]
    universe = [json.loads(line) for line in universe_file.read_text(encoding="utf-8").splitlines()]
    if len(universe)!=background["pool_node_count"] or len({tuple(row) for row in universe})!=len(universe):
        raise ValueError("Background identity universe is incomplete or duplicated")
    if any(host!=window["host_uuid"] or anchor!=window["end_nanos"]-1 for host,uid,anchor in universe):
        raise ValueError("Background identities do not match their native window")
    def rank(identity):
        host,uid,anchor=identity
        fields=[background["seed"],host,window["start_nanos"],window["end_nanos"],uid,anchor]
        return hashlib.sha256(json.dumps(fields,separators=(",", ":")).encode()).hexdigest(),host,uid,anchor
    expected=sorted(universe,key=rank)[:background["limit"]]
    identities=[[row["host_uuid"],row["node_uuid"],row["anchor_nanos"]] for row in candidates]
    if (identities!=expected or len(candidates)!=background["candidate_count"]
            or background["unknown_candidate_labels"]!=len(candidates)
            or any(row.get("label") is not None for row in candidates)
            or any(not window["start_nanos"]<=row["first_event_nanos"]<=row["last_event_nanos"]<window["end_nanos"]
                   or row["witness_record_index_1based"]<1 for row in candidates)
            or any(row.get("selection_sha256")!=rank(identity)[0] for row,identity in zip(candidates,identities))):
        raise ValueError("Background candidates are not the frozen seeded unknown-label draw")
    overlap=sum(db.execute("SELECT 1 FROM nodes WHERE host_uuid=? AND uuid=?",(host,uid)).fetchone() is not None
                for host,uid,anchor in identities)
    inventory["evaluation_group_count"]=1
    return {"group_review": {"manifest_sha256_utf8_lf":text_hash(group_path),"status":group["status"],
            "assignments":assignments,"evaluation_groups":1,"independence_claim":False},
        "background_review_pool": {"manifest_sha256_utf8_lf":text_hash(background_path),"candidate_count":len(candidates),
            "pool_node_count":len(universe),"all_labels_unknown":True,"verified_benign_labels":0,
            "candidate_identity_overlap_with_current_pilot":overlap,"accepted_training_background":False,
            "metadata_for_expanded_training_cohort_verified":False}}


def blockers(policy, inventory, changes, recovery):
    """Necessary preparation conditions; no branch returns training approval."""
    reasons = []
    def add(code, reason):
        reasons.append({"code": code, "reason": reason})
    uniform = recovery.get("status") == "complete_uniform_metadata_not_training_ready" and recovery.get("scope") == UNIFORM_SCOPE
    if recovery.get("target_count") and not uniform:
        add("annotation_directed_metadata", "The follow-up searched published reference UUIDs only; the enriched graph is review-only until metadata scope is independent of membership.")
    if not policy["sampling"]["background_windows"]:
        reason = ("An unknown-label review pool exists, but no background cohort has been accepted for features/training."
                  if policy["version"]==2 else "Only case-conditioned windows exist in this pilot; no independently selected, coverage-reviewed background windows are declared.")
        add("background_cohort_missing", reason)
    if policy["label_contract"]["verified_node_classification_labels"] is None:
        add("binary_node_ground_truth_missing", "Typed reference membership and unknown nodes do not supply reviewed binary attack/benign node ground truth.")
    groups=inventory.get("evaluation_group_count",inventory["case_group_upper_bound_before_campaign_review"])
    if groups < policy["split"]["minimum_distinct_groups"]:
        add("insufficient_whole_groups", f"Only {groups} evaluation groups are available; three nonempty chronological partitions cannot be populated without dividing/reusing a group.")
    if not policy["split"]["campaign_group_review_complete"]:
        add("campaign_group_review_missing", "Distinct case names, host UUIDs or disjoint node UUIDs do not establish independent campaign/context groups.")
    if policy["split"]["history_horizon_nanos"] is None:
        add("history_horizon_not_frozen", "Choose and record the actual input history before calculating a purge gap or constructing graphs/features.")
    return reasons


def audit(policy_path, original, review, recovery_report_path, event_gate_path, annotations_path, background_path=None, group_path=None):
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    validate_policy(policy)
    recovery = json.loads(recovery_report_path.read_text(encoding="utf-8"))
    if recovery["status"] not in {"complete_metadata_review_not_training_ready","complete_uniform_metadata_not_training_ready"}:
        raise ValueError("A completed, pinned metadata review is required")
    before_hash, after_hash = file_hash(original), file_hash(review)
    if (before_hash, after_hash) != (recovery["input_graph_sha256"], recovery["database_sha256"]):
        raise ValueError("Graph fingerprints do not match the completed recovery report")
    event_gate = json.loads(event_gate_path.read_text(encoding="utf-8"))
    if text_hash(annotations_path) != event_gate["annotations_sha256"]:
        raise ValueError("Event labels changed; review the Event gate again before reusing it")
    with closing(sqlite3.connect(review.resolve().as_uri()+"?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Graph integrity check failed")
        validate_uniform_scope(recovery,db)
        inventory = profile(db)
        db.execute("ATTACH DATABASE ? AS baseline", (original.resolve().as_uri()+"?mode=ro",))
        identity_differences = db.execute("SELECT COUNT(*) FROM nodes n LEFT JOIN baseline.nodes b ON b.id=n.id WHERE b.id IS NULL OR n.host_uuid IS NOT b.host_uuid OR n.uuid IS NOT b.uuid").fetchone()[0]
        if identity_differences or db.execute("SELECT COUNT(*) FROM baseline.nodes").fetchone()[0] != inventory["nodes"]:
            raise ValueError("The baseline and review graph do not have the same entity identities")
        listed_ids = {r[0] for r in db.execute("SELECT c.node_id FROM case_nodes c JOIN nodes n ON n.id=c.node_id "
            "JOIN published_nodes p ON p.case_id=c.case_id AND p.uuid=n.uuid")}
        changes = {"listed_nodes_changed": 0, "unlisted_nodes_changed": 0}
        # Materialize membership once. A correlated scan of case_nodes for each
        # changed node becomes quadratic when tens of thousands are repaired.
        for (node_id,) in db.execute("SELECT n.id FROM nodes n JOIN baseline.nodes b ON b.id=n.id WHERE "
                "n.kind IS NOT b.kind OR n.subtype IS NOT b.subtype OR n.metadata_status IS NOT b.metadata_status"):
            changes["listed_nodes_changed" if node_id in listed_ids else "unlisted_nodes_changed"] += 1
        baseline_metadata = [dict(zip(("listed_uuid", "metadata_status", "nodes"), r)) for r in db.execute("""
            SELECT EXISTS(SELECT 1 FROM baseline.published_nodes p WHERE p.case_id=c.case_id AND p.uuid=n.uuid),
                   n.metadata_status,COUNT(*) FROM baseline.case_nodes c JOIN baseline.nodes n ON n.id=c.node_id
            GROUP BY 1,2 ORDER BY 1,2""")]
        reviewed_inputs=validate_review_inputs(policy,db,inventory,recovery,after_hash,background_path,group_path)
    history_review = None
    if policy["split"]["history_horizon_nanos"] is not None:
        name = policy["split"].get("input_spec_file", "")
        if not name or Path(name).name != name:
            raise ValueError("A frozen history requires a sibling input-spec file")
        windows = [dict(case_id=c["case_id"], host_uuid=c["host_uuid"],
                        start_nanos=c["start_nanos"], end_nanos=c["end_nanos"])
                   for c in inventory["cases"]]
        if background_path is not None:
            windows.append(json.loads(background_path.read_text(encoding="utf-8"))["window"])
        history_review = validate_input_contract(policy, policy_path.parent / name, windows)
    report = {"protocol_id": policy["protocol_id"], "review_completed": True,
        "status": "review_complete_preparation_incomplete", "policy_sha256_utf8_lf": text_hash(policy_path),
        "audit_code_sha256_utf8_lf": text_hash(Path(__file__)),
        "original_graph_sha256": before_hash, "review_graph_sha256": after_hash,
        "recovery_report_sha256_utf8_lf": text_hash(recovery_report_path),
        "metadata_recovery_scope": recovery.get("scope","published_reference_uuid_targets_only"),
        "inventory": inventory, "metadata_change_scope": changes,
        "baseline_metadata_by_reference_membership": baseline_metadata,
        **reviewed_inputs,
        "input_history_review": history_review,
        "blocking_conditions": blockers(policy, inventory, changes, recovery),
        "original_event_track_unchanged": {"status": event_gate["status"],
            "eligible_label_counts": event_gate["eligible_label_counts"],
            "eligible_label_group_counts": event_gate["eligible_label_group_counts"],
            "annotations_sha256_utf8_lf": text_hash(annotations_path),
            "gate_sha256_utf8_lf": text_hash(event_gate_path),
            "note": "Separate Event-level evidence; node references never relabel these Events or satisfy its gate."},
        "background_candidates_created": False, "feature_vectors_created": False,
        "partitions_created": False, "models_selected_or_trained": False,
        "training_authorized_by_this_audit": False,
        "limitations": ["Graph hashes and SQLite integrity checked; raw archives not reread.",
            "Case count is an upper bound before campaign/context merging, not proof of independence.",
            "No shared exact UUID is not proof of absence of shared campaign/causal context.",
            "This audit does not validate future candidate windows, labels, graph histories or actual partitions."]}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("protocol", "original-graph", "review-graph", "recovery-report", "event-gate", "annotations", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--background-review",type=Path)
    parser.add_argument("--group-review",type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.suffix != ".json":
        raise ValueError("Use a fresh JSON report path")
    result = audit(args.protocol, args.original_graph, args.review_graph, args.recovery_report,
                   args.event_gate, args.annotations,args.background_review,args.group_review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(result, indent=2)+"\n").encode())
    print(json.dumps({"status": result["status"], "blocking_conditions": [r["code"] for r in result["blocking_conditions"]],
                      "partitions_created": False}), flush=True)
    # A successfully completed audit is not a successful preparation/training gate.
    return 2 if result["blocking_conditions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
