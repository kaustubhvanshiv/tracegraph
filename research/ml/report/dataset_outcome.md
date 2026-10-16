# ML-R1.1 — dataset selection outcome and feasible learning tasks

Assessment date: **2026-10-16**. Scope: the downloaded Windows FiveDirections
subset and existing code/reports in this checkout. This is an evidence review,
not a new dataset scan, training run, benchmark evaluation or model selection.

## Decision and stop condition

**None of the four candidate tasks is ready for a credible end-to-end learning
or comparison experiment with the currently audited local evidence.** Parsing,
reference auditing, selected-event normalization and bounded source review are
executable now and have already produced useful artifacts. They do not supply
the missing classes, independent incidents or reviewed chain benchmark.

Apply the restored ML-R1 stop condition to this audited subset: **do not proceed
to ML-R2 or ML-R4, select a GNN, or train a DARPA detector on this evidence**.
Task 4 is conditional on a reviewed case and protocol; it is not confirmed
executable merely because it does not need per-event attack labels.

This finding is limited to the supplied/verified data. It is not a claim that
the complete DARPA release or every other candidate dataset is unsuitable.
ML-R1.2's LANL secondary-benchmark assessment remains pending and may inform a
later decision. Additional datasets/models or a changed research scope require
the user's approval. This report does not reactivate deferred tasks.

## Dataset identity and provenance

Selected primary dataset: **DARPA Transparent Computing Engagement 5 (TC E5)**,
starting with the FiveDirections Windows stream. Selection rationale is in
[primary_dataset_selection.md](../../../data/ml/comparison/primary_dataset_selection.md);
it is referenced rather than rewritten here. That document describes the
initial selection snapshot; later measured coverage and support availability
are recorded below and in the linked audit reports.

Actual raw source:

```text
D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections
```

The six gzip-wrapped Avro containers are segments **15, 17, 20, 23, 27 and 121**
of `ta1-fivedirections-1-e5-official-1`, totaling 1,891,510,041 compressed bytes.
The source support folder is `D:\Deep Learning\darpa-tc-e5-support`, containing
the report/schema ZIPs and operational event log. The support contents and
provenance are in [support_inventory.json](../../../data/ml/datasets/darpa/support_inventory.json).

The earlier analyses and restored task text refer to `../datasets/Darpa/`,
LANL, UNSW-NB15, CIC-IDS2017 and two local DARPA streams. All four historical
`../datasets/...` candidate paths are absent in this checkout. Only the six
FiveDirections containers are verified here; CADETS is not available at that
historical path and no CADETS inventory is established on this machine. Do
not infer current availability from analysis performed on another workstation.

## What the existing audit establishes

| Evidence and scope | Established result | Limitation |
|---|---|---|
| [Full reference report](../../../data/ml/datasets/darpa/full_reference_report.json), all six files | 60,000,000 records; 58,037,343 Events; 257,164 Subject definitions | Aggregate raw counts are not labeled sample counts or complete investigation graphs. |
| Same full audit | No Host/Principal definitions and no definition for actor parent `1fca97f4e4134d05869b31eb09df8770` in these files | Optional schemas do not guarantee reconstructible hosts, users or lineage. |
| [Preparation manifest](../../../data/ml/datasets/darpa/preparation_review_manifest.json), 2,000,000-record prefix of segment 121 | Three selected events normalize as typed file/access actions; file paths 3/3, time-valid process image 1/3, user/hostname fields 0/3 | Indicator-selected review sample; these ratios are not population-wide field-availability rates. |
| [Review annotations](../../../data/ml/datasets/darpa/review_annotations.json) | One report-reviewed positive, zero verified negatives, two unknowns; one related campaign | The positive is Codex's documented report alignment, not an independently supplied STARC event label. |
| [Ground-truth contract](../../../data/ml/ground_truth.md) and preparation run | Event-action target, unknown handling and chronological group split checks exist; split generation is blocked | Defining a target does not establish that it can be learned or evaluated reliably. |
| [Network host review](../../../data/ml/datasets/darpa/network_host_review.json), segment-121 prefix | 268 local-address observations support the association of the publishing host UUID with report IP 128.55.12.55 | This is supporting host/IP evidence, not a missing Host record or complete identity history. |
| [Reference review](../../../data/ml/datasets/darpa/reference_review.md) | Report-described May 16 benign driver setup lies outside these files' event ranges | It cannot be used to manufacture negative labels for current events. |

These are previously recorded run results checked during this assessment.
The full reference audit dates from 2026-10-11; semantic preparation was updated
on 2026-10-13. No new 60-million-record scan was run for ML-R1.1.

The original task premise "before any Avro pipeline work" is historical.
Streaming readers, SQLite joins and conservative conversion to the backend
`SecurityEvent` model now exist. See [SEMANTICS.md](../data_prep/SEMANTICS.md)
for supported mappings and explicit unknowns. The annotation-readiness gap
persists despite that engineering progress.

## Four candidate learning tasks

Effort estimates below are relative planning judgments, not measured runtimes
or delivery promises: **small** means bounded inspection/documentation using
existing artifacts; **medium** means reviewed case annotation, protocol and
integration work; **large** adds substantial missing-data/annotation work and
independent evaluation. Data access and independent review time are unknown.

