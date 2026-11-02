# DARPA task status and supervised benchmark readiness

Assessment: 2 November 2026. **The requested readiness audit is complete;
the original Event-level supervised dataset is not ready.** The completed
self-supervised GCN, GraphSAGE and GAT experiments remain valid for their
declared reconstruction objective. They do not supply missing action labels.

The [machine-readable local audit](../../../data/ml/datasets/darpa/readiness_audit_20261102.json)
rechecks current annotations, exact cached review rows, native time/identity,
source inventory, metadata resolution, support ZIP contents and completed GNN
artifact bindings. No label, split, timestamp, model or raw file was changed.

## What is complete

| Work | Evidence and status |
|---|---|
| Full local graph preparation | 37 archives, 345,099,571 records, 1,312 graphs and 24,106,424 node-window rows; verified |
| GCN, GraphSAGE and GAT training | Five epochs per family; checkpoints selected by development reconstruction MSE |
| Final reconstruction evaluation | Common 2,664,540-row test cohort; all three checkpoint/test receipts complete |
| Reconstruction comparison and diagnostics | GraphSAGE has the lowest average error; frozen residual replay, charts and reports complete |
| Standalone GraphSAGE reconstruction scorer | Separately approved frozen model/scaler reuse, portable prepared-graph inputs and CPU/CUDA scoring; [commands and verification](../gnn_scoring/README.md) |
| Current readiness audit | Six Event reviews and the existing 500-node unknown-decision set revalidated; supervised gate still fails |

See [the measured results](../../../data/ml/datasets/darpa/gnn_full/RESULTS_20261102.md)
and [method/reproduction guide](../gnn_results/README.md). Completed GNN weights
and final metrics were fingerprint-checked during this audit. The prior full
1,312-graph verification was linked, not needlessly repeated.

## Original project task mapping

The current task file retains the revised ML-R feasibility gates and deferred
ML-02 through ML-11 sequence. The user separately approved label-free DARPA
reconstruction. Record that work as its own completed experiment; do not check
off the original classification/security acceptance criteria from MSE alone.

| Project task | Current status | Evidence needed to move forward |
|---|---|---|
| ML-02.4 supervised preparation | Script exists; real eligible splits unavailable | Verified benign actions, adequate independent attack/benign groups, reliable time and identity mapping |
| ML-06/ML-07 original security GNN | Separate reconstruction specification and models completed; original supervised criteria unmet | Accepted target/labels and incident-safe input/split protocol; classification training or a separately reviewed detector protocol |
| ML-08 security evaluation | Reconstruction test/diagnostics complete in separate route; security metrics unavailable | Valid security ground truth and matching evaluation unit; predeclared thresholds and metrics |
| ML-09 deterministic versus GNN comparison | Not executed | Common labelled cases, common prediction target and written threshold/evaluation protocol before either run |
| ML-10 backend and graph API integration | Deferred by ML-07/ML-09 requirements | Completed comparison plus compatible feature/graph mapping, failure isolation and explicit output meaning |
| ML-11 full original research handoff | Reconstruction reports and commands complete; original report/reproduction criteria incomplete | Security comparison, integration account and independent end-to-end reproduction |
| Revised ML-R2/ML-R4 track | Existing feasibility stop is not cleared by reconstruction | A usable, independently validated ordered-case benchmark and the task-specific source/mapping checks |

These statuses preserve the acceptance criteria in
[tasks.md](../../../.kiro/specs/tracegraph/tasks.md) and
[requirements.md](../../../.kiro/specs/tracegraph/requirements.md). No original
checkbox is promoted to complete by this review.

## Current action labels

| Review category | Count | Supervised eligibility |
|---|---:|---|
| Reviewed attack actions | 3 | Three eligible actions across two named incident/group IDs |
| Reviewed benign action | 1 | Excluded: unresolved mixed clock epochs |
| Unknown candidate actions | 2 | Excluded from binary loss and security metrics |
| Eligible benign actions | **0** | Missing |

The existing positive and benign decisions are report/operational-log-derived
Codex reviews, not independent expert or STARC annotations. Their action-specific
scope and uncertainty remain recorded in the canonical annotation file.

The unchanged preparation split function rejects the six rows with:

1. At least three independent labelled groups required.
2. Verified benign and attack samples required in every partition.

The group count is a count of curated identifiers, not independent proof that
cases can be assigned to different partitions. With only two positive incident
groups, all three partitions cannot contain an independent positive incident.
Adding benign rows alone does not solve that positive-coverage problem. The
minimum structural gate is also not a statistical adequacy certification; a
meaningful evaluation needs enough independent examples and uncertainty analysis.

