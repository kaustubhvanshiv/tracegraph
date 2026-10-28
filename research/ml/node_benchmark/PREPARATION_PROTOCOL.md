# DARPA metadata, background and split protocol v1

Reviewed on 2026-10-28 against Requirement ML-02, tasks ML-02.1/02.2/02.4 and
the design's ML evaluation checks. These require a written sample/label contract,
incident isolation and reproducible preparation before training. This document
defines the node-pilot preparation rules; it does not replace the original
[Event-level ground truth](../../../data/ml/ground_truth.md) or activate a model.

The [machine-readable policy](../../../data/ml/datasets/darpa/node_benchmark/preparation_protocol_v1_20261028.json)
and [measured audit](../../../data/ml/datasets/darpa/node_benchmark/preparation_protocol_audit_20261028.json)
make this review repeatable. The review is complete; the current dataset is
not ready for binary supervised training or actual partition export.

**Latest review:** the [background/grouping step](BACKGROUND_REVIEW.md) prepared
500 unknown-label review IDs and accepted a conservative single evaluation group
for the current pilot. Sixty selected identities recur in the attack pilot;
no independence or benign-intent claim follows. The
[v2 audit](../../../data/ml/datasets/darpa/node_benchmark/background_group_protocol_audit_20261028.json)
has four remaining readiness gaps. The original label and split rules below
are retained; v2 adds review-input checks rather than relaxing them.

**Subsequent implementation:** the [uniform metadata pass](UNIFORM_METADATA.md)
has now completed for the frozen pilot universe. It resolves 45,806 additional
types, including 45,782 unlisted nodes, and clears the metadata-selection blocker.
The [updated audit](../../../data/ml/datasets/darpa/node_benchmark/uniform_protocol_audit_20261028.json)
still finds five other gaps. The initial comparison below records the earlier
targeted review; the uniform pass is the current metadata artifact.

## 1. Keep reference membership separate from security ground truth

| Evidence state | Stored reference label | Meaning |
|---|---:|---|
| Listed UUID, exact publishing host and matching native kind | 1 | Supported membership in that published case list |
| Unlisted UUID | NULL | Unlisted; benign/attack intent is unknown |
| Listed but missing, conflicting or mismatched native type | NULL | Reference mapping remains unresolved |
| Node occurs in a case window | No label implied | Temporal proximity is not attack intent |
| Node drawn for background review | NULL | Review candidate; not a verified negative |

The graph currently has 45 accepted reference matches and **295,397 unknown
node labels**. Of those unknowns, 295,395 are unlisted and two are listed UUIDs
with absent Subject definitions. The other 46 published references outside this
pilot are not negative examples either. None of these counts supplies reviewed
binary node attack/benign truth.

Any future binary node labels require a separate reviewed evidence file with
the native host/UUID, anchor/window, incident/background group, intended label,
source citation and native time/identity justification. A reviewer must establish
the intent and granularity; do not copy an Event's label to every connected node
or declare an entire process lifetime benign from one normal action. Conflicts,
ambiguous clocks and unsupported mappings stay unknown. That new evidence must
be accepted before classification labels or metrics are produced.

The original Event track is separate: its existing gate still has three eligible
attack actions in two groups and zero eligible benign actions. This review does
not relabel any of its six annotations or complete ML-02.4.

## 2. Make metadata recovery independent of labels

The prior follow-up intentionally repaired published reference UUIDs. It is
useful for evidence review, but the extra metadata must not determine model
sampling, features or which edges are usable before uniform recovery:

| Observed membership | Baseline resolved / nodes | After review resolved / nodes |
|---|---:|---:|
| Listed UUIDs present in the graph | 21 / 47 | 45 / 47 |
| Unlisted UUIDs | 221,337 / 295,395 | 221,337 / 295,395 |

