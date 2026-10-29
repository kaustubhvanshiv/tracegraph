"""Validate the bounded, past-only input definition without building features."""
import hashlib
import json


def history_bounds(window, spec):
    horizon = spec["history_horizon_nanos"]
    if (type(horizon) is not int or horizon <= 0
            or spec["history_interval"] != "[anchor_nanos - history_horizon_nanos + 1, anchor_nanos]"
            or spec["future_events_allowed"] is not False
            or spec["native_event_reference_neighborhood_hops"] != 1
            or spec["unknown_labels_used_for_supervised_training"] is not False
            or spec["offline_metadata_proves_arrival_time_availability"] is not False
            or spec["purge_gap_minimum_nanos"] < horizon):
        raise ValueError("Invalid past-only input definition")
    start, end = window["end_nanos"] - horizon, window["end_nanos"]
    if start < window["start_nanos"]:
        raise ValueError("Frozen window cannot accommodate the declared history")
    return dict(start_inclusive_nanos=start, end_exclusive_nanos=end,
                anchor_nanos=end-1, within_existing_window=True,
                continuous_coverage_proven=False)


def validate_input_contract(policy, spec_path, windows):
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(spec_path.read_text(encoding="utf-8").encode()).hexdigest()
    if (policy["split"]["history_horizon_nanos"] != spec["history_horizon_nanos"]
            or policy["split"].get("input_spec_sha256_utf8_lf") != digest):
        raise ValueError("Input definition and preparation policy differ")
    intervals = [dict(window_id=w.get("case_id", w.get("window_id", "review")),
                      host_uuid=w["host_uuid"], **history_bounds(w, spec)) for w in windows]
    return dict(status="input_definition_frozen_no_graph_inputs_created", input_spec_id=spec["input_spec_id"],
        input_spec_sha256_utf8_lf=digest, history_horizon_nanos=spec["history_horizon_nanos"],
        native_event_reference_neighborhood_hops=spec["native_event_reference_neighborhood_hops"],
        purge_gap_minimum_nanos=spec["purge_gap_minimum_nanos"], intervals=intervals,
        predictor_fields_frozen=spec["predictor_fields_frozen"], graph_inputs_created=False)
