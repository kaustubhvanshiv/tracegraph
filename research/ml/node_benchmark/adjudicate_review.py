"""Record evidence insufficiency for frozen candidates without inventing labels.

Consumes a source-reviewed findings artifact. This records unknown decisions
only; it cannot import binary labels, create supervised splits or train.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from research.ml.node_benchmark.audit_protocol import file_hash, text_hash, validate_policy
from research.ml.node_benchmark.background_review import canonical
from research.ml.node_benchmark.input_contract import history_bounds


def adjudicate(packet_manifest, findings_path, policy_path, spec_path, output):
    if output.exists():
        raise ValueError("Use a fresh evidence-decision output directory")
    report = json.loads(packet_manifest.read_text(encoding="utf-8"))
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    validate_policy(policy)
    if (policy["split"]["history_horizon_nanos"] != spec["history_horizon_nanos"]
            or policy["split"].get("input_spec_sha256_utf8_lf") != text_hash(spec_path)):
        raise ValueError("Input definition and preparation policy differ")
    packet_file = packet_manifest.parent / "packets.jsonl"
    packet_sha = file_hash(packet_file)
    if (report["status"] != "complete_native_evidence_packets_unknown_labels"
            or packet_sha != report["packet_file_sha256"]
            or packet_sha != findings["packet_file_sha256"]):
        raise ValueError("Evidence packets differ from the source-reviewed artifact")
    if (findings["classification_decision"] != "retain_unknown_all_candidates"
            or findings["binary_intent_evidence_rows"] != []
            or findings["source_absence_proves_no_attack"] is not False
            or findings["all_candidate_actions_certified_benign"] is not False
            or findings["training_authorized"] is not False or not findings["reviewer"]):
        raise ValueError("This review may record insufficiency only, never manufacture binary labels")
    for source in findings["source_files"]:
        path = Path(source["path"])
        if source["hash_format"] not in ("binary", "utf8_lf"):
            raise ValueError("Unsupported source fingerprint format")
        actual = file_hash(path) if source["hash_format"] == "binary" else text_hash(path)
        if actual != source["sha256"]:
            raise ValueError("Reviewed support source changed")
    window = findings["reviewed_window"]
    interval = history_bounds(window, spec)
    packets = [json.loads(line) for line in packet_file.read_text(encoding="utf-8").splitlines()]
    if len(packets) != report["candidate_count"]:
        raise ValueError("Packet count changed")
    decisions, seen, flags, actions = [], set(), Counter(), Counter()
    for packet in packets:
        row = packet["candidate"]
        identity = (row["host_uuid"], row["node_uuid"], row["anchor_nanos"])
        if (identity in seen or packet["label"] is not None or row["label"] is not None
                or row["host_uuid"] != window["host_uuid"] or row["anchor_nanos"] != window["end_nanos"]-1
                or not window["start_nanos"] <= row["first_event_nanos"] <= row["last_event_nanos"] < window["end_nanos"]):
            raise ValueError("Candidate identity, window or unknown label changed")
        seen.add(identity)
        review_flags = []
        if packet["witness_actor_context"]["status"] == "future_start_in_chain":
            review_flags.append("future_start_in_witness_chain_no_clock_repair")
        if packet["pilot_overlap"]:
            review_flags.append("pilot_identity_overlap_requires_group_or_purge_review")
        flags.update(review_flags)
        actions[packet["witness"]["raw_record"]["datum"].get("type", "<missing>")] += 1
        decisions.append(dict(host_uuid=identity[0], node_uuid=identity[1], anchor_nanos=identity[2],
            label=None, review_status="source_review_complete_intent_not_established",
            security_ground_truth_review="No independent binary action-intent evidence established in reviewed sources",
            review_id=findings["review_id"], reviewer=findings["reviewer"],
            source_finding_ids=[f["id"] for f in findings["findings"]],
            witness_event_uuid=row["witness_event_uuid"], witness_raw_sha256=row["witness_raw_sha256"],
            review_flags=review_flags, supervised_eligible=False,
            supervised_exclusion_reason="unknown_security_intent_not_a_verified_attack_or_benign_label"))
    output.mkdir(parents=True)
    decision_file = output / "review_decisions.jsonl"
    decision_file.write_bytes(b"".join(canonical(d) + b"\n" for d in decisions))
    result = dict(status="source_sufficiency_review_complete_training_blocked", candidate_count=len(decisions),
        source_sufficiency_decisions=len(decisions), verified_binary_labels=0, unknown_labels=len(decisions),
        supervised_eligible=0, review_flag_counts=dict(flags), witness_action_counts=dict(actions),
        history_interval_for_review_window=interval, input_spec_id=spec["input_spec_id"],
        input_spec_sha256_utf8_lf=text_hash(spec_path), findings_sha256_utf8_lf=text_hash(findings_path),
        packet_file_sha256=packet_sha, decision_file_sha256=file_hash(decision_file),
        producer_sha256_utf8_lf=text_hash(Path(__file__)), preparation_policy_sha256_utf8_lf=text_hash(policy_path),
        binary_labels_assigned=False, original_event_labels_changed=False, actual_partitions_created=False,
        graph_inputs_created=False, models_selected_or_trained=False, preparation_complete=False,
        limitations=["Evidence sufficiency review by Codex, not independent expert security annotation",
            "No source-absence, process-name, pre-attack-date or reference-membership rule supplied benign labels",
            "Unknown decisions do not supply an accepted background training cohort or independent groups"])
    (output / "manifest.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("packet-manifest", "findings", "policy", "input-spec", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = adjudicate(args.packet_manifest, args.findings, args.policy, args.input_spec, args.output)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
