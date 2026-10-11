# ML-02 — ground truth and split plan

Status on 2026-10-11: **label contract defined; review preparation executed;
training blocked by evidence coverage**.
ML-02.1, ML-02.2, and ML-02.4 are not complete. No labeled splits or model
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

## Proposed target and label contract

Prediction target: **whether a CDM Event is a documented ACT attack
action**. This is narrower than whether a host is compromised or a relationship
is relevant to an investigation. External annotations must be reviewed against
this target before importing them.

Sample unit: one unique Event. Proposed graph input: its available
causal context from process/object relationships at or before its timestamp,
with the history window selected and documented in ML-06. Do not use future
activity or label-dependent graph construction as an input feature.

| Label | Admissible evidence |
|---|---|
| Positive (`1`) | A source annotation explicitly identifies the event as an ACT attack action, or a reviewed report-to-event match establishes the action using host identity, UTC time, and specific process/file/network evidence. Record the source page/annotation and incident ID. |
| Negative (`0`) | Explicitly verified benign activity, e.g. a documented benign-only interval whose host and time coverage match the available telemetry, or an explicit reviewed benign annotation. Record the verification evidence. |
| Unknown (`null`) | Everything else, including events merely inside an attack interval, events on a compromised host without action evidence, and events with missing annotation coverage. Exclude from supervised loss and binary metrics. |

Three precise report-to-event matches have now been checked in segment 121:
the generated filenames `PD2GziBJ2wpDwP`, `7B4qoq3yWIKPQh`, and `DXu0yAtkCpuUTo`
occur as file-open actions at the corresponding May 17 attack times. Their
event UUIDs and source pages are in the support review. They remain review
candidates until the annotation protocol is finalized. Verified benign
host-1 examples and independent attack groups are still missing. None of the
9,650,235 Events in this full segment scan is automatically assigned a binary label.
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

## Proposed leakage-safe split policy

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
is not yet executable: sufficient independent groups and verified benign
examples are missing. No split files have been created.

## Controlled scenarios (ML-02.3)

The four folders under `data/scenarios/` currently contain placeholders. The
backend also has evaluation fixtures, but they are not automatically labels for
ACT attack actions. Validate scenario labels against this target before using
them. In particular, a login→process→network→file chain is not sufficient proof
of an attack. Controlled scenarios will supplement, rather than replace, a
primary dataset test split.

## Preparation status

Implemented and executed: bounded gzip/Avro inspection, embedded schema audit,
record/event counts, timestamp precision and ordering diagnostics, and field
availability reporting (`research/ml/data_prep/inspect_fivedirections.py`).
Support ZIP/PDF reading (`read_support.py`) is implemented and tested. A full
segment-121 coverage scan (`audit_attack_coverage.py`) matched the downloaded
schema and report-derived indicators. Other segment scans remain prefix-only.

Implemented: `prepare_dataset.py` streams annotation-listed source files,
indexes subject references in SQLite, validates exact UUID/host/time/action
matches, deduplicates selected events and quarantines conflicting payloads.
The offline adapter is registered in a private instance of the existing
`AdapterRegistry` and validates output against the backend `SecurityEvent`
schema. It preserves the original CDM action and integer nanoseconds, without
inventing hostname, process, user, or file semantics. Unknown object categories
remain `cdm_event`; detailed canonical mappings are still pending.

The label import contract is `review_annotations.json` version 1 with an
`events` array: event_uuid, host_uuid, timestamp_nanos (integer UTC epoch
nanoseconds), cdm_event_type, source_file, label, group_id, review_status,
and evidence. A binary label requires `review_status: verified`, evidence and
a curated group ID. Candidate annotations always retain null labels.
Current report matches do not fully establish actor and host identity, so
all three remain unknown. No downloaded STARC annotation schema is available.

The executable splitter orders whole groups by earliest timestamp, targets
60/20/20, and rejects interleaved intervals, context overlap, duplicate sample
IDs, missing groups and missing classes. Context length is supplied explicitly
in nanoseconds; zero means event-only splitting and cannot validate a future
graph history window. It writes split IDs only when all checks pass.

Executed a 2,000,000-record segment-121 preparation scan: all three selected
events found, zero conflicts, zero binary labels, one process reference
resolved. The remaining two share missing parent UUID
`1fca97f4e4134d05869b31eb09df8770`. Reference joins are audit metadata only;
entity availability in a file does not establish event-time-valid features.
See [the preparation manifest](datasets/darpa/preparation_review_manifest.json).

Pending: complete entity/time/host joins, detailed canonical object semantics,
verified positives and negatives, independent groups and actual supervised
splits. The available support report does not prove benign labels for the
current selected telemetry. ML-02 tasks remain unchecked until these gates pass.
Research code stays outside production APIs until ML-07 and ML-09 pass.
