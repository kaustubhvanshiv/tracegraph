# ML-03.1 — classical baseline feasibility

Decision on 2026-10-11: **a supervised classical baseline is not justified
with the current labeled subset**. No classifier, model checkpoint or baseline
metrics are produced. This decision can be revisited when ML-02 provides
adequate labels and valid partitions; it does not rule out tabular methods for
the complete DARPA dataset.

## Evidence

The target is whether a unique CDM Event is a documented ACT attack action.
The [label contract](../../../data/ml/ground_truth.md) excludes unknown events
from supervised loss and binary metrics.

The [preparation manifest](../../../data/ml/datasets/darpa/preparation_review_manifest.json)
contains three selected review events: **one report-reviewed positive, zero
verified negatives and two unknowns**. They are related to one campaign, not
independent examples suitable for different partitions. Selection by known
attack artifact also makes these events an evidence-review sample, not a
representative classification dataset.

The [full reference audit](../../../data/ml/datasets/darpa/full_reference_report.json)
decoded 60 million records, including 58,037,343 Events. Large raw event counts
do not supply ground truth. Missing actor, Host and Principal definitions limit
feature coverage. The documented benign driver setup is outside the downloaded
event ranges; see the [reference review](../../../data/ml/datasets/darpa/reference_review.md).

## Why training would not provide a useful comparison

- There are no verified negative examples from which to learn or measure false
  positives. Unknown events cannot be substituted for negatives.
- One positive campaign cannot populate independent train, validation and test
  partitions. Splitting its three related actions would leak incident evidence.
- There are no valid prepared splits. Threshold selection and held-out precision,
  recall, F1, PR-AUC, ROC-AUC, false positives and false negatives cannot be
  evaluated meaningfully under the required protocol.
- Artifact names, UUIDs and report markers were used to select/review these
  samples. Feeding them to a model would encourage memorization of the label
  evidence rather than testing generalization to new incidents.

An always-positive predictor, an arbitrary rule score, or a toy synthetic
classifier would not establish a DARPA attack-detection baseline here.

## Conditions for revisiting ML-03.2 and ML-03.3

First establish verified positive and benign events with recorded evidence,
adequate independent incident/benign groups, and chronological partitions
containing both classes. Apply the ML-02 context-overlap checks and inspect
achieved counts and annotation coverage before choosing a model.

A later feature assessment can consider event-type frequencies over a fixed
past-only window, time since the preceding event, and per-entity occurrence
counts. These features are conditional on reliable entity resolution and
event-time semantics. No features have been engineered at this stage. Raw
graph adjacency, labels, annotation fields, UUIDs, exact generated filenames,
future events and test-derived statistics must not be inputs. Severity and
rule-signal features require a separate availability and circularity review.

If a baseline becomes useful, use at most one allowed classifier, fit all
preprocessing on training only, tune thresholds on validation, and reserve
test for the final evaluation. A stochastic seed cannot repair missing labels
or invalid partitions.

## Reporting and next task

The final ML-09 comparison must explicitly state that the classical learned
baseline was omitted because the current annotation coverage did not support
training and independent evaluation. It must not present this omission as
evidence that a GNN performs better. The deterministic correlation baseline
remains a separate planned comparison.

ML-03.1 is complete; optional ML-03.2 and ML-03.3 are deferred. ML-02 remains
incomplete. ML-04 can proceed on a clearly identified synthetic toy dataset
to demonstrate tensors, forward/loss/backpropagation, minibatch training and
validation monitoring. Its results will not be security-detection metrics.
