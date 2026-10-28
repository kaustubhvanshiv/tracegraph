# Uniform native metadata recovery

This implements the metadata-scope step in the
[preparation protocol](PREPARATION_PROTOCOL.md). It searches for every identity
in a frozen pilot inventory, rather than only published reference UUIDs. The
result remains a case-conditioned offline graph; this does not create a normal
background population, binary labels, independent groups or model inputs.

The [measured result](../../../data/ml/datasets/darpa/node_benchmark/uniform_metadata_20261028.md)
records the completed 295,442-node pass and 45,806 additional native types.

## Selection and evidence

Start from the original compact graph, whose native metadata was populated for
all selected nodes before the targeted follow-up. The targeted repair graph is
not an input. Freeze all identities using only:

```sql
SELECT id, host_uuid, uuid FROM nodes ORDER BY host_uuid, uuid;
```

The local `universe.jsonl` contains `[host_uuid, uuid]` as compact JSON per line.
Its SHA-256 and identity count are recorded before any reference join. The pilot
has 295,442 identities: 295,243 observed nodes and 199 context-only nodes. This
is a superset of all observed nodes, independent of native type, missingness or
published-reference membership. Node IDs are bookkeeping, not hash inputs or
predictive features.

Every node receives the same search coverage:

- Reuse the eight original complete object-definition scans, including their
  unresolved outcomes and retained type evidence. Source size/modification-time
  guards and complete source counts must agree with the pinned pilot.
- Reuse the global Host/Principal/Subject index already applied to the original
  graph. Its counts are checked against the complete 37-file reference audit.
- Read the remaining eighteen audited archives in the two publishing-host
  streams fully. Select native object definitions by exact host plus UUID;
  scan both resolved and unresolved nodes, without stopping after a match.
- Compare native kind/subtype with existing evidence. Conflicting types remain
  unknown; stable known types retain their original metadata. Fill missing types
  identically for listed and unlisted nodes. References are refreshed afterward.

The original Event windows and all native graph selection remain fixed. The
eleven other-host archives are outside the object search for this primary-host
pilot; their process/principal/host definitions remain part of the reused index.
Local absence is not release-wide absence. The source audit uses file identity
guards, not a claim of publisher-verified download authenticity.

## Runtime and storage

Single-record Avro blocks are filtered with a small native union-tag set and an
in-memory UUID lookup. Only matching definitions are decoded. Multi-record
blocks are decoded entirely, avoiding a scan over hundreds of thousands of byte
patterns. Gzip footer/exhaustion and complete record totals are checked.

Definitions are spooled to `uniform_object_definitions` in a separate graph
copy. The table stores the first native source position/fingerprint, kind,
subtype, occurrence count and conflict marker for each matched node. It does
not retain full object payloads or every repeated definition; original archives
and source positions support further evidence recovery. Only kind/subtype
disagreement determines object-type conflicts here.

The output database is limited to 4 GiB by default. The original graph, targeted
review graph and DARPA archives are preserved. No PostgreSQL restore, GPU,
additional download or model installation is required.

## Reproduce

From the repository root with the existing ML environment:

First reproduce the original graph and full reference cache using the
[graph-format guide](GRAPH_FORMAT.md). These local databases/caches are not part
of a fresh Git clone. Keep the source snapshot identical to the one recorded in
that graph's manifest. For a fresh build on another machine, use its local
`manifest.json` as `--pilot-report`; the committed pilot report pins this run's
physical SQLite fingerprint, which can differ across rebuilds.

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.uniform_metadata `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --graph ".cache/ml-runs/compact-graphs-20261028/graph.sqlite" `
  --pilot-report "data/ml/datasets/darpa/node_benchmark/compact_graph_report_20261028.json" `
  --reference-audit ".cache/ml-runs/ml02-scp-all-references-20261027" `
  --output ".cache/ml-runs/uniform-metadata-20261028-new" `
  --max-gib 4
```

Use a fresh output directory. Completion status must be
`complete_uniform_metadata_not_training_ready`. The database, universe and
progress manifest stay local and ignored by Git. File/type availability from
offline reconstruction still does not establish availability at a prediction
anchor; no predictive fields are exported.

Run the protocol auditor using the uniform graph and its completion manifest
instead of the targeted-review graph/report:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.audit_protocol `
  --protocol "data/ml/datasets/darpa/node_benchmark/preparation_protocol_v1_20261028.json" `
  --original-graph ".cache/ml-runs/compact-graphs-20261028/graph.sqlite" `
  --review-graph ".cache/ml-runs/uniform-metadata-20261028-new/graph.sqlite" `
  --recovery-report ".cache/ml-runs/uniform-metadata-20261028-new/manifest.json" `
  --event-gate "data/ml/datasets/darpa/split_gate_report_20261027.json" `
  --annotations "data/ml/datasets/darpa/review_annotations.json" `
  --output ".cache/ml-runs/uniform-metadata-20261028-new/protocol_audit.json"
```

The auditor checks exact identity-universe count/hash, the completed uniform
scope and absence of annotation-based selection before clearing the metadata
selection blocker. Other preparation blockers are assessed separately. A
successful uniform pass is not permission or evidence to train.

Verification:

```powershell
research/ml/.venv/Scripts/python.exe -m unittest research.ml.tests.test_uniform_metadata -v
```

Tests cover identity selection independent of labels/metadata, listed and
unlisted recovery, host rejection, exact raw positions/fingerprints, both block
layouts, conflict withholding, truncated/count-mismatched input, preservation
of the original graph and verified admission through the protocol audit.
