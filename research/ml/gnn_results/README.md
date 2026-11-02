# Full local DARPA GNN results and error analysis

All three approved models completed five epochs and final reconstruction
evaluation. The next task after training is complete: audit saved artifacts,
compare the frozen models, inspect residuals and publish reproducible results.

The [measured comparison, CSV, figures and linked evidence](../../../data/ml/datasets/darpa/gnn_full/RESULTS_20261102.md)
cover GCN, GraphSAGE and GAT on the same 2,664,540 test node-window rows.
GraphSAGE has the lowest development MSE and lowest observed test MSE/MAE.
Its test MSE is 0.354878308, 36.53% below the training-mean reference.
This is a reconstruction result; no attack-detection accuracy was measured.

A [12-page Word report](../../../Documents/TraceGraph_DARPA_GNN_Comparative_Report_20261102.docx)
contains the dataset, architectures, training protocol, complete epoch histories,
measured comparison and charts, execution timings, residual analysis, verification,
limitations, checkpoint fingerprints and reproduction commands.

For a quick overview, use the [two-page illustrated summary](../../../Documents/TraceGraph_DARPA_GNN_Short_Report_20261102.docx).
It keeps the essential model settings, measured results, comparison chart,
learning curve, residual findings and interpretation limits.

GraphSAGE's median row MSE is 0.010364, but its 95th percentile is 0.990546,
higher than GAT's 0.763579. GAT has the largest maximum row error, 2705.290039.
The highest-error 1% of test rows contributes 65.16% of squared residual for
GCN, 61.36% for GraphSAGE and 69.94% for GAT. Average-error and tail-error
rankings differ. Incoming LOGOUT reference counts are the largest individual
feature residual contributor for each model; this identifies reconstruction
error concentration, not a security conclusion or feature causality.

## Dataset and protocol

All 37 local FiveDirections archives were prepared: 345,099,571 raw records,
330,788,968 eligible unique Events, 1,312 graphs and 24,106,424 node-window
rows. The two chronological purge gaps account for 2,058,940 Events. The local
download is not the whole DARPA release. Graph counts and native Event totals
are separate units from training rows or globally unique entities.

| Partition | Graphs | Node-window rows | Native Events |
|---|---:|---:|---:|
| Training | 758 | 15,819,608 | 211,686,253 |
| Development | 284 | 5,622,276 | 77,198,703 |
| Test | 270 | 2,664,540 | 39,845,072 |

The [frozen specification](../gnn_full/TASK_SPEC.md) defines host-specific
five-minute graphs, 115 native activity-count features, an undirected adjacency
projection, `log1p` plus training-only population normalization, and chronological
partitions. Training ends before 9 May 2019 00:00 UTC; development starts at
00:05 and ends before 10 May 00:00; test starts at 10 May 00:05.

All models use 64 hidden and 32 latent values, a linear reconstruction decoder,
batch size 256 seed nodes, fanouts 10/5, Adam at 0.001 with weight decay 0.0001,
five epochs and seed 42. GAT has four first-layer attention heads. Parameter
counts differ: GCN 13,299; GraphSAGE 22,707; GAT 13,491. Equal widths are not
equal model capacity. GCN normalization uses the sampled computation graph.

During training, 20% of context-node feature vectors are masked to normalized
zero and the loss uses masked seed nodes. Evaluation masks all seed nodes,
with the same seeded neighbor sampler and context masking. Consequently train
and evaluation loss levels use different masking rules. These are within-window
imputation metrics, not future-event prediction. The reference predicts the
normalized training mean; the report records its MSE, not an invented MAE.

Development selects each checkpoint, including initialization. Selected epochs
are GCN 5, GraphSAGE 5 and GAT 3. All three selections were frozen before final
test evaluation. Standalone `run.json` status/test flags are historical receipts
for the pre-test training stage; `test.json` and `complete.json` record the final
evaluation. Do not overwrite those receipts to make their historical flags current.

## Verification and error analysis

