# Standalone GraphSAGE reconstruction scorer

User-approved follow-up: reuse the verified epoch-5 GraphSAGE checkpoint and
training-only scaler outside the backend. This command scores prepared native
five-minute graphs. It never trains, fits a scaler or chooses a threshold.

The local export is `.cache/ml-runs/graphsage-offline-20261102/bundle`.
Its eight files total 115,395 bytes, including the checkpoint, configuration,
115-column feature schema, scaler, source receipts and a hashed manifest.
Trust this bundle-manifest SHA256 before loading:

```text
f79497e145e1ec873fb79fda42917d7d0c05eaf0ea44a8a41bf12cec7075d679
```

The checkpoint SHA256 remains
`cd4eec384931a2fe3bad5c1ee4ca23ad71511b5594dc2dcde204ab99a3fffd5e`.
Weights, native UUID rows and copied graphs stay local under ignored `.cache`.
The [aggregate verification receipt](../../../data/ml/datasets/darpa/gnn_full/offline_scoring_20261102.json)
records the measured replay and CPU/CUDA comparison.

## Teammate commands

Run from the repository root on `deeplearning/shlok`, using Python 3.11,
PyTorch 2.15.0, NumPy 2.4.6 and PyG 2.8.1. The existing isolated CUDA environment
is `.cache/ml-envs/darpa-gpu-py311`; its full installation lock is
[`requirements-gnn.txt`](../gnn_full/requirements-gnn.txt). Inference imports
NumPy, Torch and PyG plus their dependencies; it does not read Avro, SQLite,
DuckDB, Arrow or raw archives. CPU execution is supported in that environment.
A separate CPU-only wheel installation has not been validated for this scorer.

Export from the already verified completed workspace, without rerunning training:

```powershell
$py = '.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe'
$base = '.cache/ml-runs/graphsage-offline-20261102'
$work = 'D:/Deep Learning/tracegraph-gnn-workspace'
$sha = 'f79497e145e1ec873fb79fda42917d7d0c05eaf0ea44a8a41bf12cec7075d679'

# Run these exports only when their destination folders do not exist.
& $py -m research.ml.gnn_scoring export --work $work `
  --verification data/ml/datasets/darpa/gnn_full/verification_20261102.json `
  --output "$base/bundle"
& $py -m research.ml.gnn_scoring inputs --work $work `
  --bundle "$base/bundle" --bundle-sha256 $sha --partition test `
  --output "$base/test-input"
```

All 270 test graphs and 2,664,540 test node-window rows are included when
`--graph-key` is omitted. To export a named subset, repeat `--graph-key` with
exact `graphs/<host>_<window_start_nanos>.npz` keys. This is explicit subset
selection for an inference check; it does not change the completed training.

After exporting, scoring needs only the repository's matching inference code,
the bundle and the input package. Copy them together to another location or
machine with the supported runtime. The original training workspace and raw
archives are not required by `score`:

```powershell
& $py -m research.ml.gnn_scoring score `
  --bundle "$base/bundle" --bundle-sha256 $sha `
  --input "$base/test-input/input.json" `
  --output "$base/my-new-cuda-scores" --device cuda
