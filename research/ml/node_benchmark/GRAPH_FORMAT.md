# Compact native-CDM graph pilot

This builder uses the downloaded gzip-wrapped Avro data directly. It does not
need the processed PostgreSQL dump, a database server, CUDA or a model package.
The graph database and raw data remain outside Git; code, configuration and
summary reports can be committed.

The subsequent [native metadata recovery](METADATA_RECOVERY.md) preserves this
original pilot and produces a separate enriched graph for annotation review.
See the [measured follow-up](../../../data/ml/datasets/darpa/node_benchmark/metadata_recovery_20261028.md)
before using either artifact for feature or sampling work.

## Selection and interpretation

The configuration selects the primary publishing host and a half-open UTC
window for each case. The initial pilot uses:

| Case | Publishing host | UTC interval, 2019 |
|---|---|---|
| Copykatz | FiveDirections 2 | May 9, 17:25:00 to 17:57:00 |
| Drakon | FiveDirections 1 | May 17, 20:10:00 to 20:16:00 |

Every downloaded same-host archive whose completed Event bounds intersects the
window is scanned fully. Publication order can move backwards in time; the
reader never stops when one record passes the window end. Bounds select files,
not labels. The scan's complete record/type counts must match the prior audit.

These are case-conditioned, primary-host slices. They are not complete attack
incidents, representative background samples, or a reproduction of the full
PIDSMaker benchmark. Cross-host case activity and other days may be outside
scope. No train/validation/test designation is attached to either slice.

## Tables

| Table/view | Meaning |
|---|---|
| `cases` | Publishing host and exact integer-nanosecond bounds |
| `nodes` | Native entities keyed by publishing host plus UUID; kind/subtype and optional Subject metadata |
| `case_nodes` | Whether an entity is directly observed in selected Events or included only as native metadata context |
| `events` | Deduplicated native Events with original action, timestamp, actor and fingerprint |
| `edges` | Each Event's subject-to-predicate reference, retaining predicate role 1 or 2 |
| `event_sources` / `sources` | Original archive and 1-based raw record position for every selected source occurrence |
| `node_paths` / `paths` | Deduplicated path observations with first/last observed Event times |
| `metadata_links` | Native `parentSubject` and `localPrincipal` references, distinct from Event relations |
| `subject_context` | Process-chain resolution, maximum known start time and unresolved/cyclic/conflicting states |
| `published_nodes` / `reference_matches` | Pinned external references and typed UUID-match outcomes, separate from graph data |
| `node_reference_labels` | Published membership is 1 for a typed match; every other label remains NULL |
| `usable_event_relations` | Nonconflicting relations with resolved endpoints and time-valid source/destination Subject context |

Edges preserve the native actor/reference roles. They do not infer
information-flow direction: a file READ is still stored with its Subject and
predicate roles, rather than silently being interpreted as a causal edge in a
particular direction. Deriving a model-specific provenance representation is
a later, explicit semantic decision.

## Integrity and missing information

- The same textual UUID on two hosts remains two entities. Joins never use PID
  or filename as identity substitutes. Thread CIDs are not process PIDs.
- Identical Event UUID/content occurrences are deduplicated while retaining
  each raw source position. Different contents under the same host/Event UUID
  mark the Event conflicting; it is excluded from the usable view.
- Object kind/subtype are resolved from native definitions in the scanned
  archives or validated typed caches. An annotation description or path-shaped
  string never supplies a missing type. Object conflicts compare these used
  fields; permissions and other omitted properties are not model features.
- Subject/Host/Principal definitions and ancestor references can be read from
  the completed 37-file reference index. Those are offline metadata joins, not
  proof that the definitions had arrived before an online detector saw an Event.
- Missing/future starts, missing parents, cycles and conflicting definitions
  remain recorded. The usable view requires time-valid process context and
  withholds future or unresolved destination Subject context as well.
- Metadata-only ancestors and principals are counted separately from entities
  directly touched by selected Events. Reference coverage distinguishes these
  two origins; they are not interchangeable evaluation samples.

The database uses a temporary disk-backed object-definition spool during the
scan. The spool is dropped after metadata joins. Compaction is attempted only
when the original plus compacted file fits the configured budget. The default
SQLite page limit is 4 GiB; a failed/incomplete extraction never becomes a
training-ready dataset. Existing output directories are not overwritten.

## Annotation meaning

Only the two configured case lists are attached to this pilot: 87 published
Copykatz references and six Drakon references. This differs from the four-file,
157-unique-node source inventory. CSV hashes are checked before use; numeric
third-column values are never treated as Avro record positions or features.

Reference lists do not select which Events are extracted. Listed-node
membership does not label all neighboring Events, and absence from a list does
not assign benign label 0. Missing references mean **not found in this pilot**,
not absent from DARPA. A matching UUID with unresolved or incompatible native
kind is recorded separately from an accepted typed match.

The original Event-level `review_annotations.json` is never modified. No graph
node label should be copied back into it. Reference labels, UUIDs, CIDs,
case identifiers and curated source metadata are traceability/evaluation data;
they must not be automatically converted into model features.

## Reproduce

Prerequisites: the existing local raw archives, completed reference index, two
typed preparation caches and pinned public CSVs from the earlier review.
Run from the repository root:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.build_graphs `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --config "data/ml/datasets/darpa/node_benchmark/pilot_cases_20261028.json" `
  --public-audit "data/ml/datasets/darpa/public_node_annotation_audit_20261027.json" `
  --annotation-dir ".cache/ml-runs/public-source-research-20261027" `
  --reference-audit ".cache/ml-runs/ml02-scp-all-references-20261027" `
  --typed-cache ".cache/ml-runs/ml02-label-preparation-20261017" `
  --typed-cache ".cache/ml-runs/host2-case-preparation-20261027" `
  --output ".cache/ml-runs/compact-graphs-20261028-new" `
  --max-gib 4
```

The output contains `graph.sqlite` and `manifest.json`. Use a new output path
for a fresh run. Progress counts describe raw records scanned/selected; the
finished manifest separately reports unique Events and graph entities.

Useful read-only checks:

```sql
SELECT case_id, COUNT(*) FROM events GROUP BY case_id;
SELECT metadata_status, COUNT(*) FROM nodes GROUP BY metadata_status;
SELECT case_id, published_reference_label, COUNT(*)
FROM node_reference_labels GROUP BY case_id, published_reference_label;
SELECT case_id, status, COUNT(*) FROM reference_matches GROUP BY case_id, status;
```

The `published_reference_label = 0` count must be zero. Counts in the usable
view are data-quality diagnostics, not a model's true positives or detection
accuracy. The pilot is not training-ready until label interpretation, context,
background sampling and independent split coverage have been reviewed.
