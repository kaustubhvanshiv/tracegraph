# DARPA E5 FiveDirections: public-source research, 2026-10-27

**New finding: PIDSMaker publishes four E5 FiveDirections node-annotation
files.** Nineteen annotated Subject UUIDs occur in our existing metadata.
This supplies external case evidence, but does not by itself complete the
current action-specific Event labeling and split requirements of ML-02.4.

No training, label import, timestamp correction or additional raw-data download
was performed. The existing six-event review and training gate are unchanged.

## Official sources

The official [E5 README](https://github.com/darpa-i2o/Transparent-Computing/blob/244ae2401032ce92ac3b72f49b8039cae67d60d6/README.md)
describes the May 2019 exercise, TA1 telemetry, CDM20 schema, parser tools,
ACT ground truth and STARC attack annotations. Background benign activity
continued during attacks. Consequently, an attack time window alone does not
identify every event's class. The README also describes the release as research
prototype output with imperfections; it does not supply a binary label column.

The repository tree at that commit contains only `README.md` and
`README-E3.md`. The [E3 README](https://github.com/darpa-i2o/Transparent-Computing/blob/244ae2401032ce92ac3b72f49b8039cae67d60d6/README-E3.md)
documents a separate April 2018 release and CDM18. E3 annotation UUIDs are not
substitutes for our May 2019 E5 data.

The [DARPA program page](https://www.darpa.mil/research/programs/transparent-computing)
explains provenance capture, causal dependencies, APT detection and forensic
analysis. It marks the program complete and the page no longer maintained.
It supplies program context, not a new annotation download or alarm-ID mapping.

Two public issue threads corroborate the practical annotation problem:

- [Issue #4: empty STARC folder](https://github.com/darpa-i2o/Transparent-Computing/issues/4)
  was opened on December 29, 2022. The thread inspected has no posted solution.
  This is a user's report, not a provider explanation of why files are missing.
- [Issue #1: separating benign and attack data](https://github.com/darpa-i2o/Transparent-Computing/issues/1)
  includes users discussing report-to-event alignment, time accuracy and the
  number of events within one minute. These comments are observations, not an
  authoritative labeling algorithm or clock calibration.

The earlier [Drive availability audit](scp_source_availability_20261027.json)
remains the evidence for the actual folder/PDF contents. No fresh Drive check
is claimed by this public-web follow-up.

## Published E5 FiveDirections annotations found

The authors' [PIDSMaker repository](https://github.com/ubc-provenance/PIDSMaker)
contains an annotation version named `orthrus`. At commit
`438a05a7c55256f639e5b5945cf4828fe3ee078e`, its
[case manifest](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/Ground_Truth/orthrus/readme.md)
and actual files include:

| File under `Ground_Truth/orthrus/E5-FIVEDIRECTIONS/` | Rows / unique nodes within file | Subject UUIDs found in our metadata |
|---|---:|---:|
| [node_fivedirections_e5_copykatz_0509.csv](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/Ground_Truth/orthrus/E5-FIVEDIRECTIONS/node_fivedirections_e5_copykatz_0509.csv) | 87 | 17 |
| [node_fivedirections_e5_bits_0515.csv](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/Ground_Truth/orthrus/E5-FIVEDIRECTIONS/node_fivedirections_e5_bits_0515.csv) | 54 | 0 |
| [node_fivedirections_e5_dns_0517.csv](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/Ground_Truth/orthrus/E5-FIVEDIRECTIONS/node_fivedirections_e5_dns_0517.csv) | 11 | 0 |
| [node_fivedirections_e5_drakon_0517.csv](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/Ground_Truth/orthrus/E5-FIVEDIRECTIONS/node_fivedirections_e5_drakon_0517.csv) | 6 | 2 |

Measured total: **158 rows, 157 distinct node UUIDs**, including 40 Subjects,
82 distinct file nodes and 35 network nodes. One file UUID occurs in both
Copykatz and BITS. Four filenames therefore do not establish four independent
split groups or 158 training Events.

The files have no header and contain a node UUID, a descriptive dictionary and
a numeric third field. They are not per-Event binary attack/benign annotations.
The [label loader](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/pidsmaker/utils/labelling.py)
uses the first column to look up the current graph's node index, retains the
second column as descriptive data and ignores the third column in that lookup.
We do not use that number as an Avro record position or native CDM identifier.
The DARPA fallback associates events touching annotated nodes within attack
windows. That rule differs from our action-specific Event contract and has not
been adopted here.

The framework's [dataset configuration](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/pidsmaker/config/config.py)
uses `US/Eastern` for this benchmark. This is useful comparison metadata;
it does not define the clock used by the original MARPLE alarm formatter.
The [dataset documentation](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/docs/docs/datasets.md)
describes node evaluation and distinct normal training/validation graphs versus
mixed test graphs. Its overview labels FiveDirections as Linux; our measured
Windows paths and CDM source semantics remain authoritative for our local data.
These are third-party research annotations, not recovered official STARC files.

## What the local comparison establishes

Only UUID presentation was normalized: uppercase hyphenated UUIDs became
lowercase 32-digit hex, preserving all 16 bytes. The existing SQLite index was
opened read-only. Every match retains publishing host, Subject type, CID,
start time, source filename and record position in the
[comparison report](public_node_annotation_audit_20261027.json).

The 19 matches are Subjects: 17 from the Copykatz file and two from Drakon.
The index stores Host/Subject/Principal definitions, not FileObject or
NetFlowObject definitions. A zero here is not proof that an annotation's
objects or Events are absent from the raw files or full release.

Useful exact correspondences include:

- Copykatz process `e9ac31c9c0404626821064a39dfaf516`, host 2, PID 6208,
  is the Firefox parent already established for the two reviewed `tropical`
  output actions. This supports case identity; it does not relabel every action
  by that process.
- Drakon lists thread `b890ef7a5c86467d95ab7030c9dfa7e3`, the direct subject
  of our two unknown host-1 artifact-access candidates. Its missing process
  parent remains unresolved. The node annotation does not repair that join.
- Drakon also lists `8d1252ea10594bb2a5583880fa606aba`, the direct subject of
  the already reviewed host-1 positive action.

None of these files supplies an explicitly verified benign Event, or a mapping
for the unresolved SCP alarm's CDL Subject 119657 / Object 835986. No public
formatter specification or authoritative mapping was found in the sources
examined. This is a bounded search result, not proof none exists elsewhere.

## Additional primary literature

- [Sometimes Simpler is Better, USENIX Security 2025](https://www.usenix.org/system/files/usenixsecurity25-bilot.pdf)
  links the authors' framework and explains how expanding malicious labels to
  neighborhoods can distort evaluation. It supports checking label units and
  methodology before comparing models. No published accuracy is claimed as a
  TraceGraph result.
- [The CDM authors' TaPP 2020 paper](https://www.usenix.org/conference/tapp2020/presentation/khoury)
  explains the common event/provenance model across platforms. Schema semantics
  and attack-class annotations serve different purposes.
- [Cyber Persistence Detector, authors' paper](https://dartlab.org/assets/pdf/cpd.pdf)
  explicitly evaluates Windows E5 FiveDirections persistence cases. This is
  evidence that the subset is used in research, not a replacement Event-label
  manifest or a measured size of our downloaded subset.

## Reproduce and choose the next step

1. Open the four CSVs at the pinned commit above. Reading them is sufficient;
   no new telemetry archive or framework installation is needed for inspection.
2. Parse them as headerless CSVs. Count rows, UUIDs and descriptive node types.
   Normalize UUID presentation with `uuid.UUID(value).hex`; do not alter byte
   order or join by PID/path. Compare file hashes with the JSON audit.
3. Query the existing read-only `.cache/ml-runs/ml02-scp-all-references-20261027/references.sqlite`:

   ```sql
   SELECT uuid, host, kind, filename, record_index, payload
   FROM entities WHERE uuid = ?;
   ```

   Keep each returned host and inspect kind, temporal validity and direct
   lineage. Identical paths/PIDs do not justify another UUID or host.
4. Treat these matches as external evidence for a focused action review. Review
   FileObject/network nodes separately before claiming their coverage. Keep
   unknown Events unknown unless their particular action is justified.
5. Obtain/review benign action evidence and independent case coverage under the
   current contract before exporting splits. Adopting the framework's node
   benchmark, normal-only training dates or node-touch rule would change the
   evaluation protocol and needs the user's approval first.

**Conclusion:** public node annotations provide a concrete new review path.
They do not yet complete ML-02.4, resolve the SCP mapping, or authorize a model
experiment. The current eligible set remains three attack actions across two
incident groups and zero benign actions. No further raw download batch is queued.
