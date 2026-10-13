# ML-02 — ground truth and split plan

Status on 2026-10-11: **label contract defined; review preparation executed;
training blocked by evidence coverage**.
ML-02.1 and ML-02.2 definitions and ML-02.3 scenario planning are complete.
ML-02.4 remains incomplete for the actual dataset. No labeled splits or model
performance claims exist. The support ZIPs are now available under
`D:\Deep Learning\darpa-tc-e5-support`; see the
[support review](datasets/darpa/support_review.md) and
[source inventory](datasets/darpa/support_inventory.json).

## Selected dataset

DARPA Transparent Computing Engagement 5, FiveDirections Windows stream.
Exact raw source path:

```text
D:\Deep Learning\fivedirections-20261010T174625Z-1-049
```

See the [primary dataset decision](comparison/primary_dataset_selection.md),
[local inspection](datasets/darpa/fivedirections_local_inspection.md), and
[support-file checklist](download_checklist.md). This absolute Windows path
supersedes the task file's historical `../datasets/` examples for this download.

## Prediction target and label contract (ML-02.1)

Prediction target: **whether a CDM Event is a documented ACT attack
action**. This is narrower than whether a host is compromised or a relationship
is relevant to an investigation. External annotations must be reviewed against
this target before importing them.

Sample unit: one unique CDM Event, identified by stream and Event UUID.
The target concerns that action, not the host's compromise state or whether
two events are related. Label 1 denotes documented attacker activity; label 0
denotes specifically verified benign activity; null denotes insufficient evidence.
There is no native binary attack-label field in the inspected CDM records.
The reviewed external annotation contract supplies the label and provenance.
The historical DARPA analysis's outside-attack-window negative definition is
superseded here: lack of attack coverage does not prove an event benign.

Graph unit: one event-centered temporal provenance subgraph `G(e, W)` per
sample event `e`, with a fixed history horizon `W`. Its seed nodes are the
event's resolved subject and predicate objects. Include only observed causal
ancestors connected to those seeds through resolved process-parent and
subject/object references, with evidence timestamps in `[t(e)-W, t(e)]`,
from the same partition. Preserve CDM edge actions and entity types. Unresolved
references are missing evidence, not fabricated nodes with guessed attributes.
Do not include future events, label metadata, or future-created entity state.

`W` and any computational sampling caps are explicit experiment parameters
to be selected using training/validation in ML-06; the graph unit is defined
here without selecting a GNN architecture. Events with insufficient graph
coverage must be flagged or excluded with counts, consistently across splits.
No graph input has been constructed for the current three review events.

| Label | Admissible evidence |
|---|---|
| Positive (`1`) | A source annotation explicitly identifies the event as an ACT attack action, or a reviewed report-to-event match establishes the action using host identity, UTC time, and specific process/file/network evidence. Record the source page/annotation and incident ID. |
| Negative (`0`) | Explicitly verified benign activity, e.g. a documented benign-only interval whose host and time coverage match the available telemetry, or an explicit reviewed benign annotation. Record the verification evidence. |
| Unknown (`null`) | Everything else, including events merely inside an attack interval, events on a compromised host without action evidence, and events with missing annotation coverage. Exclude from supervised loss and binary metrics. |

Three precise report-to-event matches have now been checked in segment 121:
the generated filenames `PD2GziBJ2wpDwP`, `7B4qoq3yWIKPQh`, and `DXu0yAtkCpuUTo`
occur as file-open actions at the corresponding May 17 attack times. Their
event UUIDs and source pages are in the support review. The subsequent
[reference review](datasets/darpa/reference_review.md) establishes one
report-reviewed positive (`DXu0yAtkCpuUTo`); the other two remain unknown
because their actor parent is absent. Verified benign host-1 examples and
independent attack groups are still missing. No entire segment or interval
is automatically assigned binary labels.
Do not derive labels from TraceGraph `combined_score`, severity, or an LLM.

The preparation manifest should record: stream, event UUID, host UUID,
timestamp in integer nanoseconds, publishing session, incident ID, label,
evidence source/version, page or annotation reference, matching method,
review status, and uncertainty. An incident ID is curated attack metadata;
`sessionNumber` and Windows `SessionId` are not incident IDs.

