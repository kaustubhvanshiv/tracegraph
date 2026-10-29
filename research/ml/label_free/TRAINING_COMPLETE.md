# Approved training completed

Verified on 2026-10-29: **both approved label-free models have finished
training and same-seed repetition**. No training job remains running or pending
for these two frozen configurations. The completion check reloads all four
checkpoints, verifies source/configuration/data/history hashes and checkpoint
selection, then reproduces clean train/development metrics on CUDA.

| Model | Epochs run | Selected epoch | Development MSE | Development MAE |
|---|---:|---:|---:|---:|
| Ordinary autoencoder | 200 | 185 | 0.033141211 | 0.066414706 |
| Denoising autoencoder | 60 | 40 | 0.062845558 | 0.101504706 |

The denoising run stopped under its fixed patience rule; stopping at 60 epochs
is completed training, not an interrupted 200-epoch run. Each model's repeated
full run matched its complete history, configuration and selected weights.
The original model performs better on clean development reconstruction. This
is selection-data evidence, not a final independent ranking or attack accuracy.

All **87 relevant software tests pass**, with no skips. No additional optimizer
steps or holdout reads were needed for the completion check. Raw data, weights,
scaler, configuration and prior reports remain unchanged. The previous
ordinary-model final evaluation remains historical; denoising has no final
evaluation on a fresh cohort yet.

## Recheck completion

From the repository root, with the saved local runs and pinned CUDA environment:

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m research.ml.label_free.verify_training `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --ordinary ".cache/ml-runs/label-free-gpu-20261029" `
  --denoising ".cache/ml-runs/denoising-darpa-20261029" `
  --output ".cache/ml-runs/training-completion-new.json"
```

Use a fresh report path. See the [completion evidence](../../../data/ml/datasets/darpa/label_free/training_completion_report_20261029.json),
[original training commands](GPU_TRAINING.md), [denoising commands](DENOISING.md)
and [teammate handoff](REPRODUCING.md). Weights stay in the ignored run folders.

## What remains outside training completion

A fresh final comparison needs a new source-verified evaluation cohort for
both frozen models. The existing source inventory reports this archive spans
2019-05-07 13:02:36.426–15:10:48.557 UTC, so later candidate windows exist in
its timestamp bounds. Bounds alone do not establish complete five-minute
coverage, actor/context independence or verified labels; no new cohort was
extracted/scored during this completion check.

Original supervised ML-02.4, GNN experiments/comparison and production
integration retain their previous unmet prerequisites. Additional models are
not selected by the request to finish the two approved training experiments.
Further evaluation is separate from the training that is now complete.
