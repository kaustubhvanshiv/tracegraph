# Unknown-label background review and conservative grouping

This is the next evidence-preparation step after uniform metadata recovery.
The [measured result](../../../data/ml/datasets/darpa/node_benchmark/background_group_review_20261028.md)
records 500 review candidates from 7,034 observed nodes, one conservative
evaluation group for the current two cases, and 34 passing software checks.
It does not provide benign training labels or independent partitions.

## What is fixed before sampling

The [review plan](../../../data/ml/datasets/darpa/node_benchmark/background_review_plan_20261028.json)
declares host 1 and the half-open UTC window
`2019-05-07T13:05:00Z` to `2019-05-07T13:10:00Z`. The rationale is the ACT
report's first listed attack day being May 8, not an assertion that every earlier
action was benign. The operational log's documented clock reset affects host 2;
no timestamp correction is applied here and no complete calibration is claimed.

Selection never reads node-reference CSVs, native object kinds, metadata
completeness or security labels. All available audited source files whose Event
bounds intersect the declared host/window are read fully; the bounds alone are
not considered proof of continuous coverage. In this snapshot that means one
10-million-record archive. Complete record/type counts and source identity
guards are rechecked. This is coverage of the available local subset, not the
whole DARPA release.

The producer deduplicates selected native Event UUIDs and quarantines conflicting
payloads inside the selected window. Its frozen universe contains every node
observed in the remaining Event references. It does not import metadata-only
ancestors as review samples or infer node types from Event actions.

The seed is 42 and the review budget is 500. The ordering hashes the exact
canonical list `[seed, host_uuid, start_ns, end_ns, node_uuid, anchor_ns]`, with
`anchor_ns = end_ns - 1`. UUIDs are randomization/traceability keys, not future
predictive features. The auditor recomputes the complete ordering and selected
IDs independently. Every candidate's label stays NULL.

## Reproduce the pool

Prerequisites are the existing 37 downloaded archives, the completed reference
audit/cache and the downloaded support folder. No new dataset, PDF package,
database server, CUDA or model package is required by this producer. The ACT PDF
member and operational log are checked against their pinned hashes; source
documents are not executed or modified.

From the repository root:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.background_review `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --plan "data/ml/datasets/darpa/node_benchmark/background_review_plan_20261028.json" `
  --reference-audit ".cache/ml-runs/ml02-scp-all-references-20261027" `
  --support "D:/Deep Learning/darpa-tc-e5-support" `
  --output ".cache/ml-runs/background-review-pool-20261028-new"
```

Use a fresh output directory. Expected completion is
`complete_unknown_label_review_pool`, with 500 unknown candidates and zero
verified benign labels. Matching raw contents/window/seed reproduce the same
candidate IDs and file digest; file-identity/provenance reports are specific to
the validated local snapshot. A fresh Git clone requires the preceding raw-data
and audit steps; it does not contain these caches or databases. Do not bypass
fingerprint checks to substitute a different snapshot.

Local outputs:

| File | Purpose |
|---|---|
| `universe.jsonl` | All frozen native host/UUID/anchor identities |
| `review_candidates.jsonl` | The seeded subset, NULL labels and exact native Event witnesses |
| `manifest.json` | Source/support/plan hashes, complete-scan counts, time buckets and outcome |

Each witness records the original filename, 1-based raw record index, Event
UUID, native reference role and full canonical raw SHA-256. All 500 associations
in this run were independently verified against 497 distinct raw Events.
The original Event annotations remain unchanged. Candidate IDs and raw records
are local and ignored by Git; published files contain summaries and source pins.

## Interpret the group review correctly

The [group manifest](../../../data/ml/datasets/darpa/node_benchmark/group_review_20261028.json)
binds the exact current graph/case set and assigns both cases to one conservative
evaluation holdout group. It does not assert a common actor/campaign, create a
test partition or modify the original Event-level incident groups.

The ACT report explicitly links May 16 host-1 verifier persistence to the May 17
continuation. It also states that named threat actors were not simulated. Common
Drakon tooling or shared infrastructure is therefore not used as campaign proof.
Until independence is established, keeping the current cases together is safer
than claiming two independent units. This leaves only one evaluation group,
which cannot support three whole-group partitions.

The cached Subject-command review found two later host-1 `filemon` service
processes. Those times do not match the earlier documented benign setup and the
report includes starting the driver during the May 17 attack. They are not
automatically labeled benign or malicious. The group manifest preserves the
native references and source-page decisions.

The background pool is not independent merely because it precedes the attacks:
60 selected node identities recur in the existing pilot. Preserve the frozen
review draw. Future sample/entity/context overlap must be grouped or purged
before a split; do not redraw favorable examples after seeing annotations.

## Run the v2 audit

The [v2 policy](../../../data/ml/datasets/darpa/node_benchmark/preparation_protocol_v2_20261028.json)
retains the original label, uniform-metadata and 60/20/20 whole-group rules.
It adds required review-manifest checks. Accepted training background windows
remain empty: preparing an unknown-label pool is not accepting it for training.

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.audit_protocol `
  --protocol "data/ml/datasets/darpa/node_benchmark/preparation_protocol_v2_20261028.json" `
  --original-graph ".cache/ml-runs/compact-graphs-20261028/graph.sqlite" `
  --review-graph ".cache/ml-runs/uniform-metadata-20261028/graph.sqlite" `
  --recovery-report ".cache/ml-runs/uniform-metadata-20261028/manifest.json" `
  --event-gate "data/ml/datasets/darpa/split_gate_report_20261027.json" `
  --annotations "data/ml/datasets/darpa/review_annotations.json" `
  --background-review ".cache/ml-runs/background-review-pool-20261028-new/manifest.json" `
  --group-review "data/ml/datasets/darpa/node_benchmark/group_review_20261028.json" `
  --output ".cache/ml-runs/background-review-pool-20261028-new/protocol_audit.json"
```

The group review and graph fingerprints must correspond to your actual reviewed
artifacts; this run's public manifests identify this run's local databases.
For a rebuilt graph, recheck its provenance and scope and create the corresponding
review manifest rather than copying a foreign fingerprint as proof.

The auditor reads both graphs and existing review artifacts; it creates no new
candidates, labels, features or splits itself. It checks all candidate-file
digests, unknown labels, seeded ordering, native window scope and group coverage,
and measures identity overlap. Python exit code 2 is expected: four readiness
conditions remain unsatisfied. The updated
[audit summary](../../../data/ml/datasets/darpa/node_benchmark/background_group_protocol_audit_20261028.json)
records the existing review pool while its candidate-creation flag refers only
to the auditor's own read-only action.

Verification:

```powershell
research/ml/.venv/Scripts/python.exe -m unittest research.ml.tests.test_background_review research.ml.tests.test_review_inputs -v
```

These seven new checks cover native host/time filtering, conflict quarantine,
seeded reproducibility, witness selection, candidate-label protection, frozen
draw integrity and conservative group coverage/independence rules. The full
relevant graph/preparation suite has 34 passing software checks.

## Before any training use

Review action intent and native identity/time evidence in a separate annotation
artifact. Do not overwrite the frozen candidate file or set its unknowns to 0.
The present sources do not establish 500 benign examples. Any accepted expanded
training cohort also needs a frozen universe and uniform metadata/availability
checks; the existing metadata pass covers only the original two-case pilot.
Independent whole groups and a frozen history horizon are still required.
No model objective/architecture, new security labels or training is approved by
these diagnostic outputs.