| Candidate | Support in the current subset | Missing prerequisite | Estimated effort to close the gap | Current disposition |
|---|---|---|---|---|
| **1. Classify individual entities/events as malicious or benign** | Typed event records and provenance references support a possible event representation. One reviewed event is positive. | Verified benign actions, independently reviewed positives, representative sample selection, sufficient independent groups and valid partitions. An event label cannot automatically label its process, host or all associated edges. | **Large:** acquire/review missing evidence, quantify class/group coverage, resolve required features and validate leakage-safe partitions. | **Defer.** One positive and no negatives cannot support the proposed binary experiment. |
| **2. Learn relevance of candidate relationships/subgraphs** | Existing `TemporalCorrelationEngine` provides deterministic correlation signals and candidate relationships in the engineering pipeline. | Reviewed positive/negative relevance labels for relationship pairs or subgraphs; validated scenario/case outputs; mapping from event evidence to the relevance target. Event attack labels and relevance labels are different units. | **Large:** define annotation rubric, create/review cases, run candidate generation, verify sample size and scenario-held-out evaluation. | **Defer.** No labeled candidate-pair/subgraph corpus is established. `combined_score` is not ground truth. |
| **3. Reconstruct an ordered attack chain from evidence** | The support narrative and three artifact matches permit bounded manual chronology/source review. | A reviewed reference sequence linked to observed event IDs, justified causal steps, missing-step/unknown rules, retrieval candidates and a ranking evaluation protocol. Three temporal file opens do not establish the complete attack chain. | **Medium to large:** convert one bounded narrative case, reconcile telemetry gaps, independently review its event/edge mapping; more cases needed for stronger claims. | **Defer experimental claims.** Manual evidence inspection is executable now; scored chain reconstruction is not ready. |
| **4. Use an LLM to assemble/explain a chain from retrieved evidence** | `AIContextBuilder` and the summary provider interface provide engineering scaffolding. Per-event binary labels are not necessary for generation. | A case with a known reviewed attack sequence, reference-supported claim rubric, executable evidence/context pipeline, fixed model/prompt/budget and controlled evaluation. Provider access and an actual model have not been verified or selected here. | **Medium after a usable case exists**, potentially **large** if a new benchmark is needed. Verify data/terms/mappings before any external benchmark adoption. | **Defer comparison.** A mock summary or source-ID check does not validate chain accuracy. ML-R2's task-4 prerequisite is not met. |

Tasks 1 and 2 are learning objectives over different sample/label units. Tasks
3 and 4 are evidence retrieval, reconstruction and explanation objectives;
they do not become event classifiers by reusing the same telemetry. No
architecture, feature vector, hyperparameter or new dataset is selected here.

## Case, scenario and pipeline readiness

The four `data/scenarios/` directories contain only `.gitkeep` files. Task 29
does not currently supply populated, validated cases with event-level labels,
relationship truth or an ordered reference attack chain in those folders.
Other engineering fixtures, demo seed data and an attack-looking chain must
not be promoted into attack ground truth without review.

`AIContextBuilder` assembles a bounded `InvestigationContext`; the summary
service has a default mock provider and evidence-reference checks. These are
implementation capabilities, not evidence that an LLM recovers a known chain
or that each cited claim is supported. No external inference was invoked and
no DiagChain availability, licence, APT29 content or metrics were verified.

The XNOR experiment remains a synthetic educational artifact. It demonstrates
training mechanics and checkpoint reuse, not any of these four DARPA tasks.
The restored revised plan governs further research; recorded legacy checkmarks
do not satisfy its evidence gates.

## Remaining uncertainties and acceptance gates

- **Optional-field population:** broad raw type counts are known; complete,
  event-time-valid feature availability across scenarios is not. The three
  selected-event rates above cannot establish population coverage.
- **Scenario counts:** total Events are known, but independently annotated
  event counts per attack/benign scenario and relevance class are not. One
  campaign's phases must not be split into supposedly independent incidents.
- **Diversity:** only one Windows stream is verified. No claim of cross-host,
  cross-OS or cross-performer generalization is supported. The historical
  CADETS/FiveDirections diversity assumption is unverified on this machine.
- **Label provenance:** the report-derived positive retains its documented
  uncertainty; independent review and annotation coverage remain unresolved.
  Unknown events remain unknown, not benign.
- **Evaluation:** three partitions containing both classes are a necessary
  binary-evaluation gate, not a universal sufficient sample-size criterion.
  Required sample size depends on independent cases, imbalance and the claim.
  Model selection and fixed thresholds require separate validation evidence.
- **Missing data:** process restarts, nonconsecutive segments and out-of-order
  timestamps require explicit coverage/causality audits. More raw records alone
  do not create labels or an ordered reference chain.

## Executable work and recorded outcome

**Executable now:** inspect the documented evidence, reproduce bounded audits
if needed, maintain conservative mappings, and document feasibility/unknowns.
No scan rerun or extra implementation is necessary to establish this finding.

**Executable after specific prerequisites:** tasks 1/2 after reviewed labels,
sample coverage and independent evaluation groups; tasks 3/4 after a reviewed
ordered case and evaluation protocol, plus a verified implementation/provider
for the chosen comparison. Future benchmark adoption needs its own approval
and terms/mapping verification.

**Currently infeasible:** credible supervised detector training, learned
relationship scoring, a scored complete attack-chain benchmark, or an LLM
graph-context comparison using the three current review events alone.

ML-R1.1 is complete as a feasibility assessment with a stop finding. ML-R1 as
a whole remains incomplete because ML-R1.2 has not been performed. Do not
start ML-R2 until task 4 is actually shown executable and the stop finding is
revisited with new evidence. No trained model or improved-detection claim is
an output of this report.
