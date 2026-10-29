# Source review before supervised training

**2026-10-29: evidence-sufficiency review completed; supervised dataset
preparation remains incomplete.** All 500 frozen node/anchor candidates have
recorded unknown decisions. A five-minute past-only input definition is fixed
for this node preparation route. Three dataset blockers remain, down from four
after defining the history. No model, supervised feature set or split exists.

See the [measured review](../../../data/ml/datasets/darpa/node_benchmark/pretraining_review_20261029.md),
[source findings](../../../data/ml/datasets/darpa/node_benchmark/evidence_findings_20261029.json)
and [current audit](../../../data/ml/datasets/darpa/node_benchmark/pretraining_protocol_audit_20261029.json).

## Evidence decisions

The source review covers every saved candidate, its witness action and native
context, the ACT schedule, the May 7 operational log and the report's dated
benign/false-positive examples. The 500 witnesses span 16 native action types.
No reviewed support source establishes binary action intent for this precise
host/window cohort. This records evidence insufficiency; it is not an
independent expert security annotation pass.

ACT page 8 lists the first attack day as May 8, which does not certify earlier
telemetry benign. Pages 28-31 contain May 7 historical logon times inside the
later May 9 Copykatz output, not annotations for these earlier host-1 actions.
The May 7 operational recovery concerns host 2. Page 135's SCP and filemon
examples concern other dates/actions. Familiar executables, resolved native
definitions and absent annotation membership do not establish benign intent.

Each decision keeps `label: null` and supervised eligibility false, recording
the reviewed source findings and original witness fingerprint. Sixty decisions
disclose pilot identity overlap; seven disclose a future start in the witness
ancestry. These timing flags concern particular relations; they do not label
or discard all activity of the node. Original timestamps/annotations are intact.

## Fixed input definition

[The input specification](../../../data/ml/datasets/darpa/node_benchmark/node_input_spec_20261029.json)
defines a five-minute history and one-hop native Event-reference neighborhood,
without recursive expansion or a fanout cap. Native reference roles are
preserved; no information-flow direction is inferred. For exclusive endpoint
`end`, the anchor is `end - 1` ns and history is `[end - 300 seconds, end)`,
equivalently `[anchor - W + 1, anchor]`. This avoids an extra nanosecond
before the frozen review window.

Five minutes fits the already frozen five-minute review window and the
six-minute/32-minute pilot windows. This is a bounded definition chosen without
model results, not an optimal detection horizon. Any later change requires a
new spec version and fresh context/split checks. The original Event track's
later ML-06 history selection is unchanged.

The purge gap must be at least five minutes. Exclude a relation with missing,
conflicting or cyclic required Subject ancestry, or a Subject start after its
Event. Unsupported offline metadata is excluded from predictors. Actual feature
definitions remain later work; start ordering is not arrival-time availability.

The auditor requires a pinned spec for non-NULL history and checks its horizon,
past-only rules and fit within all three existing windows. Bounds fitting does
not prove continuous telemetry, valid features or training readiness.

## Reproduce the recorded unknown decisions

Complete the prior [packet preparation](EVIDENCE_REVIEW.md), then run from the
repository root with the existing ML environment and a fresh output path:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.adjudicate_review `
  --packet-manifest ".cache/ml-runs/native-review-packets-20261029/manifest.json" `
  --findings "data/ml/datasets/darpa/node_benchmark/evidence_findings_20261029.json" `
  --policy "data/ml/datasets/darpa/node_benchmark/preparation_protocol_v2_history_20261029.json" `
  --input-spec "data/ml/datasets/darpa/node_benchmark/node_input_spec_20261029.json" `
  --output ".cache/ml-runs/pretraining-review-20261029-new"
```

This records already reviewed insufficiency, checks packet/support hashes,
preserves candidate ordering, and refuses binary import or blanket benign
certification. `review_decisions.jsonl` and `manifest.json` stay under ignored
`.cache`. They are not training samples. The prior packets/blank human worksheet
remain intact. For a different checkout path, copy the findings file locally,
update only its source paths while retaining hashes/decisions, and pass that
copy to `--findings`.

## Reproduce the latest audit

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.audit_protocol `
  --protocol "data/ml/datasets/darpa/node_benchmark/preparation_protocol_v2_history_20261029.json" `
  --original-graph ".cache/ml-runs/compact-graphs-20261028/graph.sqlite" `
  --review-graph ".cache/ml-runs/uniform-metadata-20261028/graph.sqlite" `
  --recovery-report ".cache/ml-runs/uniform-metadata-20261028/manifest.json" `
  --event-gate "data/ml/datasets/darpa/split_gate_report_20261027.json" `
  --annotations "data/ml/datasets/darpa/review_annotations.json" `
  --background-review ".cache/ml-runs/background-review-pool-20261028/manifest.json" `
  --group-review "data/ml/datasets/darpa/node_benchmark/group_review_20261028.json" `
  --output ".cache/ml-runs/pretraining-review-20261029-new/protocol_audit.json"
```

Expected Python exit code **2** means the review completed with preparation
blockers. It is not a failed software test. Current blockers are
`background_cohort_missing`, `binary_node_ground_truth_missing` and
`insufficient_whole_groups`.

## Evidence needed to finish

1. Independently supported action-intent annotations, with native publishing
   host, UUID, time/timezone, action and provenance. Verified benign examples
   are required. A node/anchor security target also needs an explicit rule
   connecting action evidence to the temporal node sample; Event and node
   labels cannot be interchanged.
2. Enough justified independent incident/background groups for three chronological
   partitions, with both known classes in each. Three groups is a minimum, not
   a guarantee of credible evaluation. The current conservative node pilot has
   one evaluation group; splitting it by row does not create independence.
3. An accepted background training cohort using that evidence, uniform metadata
   and availability review across the expanded cohort, followed by actual
   identity/context isolation checks and reproducible split export.

Another unlabeled archive or more GPU capacity does not itself resolve these
conditions. A different target or weaker labeling/evaluation assumptions require
discussion, not a silent completion of ML-02. Feature/model design follows valid
dataset preparation and the existing task prerequisites.

The relevant suite has **46 passing software tests**, including six added checks
for exact history bounds, future/gap rules, deterministic unknown decisions,
fabricated-label rejection, changed sources and pinned-spec audit integration.
