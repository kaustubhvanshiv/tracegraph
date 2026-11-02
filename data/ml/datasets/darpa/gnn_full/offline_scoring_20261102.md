# Standalone GraphSAGE scoring — 2 November 2026

The approved standalone scorer reuses the verified development-selected
epoch-5 GraphSAGE model (22,707 parameters) and its training-only scaler.
It scores complete prepared five-minute graphs on CPU or CUDA, without
retraining or access to the original raw archives after export.

| Full test replay | Measured result |
|---|---:|
| Graphs scored | 270 / 270 |
| Node-window rows scored | 2,664,540 / 2,664,540 |
| Native Events represented by those graphs | 39,845,072 |
| Reconstruction MSE | 0.3548783080187744 |
| Reconstruction MAE | 0.0667724345899813 |
| Training-mean reference MSE | 0.5591168302698646 |
| Absolute difference from frozen MSE, MAE and reference | 0 for all three |
| Local NVIDIA RTX 4050 scoring time | 122.60 seconds |
| Portable frozen bundle | 115,395 bytes; eight files |

Every native row identity and row count was checked against the prepared
graphs. All row metrics are finite; graph/global totals reconcile with the
row CSV. File, checkpoint-state, scaler, input and source-code fingerprints
are recorded in the [machine-readable verification receipt](offline_scoring_20261102.json).
The output contains a row-error CSV, graph metrics and a completion receipt.

A separate CPU run scored 3,495 real rows in two of the same test graphs,
including a multi-batch graph. Every selected CPU row agrees with its CUDA
counterpart within `rtol=1e-5, atol=1e-7`. CPU mode was tested in the existing
CUDA-capable Python environment with GPU visibility disabled; an independent
CPU-only wheel installation and clean-machine reproduction were not performed.
These runs have different row counts and do not form a CPU/GPU speed benchmark.

All **47 relevant software tests pass**, including 19 new scorer/report checks.
They cover frozen inference, full seed coverage, source-folder independence,
CPU/CUDA parity, malformed graphs and feature schemas, safe array-header/CSR
bounds checks, artifact tampering, partial failures and unsupported security
claims. The scorer's test fixtures are synthetic and untrained; the table
above comes from real prepared DARPA test graphs.

Trusted final bundle manifest SHA256:

```text
f79497e145e1ec873fb79fda42917d7d0c05eaf0ea44a8a41bf12cec7075d679
```

The local bundle and outputs are under
`.cache/ml-runs/graphsage-offline-20261102/`; weights, copied graphs and native
row-level outputs remain local. The published receipt contains aggregates and
fingerprints. Earlier scorer-validation revisions were preserved separately
inside that local folder; the trusted digest above identifies the final bundle.

This is numerical reconstruction replay, with unknown security intent.
No labels, security threshold, attack probability or detection accuracy are
inferred. The inspected test cohort supplies no fresh model-selection evidence.
Within-window context and recurring native entities remain limitations.
External prepared-graph Event semantics need validation by their producer.
Backend integration remains deferred.

See [the teammate commands and input/output contract](../../../../../research/ml/gnn_scoring/README.md)
and [the original project task gates](../../../../../research/ml/report/task_status_20261102.md).
