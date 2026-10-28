# Native metadata recovery for the compact DARPA graph

Run this after the [compact graph builder](GRAPH_FORMAT.md). It addresses
published-reference UUIDs that are observed in the graph but lack native types.
It does not extend the graph's Event windows, create feature vectors, assign
benign labels or train a model.

## Evidence rules

An exact `(publishing host UUID, entity UUID)` definition supplies the type.
Annotation paths, process IDs, matching names and Event actions do not supply
missing definitions. An expected type in a published CSV is a comparison target,
not native evidence. A recovered type can disagree with the published type;
such a row remains unknown in `node_reference_labels`.

The command validates the completed pilot graph's SHA-256 and the complete
reference-cache source sizes/modification times. It verifies the cached
Host/Principal/Subject record counts and checks for unused definitions before
reading more telemetry. A contradictory cached/fresh definition fails the run
for review.

The original pilot already read eight intersecting archives completely. Their
completed scans are reused for these unresolved UUIDs. Remaining downloaded
archives in the same publishing-host filename streams are read to exhaustion,
including dates outside the case windows. This is an offline metadata join;
it does not establish that a definition was available when an Event arrived.
The search covers this local subset, not the full DARPA release or other hosts.

## Efficient, conservative Avro filtering

The reader validates that the datum union is the first field and native
definition UUIDs use a leading fixed 16-byte field. On single-record Avro blocks,
the union tag and UUID select candidate definitions for normal Avro decoding.
For multi-record blocks, any target UUID byte occurrence triggers decoding of
the entire block. Normal decoded kind, host and UUID checks then decide whether
a record is evidence. A byte match alone never resolves a node.

Every block is read, and its record count contributes to a total checked against
the existing complete source audit. Gzip exhaustion/footer validation is forced
separately: an incomplete gzip trailer must not appear to be successful Avro
exhaustion. The fast filter does not recount every CDM type or replace the
previous full decoding/type audit. Tests compare both block layouts with normal
decoding, including exact 1-based source positions and raw fingerprints.

## Reproduce

From the repository root, with the existing ML environment and audited caches:

```powershell
research/ml/.venv/Scripts/python.exe -m research.ml.node_benchmark.recover_metadata `
  --source "D:/Deep Learning/fivedirections-20261010T174625Z-1-049/fivedirections" `
  --graph ".cache/ml-runs/compact-graphs-20261028/graph.sqlite" `
  --pilot-report "data/ml/datasets/darpa/node_benchmark/compact_graph_report_20261028.json" `
  --reference-audit ".cache/ml-runs/ml02-scp-all-references-20261027" `
  --output ".cache/ml-runs/compact-metadata-recovery-20261028-new"
```

Use a fresh output directory. The original graph and DARPA files are preserved.
The command requires room for a separate graph copy plus a 2 GiB reserve. The
large processed PostgreSQL dump, a GPU and model packages are unnecessary.

Outputs remain local and ignored by Git:

| Output | Content |
|---|---|
| `manifest.json` | Input/code hashes, source coverage, per-UUID results, before/after counts and integrity results |
| `definitions.json` | Matched native definition payloads with source positions and canonical raw SHA-256 fingerprints |
| `graph.sqlite` | A separate graph with enriched node metadata and refreshed reference/context views |

The graph adds `metadata_recovery_evidence`, keyed by node, source filename and
record position. It stores all recovered type evidence, including conflicting
definitions. It updates only retained native type fields for existing nodes;
Events, source occurrences, edges, case membership and path observations retain
their original selection. Definitions disagreeing on kind/subtype are withheld.
Object properties outside those retained type fields are preserved as evidence,
but are not used to construct model features or to decide type conflicts.

`typed_uuid_match` remains published-reference membership, not an expert Event
label or a detection result. Missing, conflicting and mismatched types retain
NULL labels. No node is declared benign because its UUID was unlisted.

This is annotation-directed evidence recovery: only the unresolved published
references were targeted. The enriched graph is a review artifact. Before using
it for model features or graph sampling, establish the same metadata-recovery
rules for all sampled nodes, independently of reference membership. Otherwise,
metadata availability and newly usable relations could reveal which nodes were
targeted for annotation review rather than describe attack behavior.

## Verify

```powershell
research/ml/.venv/Scripts/python.exe -m unittest research.ml.tests.test_recover_metadata -v
```

The completion manifest must have `complete_metadata_review_not_training_ready`.
It records unchanged input graph identity/native table counts, SQLite integrity,
the conservative usable-relation count and zero fabricated benign labels.
Keep the original and enriched graph hashes with their respective reports;
metadata enrichment intentionally changes the enriched file's hash.
