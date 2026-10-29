# DARPA FiveDirections: label-free reconstruction experiment

Experiment date: **2026-10-29**. This report consolidates the user-approved
label-free DARPA route. A feedforward autoencoder reconstructed 62 native
activity features, with lower MSE/MAE than a training-mean reference on the
limited final holdout. The result establishes an executable, reproducible local
reconstruction pipeline; attack-detection performance has not been measured.

The [generated results table](../../../data/ml/datasets/darpa/label_free/results_table_20261029.md)
and [linked experiment summary](../../../data/ml/datasets/darpa/label_free/experiment_summary_20261029.json)
come directly from the saved evidence. Use the [reproduction guide](REPRODUCING.md)
for commands and required local inputs.

## Dataset, source and selection

The dataset is **DARPA Transparent Computing Engagement 5**, FiveDirections
Windows telemetry, using gzip-compressed Avro/CDM records. The project's
[dataset selection rationale](../../../data/ml/comparison/primary_dataset_selection.md)
records why typed process/object activity fits TraceGraph's provenance work.
That earlier document describes a smaller historical download; this experiment
uses the later audited inventory and counts below. This pilot did not establish
a dataset-specific redistribution licence.

The source directory on this machine is:

```text
D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections
```

The acquisition directory is named with a 2026-10-10 download timestamp; this
experiment was prepared/trained on 2026-10-29. Recorded dataset-source links are
in the [dataset catalogue](../../../data/ml/datasets/README.md). No new website research, download
or release-wide authenticity check was performed for this consolidation.

The inventory has 37 local archives. The fixed experiment selects the complete
`ta1-fivedirections-1-e5-official-1.bin.gz` archive: 308,986,723 compressed bytes,
10,000,000 decoded records, including 9,572,528 Events. These counts describe
that archive, not the complete DARPA release or the number of training rows.
The selected actor windows contribute 444,011 native Events to **1,358 rows**.

Host scope is `2ab88dcdcbe641dfac699f6d6058e398` on May 7, 2019. Native subject
UUIDs may identify threads; no process-root resolution is claimed. All
`security_label` values remain unknown, including the training partition.
The period is not certified benign. Original supervised evidence still lacks
eligible benign examples and independent incident coverage, which is why the
user approved this separate objective.

## Problem and representation

For each native `(host, Event.subject, five-minute window)`, reconstruct its
observed numeric activity vector. The input is also the reconstruction target.
There are no attack/benign targets, inferred pseudo-labels or security threshold.

This route uses **vectors**, not graph message passing. Native UUIDs group
Events and preserve traceability; no adjacency matrix, node/edge embeddings,
GNN layers or graph pooling enter the autoencoder. Prior node-benchmark graph
artifacts are a separate track.

For contributing Events `E` and fixed schema action vocabulary `A`, features are:

| Feature group | Count | Derivation |
|---|---:|---|
| `event_count` | 1 | Number of contributing native Events |
| `count_EVENT_*` | 56 | For each `a` in `A`, number of Events with native action `a` |
| `count_unknown_action` | 1 | Number of Events whose action is outside `A` |
| `predicate_reference_count` | 1 | Sum of present first and second predicate references over Events |
| `second_predicate_event_count` | 1 | Number of Events with a second predicate |
| `no_predicate_event_count` | 1 | Number of Events with neither predicate |
| `active_span_seconds` | 1 | `(max(timestampNanos)-min(timestampNanos))/1e9` |

The fixed action vocabulary/order is in the [preparation plan](../../../data/ml/datasets/darpa/label_free/preparation_plan_20261029.json).
UUID values, PIDs, paths, command lines, absolute timestamps, source positions,
case IDs, labels and entity-metadata availability are excluded from predictors.
Count features are correlated by construction; equal feature weighting should
not be interpreted as equal semantic importance.

## Preprocessing and partition design

Each raw nonnegative feature receives `log1p`, then population z-score scaling
using training-only means/deviations. Development and holdout reuse those
statistics. Thirty training-constant columns retain scale one and remain in
the 62-feature loss denominator. No scaler is fitted during scoring.

| Partition | UTC interval on 2019-05-07 | Five-minute windows | Rows |
|---|---|---:|---:|
| Training | 13:05–13:20 | 3 | 1,184 |
| Development | 13:25–13:30 | 1 | 76 |
| Holdout | 13:35–13:40 | 1 | 98 |

Five-minute purge gaps separate partitions. Native actors belong to the first
selected partition in which they appear; later-partition rows are excluded.
This removed 112 development and 105 holdout rows and gives zero sampled actor
ID overlap. Repeated actor windows remain within training. Later partitions are
therefore biased toward newly observed actors, potentially threads.

This is not full context isolation: referenced-object overlaps are 634 for
train/development, 1,059 for train/holdout and 440 for development/holdout.
Thirty-four of 98 holdout rows also have an identical raw feature profile in
training. Same-host/day activity can remain correlated despite actor separation.

## Algorithm and optimization

The **feedforward autoencoder** is:

```text
Linear(62,16) → ReLU → Linear(16,4) → Linear(4,16) → ReLU → Linear(16,62)
```

