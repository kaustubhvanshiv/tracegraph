# DARPA native evidence packets - 2026-10-29

The next evidence-preparation step is complete: all **500 frozen candidates**
have a source-linked native evidence packet, a local HTML reader and a blank
human-review worksheet. All 500 security labels remain NULL. This creates an
inspectable review artifact; it does not claim completed human annotation or
complete ML-02.4.

| Measured result | Count |
|---|---:|
| Frozen candidates, unchanged selection and ordering | 500 |
| Candidate Event witnesses verified | 500 |
| Distinct witness Events | 497 |
| Complete source archive scans | 1 |
| Raw records read in that complete scan | 10,000,000 |
| Candidates with one native definition payload in reviewed sources | 500 |
| Candidates with conflicting or missing definitions in reviewed sources | 0 |
| Actor chains with all native starts at/before the witness | 493 |
| Candidate actor chains containing a future start | 7 |
| Candidate identities overlapping the attack pilot | 60 |
| Unknown labels / new verified benign labels / new verified attack labels | 500 / 0 / 0 |
| Relevant software tests passed | 40 |

## Evidence and timing findings

Native kinds are 270 MemoryObject, 84 RegistryKeyObject, 52 Subject, 49
FileObject, 22 NetFlowObject, 16 SrcSinkObject and seven IpcObject records.
These kinds come from exact host/UUID native definitions, not filenames,
process names or published annotation descriptions.

All 500 candidates received the same object-definition search in the complete
original review-window archive. Host/Principal/Subject definitions were joined
by host and UUID from the complete 37-file metadata index. Zero missing or
conflicting results describe these review sources only; other release fragments
were not searched for object-definition conflicts. Native kinds do not establish
whether an action was malicious or benign.

The seven future-start packets share one witness actor. Their actor chains
contain a native start **3-7 milliseconds after the witness Event**. These
inconsistencies are preserved as review flags. The timing could reflect capture
or ordering issues; no cause or timestamp repair is established here.
The other 493 chains have consistent native start ordering, which still does
not establish arrival-time availability, valid predictive features or benign
security intent. All metadata is explicitly marked offline-only.

The 60 pilot overlaps remain visible in the packets with the existing
conservative evaluation group. An earlier action by a shared entity does not
inherit a later attack label. These candidates have not become independent
negative samples, and the frozen draw was not replaced after inspection.

## Independent verification

The saved packets were checked independently of the producer's helpers:

- Every candidate row and its ordering exactly match the original frozen file.
- All 500 packet witnesses match the pinned native fingerprints, host, UUID
  and declared native reference role.
- A separate raw-prefix reread verified **945 distinct source positions**:
  497 witness Events and 448 candidate object definitions. It read 506,452
  records; this prefix check is additional to the producer's complete
  10-million-record scan, not another claim of complete archive coverage.
- **179 distinct cached definition positions** were checked against the native
  metadata database, including actor lineage and principal context. Shared
  definition positions are counted once.
- Source payload fingerprints, actor-start comparisons and pilot identity
  overlap were recomputed. Original annotation and input database hashes did
  not change. Producer source SHA-256 matches the saved report.

The [completion report](native_review_packet_report_20261029.json) and
[independent verification](native_review_packet_verification_20261029.json)
contain counts and fingerprints only. The packet-file SHA-256 is:

```text
9d6c6252dde7fa65e1fe92519503e867001cb29c0c4d7c82dac485d7ef5080af
```

The local packet JSONL is 2,236,674 bytes. Full Event/command/principal data,
the HTML reader and the worksheet remain outside Git under:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\native-review-packets-20261029
```

## Repeat and review

The [teammate guide](../../../../../research/ml/node_benchmark/EVIDENCE_REVIEW.md)
contains the full reproduction command, local-reader instructions and evidence
rules. The worksheet is blank and is not consumed as training labels. A human
review must supply independently justified action intent at an explicit time;
ordinary-looking commands or the absence of an attack annotation do not prove
benign intent.

Six new software checks cover witness integrity, full-payload conflicts,
host-scoped and time-consistent actor lookup, deterministic production,
rejection of relabeled/reordered inputs and escaped HTML source text. Together
with the existing graph/recovery/protocol/background checks, **40 pass**:

```powershell
research/ml/.venv/Scripts/python.exe -m unittest research.ml.tests.test_build_graphs research.ml.tests.test_recover_metadata research.ml.tests.test_node_protocol research.ml.tests.test_uniform_metadata research.ml.tests.test_background_review research.ml.tests.test_review_inputs research.ml.tests.test_review_packets -q
```

These are software test results, not model training, validation or test metrics.
The four existing preparation gaps remain: an accepted background training
cohort, reviewed binary node ground truth, enough justified independent whole
groups and a frozen input history horizon. No new download, dependency, GPU,
model, feature vector or split was needed for this completed review-preparation
step. Original Event annotations and both existing graph artifacts are preserved.
