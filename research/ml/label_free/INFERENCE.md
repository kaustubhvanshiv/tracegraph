# Reuse the frozen model for offline scoring

**2026-10-29: LF-06 is complete.** A standalone command reloads the saved
autoencoder and its training-only scaler, accepts named raw activity features,
and writes reconstruction MSE/MAE per row. Scoring needs the bundle and a
compatible input, without training folders, original Avro files or a GPU.
This remains a research tool outside the TraceGraph backend.

All **82 relevant software tests pass** in the CUDA environment. Replaying all
1,358 existing DARPA rows reproduced the frozen metrics on CPU/CUDA within the
declared tolerances. The separate CPU-only PyTorch environment also scored all
98 holdout rows successfully. See the [measured result](../../../data/ml/datasets/darpa/label_free/offline_scoring_20261029.md)
and [aggregate verification](../../../data/ml/datasets/darpa/label_free/offline_scoring_report_20261029.json).

## Saved bundle and prerequisites

The local folder `.cache/ml-runs/label-free-offline-scoring-20261029/bundle/`
contains ten files totalling 39,525 bytes: `best.pt`, frozen training config,
source run/evaluation reports, feature schema, scaler, preparation
plan/manifest/verification, and a bundle manifest with file/code fingerprints.
Epoch 185 and all 2,210 parameters are preserved. No raw telemetry or sample rows
are included. Its manifest SHA-256 is:

```text
540f7b24bce1bcdbcdd5b8e7a2f7d028e7e3147ff47265b99dd1969f918e8417
```

Weights and individual inputs/outputs stay local in ignored folders, outside
GitHub. Teammates need repository code at this milestone and a copy of the
trusted bundle, or can reproduce [training/evaluation](GPU_TRAINING.md) and
export their own. Newly generated reports may produce different bundle hashes;
use the verified export's digest. Hashes detect changes relative to a trusted
digest and are not digital signatures.

Run commands from the repository root. The existing CPU environment uses
`requirements-training.txt`; the CUDA environment uses `requirements-gpu.txt`.
Scoring requires PyTorch release 2.15.0 and accepts the tested `+cpu` or
`+cu132` build. Requested CUDA fails explicitly if unavailable. No additional
package or dataset download was needed for this milestone.

## Export and score

To export the completed GPU run, use its pinned CUDA environment. Export
verifies the source data/run/evaluation before copying frozen artifacts.
Use fresh output paths; the completed local bundle already exists.

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m research.ml.label_free.inference export `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --run ".cache/ml-runs/label-free-gpu-20261029/full-a" `
  --evaluation ".cache/ml-runs/label-free-gpu-20261029/full-a/holdout_evaluation.json" `
  --plan "data/ml/datasets/darpa/label_free/preparation_plan_20261029.json" `
  --output ".cache/ml-runs/offline-reuse-new/bundle"
```

For a repeatable reuse check, convert a verified prepared partition to the
named input format. This conversion needs the prepared partition; scoring
the resulting input does not. These commands use the already saved bundle:

```powershell
$bundleDigest = '540f7b24bce1bcdbcdd5b8e7a2f7d028e7e3147ff47265b99dd1969f918e8417'

research/ml/.venv/Scripts/python.exe -m research.ml.label_free.inference replay-input `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --partition holdout `
  --bundle ".cache/ml-runs/label-free-offline-scoring-20261029/bundle" `
  --expected-bundle-sha256 $bundleDigest `
  --output ".cache/ml-runs/offline-reuse-new/holdout-input.jsonl"

research/ml/.venv/Scripts/python.exe -m research.ml.label_free.inference score `
  --bundle ".cache/ml-runs/label-free-offline-scoring-20261029/bundle" `
  --expected-bundle-sha256 $bundleDigest `
  --input ".cache/ml-runs/offline-reuse-new/holdout-input.jsonl" `
  --output ".cache/ml-runs/offline-reuse-new/holdout-cpu" `
  --device cpu
```

For CUDA, use `.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe`, `--device cuda`
and a fresh output folder. Inputs are limited to 10,000 rows/50 MiB per call;
batch size defaults to 256 and accepts 1–4,096. Successful outputs contain
`scores.jsonl` and `summary.json` with input/bundle hashes and actual runtime.

## Input and interpretation

Each UTF-8 JSONL line must contain these fields:

| Field | Meaning |
|---|---|
| `sample_id` | Unique nonempty string, at most 256 characters; trace key only |
| `host_uuid` | Frozen host `2ab88dcdcbe641dfac699f6d6058e398`; trace key only |
| `window_nanos` | Frozen five-minute interval, `300000000000`; contract check only |
| `raw_features` | Object mapping all 62 exact `feature_schema.json` names to native aggregates |
| `security_label` | Optional; must be JSON `null` if supplied |

Dictionary order does not matter. Missing/extra names, nonfinite/negative
values, Boolean/fractional counts, inconsistent Event/reference totals,
duplicate IDs and incompatible host/window settings are rejected. Active span
is `(last_event_nanos-first_event_nanos)/1e9` and must fit the half-open window.
Reference-count checks allow native Events with a second predicate and no first.
Structural checks do not reverify native evidence or the caller's aggregation;
the scorer does not parse Avro or resolve processes.

Normalization is exactly `(log1p(raw)-training_mean)/training_std` using the
saved training statistics; constant columns retain scale one. No trace field
or label enters the network. MSE/MAE are means across 62 normalized features,
not raw-unit errors. Rows also include the saved training-mean reference MSE.
Labels/threshold remain `null`; scoring never trains or fits preprocessing.

The holdout was already evaluated and inspected: replay verifies reuse, not
new accuracy evidence. This completes LF-06 within the approved label-free
pilot, without a new model, dataset or experiment. Original supervised ML-02.4
remains incomplete; GNN integration ML-10 remains deferred. No production
endpoint, security threshold, attack probability or detection metrics are
added. Other hosts, representations or production integration require an
explicit scope decision and validation.
