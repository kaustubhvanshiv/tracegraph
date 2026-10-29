# Frozen DARPA model: standalone scoring result

LF-06 completed on 2026-10-29. The selected epoch-185 autoencoder and saved
training-only preprocessing now form a local offline scoring bundle. It scores
compatible named raw actor-window features without training folders, original
Avro archives or retraining. The 39,525-byte bundle remains local.

| Previously evaluated partition | Rows | CPU replay MSE | CUDA replay MSE | Largest CPU/CUDA row MSE difference |
|---|---:|---:|---:|---:|
| Training | 1,184 | 0.110711494 | 0.110711493 | 9.54e-7 |
| Development | 76 | 0.033141206 | 0.033141207 | 5.96e-8 |
| Holdout | 98 | 0.072372764 | 0.072372760 | 2.98e-7 |

All 1,358 real DARPA rows reproduced the original frozen aggregate MSE/MAE
within relative tolerance 2e-6 or absolute tolerance 1e-7. Per-row CPU/CUDA
MSE, MAE and mean-reference MSE agree within relative tolerance 2e-5 or absolute
tolerance 2e-6. This is numerical agreement, not bitwise CPU/GPU equality.
The independent PyTorch 2.15.0+cpu environment also reproduced all 98 holdout
scores exactly against CPU execution of 2.15.0+cu132 on this machine.

Original checkpoints, configuration, preparation artifacts, samples and
supervised annotations were unchanged. No labels, threshold, new model,
split or production integration was introduced. The scorer checks file/code
fingerprints before loading weights with `weights_only=True`, validates named
inputs, reuses the scaler, and checks inputs/weights again before saving.
Accepting an aggregate vector does not re-establish native-source correctness.

All **82 relevant software tests pass** in the CUDA environment. Eight new
tests cover reuse without training folders/optimizer, changed artifact and
code/provenance rejection, feature ordering and invalid counts, invalid inputs,
exact replay normalization, explicit CUDA/runtime guards, and modification
detection during scoring.

These are software/replay checks on already evaluated data, not a new accuracy
benchmark. Errors do not establish security intent; original supervised
ML-02.4 remains incomplete and ML-10 integration stays deferred. No additional
download is needed for this reuse step.

See the [teammate commands and input contract](../../../../../research/ml/label_free/INFERENCE.md)
and [machine-readable verification](offline_scoring_report_20261029.json).