All 24 targeted-review changes were to listed nodes. That graph's 1,153,107 usable
relations are therefore an evidence-quality diagnostic, not a training graph.
The original graph is preserved, but its case-conditioned sampling still does
not provide a representative background cohort or sufficient partitions.

After the later uniform pass, resolved types are 45 / 47 listed nodes and
267,119 / 295,395 unlisted nodes. Unknown labels remain unchanged. The scope
requirement is now met inside this existing pilot; metadata availability at a
prediction anchor and the other preparation rules still need evidence.

Use this order for future preparation:

1. Freeze the audited source snapshot and host/time windows without consulting
   node-reference membership. Record partial-release/missing-fragment limits.
2. Enumerate **all observed nodes** in those windows, including unknown nodes.
   Freeze a digest of this universe before joining reference CSVs.
3. Apply the same definition-search scope to every node: exact publishing host
   plus native UUID, validated cached definitions and complete selected source
   streams. Preserve source positions and conflicts; never fill types from paths,
   PIDs, names, CSV descriptions or Event actions.
4. Retain missing/conflicting metadata as unknown. A later exclusion rule must
   apply identically to listed and unlisted nodes, with counts by host/window.
5. Join references only after inventory/recovery and candidate-selection rules
   have been fixed. Keep reference fields outside predictive inputs.

Past-only predictive fields require defensible availability at or before the
sample anchor. A process chain must have valid native starts before its Events.
A global offline metadata join is not proof of arrival-time availability. If a
field's availability cannot be justified, exclude that field or sample until the
rule is reviewed; do not silently use later definitions or mutable properties.

## 3. Draw background review candidates without manufacturing negatives

Choose host/time windows using source coverage and documented activity review,
before node labels are joined. Record the exact raw integer-nanosecond bounds,
available fragments, observed activity and clock findings. File min/max bounds
alone prove neither continuous coverage nor benign intent. Documented attack and
persistence contexts, including an eventual history/purge margin, are excluded
from a background-review pool; absence of a known attack still does not prove
the remaining pool is benign.

For a frozen host/window, the sample unit is
`(incident_or_background_group, host_uuid, native_node_uuid, anchor_nanos)`.
Use `anchor_nanos = window_end_nanos - 1`; the window is half-open. Observe nodes
only through native Events in the declared window. Metadata-only ancestors may
be context, not extra labeled samples.

The planned graph unit is a node-centered temporal native-reference subgraph
ending at that anchor, using only Events from `[anchor - W, anchor]` and valid
native process/principal context inside its partition. It preserves CDM reference
roles rather than inventing information-flow directions. The history `W` and
final neighborhood bounds must be fixed in the task/input specification before
this becomes an executable feature input; neither has been fabricated here.

The review-draw rule is deterministic: seed **42**, maximum **500 candidates per
host/window**, ordered by the SHA-256 hex digest of the UTF-8 canonical JSON list
`[seed, host_uuid, start_ns, end_ns, node_uuid, anchor_ns]` using compact separators.
Break digest ties by the host/UUID/anchor key. Apply this before consulting
reference membership, recovered type or metadata-completeness status. Record
the candidate IDs and selection manifest once; do not redraw after seeing labels.
These are review-budget settings, not an experiment or a model hyperparameter.

Every candidate starts NULL. Only reviewed, correctly mapped evidence can
supply a classification label. Report the review yield and unknown/exclusion
counts; do not feed unreviewed nodes to the original pipeline as label 0.
There are currently **no accepted training background windows**. A separate
500-ID unknown-label review draw is now prepared; it is not an accepted training
cohort. Controlled Task 29 scenarios may supplement evaluation when
validated; they do not supply missing native DARPA labels.

## 4. Split whole groups chronologically

Retain the existing **60/20/20 target** for train/validation/test, by ordered
whole incident or verified background groups. Exact achieved proportions must
be reported, not forced by slicing rows inside an incident.

- Review campaign, persistence, cross-host and overlapping causal-context links
  first; merge inseparable activity into one group. Distinct CSV names or hosts
  are not sufficient proof of independence.