Required validation: document the annotation schema, timestamp timezone/units,
host-name-to-UUID mapping, eligible label coverage, overlap with these segments,
conflicting matches, positive/negative/unknown counts, and reviewed examples.
Weak host/time-only matches should be retained separately, not treated as
verified event-level labels.

## Leakage-safe split policy (ML-02.2)

Random per-event splitting is unsafe: one process, action burst, duplicate
event, or campaign can produce many nearly identical records across partitions.
The prefixes also show backwards timestamp transitions; file/arrival order is
not chronological order.

1. Deduplicate by stream and Event UUID; quarantine conflicting payloads for
   the same identity. Preserve UUIDs for traceability, excluding them from model
   features. Resolve entity references with an on-disk index for large scans.
2. Order using integer event nanoseconds, with stable UUID tie-breaking.
3. Keep an entire attack incident, including related cross-host activity and
   overlapping causal contexts, in one partition. Merge related incidents into
   a group when they cannot be separated without shared attack evidence.
4. Tentatively target **60/20/20 train/validation/test** by ordered incident or
   verified benign blocks. Exact proportions depend on actual available groups;
   record the achieved counts. The current single-host subset cannot support a
   claim of generalization to unseen hosts.
5. Purge context windows that straddle a partition boundary. Gap length must be
   at least the eventual input history window. Construct separate split graphs;
   no cross-partition edges, labels, or held-out feature statistics.
6. Fit categorical vocabularies and scalers on training only. Use validation for
   choices and thresholds; hold test aside. Record a seed for stochastic steps.
7. Assert no shared sample UUIDs and no shared positive incident IDs across
   partitions. Audit causal-context overlap, feature leakage, and label-source
   coverage. Each evaluable partition needs both known classes; if it lacks
   them, do not report undefined PR-AUC/ROC-AUC as usable detection performance.

The report establishes that May 16 persistence and May 17 escalation are related
phases of the same attack. Keep them in one group. The three precise matches
cannot be divided into independent train/validation/test attacks. This policy
is executable in the preparation code, but cannot produce valid real-data
partitions because sufficient independent groups and verified benign examples
are missing. No real split files have been created. A synthetic integration
fixture checks ID-only export; it is not evidence of a DARPA evaluation split.

## Controlled scenarios (ML-02.3)

The four folders under `data/scenarios/` currently contain placeholders. The
backend also has evaluation fixtures, but they are not automatically labels for
ACT attack actions. Validate scenario labels against this target before using
them. In particular, a login→process→network→file chain is not sufficient proof
of an attack. Controlled scenarios will supplement, rather than replace, a
primary dataset test split.

Planning is complete; Task 29 scenario creation/validation and subsequent ML
execution remain pending. The intended use of each scenario is:

| Scenario | Intended use for this target | Required evidence and limitation |
|---|---|---|
| `basic_attack_sequence` | Positive controlled challenge when specific attacker actions are scripted and annotated. | An attack-looking chain alone is insufficient; each positive needs the script action and event mapping. Expected relationships are not attack labels. |
| `unrelated_events` | Graph isolation and false-correlation check; negative classification examples only if each action is verified benign. | Unrelated events may still be malicious individually. Absence of graph edges cannot define label 0. |
| `legitimate_access` | Verified benign hard negatives that resemble attack activity. | Require benign purpose, exact generated actions and event IDs; legitimate access may produce valid relationships without implying attack. |
| `multi_user_host` | Entity separation and cross-user context-contamination checks. | Shared-host topology supplies no binary labels. Annotate benign/attack actions independently and preserve campaign groups. |

Use complete scenarios as held-out groups; related variants share a group.
Do not tune features, thresholds or architectures on a scenario designated as
test. Record event counts, label balance, annotation granularity and expected
graph coverage once fixtures exist. Synthetic controlled examples cannot
replace real incident generalization, and their metrics must be reported
separately from the primary DARPA test split. The empty folders currently
contain no usable event counts or labels.

## Preparation status

