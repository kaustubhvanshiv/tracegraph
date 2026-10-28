# Uniform DARPA metadata pass - 2026-10-28

**Completed:** native object types were searched for every identity in the
original pilot, independently of published-reference membership. This replaces
the earlier reference-targeted repair as the metadata-scope preparation artifact.

| Measurement | Result |
|---|---:|
| Frozen node universe | 295,442 |
| Observed nodes / context-only nodes | 295,243 / 199 |
| Original complete archive scans reused | 8 |
| Additional same-host archives read completely | 18 |
| Existing records streamed again | 173,890,348 |
| Fresh object-definition nodes matched | 48,307 |
| Newly resolved types versus original graph | 45,806 |
| Newly resolved unlisted / listed nodes | 45,782 / 24 |
| Total resolved types | 267,164 |
| Unresolved types before / after | 74,084 / 28,278 |
| Conflicting object types found | 0 |
| Accepted typed published-reference matches | 45 |
| Unknown node labels | 295,397 |
| Native Events / relations, unchanged | 3,425,979 / 3,540,766 |
| Conservative usable native relations | 2,545,123 |
| SQLite bytes | 1,531,924,480 (about 1.53 GB / 1.43 GiB) |
| Fabricated benign node labels | 0 |

The repeated reads belong to the existing audited corpus, not newly downloaded
or unique Events. Both listed and unlisted nodes received the same source
search. Their remaining metadata completeness may differ naturally; no class
was assigned from missingness or from this repair.

## Scope and validation

The source was the original compact graph, not the targeted repair. The frozen
universe contains host/UUID identities only and was recorded before reference
joins. All observed nodes and their context nodes are included. The global
Host/Principal/Subject cache was validated across all 37 downloaded archives;
object recovery covers the 26 available archives in the two publishing-host
streams. The eleven other-host archives are outside that object search.

- Source size/modification-time guards and complete stream totals passed;
  gzip footer/exhaustion checks passed.
- Exact native-row comparisons found no changed Events, source occurrences,
  relationships, case membership, path observations or entity identities.
  Derived Event-context statuses also remained unchanged.
- All 24 previously recovered reference definitions match the uniform pass's
  stored native positions/fingerprints. Five newly recovered definition samples,
  one per newly recovered object kind, were independently redecoded with the
  ordinary Avro reader and match their exact positions/full raw fingerprints.
- Original Event annotation SHA-256 is unchanged; SQLite integrity passed.
- **27 relevant software checks passed**, including six uniform-recovery tests.
  These are software checks, not training/validation/test model results.

Frozen identity-universe SHA-256:

```text
9b18457fa19c3edda937f6b9fc66906b3d3b0fef5ce769dd51d42c3166e55333
```

The separate local database is:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\uniform-metadata-20261028\graph.sqlite
```

Database SHA-256:

```text
89e5f5d92f2cb02f9c039c8e41809c2cb081449b137fb83ac4ade0d30145d82e
```

The database, frozen identity list and raw telemetry stay local and ignored by
Git. Code, summaries and the [machine-readable completion report](uniform_metadata_report_20261028.json)
are published. See the [uniform recovery guide](../../../../../research/ml/node_benchmark/UNIFORM_METADATA.md)
for reproduction and retained evidence fields. Only native kind/subtype are
compared for object-type conflicts; complete payloads and all repeated definitions
are not stored in the spool. Original archives remain the recovery source.

## Readiness changed from six gaps to five

The [new protocol audit](uniform_protocol_audit_20261028.json) verifies the full
frozen-universe count/hash and non-reference-based recovery scope. It clears the
annotation-directed metadata-selection blocker. The follow-up audit completed
in about ten seconds without rereading the archives.

The remaining preparation gaps are:

1. No independently selected and coverage-reviewed background cohort.
2. No reviewed binary attack/benign node ground truth; reference membership is
   separate and unlisted nodes remain unknown.
3. Only two case groups before campaign review; three chronological whole-group
   partitions cannot be populated without splitting/reusing a group.
4. Campaign, persistence and cross-host context grouping still needs review.
5. The actual feature/graph history horizon has not been frozen.

Uniform native types do not prove that metadata was available at a prediction
anchor. Availability checks remain part of feature preparation. These are still
two case-conditioned primary-host slices, not a normal background or a complete
DARPA benchmark. The two unresolved listed Subject UUIDs remain unknown.
No new Event/verified benign labels, candidate draws, feature vectors, partitions
or models were created. The original Event-level ML-02.4 gate is unchanged. This pass required
no additional download, GPU or package installation.
