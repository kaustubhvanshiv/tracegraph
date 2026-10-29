# Frozen-model reconstruction error analysis

**2026-10-29: completed the next post-evaluation step.** The trained checkpoint,
configuration and preprocessing remain frozen. All 1,358 actor-window rows were
scored for numerical diagnostics; their aggregate errors reproduce the already
recorded training/development/final-evaluation metrics. No training, security
label assignment, threshold choice or production integration occurs here.

See the [measured findings and chart](../../../data/ml/datasets/darpa/label_free/error_analysis_20261029.md)
and [machine-readable analysis](../../../data/ml/datasets/darpa/label_free/error_analysis_report_20261029.json).

## Findings

Holdout per-row MSE has median **0.014623**, 95th percentile **0.449588** and
maximum **0.922778**. The worst five rows contribute 57.43% of squared residual,
and the worst ten contribute **74.58%**. The mean 0.072373 therefore hides a
concentrated tail; these descriptive percentiles are not security thresholds.

The largest holdout numerical residual shares are `count_EVENT_SIGNAL` (16.39%),
`count_EVENT_CREATE_THREAD` (9.12%), `count_EVENT_EXECUTE` (8.94%),
`count_EVENT_LOADLIBRARY` (8.55%) and `active_span_seconds` (7.31%). This is
arithmetic decomposition of squared reconstruction error, not causal feature
importance or evidence that these operations are attacks. Some large residuals
concern features whose observed raw count is zero: decoder estimates are not
additional native Events and must not be converted into graph evidence.

Of 98 holdout rows, 34 have an exact raw feature profile present in training;
their average MSE is 0.005589. The other 64 average 0.107852. This describes a
narrow numeric overlap, not proof of memorization or independent generalization.
Different raw profiles can still share object context, process families or
incident activity. The earlier actor-ownership filter also changes populations.

## Local review queue

`review_queue.jsonl` contains the ten highest-error rows from each partition,
**30 rows total**, ranked by descending MSE with sample-ID tie breaking. This
is a review budget, not an alarm cutoff. Every row retains NULL security intent.
Each entry includes:

- Sample/window and native publishing-host/actor trace keys.
- Reconstruction MSE/MAE and the mean-reference MSE for that row.
- Five largest residual features, their raw observed aggregates, normalized
  observations and normalized decoder estimates.
- An exact native witness Event UUID, action, timestamp, archive, 1-based record
  position and original raw-record fingerprint from the saved Event index.

All 30 witness references were checked against that read-only native index.
This validates traceability, not action intent or every Event in a window. No
new raw-archive scan was performed. Full traces and individual observations stay
in ignored `.cache`; public outputs contain aggregate statistics only.

The completed local output is:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\label-free-error-analysis-20261029
```

Open its `review_queue.jsonl` to inspect source evidence. A high-error row is
neither a verified attack nor a false positive; a low-error row is not verified
benign. Independent security evidence is still required for those decisions.

## Reproduce

Use the previously prepared data and completed full CUDA run/evaluation.
The existing GPU environment already has all required analysis dependencies.
Choose a fresh output directory:

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m research.ml.label_free.error_analysis `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --run ".cache/ml-runs/label-free-gpu-20261029/full-a" `
  --evaluation ".cache/ml-runs/label-free-gpu-20261029/full-a/holdout_evaluation.json" `
  --output ".cache/ml-runs/label-free-error-analysis-new"

research/ml/.venv/Scripts/python.exe -m research.ml.label_free.plot_error_analysis `
  --report ".cache/ml-runs/label-free-error-analysis-new/analysis.json" `
  --output ".cache/ml-runs/label-free-error-analysis-new/chart.png"
```

The plot uses the existing optional Matplotlib environment. The analysis checks
the frozen run/evaluation/checkpoint/config/code/data/feature/scaler provenance,
reproduces the frozen aggregate errors, verifies native witnesses and checks
unchanged weights, Event index and prepared partition fingerprints afterward.
No optimizer is instantiated. The original final evaluator and training code
were not modified to perform this analysis.

Quantiles use linear interpolation at `(n-1)*q`. Per-row and per-feature
statistics use compensated Python sums of float32 residuals; tiny rounding
differences from the GPU's aggregate reduction are expected. The source metrics
must reproduce within a fixed numerical tolerance before diagnostics succeed.

## Task alignment and next-use limits

This completes LF-05, the label-free counterpart of the project's error-analysis
and evaluation-limitations principles. It does not complete original ML-08's
GNN false-positive/false-negative analysis, since binary security labels and the
specified GNN experiment are absent. No existing supervised/GNN task is checked
off, and no model is integrated into production.

The final holdout is now evaluated and inspected. Any later tuning based on
these diagnostics is exploratory unless assessed with fresh suitable evaluation
data. Do not tune against these rows and then claim an untouched holdout result.
No new model, dataset or label policy was selected during this step.

All **74 relevant software tests pass** in the CUDA environment. Six new checks
cover quantile/decomposition correctness, exact-profile grouping, native-witness
integrity, immutable-model/NULL-label end-to-end behavior, and rejection of
altered final metrics or run bindings. These are software checks, not detection
accuracy measurements.