```

Use `--device cpu` for CPU execution. Requesting unavailable CUDA fails; it
does not silently change device. Every command preserves existing destinations
and requires a fresh output folder. A rerun should use a different output name.
The bundle pins the inference source hashes and runtime versions. Editing the
scorer requires a reviewed new export and a new trusted manifest digest.

## Input and numerical contract

`input.json` declares the exact bundled feature-schema SHA256 and a list of
complete host/window graphs. Each graph entry has exactly these fields:

```json
{
  "file": "graphs/<host>_<window>.npz",
  "graph_id": "<host>_<window>",
  "sampling_key": "graphs/<host>_<window>.npz",
  "host_uuid": "<32 lowercase hex digits>",
  "window_start_nanos": 1557461700000000000,
  "nodes": 3493,
  "adjacency_edges": 14072,
  "native_events": 47860,
  "role": "test",
  "sha256": "<exact NPZ SHA256>"
}
```

The exported `input.json` is a complete usable example. Its top-level fields
are `version: 1`, `kind: darpa_graphsage_masked_reconstruction_v1`,
`feature_schema_sha256`, `window_nanos: 300000000000`, `selection` and `graphs`.
`selection` contains `scope`, `partition`, `source_graph_manifest_sha256` and
`all_partition_graphs_included`. The exporter binds replay inputs to the
verified preparation manifest. For separately prepared external graphs use
`scope: external_prepared_graphs`, `partition: external`, a null source manifest
digest and `all_partition_graphs_included: false`; graph roles must be external.
Declared external provenance is not independently certified by the scorer.

Each NPZ contains exactly four arrays; pickle/object arrays are forbidden:

| Array | Required representation |
|---|---|
| `nodes` | Sorted, unique, nonzero native entity UUID bytes; shape `(N,)`, dtype `V16` |
| `raw` | Shape `(N, 115)`, dtype `uint32`; unnormalized native counts |
| `indptr` | Shape `(N+1,)`, dtype `int64`; monotonic CSR offsets starting at zero |
| `indices` | Shape `(E,)`, dtype `int32` or `int64`; valid node indices |

Columns are the exact ordered outgoing 57 action-reference counts, incoming
57 counts and subject-without-predicate Event count in `feature_schema.json`.
Adjacency must be symmetric, sorted and unique, with native self edges removed;
isolated subjects are supported. UUIDs are row identifiers, never predictors.
Native counts include self references even though adjacency removes self edges.
Basic reference/Event count totals must reconcile. The scorer cannot recover
feature names from an unnamed numeric array or independently verify that an
external producer counted the native Events correctly. External preparation
must establish those semantics and complete windows before scoring.

`file` is a safe path relative to the manifest; moving or renaming it is allowed.
Keep `sampling_key` canonical and unchanged: it determines the original RNG
seed together with seed 42. Mask all seed-node vectors and 20% of sampled context
vectors. Iterate all seeds in order, batches of 256, fanouts 10/5. Features use
the frozen training `log1p`/population-zscore transform and float32 inference.
An individual row's result depends on its complete graph and batch/sampling
context; do not score a row by dropping its surrounding graph.

Explicit limits are 10,000 graphs, 50 million total rows, 2 million nodes and
20 million adjacency entries per graph, 512 MiB compressed and 1,200 MiB
uncompressed per NPZ, and a 10 MiB manifest. All existing prepared graphs fit.
The scorer refuses larger or malformed inputs instead of dropping rows.
CPU preparation has one batch of lookahead and overlaps CUDA transfers/forward
passes. It does not materialize an entire graph on the GPU.

## Outputs and interpretation

| File | Meaning |
|---|---|
| `scores.csv` | Every input node's native identifier, normalized-space MSE/MAE and training-mean reference MSE |
| `graphs.csv` | Graph coverage, native Event/adjacency counts and graph reconstruction metrics |
| `summary.json` | Completion receipt with totals, device/runtime, hashes and frozen-artifact checks |
| `progress.json` | Current graph/row counters; this alone does not indicate completion |
| `failure.json` | Failure details when scoring fails after creating its output folder |

`summary.json` with status `standalone_graphsage_reconstruction_complete` is
the completion signal. CSVs remain `.partial` until coverage and artifact
checks pass. Invalid bundles/manifest/preflight failures can stop before an
output folder is created. Never treat partial files as successful evaluation.

MSE and MAE are computed across 115 normalized features per node. Aggregate
metrics weight all node-feature targets, rather than taking an unweighted mean
of graph metrics. The reference predicts the normalized training mean, zero.
CSV row metrics and batch reductions can differ slightly from roundoff.
Security-label and threshold columns stay blank; JSON thresholds stay null.
High reconstruction error is not proof of an attack. No attack probability,
precision, recall, F1 or accuracy is produced. Recurring identities and
within-window context remain the limitations of the original experiment.

## Checks

```powershell
& $py -m unittest research.ml.tests.test_gnn_scoring -q
```

Nineteen scorer/report checks cover frozen inference, malformed inputs,
header/CSR allocation guards, tampering, coverage and CPU/CUDA agreement.
The scorer's software fixtures are explicitly synthetic and untrained. Separate real
DARPA replay checks compare every test row's coverage, frozen aggregate
metrics, row-file hashes and a CPU/GPU parity subset. Neither check changes
weights, scaler, labels or backend behavior. Original ML-09/ML-10 security
comparison and backend integration remain gated as described in
[the task-status audit](../report/task_status_20261102.md).

Reproduce the real row-coverage and parity verification after scoring. The
recorded two-graph CPU input contains 3,495 rows and exercises multiple batches:

```powershell
& $py -m research.ml.gnn_scoring inputs --work $work `
  --bundle "$base/bundle" --bundle-sha256 $sha --partition test `
  --graph-key 'graphs/223cbbce1bc5451e9d2e5b3a762f31c7_1557461700000000000.npz' `
  --graph-key 'graphs/223cbbce1bc5451e9d2e5b3a762f31c7_1557952500000000000.npz' `
  --output "$base/parity-input"
& $py -m research.ml.gnn_scoring score `
  --bundle "$base/bundle" --bundle-sha256 $sha `
  --input "$base/parity-input/input.json" `
  --output "$base/my-new-cpu-scores" --device cpu
& $py -m research.ml.gnn_results.verify_scoring --work $work `
  --bundle "$base/bundle" --bundle-sha256 $sha `
  --full-input "$base/test-input/input.json" --full-score "$base/my-new-cuda-scores" `
  --cpu-input "$base/parity-input/input.json" --cpu-score "$base/my-new-cpu-scores" `
  --output "$base/my-new-verification.json"
```

This verifier needs the completed graph manifest to prove that every recorded
test graph is present. The scorer itself remains independent of that workspace.
It checks every native row identity, finite values, blank security fields,
per-graph/global reconciliation, unchanged frozen artifacts and all 3,495 CPU
rows against their corresponding full CUDA replay rows (`rtol=1e-5, atol=1e-7`).