- Shared immutable Host/Principal lookup metadata alone is not a campaign link.
  Audit actual sampled/behavioral context and incident evidence; merge or purge
  overlapping contexts rather than treating every activity on one host as a
  single attack merely because it uses the same metadata dictionary.
- Keep every positive incident and all anchors of the same native entity/context
  together. Deduplicate sample/Events and quarantine payload conflicts first.
- Require `max(train time) < min(validation time)` and
  `max(validation time) < min(test time)` after purging. The gap must cover the
  actual history horizon, and each context graph must stay inside its partition.
- Freeze the history horizon before graph construction. It remains unset in
  v1 because the task/input history has not been accepted; zero-gap export is
  not an acceptable substitute. No GNN architecture is selected here.
- Construct separate graphs; no held-out edges, shared sample/context identities
  or positive incident IDs may enter training. Record cross-partition identity
  and context checks even when exact UUID overlap is zero.
- Fit vocabularies, scalers and any learned sampling statistics on training only.
  Select thresholds/choices on validation. Lock test for final evaluation.
- Every evaluated binary partition needs both known classes and documented
  independent groups. Random per-event/node splitting is disallowed. Two current
  case windows give an upper bound of two groups, which cannot fill three splits.

Raw UUIDs/source positions remain traceability keys. Reference membership,
annotation filenames/rows, incident/case/split IDs, metadata-repair target flags,
future attributes and held-out fitted statistics are excluded predictors.
Feature engineering and model choice remain later tasks. No binary precision,
recall, F1, PR-AUC or ROC-AUC is reported from reference-only/unknown data.

## 5. Reproduce the initial review and interpret its result

From the repository root, use the existing Python environment:

This command reproduces the initial v1 review with the targeted repair artifact.
For the current v2 review with the uniform graph and separate review manifests,
use the command in [the background/group guide](BACKGROUND_REVIEW.md).

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.audit_protocol `
  --protocol "data/ml/datasets/darpa/node_benchmark/preparation_protocol_v1_20261028.json" `
  --original-graph ".cache/ml-runs/compact-graphs-20261028/graph.sqlite" `
  --review-graph ".cache/ml-runs/compact-metadata-recovery-20261028/graph.sqlite" `
  --recovery-report "data/ml/datasets/darpa/node_benchmark/metadata_recovery_report_20261028.json" `
  --event-gate "data/ml/datasets/darpa/split_gate_report_20261027.json" `
  --annotations "data/ml/datasets/darpa/review_annotations.json" `
  --output ".cache/ml-runs/node-protocol-review-20261028-new/audit.json"
```

Use a fresh report path. This command needs only the Python standard library.
It checks graph fingerprints/integrity, reads both databases read-only, measures
metadata scope and verifies unchanged Event annotation provenance. It does not
reread the raw archives, draw candidates, assign labels, build features, create
partitions or train. Python exit code **2** means the completed review found
preparation blockers. Exit code 0 would only mean no implemented blocker fired;
it would not approve future labels, partitions or training.

The initial six blockers included annotation-directed metadata, cleared by the
uniform pass. The conservative grouping review subsequently supplies a safe
one-group constraint for the current cases. The current four gaps are an
accepted background training cohort, binary node ground truth, sufficient
independent whole groups and a frozen history horizon. The unknown-label pool
does not resolve those gaps. More raw downloads alone are not a label or group
fix; this review requests no additional download.

Verification:

```powershell
research/ml/.venv/Scripts/python.exe -m unittest research.ml.tests.test_node_protocol -v
```

The frozen pilot inventory, uniform metadata and initial background/group review
are implemented. Further preparation requires reviewed action-intent evidence
and justified independent groups, freezing any expanded cohort before applying
the same metadata rule.
Candidate windows, new labels and actual partitions must be checked under this
contract before feature or training implementation. The audit itself creates
only a diagnostic JSON.
