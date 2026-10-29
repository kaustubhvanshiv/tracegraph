# Separate label-free DARPA workflow

**Error analysis completed, 2026-10-29:** the frozen model's largest ten holdout
residuals account for 74.58% of squared error; 34 of 98 rows have raw profiles
seen in training. Thirty native source-linked review entries remain local,
with all security labels unknown. All 74 relevant software tests pass. See the
[diagnostic findings and reproduction steps](ERROR_ANALYSIS.md).

**GPU full run completed, 2026-10-29:** 200 epochs on the RTX 4050, with epoch
185 selected on development. Full-run histories and weights match across two
same-seed runs. Final holdout reconstruction MSE is 0.072373 versus the mean
baseline's 0.282538; MAE is 0.090200 versus 0.181020. All 68 GPU-environment
software tests pass. See [results/chart](../../../data/ml/datasets/darpa/label_free/gpu_training_result_20261029.md)
and [GPU reproduction commands](GPU_TRAINING.md). These are reconstruction results;
security labels remain unknown and the original supervised task is unchanged.

**Training-ready, 2026-10-29:** the autoencoder, training/configuration/runtime,
checkpointing and separate holdout evaluator are implemented. Two identical
real-data three-epoch smoke runs passed; all 65 relevant software tests pass.
That earlier CPU readiness milestone preceded full GPU training. See the
[training commands](TRAINING.md) and [task alignment/status](TASK_STATUS.md).

**Preparation completed on 2026-10-29:** 1,358 native actor-window samples,
62 numeric features, chronological actor-disjoint partitions and training-only
normalization. The independent verifier recomputed every vector and scaler
statistic. All 54 relevant software checks pass. See the
[measured result](../../../data/ml/datasets/darpa/label_free/preparation_result_20261029.md).

The user approved this separate route after supervised preparation could not
establish trustworthy binary labels. It uses the existing DARPA E5 FiveDirections
raw files. No additional dataset, model package, database server or GPU setup
is required for this preparation. The original supervised Event/node tracks,
their annotations and incomplete ML-02.4 status are preserved.

## Objective and interpretation

These vectors support a later label-free activity-reconstruction experiment.
A future reconstruction model would learn a vector representation without
attack/benign targets. This preparation does not choose, install or train that
model. Every `security_label` remains NULL, including training data. The early
collection period is not certified normal and may contain undocumented attacks.

Reconstruction error or novelty, if computed later, would mean unusual activity
relative to the fitted data. It would not by itself establish an attack,
attack probability, precision, recall, F1 or detection AUC. Suitable independent
security annotations and evaluation design would still be required for those
claims. No security score or threshold exists in this preparation.

## Fixed scope and features

The [frozen plan](../../../data/ml/datasets/darpa/label_free/preparation_plan_20261029.json)
uses host 1 and five nonoverlapping five-minute windows, with UTC intervals on
May 7, 2019:

| Role | UTC interval | Windows | Exported rows |
|---|---|---:|---:|
| Training | 13:05-13:20 | 3 | 1,184 |
| Development | 13:25-13:30 | 1 | 76 |
| Holdout | 13:35-13:40 | 1 | 98 |

The intervening five-minute periods are purge gaps. Selection uses native host
and time coverage, never attack annotations, reference membership or metadata
completeness. File bounds select sources; the complete selected streams are
read and checked. Bounds and observed activity do not prove continuous release
coverage or calibrated clocks. Native timestamps are unchanged.

A row is one native CDM `Event.subject` UUID on its publishing host in one
five-minute window. Subjects may be threads; no PID or process-root inference
is made. The anchor is the window end minus one nanosecond. Only Events inside
that half-open window contribute to the row.

The **62 predictors** are:

- One total Event count.
- 56 action counts from the downloaded schema's fixed `EventType` vocabulary.
- One unknown-action count, without learning vocabulary from held-out data.
- Three structural counts: predicate references, Events with a second predicate,
  and Events with no predicate.
- One active-span duration in seconds, from the first to last contributing Event.