The verifier hashed all 1,312 graph files, checked source sizes/modification
times, reconciled all source/partition/Event counts, verified histories and
development selection, matched test reports to the aggregate, and strictly
loaded all checkpoints on CPU with matching tensor-state hashes. It checked
both the original pipeline contract and supplementary prefetch execution profile.
It did not reread/re-hash every compressed raw byte or perform a clean-machine
reproduction.

The error-analysis command replays all 270 test graphs with frozen weights and
the original evaluation masks. It computes per-feature residual contributions,
row-error quantiles, error concentration and per-graph summaries. All three
replayed MSE/MAE/reference values must reproduce the frozen test within
`rtol=1e-5, atol=1e-7`; model states and checkpoint files must remain unchanged.
Ten high-error native rows per model are retained locally with unknown labels
for traceable review. Raw UUIDs, individual scores and model weights are not
published. High error is not proof of an attack.

Six new checks cover invalid metrics, incomplete coverage/history, wrong
checkpoint selection, inconsistent aggregate/test evidence, unsupported security
claims, residual concentration and changed report inputs. Earlier 14 focused
GNN/prefetch checks passed. These are software checks, not detection scores.

## Teammate commands

Run from the repository root on `deeplearning/shlok`. The completed local
workspace is `D:/Deep Learning/tracegraph-gnn-workspace`. For full training from
raw files, follow [preparation and original execution](../gnn_full/README.md)
and the [reviewed prefetch revision](../gnn_accel/README.md). Do not launch a
training command over this completed workspace. A fresh prepared-data/training
reproduction needs a separate work directory and the same 37 source archives.
Use the isolated Python 3.11 CUDA environment pinned by
`../gnn_full/requirements-gnn.txt`; the plotting environment uses the existing
`research/ml/.venv` with Matplotlib (`../label_free/requirements-plots.txt`).

Verify completed artifacts without training:

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m research.ml.gnn_results.verify `
  --work "D:/Deep Learning/tracegraph-gnn-workspace" `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --output ".cache/gnn-results-20261102/verification.json"
```

Replay frozen test residuals on the NVIDIA GPU (several minutes; no training):

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m research.ml.gnn_results.analyze `
  --work "D:/Deep Learning/tracegraph-gnn-workspace" `
  --verification ".cache/gnn-results-20261102/verification.json" `
  --output ".cache/gnn-results-20261102"
```

Rebuild the measured comparison and figures using the plotting environment:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.gnn_results.report `
  --work "D:/Deep Learning/tracegraph-gnn-workspace" `
  --verification ".cache/gnn-results-20261102/verification.json" `
  --analysis ".cache/gnn-results-20261102/error_analysis.json" `
  --output "data/ml/datasets/darpa/gnn_full"
```

Teammates who only need the published figures can use that environment with
`python -m research.ml.gnn_results.report --plots-only --output
"data/ml/datasets/darpa/gnn_full"`. This reads the committed aggregate evidence
and requires no local raw files, checkpoints, GPU or training.

Run the reporting checks:

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m unittest research.ml.tests.test_gnn_results -q
```

## Interpretation and remaining gates

The models have one training seed and five epochs each. CUDA scatter can be
nondeterministic. There are no multi-seed confidence intervals or hyperparameter
search results. Differences should be described as observed values on this
cohort; more parameters and differing execution conditions limit causal claims
about architecture. Recorded training times are not a controlled speed benchmark.

Recurring native entity counts are 115,807 for training/development, 90,656 for
training/test and 104,835 for development/test. These are entity intersections,
not fractions of node-window rows. Shared identities and neighboring activity
limit independence. The test cohort has now been inspected for results and
diagnostics; future model tuning requires fresh evaluation evidence.

Original supervised ML-02.4, security evaluation/comparison and production
integration retain their prerequisite gaps. This separate, approved self-supervised
experiment does not mark them complete or justify a detection threshold. The
earlier 62-feature AE pilot and proposed AE–1D-CNN–BiLSTM hybrid are separate
tracks. No fourth model or production integration was started by this report.
