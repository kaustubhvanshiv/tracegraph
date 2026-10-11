# ML-01.6 — Primary dataset selection

Selected on 2026-10-11: **DARPA Transparent Computing Engagement 5 (TC E5)**,
starting with the user's **FiveDirections Windows stream**. This selects a
dataset, not a prediction target or GNN architecture.

## Evidence and scope

The existing [dataset comparison](dataset_comparison.md),
[DARPA analysis](../datasets/darpa/analysis.md), and
[graph assessment](../graph/darpa.md) support this choice. Their local paths
describe another machine's download. They do not establish what is available
on this Windows machine.

The actual source inspected here is:

```text
D:\Deep Learning\fivedirections-20261010T174625Z-1-049
```

Its `fivedirections/` subdirectory contains six `.bin.gz` segments:
15, 17, 20, 23, 27, and 121 of `ta1-fivedirections-1-e5-official-1`.
Together they occupy **1,891,510,041 compressed bytes**. They are a partial,
nonconsecutive stream, not the full Engagement 5 release.

The [local inspection](../datasets/darpa/fivedirections_local_inspection.md)
records a successful decode of 20,000 records per segment: **120,000 records,
112,498 of them events**. These are prefix counts, not dataset totals.
All six embedded schemas agree and identify CDM 2.0.

## Selection rationale

| Criterion | Rationale and qualification |
|---|---|
| Event semantics | Discrete typed provenance events, matching TraceGraph's evidence-oriented investigation model. Flow datasets have a different sample unit. |
| Graph construction | Events link subject and object UUIDs. The schema supports processes, users, hosts, files, network flows, memory, and registry objects. Referenced entity definitions may be in missing segments. |
| Relationships | File access, network operations, process execution, and login events occur in the inspected prefixes. Action mapping must preserve event meaning; logout is not login and thread creation is not necessarily process execution. |
| `SecurityEvent` compatibility | UUID, timestamp, event type, and source are available. Entity UUID joins are needed for many optional fields. Retain unsupported CDM actions explicitly; do not fabricate severity, usernames, or hostnames. Preserve nanoseconds alongside the backend's microsecond datetime. |
| Ground truth | The official release provides a separate attack narrative and mentions STARC annotations. Neither is in this user's source folder. Supervised learning requires alignment and validation first. |
| Investigation suitability | Process/object relationships and timestamps support reconstruction of sequences. Publishing session numbers are not attack incident IDs. |
| Leakage | Adjacent events, repeated UUIDs, related processes, and one attack spanning files can leak across a random split. Observed timestamp regressions also rule out assuming file order is chronological. |
| Limits and bias | A prototype-generated Windows stream from a controlled 2019 exercise cannot substantiate broad enterprise detection claims. Current prefixes contain one nonzero host UUID; the zero UUID is not another machine. Missing files and optional fields restrict reconstruction. |
| Computational feasibility | Read `gzip.open()` directly with `fastavro.reader()`, using the embedded writer schema. No bulk extraction is needed. Larger entity resolution should use an on-disk index and bounded batches. |
| Licensing | DARPA states that these files were released into the public domain, as-is. Cite the source; keep original telemetry outside Git. |

LANL remains a possible secondary benchmark based on the earlier comparison.
UNSW-NB15 and CIC-IDS2017 are useful flow classification datasets, but are a
weaker fit for process/file provenance investigations. No new downloads of
those datasets are needed for this selection.

## Next gate

ML-01.6 is complete. ML-02 label definition and preparation are pending the
ground-truth files and verification that their incidents overlap the downloaded
segments. Do not label every event in an attack time window malicious, or every
unannotated event benign. See [ground_truth.md](../ground_truth.md).

Sources: [DARPA release and manifest](https://github.com/darpa-i2o/Transparent-Computing),
[Avro object container specification](https://avro.apache.org/docs/1.12.0/specification/),
[fastavro reader documentation](https://fastavro.readthedocs.io/en/latest/reader.html).
