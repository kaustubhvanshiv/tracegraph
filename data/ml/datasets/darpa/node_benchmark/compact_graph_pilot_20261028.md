# Compact DARPA graph pilot - 2026-10-28

**Completed:** a local SQLite graph now contains the two configured primary-host
case slices. It was built from the existing raw archives, without downloading
the processed dump, restoring PostgreSQL, installing model packages or training.

Local database:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\compact-graphs-20261028\graph.sqlite
```

The database is ignored by Git. The builder, tests, configuration and this
summary are reproducible project artifacts; raw telemetry and the graph database
are not published to GitHub.

## Measured result

| Measurement | Result |
|---|---:|
| Downloaded archives validated for provenance | 37 |
| Intersecting archives fully reread for extraction | 8 |
| Existing raw records reread | 70,358,733 |
| Unique selected Events | 3,425,979 |
| Native Event reference relations | 3,540,766 |
| Native parent/principal metadata links | 37,113 |
| Entity nodes, including metadata-only context | 295,442 |
| Distinct observed path strings | 36,163 |
| Final SQLite bytes | 1,516,580,864 |
| Final size | About 1.52 GB / 1.41 GiB |
| Configured SQLite budget | 4 GiB |
| Accepted typed published-reference matches | 21 |
| Reference UUIDs present but native type unresolved | 26 |
| Reference UUIDs not represented in this pilot | 46 |
| Fabricated benign/zero node labels | 0 |

The reread records are a subset of the previously audited corpus; they do not
increase its unique record count. No selected duplicate Event/source occurrence
or conflicting Event UUID was found in this run. The builder nevertheless tests
and preserves those cases when present.

## Case coverage

| Primary-host slice | UTC interval, 2019 | Unique Events | Observed nodes | Metadata-only nodes | Typed reference matches | Present, unresolved type | Not in pilot |
|---|---|---:|---:|---:|---:|---:|---:|
| Copykatz, FiveDirections 2 | May 9, 17:25-17:57 | 2,705,805 | 212,586 | 178 | 16 / 87 | 25 | 46 |
| Drakon, FiveDirections 1 | May 17, 20:10-20:16 | 720,174 | 82,657 | 21 | 5 / 6 | 1 | 0 |

Intervals are half-open and keep native integer UTC nanoseconds. Selection uses
publishing host and time, not whether an Event touches an annotated node.
Copykatz's published list also contains context from other hosts; this pilot
explicitly retains only the configured primary host. Missing here does not
mean missing from DARPA or incorrectly annotated by the authors.

Each accepted reference match is directly observed in selected Events; none of
the 21 accepted matches is a metadata-only ancestor. The other 295,421 node
labels remain NULL. These are published node-membership references, not 21
expert-verified attack Events or model detections.

The complete source scan matters: host-2 parts 17, 18 and 19 add 73, two and
three older-window Events respectively, beyond the main parts 15 and 16.
Host-1 part 122 adds 64 Drakon-window Events. The reader did not stop at an
arrival-order timestamp boundary.

## Metadata and temporal quality

Native definitions resolve 221,358 entities; 74,084 remain unresolved. File/path
text and annotation descriptions do not fill absent definitions.

Actor-chain timing diagnostics classify the selected Events as:

| Actor context | Events |
|---|---:|
| Resolved and started no later than the Event | 2,606,925 |
| At least one required start lies after the Event | 19,350 |
| Unresolved or conflicting chain | 799,704 |

All observed Events/relations remain traceable in the database. The conservative
`usable_event_relations` view retains **1,127,908 relations** after excluding
conflicting Events, unresolved endpoints and invalid source/destination Subject
context. This is a data-quality filter, not an accuracy or detection score.

Definitions imported from reference/preparation caches are offline joins. The
process start guards do not prove online ingestion-time availability. The
graph stores entity types, selected Subject attributes and path observations;
it does not retain complete command lines/object payloads or construct model
feature vectors. Original archives and source positions support later recovery.

## Validation

- Every selected archive was scanned to completion, with exact record/type
  counts checked against the prior audit. Input sizes/modification times and
  reference/cache provenance were validated.
- SQLite integrity checks passed. No dangling Event relation, wrong actor,
  cross-host join, out-of-window Event, invalid source position or zero node
  label was found.
- All five existing attack/candidate review Events match their exact raw
  fingerprints, original archive positions, host, action and nanoseconds.
  The two candidates with missing process parent remain unresolved in the graph.
- Eight graph-extractor tests pass, covering host scope, half-open windows and
  out-of-order input, nanosecond precision, deduplication/conflicts, separate
  reference labels, source and destination time guards, and an end-to-end build.
- The research suite runs 51 checks: 48 pass in the main runtime; the three
  optional PDF-reader checks pass separately with bundled `pypdf`. No packages
  were installed. These are software checks, not model validation/test results.

The raw scan and metadata-finalizer versions are recorded by hash. Metadata-only
temporal-guard refinement preserved the native Event/entity/source row counts;
the raw-extraction methods and scan loop were checked unchanged. The current
builder performs the refined guards directly on a fresh run.

Final SQLite SHA-256:

```text
b44241cc619482d4540d01a3bb035ac0eb3010083d9451de5b5d568e6dd5bdcf
```

This identifies the local artifact; physical SQLite file hashes can differ
across rebuilds/runtime versions. Verify semantic rows/counts and source
provenance as well. The [machine-readable report](compact_graph_report_20261028.json)
contains full case/source details, context counts, missing reference UUIDs,
cache/code hashes and validation outcomes.

## Reproduce and next step

Follow the command and SQL checks in
[the graph-format guide](../../../../../research/ml/node_benchmark/GRAPH_FORMAT.md),
using [the case configuration](pilot_cases_20261028.json). A fresh output path is
required; an existing graph is never silently overwritten.

This completes the requested compact-graph extraction and coverage/storage
assessment. It does **not** complete the original Event-level ML-02.4 task,
provide verified benign labels, create independent splits or select a model.
The original six Event annotations are unchanged.

The next useful preparation step is targeted recovery/review of native metadata
for the 26 represented reference UUIDs whose type remains unresolved. Feature
construction, background sampling and a documented split/label protocol must
then be reviewed before training. The large processed dump remains optional
and on hold.
