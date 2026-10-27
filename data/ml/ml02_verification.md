# ML-02 requirement verification — 2026-10-11

**Latest SCP follow-up, 2026-10-27:** 37 archives now have complete audits,
totaling 345,099,571 raw records. Parts 18-20 did not establish a new benign
label; full-record review distinguishes repeated filename matches from the
specific source example. Existing six-row identity chains and annotations are
unchanged. The split gate still rejects training. See the
[current SCP follow-up](datasets/darpa/ml02_scp_followup_20261027.md).

**Earlier ML-02.4 continuation, 2026-10-27:** all 34 local archives are fully
audited (315,099,571 records). Two additional manually aligned attack actions
normalize successfully; the combined review set has three attacks, one
clock-excluded benign action and two unknowns. There are two eligible attack
incident groups and no eligible benign examples. Split checks still reject
training, and ML-02.4 remains partial. All 43 research tests pass. See the
[current continuation report](datasets/darpa/ml02_label_review_20261027.md).

**ML-02.4 execution, 2026-10-17:** all 28 downloaded archives now have
full scans, totaling 280 million records. The final preparation rerun reads
12 million source records and normalizes four reviewed events: one attack,
one benign administrative execution excluded for clock uncertainty, and two
unknowns. The split-eligible set still has one attack group and no benign
examples; no supervised splits or training were produced. All 43 research
tests pass. ML-02.4 remains incomplete for real supervised partitions. See the
[current label-evidence review](datasets/darpa/ml02_label_review_20261017.md).
Earlier snapshots below describe prior data and code states.

**2026-10-17 update:** 28 local archives pass checksum verification. The expanded
reference audit covers all 10 downloaded host-1 files (100 million records);
the other 18 files have bounded prefix inspections. Preparation can now import
audited metadata across segments. The same three selected events supply
hostnames in 3/3 cases and a linked username in 1/3, with process coverage still
1/3. All 38 research tests pass. Labels remain one report-reviewed positive,
two unknowns and zero verified negatives; ML-02.4 remains incomplete and no
supervised splits or training were performed. See the
[refresh report](datasets/darpa/download_refresh_20261017.md).

Updated 2026-10-13: typed offline CDM normalization and host-scoped reference
joins are now implemented. The real two-million-record rerun produces three
file-access events with paths and one time-valid Firefox process image. All
32 tests pass. ML-02.4 remains incomplete for real supervised partitions;
the verified-benign and independent-group evidence gaps are unchanged. See
[the semantic mapping notes](../../research/ml/data_prep/SEMANTICS.md).

Overall conclusion: **ML-02 is partially complete; real-data preparation and
supervised partition generation remain blocked**.

Prerequisite ML-01.6 is complete: the selected dataset is DARPA TC Engagement 5,
FiveDirections Windows. The exact download path is recorded in
[ground_truth.md](ground_truth.md).

| Subtask | Verified status | Evidence |
|---|---|---|
| ML-02.1 prediction and label definition | Complete | Exact dataset/path, documented ACT-action target, positive/negative/unknown evidence rules, unique Event sample unit and event-centered temporal provenance graph definition are documented. Graph horizon is a later experiment parameter; architecture is not selected. |
| ML-02.2 split strategy definition | Complete | Chronological whole-group 60/20/20 target, incident isolation, UUID deduplication/conflict quarantine, past-only context and training-only preprocessing rules are documented. Code rejects insufficient classes/groups and temporal/context overlap. |
| ML-02.3 controlled-scenario use plan | Complete as planning | All four Task 29 scenarios have intended use, evidence requirements and limitations. They supplement the primary test set. Task 29 itself remains unvalidated; folders contain only `.gitkeep`, so no scenario evaluation or labels are claimed. |
| ML-02.4 preparation on actual dataset | Incomplete | Streaming reader, privately registered CDM adapter, `SecurityEvent` validation, reviewed label import, reference joins, split checks and ID-only export are implemented. Real-data split generation fails the evidence gates; no supervised partitions exist. |

## Work completed during verification

Made the graph sample definition precise and documented the intended use and
limitations of each controlled scenario. Corrected checklist statuses for
definition/planning tasks; their completion does not require a trained model.

Added a check that rejects a positive incident ID assigned to multiple split
groups, and required positive incident IDs during annotation import. Added
configurable split export with default `data/ml/splits/`, as required by
ML-02.4. Export contains IDs only, preserves existing destinations
and runs only after validation. A synthetic integration fixture verifies
successful export; it is not used as security training data.

## Validation and actual evidence

The research suite passes **24 tests**. Added tests cover incident IDs crossing
groups and validated split export to the requested directory without overwrite.

The current annotation set is **one report-reviewed positive, zero verified
negatives, two unknowns and one campaign**. The selected review events are not
a representative training sample. The full raw reference audit decoded all
60 million records across six containers; it established missing entity
definitions rather than supplying attack labels for unannotated events.

The real preparation rerun inspects a two-million-record prefix of segment
121, finds all three listed events and rejects supervised splits. See
[preparation_review_manifest.json](datasets/darpa/preparation_review_manifest.json)
for counts and blocking reasons. No `data/ml/splits/` directory is created
by this blocked run.

## What prevents completing ML-02.4

Verified benign events and enough independent positive/benign groups to produce
chronological train/validation/test partitions containing both classes are
absent. Additional telemetry/annotations must provide this evidence. Related
May 16 persistence and May 17 elevation phases cannot be separated into
independent attack groups. Unknown events cannot be relabeled benign.

Complete required reference/semantic coverage for the eventual features, review
annotation coverage and provenance, then rerun preparation with the intended
history horizon. Inspect class/group counts and achieved partition proportions
before claiming ML-02 complete. No model training or performance conclusion
is justified by the current preparation outputs.