The structural split function was replayed with zero context as the least
restrictive check. It already fails. No supervised history horizon was selected,
and no split IDs were exported. The eventual past-only input window still needs
its own leakage audit after credible labels and groups exist.

## Source and annotation findings

- All 37 current gzip archives match the completed reference audit's source
  sizes and modification times. No additional unaudited gzip archive was found
  in the selected source folder. The raw data were not rescanned.
- The reference index contains 1,799,467 definitions, matches its expected
  per-source/type counts and passes SQLite `quick_check`. It was opened read-only.
- The Ground_Truth ZIP contains the ACT final report as PDF and DOCX; the
  Schema ZIP contains the schema files and schema PDF. No standalone or zipped
  CSV/JSON/JSONL/TSV annotation candidate is present in this local support folder.
- The ACT PDF is byte-identical to the previously reviewed source, SHA256
  `95785dd6e32e1585e3a3b49f7f69aac785ca9d2db05593ad919b1b627897f0a1`.
  The operational log also retains its prior fingerprint. This is an inventory
  and provenance check, not a fresh semantic review of every report page.
- The two unknown artifact-open candidates still lack the same parent Subject
  reference in the full local index. All six current process-resolution
  outcomes agree with the saved review rows. No metadata change upgrades a label.
- The benign BCDEDIT execution remains excluded because its chronology/context
  is not calibrated. Correctly identifying the command does not repair its clock.
- The separate node-pilot decision file retains 500 unknown labels and zero
  supervised-eligible rows, with a matching recorded fingerprint. Membership in
  an attack-node list is not a replacement for Event-action ground truth.

The four named `data/scenarios/` folders contain only placeholders. An existing
backend integration fixture tests graph relationships and correlation scores;
those assertions are not validated DARPA ACT action labels. No controlled
scenario was silently accepted as a replacement benchmark.

## Representation compatibility gap

The original Event target uses a past-only, event-centred provenance subgraph.
The completed GNNs use five-minute windows and reconstruct numeric node activity
with same-window neighbors. A current graph may therefore contain context later
than an individual Event's timestamp. The original temporal/incident isolation
rules do not become satisfied merely because this reconstruction run has
chronological train/development/test windows.

Likewise, `combined_score` expresses deterministic relationship relevance,
whereas these GNNs output reconstructed features. A common security target and
score conversion must be justified before ML-09. Native CDM feature counts
must also be reconciled with production `GraphResult` inputs before ML-10.
No threshold is fitted on the now-inspected reconstruction test cohort.

## Concrete evidence needed next

Use [the annotation evidence checklist](annotation_evidence_checklist.md)
and its empty intake sheet to collect source-backed action decisions. Priority:

1. Establish eligible benign actions using exact native Event/host identifiers,
   documented purpose and reliable clocks. Retain uncertain actions as unknown.
2. Establish additional independently justified attack groups and suitable
   benign coverage so training, validation and test can each contain both
   classes without sharing incidents or causal context.
3. Resolve or replace the historical benign examples with explicit evidence:
   the May 7 clock calibration, or the page-135 SCP alarm's clock/PID/CDL-to-CDM
   mapping. Their current ambiguity is documented in the
   [source-alignment review](../../../data/ml/datasets/darpa/ml02_alignment_resolution_20261027.md).
4. Review label provenance and sample size, then rerun canonical preparation and
   incident-safe split checks. Only a passed readiness review can justify a
   separately specified security model/evaluation phase.

No further broad download is justified as an automatic label fix. Additional
telemetry may be useful once a precise missing host/time interval or mapping is
identified. This audit did not check current Drive contents or download anything.

## Reproduction

From the repository root in the existing isolated research environment:

```powershell
.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m research.ml.data_prep.readiness_audit `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --support "D:/Deep Learning/darpa-tc-e5-support" `
  --reference ".cache/ml-runs/ml02-scp-all-references-20261027" `
  --prepared ".cache/ml-runs/combined-review-preparation-20261027/review_events.jsonl" `
  --annotations "data/ml/datasets/darpa/review_annotations.json" `
  --gnn-work "D:/Deep Learning/tracegraph-gnn-workspace" `
  --output "data/ml/datasets/darpa/readiness_audit_20261102.json"

.cache/ml-envs/darpa-gpu-py311/Scripts/python.exe -m unittest `
  research.ml.tests.test_readiness_audit research.ml.tests.test_prepare_dataset -q
```

Sixteen checks passed, including five new readiness checks. The software fixtures
only exercise evidence validation, class/group gates, canonical time, support
inventory and rejection of inconsistent rows; they are not DARPA labels.
