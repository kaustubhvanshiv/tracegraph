# Completed GPU training and final reconstruction evaluation

**2026-10-29: full training and final holdout evaluation are complete.**
The RTX 4050 trained the fixed autoencoder for 200 epochs; development MSE
selected epoch 185. A second same-seed full run reproduced the complete loss
history and checkpoint weights exactly before the reserved holdout was evaluated.
All 68 relevant tests passed in the CUDA environment, including the GPU hardware
test. See the [results and chart](../../../data/ml/datasets/darpa/label_free/gpu_training_result_20261029.md).

| Runtime | Measured setup |
|---|---|
| GPU | NVIDIA GeForce RTX 4050 Laptop GPU, 6 GB VRAM |
| Driver | 610.47 |
| Python / PyTorch | 3.11.9 / 2.15.0+cu132 |
| Compiled CUDA runtime | 13.2 |
| Placement | Model parameters and training vectors on `cuda:0` |
| Precision | Float32, matmul `highest`, no mixed precision |
| Determinism | Seed 42, deterministic algorithms, cuBLAS workspace `:4096:8` |

The [CUDA configuration](training_config_cuda.json) changes the device/runtime
from the CPU readiness setup. Architecture, data hashes, optimizer, learning
rate, weight decay, batch size, seed and stopping policy are unchanged. There
is no silent CPU fallback. Checkpoints are stored as CPU tensors and reloaded
onto the configured CUDA device for evaluation.

## Environment setup

A separate ignored environment preserves the original CPU installation. This
setup is already complete locally; teammates can create it once from the repo
root. CUDA packages can require a large download, separate from training time.

```powershell
research/ml/.venv/Scripts/python.exe -m venv .cache/ml-envs/darpa-gpu-py311
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m pip install -r research/ml/requirements.txt
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m pip install -r research/ml/label_free/requirements-gpu.txt
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m pip check
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -c 'import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))'
```

Use the pinned CUDA package build with a compatible driver. The NVIDIA-SMI
CUDA display describes driver capability; the framework's actual compiled
runtime here is 13.2. This task installed Python packages without changing the
GPU driver or CPU environment's PyTorch build. Installation guidance:
[PyTorch](https://pytorch.org/get-started/locally/),
[CUDA compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html),
and [float32 matmul precision](https://docs.pytorch.org/docs/main/generated/torch.set_float32_matmul_precision.html).

The configuration pins the already verified prepared snapshot. To use a freshly
recreated snapshot with different manifest hashes, review and independently
verify it, then create a separate configuration with those fingerprints. Do not
disable input checks to accept different artifacts. See [preparation](README.md).

## Train and verify repeatability

Use fresh output directories; the completed local folders already exist.

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m research.ml.label_free.train `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --config "research/ml/label_free/training_config_cuda.json" `
  --output ".cache/ml-runs/label-free-gpu-new/full-a" `
  --mode full

.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m research.ml.label_free.train `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --config "research/ml/label_free/training_config_cuda.json" `
  --output ".cache/ml-runs/label-free-gpu-new/full-b" `
  --mode full
```

Before final evaluation, compare `config_sha256_utf8_lf`, `history_sha256` and
`checkpoint_state_sha256` in the two `run.json` files. They must match for this
same-runtime repeatability check. CPU/GPU or different-device equality is not
claimed. No hyperparameter search or second model architecture was used.

## Evaluate the frozen primary checkpoint

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m research.ml.label_free.evaluate `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --run ".cache/ml-runs/label-free-gpu-new/full-a" `
  --output ".cache/ml-runs/label-free-gpu-new/full-a/holdout_evaluation.json"
```

Only after full training and development-based selection does this read the 98
holdout vectors. It verifies code/config/data/feature/scaler/checkpoint hashes,
reports reconstruction MSE and MAE against a training-mean baseline, and changes
no weights or thresholds. Preserve this final evaluation; do not tune settings
using its errors and then present the same holdout as untouched evidence.

## Local artifacts and timing

The completed runs are under:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\label-free-gpu-20261029
```

`full-a/best.pt` is the selected model. `full-a/run.json`, `history.jsonl` and
`holdout_evaluation.json` record training, selection and final evaluation.
`full-b/` is the repeatability run, not another holdout-based model choice.
`reproducibility.json` and `completion_verification.json` preserve the checks.

Primary training-loop time, including per-epoch metrics/checkpoints, was
**7.40 seconds**; primary function time including setup/transfers was
**10.81 seconds**. The repeat measured 8.93 / 12.32 seconds respectively.
These synchronized timings exclude package download/installation and Python
module import. No CPU/GPU speedup was benchmarked. PyTorch allocator peak was
about 32.4 MiB, excluding driver/CUDA-context memory outside that allocator.

## Optional figure

The chart generator requires Matplotlib, independently of the training runtime:

```powershell
research/ml/.venv/Scripts/python.exe -m pip install -r research/ml/label_free/requirements-plots.txt
research/ml/.venv/Scripts/python.exe -m research.ml.label_free.plot_results `
  --run ".cache/ml-runs/label-free-gpu-new/full-a" `
  --evaluation ".cache/ml-runs/label-free-gpu-new/full-a/holdout_evaluation.json" `
  --output ".cache/ml-runs/label-free-gpu-new/results.png"
```

All model weights, feature rows and environments remain under ignored `.cache`.
Code, locked requirements, aggregate reports and the chart are published.
Labels remain unknown, shared context remains, and these results establish
reconstruction performance for this limited pilot, not attack-detection accuracy.
