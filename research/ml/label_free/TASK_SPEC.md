# Label-free reconstruction training specification

Frozen for readiness checks on 2026-10-29, following the user's approval of a
separate label-free DARPA workflow and request to make it training-ready.
This is not the deferred GNN task in ML-06/ML-07 and does not claim ML-02.4
completion. Supervised Event and node annotations remain unchanged.

## Input and objective

Use the prepared native actor-window dataset: 62 normalized numeric features,
1,184 training rows, 76 development rows and 98 final holdout rows. The prepared
feature order, training-only scaler and source/partition fingerprints are part
of the model input contract. No trace key or security label is a predictor.

Learn to reconstruct each normalized vector `x` from itself. The target is the
observed vector, not an attack/benign class. Minimize mean squared reconstruction
error, averaged equally across rows and all 62 features. Report mean absolute
reconstruction error as a secondary metric. All 30 training-constant columns
remain in the frozen schema; report their count and do not fit a new scaler.

## Minimal model and optimization

Architecture: `Linear(62,16) -> ReLU -> Linear(16,4) -> Linear(4,16) -> ReLU ->
Linear(16,62)`. The latent and output layers are linear. Normalized inputs can
be negative, so no nonnegative output constraint is applied. There are 2,210
trainable parameters. No dropout, batch normalization or label-conditioned
sampling is used.

Default configuration: Adam, learning rate 0.001, weight decay 0.0001, batch size
64, at most 200 epochs, seed 42, one CPU thread, deterministic algorithms and
float32 tensors. Shuffle only training batches with a seeded generator. Track
full-dataset training/development reconstruction loss after every epoch. Save
the lowest development-MSE checkpoint, including initialization as epoch zero;
stop after 20 epochs without improvement greater than 0.000001. A later change
requires a new recorded configuration, not an unreported holdout-based choice.

Compare with a constant vector equal to the normalized training mean, computed
only from training rows. Report the measured baseline and autoencoder errors
without assuming the neural network improves upon the baseline.

## Readiness, training and final evaluation

Readiness uses a three-epoch train/development smoke run, checkpoint reload,
finite loss/gradient/parameter checks, and same-seed repetition on this runtime.
It does not read holdout vectors or compute holdout reconstruction metrics.
These checks demonstrate an executable pipeline, not a trained security detector.

The full training command remains separate and also reads only training and
development vectors. Early stopping and checkpoint selection use development
only. A separate final-evaluation command may read holdout vectors only after
the full run is frozen, verifies the exact checkpoint/data/config fingerprints,
and refuses to evaluate a smoke-run checkpoint. It does not change weights,
scaler, configuration or thresholds. Store results as reconstruction metrics,
with no attack prediction or security threshold.

Model weights and feature rows remain in ignored local run directories. Save
state dictionaries, load local weights with `weights_only=True`, and verify
checkpoint/config/input fingerprints before reuse. Record Python/PyTorch
versions, code hashes, seed and parameter count. Reproducibility is checked
within this fixed CPU runtime; it is not guaranteed across platforms/releases.

## Evaluation limits

Training data is unlabeled and not certified benign. Actor IDs are disjoint
across partitions, but object contexts, numeric profiles and same-host/day
activity remain correlated. Later ownership filtering biases the later cohorts
toward newly observed native actors, potentially threads. This is a limited
reconstruction pilot; loss is not an attack probability and cannot establish
precision, recall, F1, detection AUC or independent incident generalization.

The training readiness report must distinguish software checks, a smoke run,
full training and final holdout evaluation. The original supervised task stays
incomplete even if this label-free pilot runs successfully.

Implementation references: [PyTorch installation](https://pytorch.org/get-started/locally/),
[reproducibility](https://docs.pytorch.org/docs/2.15/notes/randomness.html),
and [state-dictionary checkpoint loading](https://docs.pytorch.org/tutorials/beginner/basics/saveloadrun_tutorial.html).
