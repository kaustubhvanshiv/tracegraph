# CPU preparation with NVIDIA GPU training

Completed on 2 November 2026: GAT finished all five epochs, all three models
received final test evaluation, and checkpoint/graph verification and frozen
error analysis passed. See the [measured results](../../../data/ml/datasets/darpa/gnn_full/RESULTS_20261102.md)
and [reporting/replay guide](../gnn_results/README.md). The restart notes below
describe the execution history; no full-data training remains active.

This execution adapter overlaps one CPU batch producer with CUDA computation.
It is used for the remaining full-local DARPA GAT run and subsequent frozen
test evaluation. Completed GCN and GraphSAGE reports/checkpoints are reused.
Their original serial-CUDA training remains recorded accurately.

The queue holds at most two prepared batches. Host tensors use pinned memory
and nonblocking CUDA transfers. NumPy seed order, neighbor sampling and mask
generation retain exactly the original RNG consumption. Finite-gradient checks
are combined into one GPU reduction instead of separate host synchronizations.
Batch size 256, fanouts 10/5, masking, five epochs, Adam settings, float32,
features, source coverage and chronological partitions are unchanged.

## Measured throughput and validation

A three-repeat GAT training benchmark used three real **training** graphs,
30,654 seed nodes, and no selected checkpoints or test data. Median durations:

| Loop | Seconds |
|---|---:|
| Original serial preparation | 6.9604585 |
| Bounded CPU prefetch | 5.9571895 |

That is 1.1684 times the throughput, or about 14.4% less elapsed time on this
workload. It is not a full-epoch speed guarantee. Masked reconstruction metrics
matched in the benchmark. This is a throughput measurement, not model-quality
evidence or attack-detection accuracy.

The [aggregate benchmark receipt](../../../data/ml/datasets/darpa/gnn_full/prefetch_benchmark_20261101.json)
records the three timing pairs. To repeat this local training-only measurement,
use `python -m research.ml.benchmark_gnn_prefetch` in the pinned CUDA
environment **when no full run is active**. It uses the existing D: prepared
workspace and writes its detailed receipt under `.cache/`. Do not run a competing
benchmark alongside training.

Fourteen focused tests passed: seven original full-GNN tests and seven adapter
tests. The latter cover exact batch/mask parity and coverage, cancellation,
producer failures, graph tampering, all three CUDA model/optimizer updates,
execution-profile tampering, and original checkpoint selection/reload/final-test
orchestration on a tiny software fixture. Fixture metrics are not DARPA results.

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m unittest `
  research.ml.tests.test_gnn_prefetch `
  research.ml.tests.test_gnn_full.FullGNNTests -q
```

## Reviewed local restart

The original frozen pipeline code/configuration and `contract.json` are kept
intact. `execution_profile_prefetch.json` separately fingerprints this adapter,
the original contract, graph/scaler/preparation artifacts, and the completed
GCN/GraphSAGE reports and checkpoints. All 37 raw source sizes/times were
rechecked. The stopped GAT initialization checkpoint and logs were preserved
under `gat-before-prefetch-20261101`. GAT restarts cleanly: the earlier run
completed no training epoch and has no optimizer state to resume.

`run.py` explicitly dispatches the original trainer's epoch calls to the
prefetch implementation for this process. Original contract checks remain
active. Supplementary `runs/<family>/execution.json` files identify which
implementation trained and tested each family; the final aggregate also
records the execution profile hash. Do not edit adapter code while running.

The following command is for the already reviewed local workspace. **Do not
launch it while a worker is active, or directly over a later partial GAT run.**
It requires the local supplementary profile; it is not a fresh-data bootstrap.

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -u -m research.ml.gnn_accel.run `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --audit ".cache/ml-runs/ml02-scp-all-references-20261027" `
  --work "D:/Deep Learning/tracegraph-gnn-workspace" `
  --config "research/ml/gnn_full/config.json"
```

For a teammate starting from raw files, follow `../gnn_full/README.md` for the
original complete workflow. Applying this adapter to another prepared workspace
requires its own stopped-worker and integrity review; never copy another
machine's execution profile as evidence. Required local artifacts include the
graphs, scaler, audit, original contract and completed model checkpoints.

Watch the running job with:

```powershell
Get-Content 'D:/Deep Learning/tracegraph-gnn-workspace/stdout.log' -Tail 20 -Wait
Get-Content 'D:/Deep Learning/tracegraph-gnn-workspace/progress.json'
```

The worker has no live optimizer-state resume support. Interrupting it can lose
the current model's unfinished training. All source files and preserved runs
remain untouched. Completion still requires all three selected checkpoints,
all three final reconstruction reports and a valid `complete.json`.
