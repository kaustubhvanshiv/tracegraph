# Second model: denoising autoencoder

Completed 2026-10-29 following approval of the [proposal](NEXT_MODEL_PROPOSAL.md).
The same real DARPA snapshot, scaler and 2,210-parameter architecture were used.
During training only, each of the 32 nonconstant normalized coordinates was
masked to its training mean with probability 0.20. Targets remained clean;
the 30 constant columns were unchanged. Clean development MSE selected weights.

The RTX 4050 completed **60 epochs / 1,140 updates**, stopping after patience
20; **epoch 40** was selected. Primary function time was **4.98 seconds**
including setup/transfers; the synchronized loop took **2.57 seconds**.
These exclude installation/import. Two full runs produced identical loss
histories and selected weights. No hyperparameter search was performed.

| Model/reference | Train MSE | Train MAE | Development MSE | Development MAE |
|---|---:|---:|---:|---:|
| Original autoencoder | 0.110711493 | 0.100859731 | 0.033141211 | 0.066414706 |
| Denoising autoencoder | 0.230648875 | 0.141015097 | 0.062845558 | 0.101504706 |
| Training-mean reference | 0.516129017 | 0.215315059 | 0.147637546 | 0.164320454 |

These are clean normalized reconstruction metrics, separate from the masked
training objective recorded in history. Denoising beats the mean reference
but performs worse than the original autoencoder on this development set.
Development is selection data, so this is not an independent final ranking.

The existing 98-row holdout was not opened, enforced by a file-access guard
during both actual runs. Original weights remain unchanged. No new final
evaluation, security labels, threshold or production integration was added.
Both frozen models need fresh source-verified evaluation data for a final
comparison. Reconstruction errors do not establish attack detection.

## Teammate commands

Use the existing pinned CUDA environment and exact prepared snapshot from the
repository root. Choose fresh output folders:

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m research.ml.label_free.denoising_train `
  --data ".cache/ml-runs/label-free-darpa-20261029" `
  --config "research/ml/label_free/training_config_denoising_cuda.json" `
  --output ".cache/ml-runs/denoising-new/full-a" --mode full
```

Repeat using `denoising-new/full-b`, then compare `history_sha256` and
`checkpoint_state_sha256` in the run reports. Completed local runs are under
`.cache/ml-runs/denoising-darpa-20261029/`; `full-a/best.pt` is selected.
Weights remain local. The [aggregate report](../../../data/ml/datasets/darpa/label_free/denoising_training_report_20261029.json)
records settings, metrics, hashes, GPU placement and repeatability. The ordinary
autoencoder evaluator rejects this distinct run status; no new final evaluator
is invoked before a fresh cohort exists.

All **33 relevant training, diagnostics, inference and report tests pass**,
including two new checks of repeatable masking, constant/target preservation,
clean-development selection, checkpoint reload, repeatability and holdout
separation. Run the new checks with:

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m unittest research.ml.tests.test_denoising_training.DenoisingTests -q
```

This completes the second-model train/development experiment. The earlier
final report remains the first-model historical report. Original supervised
and GNN prerequisites remain unmet. No new download was needed.
