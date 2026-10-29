# Label-free training readiness and task check - 2026-10-29

**Ready for the full label-free reconstruction run.** The training pipeline and
separate final evaluator are implemented and tested. Two real-data three-epoch
CPU smoke runs produced exactly identical histories and model states. The
[task audit](../../../../../research/ml/label_free/TASK_STATUS.md) confirms this
is the approved separate route, not completion of the original supervised/GNN
tasks. Full training and real holdout evaluation remain unexecuted.

| Check | Result |
|---|---|
| Input | 62 fixed normalized DARPA features |
| Model | 62 -> 16 -> 4 -> 16 -> 62 autoencoder, 2,210 parameters |
| Runtime | Python 3.11.9, PyTorch 2.15.0+cpu, NumPy 2.4.6 |
| Optimizer | Adam, LR 0.001, weight decay 0.0001, batch 64 |
| Readiness budget | Two runs, three epochs each, seed 42 |
| Data used per run | 1,184 training and 76 development samples |
| Optimization | 57 finite update steps per run; weights changed |
| Checkpoint | Development-MSE selection and exact reload verified |
| Same-runtime reproducibility | Identical histories and checkpoint states |
| Real holdout model evaluation | Not run; 98 rows reserved |
| Software validation | 65 relevant tests passed; `pip check` passed |

Reconstruction metrics from the first smoke run:

| Metric | Initial model | Selected epoch-3 model | Training-mean baseline |
|---|---:|---:|---:|
| Training MSE | 0.544976 | 0.496924 | 0.516129 |
| Training MAE | 0.313643 | 0.244688 | 0.215315 |
| Development MSE | 0.184693 | 0.145567 | 0.147638 |
| Development MAE | 0.266208 | 0.192578 | 0.164320 |

Development MSE improved slightly over the simple baseline while MAE remained
higher. This smoke check establishes executable optimization and model
selection, not a final quality result. No configuration was chosen using real
holdout reconstruction errors.

The [smoke report](smoke_training_report_20261029.json) preserves exact losses,
runtime and code/checkpoint/data fingerprints. The
[readiness audit](training_readiness_report_20261029.json) confirms both runs
match, weights reload, and the final evaluator rejects the actual smoke
checkpoint before opening holdout vectors. Tests also guard holdout access
during training. Checkpoint model-state SHA-256:

```text
6ba09ffded514cc1129b75482fd1dc4bf864da15398bcf2226f6645135146e9f
```

Local run artifacts are under:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\label-free-training-ready-20261029
```

The [training guide](../../../../../research/ml/label_free/TRAINING.md) contains
the pinned-runtime setup, smoke check, full-run command and separate final
evaluation command. Weights and feature data remain local. Only code, runtime
pins and aggregate reports are published.

Original supervised annotations and policy fingerprints are unchanged. Unknown
security intent and shared object context remain; reconstruction error is not
attack probability or detection accuracy. Original ML-02.4 remains incomplete,
and the deferred GNN tasks have not been reactivated or marked complete.
