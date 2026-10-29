# Proposed second experiment: denoising autoencoder

Status: **approved and completed**; see [measured results](DENOISING.md).
Prepared on 2026-10-29 after the user asked to train the next model before
extending evaluation data. This is a second autoencoder training variant,
not a GNN or an independently established best algorithm for DARPA.

## Reason for this candidate

The existing 62-feature vectors and unknown security intent support another
label-free reconstruction experiment. A denoising autoencoder learns to
reconstruct clean observations from partially corrupted inputs. The proposed
comparison asks whether that training objective improves development-set
reconstruction relative to the existing ordinary autoencoder. This is a
project-specific hypothesis, not a promised improvement.

Algorithm reference: Vincent et al., ICML 2008,
[Extracting and Composing Robust Features with Denoising Autoencoders](https://icml.cc/2008/papers/592.pdf).
The masking rate and normalized-feature adaptation below are proposed settings
for this experiment, not values established by that paper for DARPA.

## Frozen proposal before any training

- Reuse the independently verified DARPA snapshot and saved training-only scaler.
- Fit on the existing 1,184 training rows; select using the 76 development rows.
- Retain the same 62 → 16 → 4 → 16 → 62 architecture and 2,210 parameters.
- During training only, independently mask each nonconstant normalized input
  coordinate with probability 0.20 by replacing it with zero (its training
  mean). Leave training-constant columns unchanged. Keep the clean vector as
  the target. These are numerical training perturbations, not native Events
  or new ground-truth samples.
- Keep Adam, learning rate 0.001, weight decay 0.0001, batch size 64, seed 42,
  maximum 200 epochs, patience 20 and minimum improvement 1e-6.
- Use the existing CUDA environment and RTX 4050. No new package/dataset download.
- Use an independent seeded masking generator; preserve the original run,
  checkpoint, reports and offline bundle.
- Select the lowest **clean development MSE**, including initialization.
  Record the masked-input training objective separately from clean reconstruction
  MSE/MAE so those quantities cannot be confused.
- Repeat the frozen run for same-runtime reproducibility; record actual device,
  settings, histories, selected weights, hashes and synchronized timing.
- Compare clean train/development MSE/MAE with the existing autoencoder and
  training-mean reference, without assuming the denoising variant wins.

## Evaluation boundary

Do not use the previously inspected 98-row holdout to select or tune this
second model. Initially train and compare on train/development only. A fresh,
source-verified evaluation cohort is needed before a new final comparison.
Development performance is model-selection evidence, not an independent test.

All security labels remain unknown. Neither clean nor denoising reconstruction
error supplies an attack probability, threshold, precision/recall/F1 or GNN
task completion. The user confirmed this model choice before implementation and training.
