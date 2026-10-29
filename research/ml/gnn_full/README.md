# Full local DARPA: GCN, GraphSAGE and GAT

User-approved target: **self-supervised masked-node feature reconstruction**.
Read the [frozen task specification](TASK_SPEC.md) before interpreting results.
This route covers every locally downloaded archive; it does not turn unknown
security intent into benign labels or claim full Engagement 5 coverage.

## Inputs and scale

- 37 unchanged FiveDirections `.bin.gz` archives, 10,956,483,982 compressed bytes.
- 345,099,571 raw records; 330,788,968 raw Event records before deduplication.
- Raw source: `D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections`.
- Complete prior audit: `.cache/ml-runs/ml02-scp-all-references-20261027/`.
- Separate derived workspace: `D:\Deep Learning\tracegraph-gnn-workspace`.
- The earlier 1,358-row autoencoder dataset is not the GNN input.

The actual graph/node counts are unknown until full extraction and global
deduplication complete. The [inventory](../../../data/ml/datasets/darpa/gnn_full/local_inventory_20261029.json)
and [real-file preflight](../../../data/ml/datasets/darpa/gnn_full/preflight_20261029.json)
record the measured starting point. The 100,000-record preflight is only a
throughput/storage measurement, not a selected training subset. It projected
about 17.2 GiB of staging data and roughly two hours for scanning if that prefix
were representative. Deduplication, graph verification and training are extra;
these projections are not a guaranteed duration or storage upper bound.

## Sequential execution

The pipeline performs these stages automatically, stopping on failed checks:

1. Read all 37 archives completely; validate counts, metadata and gzip exhaustion.
   Write resumable per-source Parquet files and SHA-256 receipts.
2. Globally deduplicate native `(host,Event UUID)` keys; remove identical repeats
   and quarantine all conflicting raw-record fingerprints. Export five-minute
   host/time buckets. Delete only verified derived staging copies after durable
   deduplication/export; source archives stay untouched.
3. Compile every eligible graph and independently recompute all node vectors
   with SQL. Fit the scaler on training node-windows only. Record native entity
   overlap, purge gaps, invalid-record exclusions and partition coverage.
4. Train GCN, then GraphSAGE, then GAT using sampled neighbors, every eligible
   seed node per epoch and five maximum epochs. Choose by development MSE.
5. Reload all three selected checkpoints and evaluate the temporal test cohort
   only after every model is selected. Save reconstruction metrics/reference.

The workload is CPU/disk-heavy until training. The RTX 4050 is used for the GNN
batches. This is homogeneous message passing over a projection of native
references; action counts are features and native metadata kinds are not inferred.
It is within-window feature imputation, with recurring entities across temporal
partitions. It is not independent-incident attack classification.

At the user's request the extraction was upgraded to **four parallel CPU
readers**, and DuckDB uses **ten threads** for deduplication/aggregation. The
machine has ten physical cores / sixteen logical threads but only about
2.6 GiB RAM was available at the resource check, so four reader processes are
the current memory-bounded setting. Reader subprocesses do not load GPU
libraries; the main process defers importing them until training. This aims
for faster throughput without exhausting memory, not constant 100% CPU/GPU
utilization. GPU work starts when verified graphs are ready.

Three verified source archives were preserved when switching from serial to
parallel extraction. The original contract is retained as
`contract.serial-resource-revision.json`, with the authorized change recorded
in `cpu_resource_revision.json`. The unfinished derived source was preserved
and restarted. The objective, split rules, schema and full local coverage did
not change.

The isolated CUDA environment has PyTorch 2.15.0+cu132, PyG 2.8.1, DuckDB 2.0.0
and PyArrow 26.0.0. All three real PyG operators passed CUDA forward/backward;
the dependency lock is [requirements-gnn.txt](requirements-gnn.txt). Six new
software checks cover full-stream/dedup integrity, independent node features,
temporal gaps, bounded sampling, CUDA gradients and the complete three-model
execution sequence on a tiny software fixture. Fixture metrics are not DARPA
training results. The full relevant suite contains 93 passing tests.

From the repository root, using the approved derived D: workspace:

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -u -m research.ml.gnn_full.run `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --audit ".cache/ml-runs/ml02-scp-all-references-20261027" `
  --work "D:/Deep Learning/tracegraph-gnn-workspace" `
  --config "research/ml/gnn_full/config.json"
```

Do not start a second instance while the first is running. Large artifacts,
environment and checkpoints stay local; source code and aggregate evidence
belong on `deeplearning/shlok`.

## Live output and completion

The launched job records `process.json`, `stdout.log`, `stderr.log` and atomic
`progress.json` in the work directory. To see actual live output:

```powershell
Get-Content -LiteralPath 'D:\Deep Learning\tracegraph-gnn-workspace\stdout.log' -Tail 30 -Wait
```

Closing a log viewer does not stop the worker. Inspect `stderr.log` for runtime
warnings/errors; the current phase is in `progress.json`. `failure.json` records
an unsuccessful invocation. Existing receipted phases can be reused only with
the same frozen code/configuration/runtime and unchanged inputs. A partial
unreceipted source/bucket export needs inspection before resuming; do not
silently skip it or launch multiple jobs against one work directory.

Parallel per-source stdout/stderr may additionally appear in
`bootstrap.stdout.log` / `bootstrap.stderr.log`; the main live log records
combined source progress. The earlier refused duplicate launch is recorded
separately and is not a current worker failure. A background worker can be
hidden from sandbox process listings, so inspect actual progress or the host
process before declaring it stopped. A quiet current-thread follow-up checks
completion/failures every 30 minutes; it does not start duplicate jobs.

`complete.json` is the completion marker, created only after full verified
preparation, all three training runs and all three final reconstruction tests.
Its absence means the full experiment is not complete. Checkpoint paths are
`runs/gcn/best.pt`, `runs/graphsage/best.pt` and `runs/gat/best.pt`. Reconstruction
MSE/MAE are not attack probabilities or detection accuracy. CPU/GPU scatter
numerics may differ; exact bitwise GNN repeatability is not promised.
