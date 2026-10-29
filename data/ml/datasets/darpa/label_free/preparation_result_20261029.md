# Separate label-free DARPA preparation - 2026-10-29

**Completed and independently verified.** The existing raw FiveDirections data
produced 1,358 unlabeled native actor-window vectors with 62 numeric features.
The [workflow guide](../../../../../research/ml/label_free/README.md) provides
reproduction commands, feature semantics and evaluation limits.

| Result | Value |
|---|---:|
| Available raw archives whose identity guards were checked | 37 |
| Complete overlapping archive read | 1 |
| Raw records decoded | 10,000,000 |
| Same-host Events in the time envelope, including purge gaps | 906,147 |
| Events in the five selected windows | 623,671 |
| Missing native actors / conflicting Event UUIDs / identical repeats | 0 / 0 / 0 |
| Actor-window rows before ownership exclusions | 1,575 |
| Excluded development / holdout rows belonging to earlier actors | 112 / 105 |
| Exported training / development / holdout rows | 1,184 / 76 / 98 |
| Total exported rows / features | 1,358 / 62 |
| Native Events contributing to exported rows | 444,011 |
| Shared sample actor IDs across each partition pair | 0 |
| Constant training feature columns | 30 |
| History length / minimum temporal purge gap | 300 / 300 seconds |
| Security labels unknown / attack / benign | 1,358 / 0 / 0 |
| Relevant software tests passed | 54 |

The native Event envelope is May 7, 2019, 13:05-13:40 UTC on host 1.
Training spans 13:05-13:20, development 13:25-13:30, and holdout 13:35-13:40.
These are 60/20/20 proportions of active time; row proportions differ after
ownership exclusions. Early timing does not certify normal or benign activity.

All 62 features come from native Event action/reference counts and active span.
No UUID value, PID, absolute time, path, command, source position, annotation or
offline metadata definition is a predictor. `log1p` and population z-score
parameters use training rows only. The representation is an aggregate numeric
activity vector; it is not an executed graph model or a reactivation of the
deferred supervised GNN tasks.

The [preparation report](preparation_report_20261029.json) records the full
feature order and fingerprints. The [independent verification](verification_report_20261029.json)
recomputed all 1,358 vectors using SQL aggregates, checked their native witnesses
and temporal bounds, recomputed normalization from training alone, and verified
the expected actor ownership and exported sample universe.

Shared native object contexts remain **634 / 1,059 / 440** for training/development,
training/holdout and development/holdout. Shared raw feature-profile counts are
**5 / 11 / 3**. These are disclosed rather than described as full context
isolation. Same-host/day correlation and later-actor selection limit inference;
independent attack-incident coverage and detection accuracy are not established.

Local artifacts are in:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\label-free-darpa-20261029
```

The deduplication index is 268,972,032 bytes. Feature rows, source traces and
normalization parameters remain local; only code, plan and summaries go to Git.
The original supervised labels/graphs and ML-02.4 status are unchanged. No new
dataset, package, GPU configuration, model, security score or threshold was used.
The approved label-free preparation is complete; model specification and
training remain subsequent work, and would not establish attack detection
performance without an appropriate independently labeled evaluation.