Implemented and executed: bounded gzip/Avro inspection, embedded schema audit,
record/event counts, timestamp precision and ordering diagnostics, and field
availability reporting (`research/ml/data_prep/inspect_fivedirections.py`).
Support ZIP/PDF reading (`read_support.py`) is implemented and tested. A full
segment-121 coverage scan (`audit_attack_coverage.py`) matched the downloaded
schema and report-derived indicators. A later reference audit fully scanned
all six segments; the original inspection and indicator reports retain their
original, narrower scopes.

Implemented: `prepare_dataset.py` streams annotation-listed source files,
indexes subject references in SQLite, validates exact UUID/host/time/action
matches, deduplicates selected events and quarantines conflicting payloads.
The offline adapter is registered in a private instance of the existing
`AdapterRegistry` and validates output against the backend `SecurityEvent`
schema. The 2026-10-13 update adds conservative typed semantic mappings and
host-scoped entity joins. Original CDM actions and integer nanoseconds remain
in raw metadata; canonical actions distinguish file access, network direction,
login/logout and thread/process lifecycle. Optional fields require supporting
definitions and process start times at or before the event. Unknown object
categories remain `cdm_event`. See
[the mapping contract](../../research/ml/data_prep/SEMANTICS.md).

The label import contract is `review_annotations.json` version 1 with an
`events` array: event_uuid, host_uuid, timestamp_nanos (integer UTC epoch
nanoseconds), cdm_event_type, source_file, label, group_id, review_status,
and evidence. A binary label requires `review_status: verified`, evidence and
a curated group ID. Candidate annotations always retain null labels.
Positive labels additionally require an incident ID for explicit incident
isolation checks; negative labels use a verified benign block group.
The current annotations contain one verified report-derived positive and two
unknown candidates. Host/IP evidence is inferred from local netflow fields;
missing Host and Principal records remain explicit limitations. This is a
manual source review, not STARC event annotations. No downloaded STARC
annotation schema is available.

The executable splitter orders whole groups by earliest timestamp, targets
60/20/20, and rejects interleaved intervals, context overlap, duplicate sample
IDs, missing groups and missing classes. Context length is supplied explicitly
in nanoseconds; zero means event-only splitting and cannot validate a future
graph history window. It writes split IDs only when all checks pass.
It also rejects a positive incident ID assigned to multiple groups. Sorting is
deterministic and does not use randomness; a seed is unnecessary for this step.
Stochastic model/sampling steps must record their own seed later.

The CLI now defaults validated ID-only split export to `data/ml/splits/`;
`--split-output` can name a fresh run-specific directory. Existing split
directories are preserved and raw-source destinations rejected. A blocked run
does not create the split directory. Local review events and entity indexes
remain in the ignored output run; they are not copied into tracked split files.

Executed a 2,000,000-record segment-121 preparation scan: all three selected
events found, zero conflicts, one positive and two unknowns, one process reference
resolved. The remaining two share missing parent UUID
`1fca97f4e4134d05869b31eb09df8770`. Reference joins are audit metadata only;
entity availability in a file does not establish event-time-valid features.
See [the preparation manifest](datasets/darpa/preparation_review_manifest.json).

A full cross-segment audit subsequently decoded all 60,000,000 records
(58,037,343 Events) across six files and indexed 257,164 Subject definitions.
No Host or Principal definitions, nor the missing actor parent, are present
in this downloaded subset. The first five segments end by May 10; segment 121
starts May 16 at 20:17 UTC. The May 16 11 AM EDT benign setup described on
report page 135 is outside these event ranges and cannot supply negative labels.
See [the full reference report](datasets/darpa/full_reference_report.json).

The semantic preparation rerun on 2026-10-13 found three typed FileObjects
for the selected actions and produced three canonical file-access events with
their event paths. One contains a valid Firefox process image. User and host
fields remain null because their definitions are missing. All 32 research
tests pass; label counts and split blockers are unchanged.

Pending: missing entity/time/host evidence, verified positives and negatives,
independent groups, experiment-specific graph/feature coverage and actual supervised
splits. The available support report does not prove benign labels for the
current selected telemetry. Only ML-02.4 and the overall ML-02 task remain
unchecked; definition/planning completion does not imply training readiness.
Research code stays outside production APIs until ML-07 and ML-09 pass.
