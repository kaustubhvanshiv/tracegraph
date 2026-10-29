# Full local DARPA GNN experiment — frozen task specification

Authorized 2026-10-29: the user selected self-supervised graph-feature
reconstruction and requested GCN, GraphSAGE and GAT on the whole downloaded
dataset. This specification precedes GNN implementation. It supersedes no
security annotation and does not claim the original supervised task complete.

## Coverage and target

Use every one of the 37 unchanged locally audited FiveDirections gzip archives:
345,099,571 raw records, including 330,788,968 raw Events before deduplication.
This is the complete local download, not the complete Engagement 5 release.
All sources must be exhausted and their record/type counts and file metadata
checked against the existing full reference audit. No annotation-based source
selection, event prefix limit, arbitrary row subset or certified-normal claim.
Invalid/missing native identifiers, Event conflicts and partition-gap Events
must have explicit accounting. Raw source files remain untouched.

The target is each node's observed numeric activity vector, reconstructed from
a masked input and graph neighbors. It is not an attack/benign target. Report
masked-node MSE/MAE, the training-mean reference, and coverage. Security
precision/recall/F1/AUC and attack probabilities are unavailable.

## Graph representation and partitions

Construct host-specific, half-open five-minute graphs using native timestamps.
Nodes are native `(publishing host UUID, entity UUID)` endpoints; subjects may
be threads. Relations are native subject-to-predicate references, retaining
first/second role during preparation. Message passing uses an undirected
projection; this does not assert information-flow direction. Repeated endpoint
pairs within a window collapse for adjacency, while native action occurrence
counts remain features. Self-loops are handled by each convolution's standard
operator. Events with no object may yield isolated subject nodes.

Use a fixed action vocabulary from the recorded schema plus an unknown action
bucket. For every endpoint, count outgoing and incoming references by action,
plus subject Events without a predicate. No UUID value, absolute timestamp,
path, command line, attack annotation or offline entity-availability indicator
is a predictor. Features receive log1p and training-only population z-scoring;
constant training columns use scale one. No validation/test scaler fitting.

Chronological windows: training before 2019-05-09T00:00:00Z; development from
2019-05-09T00:05:00Z to 2019-05-10T00:00:00Z; test from
2019-05-10T00:05:00Z onward. The two five-minute gaps are excluded and counted.
No graph spans a partition boundary. All local source files are processed,
including those containing mixed partitions. Repeated native entities may
occur over time and must be measured/disclosed; this is temporal generalization
with recurring entities, not identity-isolated or independent-incident testing.

## Matched model/training protocol

Use PyTorch Geometric GCNConv, SAGEConv (mean aggregation) and GATConv. Each
encoder has two message-passing layers, hidden width 64, latent width 32,
ReLU between layers and a linear latent-to-feature decoder. GAT uses four
heads concatenated to width 64, then one 32-wide head. Record actual parameter
counts; equal widths do not imply equal parameter budgets.

At training time mask whole feature vectors of 20% of sampled context nodes
to normalized zero; compute loss only on masked seed nodes. Evaluate all seed
nodes with seed inputs masked and deterministic sampled neighbors. The target
remains the clean vector; this is within-window feature imputation. Known graph
structure/neighbor activity can reveal target information; these metrics are
not independent security detection or future-link prediction.

If a tiny training batch happens to have zero masked seeds, mask one uniformly
chosen seed so that the batch has a defined optimization target. CUDA scatter
kernels may remain nondeterministic: use seeded sampling and warn-only
deterministic algorithms, record that limitation, and check checkpoint reload
within numerical tolerance rather than claiming exact GPU reproducibility.

Use batches of 256 seed nodes and bounded CPU neighbor sampling (fanouts 10
then 5), shared across the three architectures. GCN normalization is over the
sampled computation graph, an explicit approximation to full-graph GCN.
Sampler choices and dropped duplicate neighbors must be deterministic for
validation/test. Iterate every eligible seed node per epoch; no fixed small
training-row cap. Five maximum epochs, Adam lr 0.001/weight decay 0.0001, seed
42, float32 on the RTX 4050, checkpoint by development masked MSE including
initialization. No tuning using test results. Missing CUDA fails explicitly.
Freeze all three selected checkpoints before final test comparison.

## Resources and completion criteria

Full-graph materialization on the 6 GB GPU is unsuitable. Use disk-backed
preparation and bounded graph batches/neighbor sampling. Benchmark storage and
throughput before committing the complete extraction. Stop safely on low disk,
source changes, count mismatch or failed integrity checks; do not silently
reduce coverage. Temporary derived artifacts may use a separate D: work folder
with required filesystem approval. Existing C: has only about 18 GiB free.

Resource amendment authorized by the user: use four independent CPU archive
readers, ten DuckDB threads and CUDA model batches. Available RAM bounds reader
concurrency. Preserve verified serial extraction receipts and the prior
contract when switching. This performance amendment changes no target, feature,
partition or source-coverage rule.

Completion requires 37/37 source validation, explicit deduplication/conflict
policy, independent graph/vector checks, all three completed training runs,
checkpoint reload, development-only selection, held-out reconstruction metrics,
baseline comparison, provenance, tests and teammate commands. No completed
training claim is permitted from a smoke test or partial extraction.

References: [PyG installation](https://pytorch-geometric.readthedocs.io/en/stable/install/installation.html),
[GCNConv](https://pytorch-geometric.readthedocs.io/en/stable/generated/torch_geometric.nn.conv.GCNConv.html),
[SAGEConv](https://pytorch-geometric.readthedocs.io/en/stable/generated/torch_geometric.nn.conv.SAGEConv.html),
[GATConv](https://pytorch-geometric.readthedocs.io/en/stable/generated/torch_geometric.nn.conv.GATConv.html).
