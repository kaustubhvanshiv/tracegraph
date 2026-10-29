# Teammate reproduction and handoff

Run from the repository root on branch `deeplearning/shlok`. This guide
separates reproducing published results from rerunning training or raw
preparation. No new model, threshold or dataset is needed for the handoff.
Read the [final report](FINAL_REPORT.md) before interpreting the scores.

## 1. Rebuild the published results table

This command needs only the repository reports/configuration and Python 3.11;
it does not import PyTorch or access raw data, sample rows or weights:

```powershell
python -m research.ml.label_free.report `
  --reports "data/ml/datasets/darpa/label_free" `
  --config "research/ml/label_free/training_config_cuda.json" `
  --output ".cache/ml-runs/teammate-results-new"
```

Use the repository's existing Python executable if `python` is not configured,
for example `research/ml/.venv/Scripts/python.exe`. Choose a fresh output path.
The result is `summary.json` and `results_table.md`. The command cross-checks
dataset/verification/config/run/evaluation fingerprints, checkpoint identity,
counts, unknown-label/scaler policy, and diagnostic/replay metric agreement.
It reads measured values instead of substituting hand-entered results.
Conflicting evidence fails before outputs are written. This is report
reconstruction, not a fresh model evaluation.

The committed [results table](../../../data/ml/datasets/darpa/label_free/results_table_20261029.md)
and [summary](../../../data/ml/datasets/darpa/label_free/experiment_summary_20261029.json)
were generated this way. Their source reports remain historical records;
older software-test totals refer to those milestones.

## 2. Check the prepared local dataset

Required local inputs are the completed preparation directory and native
`events.sqlite`; these are ignored files and do not arrive through Git.
Recompute the saved vectors/scaler using read-only SQL and a new report path:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.label_free.verify `
  --directory ".cache/ml-runs/label-free-darpa-20261029" `
  --plan "data/ml/datasets/darpa/label_free/preparation_plan_20261029.json" `
  --output ".cache/ml-runs/teammate-check-new/verification.json"
```

Expected: 1,358 vectors, 62 features, partition counts 1,184/76/98, zero sampled
actor overlap and unknown security labels. This verifies the saved index and
prepared artifacts; it does not reread original Avro or prove benign activity.
Do not replace the frozen `verification.json` used by training.

## 3. Score with the saved checkpoint

Follow [offline scoring commands](INFERENCE.md). Required inputs are a trusted
ten-file bundle and compatible named raw feature rows. A teammate can receive
these local files from the project owner; GitHub contains code/aggregate
reports, not weights or row data. Scoring works with the pinned CPU build and
does not require the training directories. The bundle digest, host, window,
feature names and runtime are checked before scoring. Read per-row
`reconstruction_mse`/`reconstruction_mae`; labels and thresholds remain `null`.

## 4. Repeat training and final evaluation

With the **exact prepared snapshot** and pinned CUDA environment, follow
[GPU setup and training](GPU_TRAINING.md). Run two fresh full output directories,
compare configuration/history/model-state hashes, and then evaluate the frozen
primary checkpoint using the separate evaluator. Its commands preserve the
same architecture, feature schema, scaler, development-selection rule and seed.
Use [error analysis](ERROR_ANALYSIS.md) for diagnostics and [offline scoring](INFERENCE.md)
for export/reuse. Optional figures use `requirements-plots.txt`.

This repeats an existing experiment. The holdout has already been inspected;
rerunning it does not create fresh evidence for later hyperparameter tuning.
CPU scoring portability has been checked; full CPU training is not claimed
to reproduce the CUDA training weights bitwise.

## 5. Recreate raw preparation when necessary

Follow [raw preparation and verification](README.md#reproduce). Required inputs:

- The existing source gzip archive(s) at the documented path, left unchanged.
- The frozen preparation plan, including its reference-audit fingerprint.
- The completed local reference-audit cache
  `.cache/ml-runs/ml02-scp-all-references-20261027/`, including its
  `reference_report.json` and supporting local artifacts.
- The pinned preparation environment (`research/ml/requirements.txt`).

The local preparation consumed one complete 10-million-record archive selected
from the 37-file audited inventory. It did not require every archive to become
training data. The source cache and large binary files are not distributed in
Git. Copying downloads to another machine can change recorded file metadata;
manifests also bind source reports and code versions. A freshly generated
snapshot may therefore have different provenance hashes.

If fingerprints differ, stop and review/independently verify the new source
inventory, preparation plan and snapshot. Record a separate reviewed plan/config
for that reproduction. Do not edit the historical reports or bypass the frozen
checks to make new data look identical. No automated migration or fresh-machine
raw reconstruction was performed in this handoff. The exact local experiment
and report-only reproduction are the verified paths.

## 6. Software validation

The test command used for this handoff is recorded in the
[handoff verification](../../../data/ml/datasets/darpa/label_free/handoff_verification_20261029.json).
Tests check software behavior, not attack accuracy. The new reporting checks
verify known frozen results, reject replaced run/mismatched diagnostic evidence,
and reject label/preprocessing/weight-change claims. A clean output from the
report command is not a substitute for raw-data or model-run validation.

The [task status](TASK_STATUS.md) preserves the incomplete supervised and
deferred GNN/integration tasks. Choose and validate the next experiment before
changing the model, host coverage, target, dataset or production pipeline.
