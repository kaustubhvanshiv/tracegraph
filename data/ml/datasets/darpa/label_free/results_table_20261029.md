# Frozen reconstruction results

| Partition | Rows | Autoencoder MSE | Autoencoder MAE | Mean reference MSE | Mean reference MAE |
|---|---:|---:|---:|---:|---:|
| train | 1,184 | 0.110711493 | 0.100859731 | 0.516129017 | 0.215315059 |
| development | 76 | 0.033141211 | 0.066414706 | 0.147637546 | 0.164320454 |
| holdout | 98 | 0.072372757 | 0.090199672 | 0.282537609 | 0.181020141 |

MSE/MAE average errors in normalized feature space. These are the original frozen
results, not replay-rounded replacements or attack-detection metrics. The mean
reference is fitted on training only. No rule/GNN security comparison is claimed.
