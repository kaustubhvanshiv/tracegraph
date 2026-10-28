# DARPA background and grouping review - 2026-10-28

**Completed the next preparation step:** a deterministic, unknown-label review
pool and a conservative evaluation-group manifest are ready. No benign label,
model input, partition or trained model was manufactured.

| Measurement | Result |
|---|---:|
| Review window, UTC | May 7, 2019, 13:05-13:10 |
| Publishing host | FiveDirections 1 |
| Available overlapping archive read completely | 1 |
| Raw records read | 10,000,000 |
| Selected native Events in the window | 162,830 |
| Distinct nonconflicting selected Events | 162,830 |
| Observed node identities in the review pool | 7,034 |
| Seed / review budget | 42 / 500 |
| Frozen review candidates | 500 |
| Candidate labels unknown / verified benign | 500 / 0 |
| Selected candidate identities also present in the attack pilot | 60 |
| Conservative evaluation groups for the current two cases | 1 |
| Relevant software tests passed | 34 |

The five minute buckets contain 56,145, 25,021, 21,724, 41,521 and 18,419 raw
Event records. These are activity counts in the local subset, not proof of
continuous release coverage or benign intent. Full source counts/type counts
match the existing audit; raw timestamps remain unchanged.
The reread records are part of the existing corpus, not additional unique data.

## Background evidence decision

The review window precedes the first attack day listed in the ACT report's
page-8 schedule. It was selected without node-reference membership, native
types or metadata completeness. That timing is a review rationale, not a benign
ground-truth rule: setup/testing or unreported activity may exist. The operational
log's documented May 7 clock reset concerns host 2; no correction is applied to
this host-1 data, and absence of a logged reset is not complete calibration proof.

The complete cached Subject-command search returns two `filemon` leads, both
on host 1 at approximately 20:13 UTC on May 17. They do not establish the benign
setup described for May 16 or the earlier May 17 host-2/host-3 setup. The report
also includes starting the driver during the later attack (page 126). Both leads
remain excluded from new benign-label assignment; no new attack label is inferred
from a command name either. Exact native UUIDs, positions and evidence decisions
are preserved in the [group review](group_review_20261028.json).

All 500 candidates retain NULL labels. Each has a native host/UUID/anchor and
an exact source Event witness. They are evidence-review IDs, not normal training
samples. Metadata for an expanded training cohort has not been recovered or
validated. Only the original pilot has completed the uniform metadata pass.

## Grouping decision

ACT page 8 explicitly says this engagement did not simulate named threat actors.
Shared Drakon tooling or shared infrastructure therefore does not identify a
common campaign. Conversely, different dates/hostnames alone do not prove that
the cases are independent for evaluation.

Pages 91-92 and 126 explicitly connect host-1 May 16 verifier persistence with
the May 17 continuation. Those phases must stay together. The current two
pilot cases are conservatively assigned to the same **evaluation holdout group**
until separation is justified. This is a preparation constraint, not a claim
that May 9 and May 17 were one real attack campaign or an actual test partition.

The group manifest covers the exact two case IDs and the pinned uniform graph.
The auditor rejects missing cases, multiple supposedly conservative groups or
unsupported independence/common-actor claims. Original Event-level groups and
all six Event annotations remain unchanged.

The background draw also exposes a concrete leakage risk: **60 of 500 selected
node identities recur in the attack pilot**. Keep the frozen draw intact for
review. Before future splitting, overlapping entity/anchor/context samples must
be assigned together or purged under a documented rule. Do not call the earlier
window an independent negative group or redraw after inspecting reference labels.

## Verification and artifacts

The auditor independently recomputed the seeded ordering from all 7,034 frozen
identities and verified the exact 500 selected IDs. All 500 native associations
were independently checked against 497 distinct raw source Events: host, UUID,
role, timestamp, position and full raw fingerprint agree. Original annotation
SHA-256 remains:

```text
f3c129e55ed3117f4b69b19c0cc3c15b8c12ce2f7a19af6391682aedbb8ce2be
```

The pool, selected IDs and verification files are local:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\background-review-pool-20261028
```

Candidate-file SHA-256:

```text
429c3a9b41673aefd49138acdeb83002ff58195278c17101f886b69d1af70f82
```

Code, source pins, [background completion summary](background_review_report_20261028.json),
[policy v2](preparation_protocol_v2_20261028.json) and
[updated readiness audit](background_group_protocol_audit_20261028.json) are
published. The 500 candidate IDs, raw telemetry, source PDF and databases are
not uploaded. Use the [reproduction guide](../../../../../research/ml/node_benchmark/BACKGROUND_REVIEW.md).

## Training readiness

The conservative grouping-review requirement is satisfied for this pilot.
Four preparation gaps remain: an accepted background training cohort, reviewed
binary node ground truth, sufficient independent whole groups (the safe current
assignment has only one), and a frozen input history horizon. The unknown-label
review pool is not an accepted training cohort. The original Event-level gate
also remains three eligible attack actions and zero eligible benign actions.

No extra download, package installation, GPU use, model selection or training
was required. The existing two-case graph and its security labels were preserved.

Sources reviewed: the existing `TA51_Final_report_E5.pdf` (physical pages 8,
26-27, 91-92, 108-110, 126-127 and 135; key pages visually checked), SHA-256
`95785dd6e32e1585e3a3b49f7f69aac785ca9d2db05593ad919b1b627897f0a1`,
and `Engagement-5-Event-Log.md`, UTF-8/LF SHA-256
`70b111fff7bc4662d4c22664be19c4c08702a36676f31f160d4b3a856ee5c3c9`.
