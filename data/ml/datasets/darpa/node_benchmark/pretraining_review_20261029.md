# Evidence review and fixed input history - 2026-10-29

**Completed the evidence-sufficiency review and bounded input definition.
Supervised dataset preparation remains incomplete.** The available support
files do not establish eligible binary ground truth for the 500 frozen review
candidates. The [reproduction guide and evidence requirements](../../../../../research/ml/node_benchmark/PRETRAINING_REVIEW.md)
explain what is needed to finish before training.

| Result | Measured value |
|---|---:|
| Candidate evidence-sufficiency decisions recorded | 500 |
| Unknown labels / eligible supervised candidates | 500 / 0 |
| New verified attack or benign labels | 0 |
| Pilot identity-overlap flags retained | 60 |
| Future-start witness-chain flags retained | 7 |
| Native witness action types reviewed | 16 |
| Fixed node input history | 300 seconds |
| Native Event-reference neighborhood | 1 hop |
| Minimum purge gap | 300 seconds |
| Existing windows checked for history fit | 3 |
| Remaining dataset readiness blockers | 3 |
| Relevant software tests passed | 46 |

The interval is `[end - 300 seconds, end)` with anchor `end - 1` ns. It fits
the review window and both pilot cases without future Events or an extra
nanosecond outside the review interval. This fixes the history-definition gap
only. It does not prove continuous telemetry, online metadata availability,
valid features or independent partitions. Required native process starts must
precede each relation's Event; no timestamp repair was made.

The source review compared candidate actions/context with ACT physical pages
8, 26-31 and 135, plus the operational log's May 7 section. May 7 dates on
pages 28-31 are historical logon fields embedded in May 9 attack output, not
action labels for the earlier review window. Operational recovery concerns a
different host; false-positive examples concern different dated actions.
No new binary label follows. This is a Codex evidence-sufficiency review,
not expert/STARC annotation.

The [source findings](evidence_findings_20261029.json) preserve those decisions
and hashes. The [decision summary](source_evidence_review_report_20261029.json)
binds all 500 NULL decisions to the existing packet fingerprint. Local
`review_decisions.jsonl` SHA-256:

```text
c71c5b4786fd7c436eee5bb6c607e820b2c013f98f1b4220c90946ac884e7733
```

The [current audit](pretraining_protocol_audit_20261029.json) removes
`history_horizon_not_frozen` after checking the
[pinned input specification](node_input_spec_20261029.json). Remaining blockers:

- No accepted background training cohort.
- No reviewed binary node attack/benign ground truth.
- Only one conservative evaluation group, insufficient for three independent
  chronological partitions.

The separate original Event track remains **three eligible attack actions,
zero eligible benign actions**, with annotations and history selection unchanged.
Node evidence decisions were not copied into it. No new download, feature
vector, graph input, partition, model selection or training occurred. ML-02.4
is not marked complete. Completion requires trustworthy label evidence and
sufficient independent group coverage; code cannot manufacture it.