It has 2,210 trainable parameters. The four-dimensional bottleneck and output
are linear; no graph layers, dropout or batch normalization are used. Adam is
the optimizer, not a second learning model. Configuration: learning rate 0.001,
weight decay 0.0001, batch size 64, seed 42, float32, up to 200 epochs and
patience 20 with minimum improvement 1e-6. See the
[frozen CUDA configuration](training_config_cuda.json) and [task specification](TASK_SPEC.md).

Training minimizes MSE averaged over rows and all 62 normalized features.
Development MSE selects the checkpoint, including initialization as epoch zero.
The run reached 200 epochs/3,800 updates; epoch **185** was selected. The final
holdout was read after selection and the same-seed repeatability check. Later
diagnostics/replay inspected it; it must not now be reused as untouched evidence
for tuning.

## Reference, metrics and results

The reference reconstructs every row as the normalized **training mean vector**.
It is fitted only on training data. One neural model and one constant reference
were measured; no three-model benchmark or best architecture claim is supported.
TraceGraph's deterministic `combined_score` answers a different question and
was not treated as a reconstruction predictor or attack ground truth.

MSE matches the optimization objective; MAE supplies a complementary absolute
error measure. Both use normalized feature space. Security precision, recall,
F1, ROC/PR AUC, false positives/negatives and detection latency are unavailable
without a validated security target and suitable evaluation design.

| Partition | Rows | Autoencoder MSE | Autoencoder MAE | Mean reference MSE | Mean reference MAE |
|---|---:|---:|---:|---:|---:|
| train | 1,184 | 0.110711493 | 0.100859731 | 0.516129017 | 0.215315059 |
| development | 76 | 0.033141211 | 0.066414706 | 0.147637546 | 0.164320454 |
| holdout | 98 | 0.072372757 | 0.090199672 | 0.282537609 | 0.181020141 |

MSE/MAE average errors in normalized feature space. These are the original frozen
results, not replay-rounded replacements or attack-detection metrics. The mean
reference is fitted on training only. No rule/GNN security comparison is claimed.

Holdout MSE is about **74.38% lower** than the training-mean reference. This is
a relative reconstruction-error reduction, not 74.38% detection accuracy.
Metrics from different devices/row-reduction orders can differ slightly;
the generated table preserves the original frozen evaluation values.

## Error analysis

The ten largest holdout row errors account for **74.58%** of squared residual;
five account for 57.43%. Median row MSE is 0.014623, the 95th percentile is
0.449588, and maximum is 0.922778. These are descriptive values, not alarm cutoffs.

The largest residual shares are SIGNAL count (16.39%), CREATE_THREAD count
(9.12%), EXECUTE count (8.94%), LOADLIBRARY count (8.55%) and active span (7.31%).
They decompose numerical error and do not establish causality or maliciousness.
Decoder estimates are not observed native Events and must not become graph
evidence. The 34 holdout rows whose raw profiles also appear in training have
mean MSE 0.005589; the other 64 have mean 0.107852. This descriptive overlap
does not by itself prove memorization or independent generalization.

Thirty local review entries retain native witness references and unknown
intent. Witnesses were checked against the saved Event index, not newly
reread from the raw archive. See [error analysis](ERROR_ANALYSIS.md).

## Execution and reproducibility evidence

Training used an RTX 4050 Laptop GPU (6 GB), Python 3.11.9, PyTorch
2.15.0+cu132 and compiled CUDA 13.2. Model/tensors were on `cuda:0`, with
deterministic algorithms and highest float32 matmul precision. Two full runs
matched complete loss histories and selected model states exactly on this
runtime. This does not guarantee bitwise equality across other hardware.

The primary synchronized training loop took 7.40 seconds including per-epoch
metrics/checkpoints; the training function took 10.81 seconds including setup
and transfers. These exclude installation/import and do not measure a GPU
speedup or end-to-end detection latency.

All 1,358 existing rows reproduced the frozen metrics during CPU/CUDA scoring
within declared tolerances. The independent CPU-only build reproduced all 98
holdout row scores against CPU execution of the CUDA build. The local frozen
bundle is 39,525 bytes; weights and individual rows stay outside GitHub.
See [offline scoring](INFERENCE.md).

The handoff independently recomputed every vector/scaler from the saved native
Event index and regenerated the results table from linked public reports.
It did not repeat a complete raw extraction or train again. Exact local
artifact reproduction and instructions are documented; an independent
clean-machine reproduction has **not** been performed.

All **85 relevant software tests pass**, including three reporting checks for
known frozen results, inconsistent evidence and unsupported policy changes.
These checks validate software behavior, not security detection accuracy.

## Conclusions and remaining gates

This limited pilot supports native feature extraction, verified preprocessing,
development-based selection, deterministic local training, final reconstruction
evaluation, traceable residual analysis and frozen checkpoint reuse. It does
not establish security effectiveness, independent incident/host generalization,
benign training data, attack probabilities or a deployable detector.

LF-01 through LF-07 of this separate route are complete. Original supervised
ML-02.4 remains incomplete, GNN experiments/comparison remain deferred, and
ML-10 production integration has not started. The original ML-11 GNN research
requirements are not marked complete by this vector report.

Further detector work needs trustworthy label evidence and independent incident
coverage. New model comparisons, other hosts/representations or production
integration require the user's next scope decision. The current report does
not authorize or silently select those experiments.