No UUID value, PID/CID, absolute timestamp, hostname, command line, path, source
position, label, case ID or offline entity definition is a predictor. UUIDs
are used only for deduplication, row grouping, partition ownership and trace
evidence. This is a numeric activity-vector route, not the earlier node-centered
graph representation or a GNN implementation.

## Split and scaling rules

Each native actor belongs to the earliest selected partition in which it is
observed. Its later-partition rows are excluded. This retains repeated windows
of an actor within training, while preventing the same sampled actor ID from
appearing across partitions. It removed 112 development and 105 holdout rows.
This biases later data toward newly observed native actors, potentially threads;
it does not prove unseen-process or incident generalization.

Common referenced objects remain: training/development share 634 object IDs,
training/holdout 1,059, and development/holdout 440. Identical raw numeric
profiles also recur across partitions. Object IDs are not predictors and there
are no borrowed graph embeddings, but related activity can remain correlated.
Do not describe these partitions as fully context-isolated, independent attack
incidents or a benchmark across hosts.

Each nonnegative feature receives `log1p`, followed by population z-score
normalization fitted on training rows only. Development/holdout reuse those
parameters unchanged. Thirty training columns are constant and use scale 1;
they remain in the fixed schema. Future novelty in such columns is not an
attack label. Model selection should use development data; preserve the holdout
for its declared final reconstruction check, with these limits reported.

## Reproduce

Use the existing ML environment from the repository root. Prerequisites are the
downloaded gzip files and completed reference audit. Use a fresh output folder:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.label_free.prepare `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --plan "data/ml/datasets/darpa/label_free/preparation_plan_20261029.json" `
  --reference-audit ".cache/ml-runs/ml02-scp-all-references-20261027" `
  --output ".cache/ml-runs/label-free-darpa-20261029-new"

research/ml/.venv/Scripts/python.exe -m research.ml.label_free.verify `
  --directory ".cache/ml-runs/label-free-darpa-20261029-new" `
  --plan "data/ml/datasets/darpa/label_free/preparation_plan_20261029.json" `
  --output ".cache/ml-runs/label-free-darpa-20261029-new/verification.json"
```

The completed run is local under
`C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\label-free-darpa-20261029`:

| File | Meaning |
|---|---|
| `train.jsonl`, `development.jsonl`, `holdout.jsonl` | Ordered rows, raw and normalized vectors, native trace, NULL security label |
| `feature_schema.json` | Exact feature order and units |
| `scaler.json` | Training-only transform parameters and constant columns |
| `events.sqlite` | Bounded native deduplication/verification index; no database service needed |
| `manifest.json` | Counts, scope, source/output fingerprints and limitations |
| `verification.json` | Independent SQL feature, trace, ownership and scaling checks |

The producer uses at most a 2 GiB SQLite index and 100,000 actor-window states;
it requires 3 GiB free working space and fails rather than silently subsampling
or relaxing disjointness. Event UUID/content conflicts are quarantined inside
the full selected time envelope, including purge gaps. It checks gzip exhaustion,
complete record/type counts and unchanged audited source sizes/times. These
support local reproducibility, not publisher authenticity or release-wide
deduplication. No raw archive is edited or copied into Git.

All feature rows, trace data, scaler and database stay under ignored `.cache`.
Code, plan and count/fingerprint summaries are published. There is no stochastic
operation: identical inputs produce the same ordered vectors and file hashes.
Small Avro integration fixtures check two-run reproducibility; the real output
is independently recomputed from its saved native Event index, not a second
complete raw-data extraction.

## Verify and continue

```powershell
research/ml/.venv/Scripts/python.exe -m unittest research.ml.tests.test_label_free -v
```

The eight new software checks cover unknown-label rules, temporal boundaries,
source completeness, duplicate/conflict quarantine, deterministic artifacts,
actor ownership, training-only scaling, resource guards and independent detection
of relabeled/tampered vectors, scaler statistics or concealed shared context.

**Preparation and training-readiness tasks are complete.** The reviewed model,
loss and configuration are in the [training specification](TASK_SPEC.md).
Full GPU training and final reconstruction evaluation are also complete; use
the [GPU instructions](GPU_TRAINING.md) to reproduce them.
No detection-performance claim follows from the prepared rows or software-test count.
