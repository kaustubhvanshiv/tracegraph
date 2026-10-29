# Training-ready label-free DARPA pilot

**2026-10-29: ready for the full reconstruction run.** The model, input checks,
loss, optimizer, checkpoint selection, early stopping and separate final evaluator
are implemented. Two real-data three-epoch smoke runs produced identical loss
histories and weights. All **65 relevant software tests pass** and `pip check`
reports no broken dependencies. Full training and real holdout evaluation have
not been run. See the [task status](TASK_STATUS.md) and
[measured readiness result](../../../data/ml/datasets/darpa/label_free/training_readiness_20261029.md).

## Scope and model

The user approved this separate label-free route. It does not complete original
ML-02.4 or activate the deferred supervised GNN tasks. The
[task specification](TASK_SPEC.md) was written before model code, and the
[frozen configuration](training_config.json) pins the verified dataset snapshot.

The CPU model is a `62 -> 16 -> 4 -> 16 -> 62` autoencoder with 2,210 parameters,
ReLU hidden layers and linear latent/output layers. It reconstructs normalized
activity vectors. Adam minimizes mean squared error, with learning rate 0.001,
weight decay 0.0001, batch size 64, seed 42 and one CPU thread. The full budget
is 200 epochs, with patience 20 and minimum improvement 0.000001. Exact settings
and the input hashes are in the configuration. No GPU driver setup is needed
for this small pilot.

All 62 prepared features remain fixed. No label, trace field, UUID value or
heldout-fitted statistic enters the model. The scaler is verified and reused,
not refit. A constant normalized training-mean vector provides the comparison
baseline. MSE and MAE measure reconstruction only. The smoke model has slightly
lower development MSE than the baseline and higher MAE; no general performance
win or attack accuracy is claimed.

## Runtime setup

Use the existing ML environment from the repository root. On a fresh setup,
install the base preparation dependencies first, then the locked CPU runtime:

```powershell
research/ml/.venv/Scripts/python.exe -m pip install -r research/ml/requirements.txt
research/ml/.venv/Scripts/python.exe -m pip install -r research/ml/label_free/requirements-training.txt
research/ml/.venv/Scripts/python.exe -m pip check
```

The checked local versions are Python 3.11.9, PyTorch 2.15.0+cpu and NumPy 2.4.6.
The training requirements also pin their resolved dependencies. Use a new
recorded configuration for a different runtime or model instead of silently
reusing a run's claimed reproducibility. Same-seed equality was measured on this
CPU/runtime, not promised across releases/platforms.

## Smoke check

The [prepared data](README.md) must already exist with its independent
`verification.json`. Use a fresh output folder:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.label_free.train `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --config "research/ml/label_free/training_config.json" `
  --output ".cache/ml-runs/label-free-smoke-new" `
  --mode smoke
```

Expected status: `smoke_passed_training_ready`. This performs three epochs on
the 1,184 training rows, checks all 76 development rows, verifies finite losses,
gradients and parameters, and reloads the selected checkpoint. The training
module never opens `holdout.jsonl`. Tests guard that file access explicitly.
Any failure produces no successful readiness status. These learned smoke weights
are a pipeline check, not the final model.

The completed local smoke runs are under:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\label-free-training-ready-20261029\smoke-a
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\label-free-training-ready-20261029\smoke-b
```

Each contains `run.json`, epoch-by-epoch `history.jsonl`, an exact configuration
copy and `best.pt`. Weights/data stay in ignored `.cache`; code and aggregate
readiness reports are committed.

## Full training command

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.label_free.train `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --config "research/ml/label_free/training_config.json" `
  --output ".cache/ml-runs/label-free-full-001" `
  --mode full
```

This command has not been executed on the real data. It starts from the fixed
seed, not smoke weights. Fresh-run training is supported; optimizer-state resume
is not implemented. The lowest development-MSE checkpoint is saved, including
initialization as epoch zero. Early stopping uses development MSE only. Training
and development errors are logged after every epoch, together with a training-only
mean baseline. The holdout remains unopened by this module.

## Separate final evaluation

After the full run and its configuration/checkpoint are frozen:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.label_free.evaluate `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --run ".cache/ml-runs/label-free-full-001" `
  --output ".cache/ml-runs/label-free-full-001/holdout_evaluation.json"
```

The evaluator rejects smoke or failed runs before reading holdout vectors. For
a completed full run, it checks checkpoint, configuration, code, dataset, feature
order and scaler fingerprints, loads local state dictionaries with
`weights_only=True`, and evaluates all 98 holdout rows without changing weights.
Do not use final holdout errors to select this run's settings or threshold.

Security labels remain unknown. Shared object context and same-host/day
correlations still limit evaluation. No attack threshold, classification output,
precision, recall, F1 or detection AUC is produced. This runs outside the
production FastAPI application.

## Tests

```powershell
research/ml/.venv/Scripts/python.exe -m unittest research.ml.tests.test_label_free_training -v
```

Eleven training checks cover model dimensions/gradients, unsafe configurations,
training-only data access, seeded reproducibility, baseline correctness, input
fingerprints and malformed labels/values, failed-run handling, checkpoint reload,
full-run evaluation and rejection of smoke/tampered checkpoints. Tiny native
fixtures exercise software paths; both reported readiness runs use the real
DARPA-derived vectors.
