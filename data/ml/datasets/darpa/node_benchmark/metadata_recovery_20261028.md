# Compact DARPA native metadata review - 2026-10-28

**Completed the review of all 26 previously unresolved reference UUIDs.**
Native evidence resolves 24 additional published-reference types; two remain
unknown because native definitions were not found. No labels were guessed from filenames, paths, PIDs or
Event actions. No new files, database services or model packages were downloaded.

## Measured result

| Measurement | Result |
|---|---:|
| Additional archives read completely | 18 |
| Additional existing records streamed | 173,890,348 |
| Prior complete pilot archive scans reused | 8 |
| Native definition evidence records | 24 |
| Newly accepted typed reference matches | 24 |
| Total accepted typed reference matches | 45 (previously 21) |
| Target UUIDs still missing native definitions | 2 |
| Enriched SQLite bytes | 1,516,654,592 |
| Conservative usable Event relations | 1,153,107 |
| Fabricated benign node labels | 0 |

The streamed records belong to the existing audited corpus; they do not add
new unique Events. The graph still contains **3,425,979 Events, 295,442 nodes
and 3,540,766 native Event relations**. Metadata enrichment changes which
relations pass the existing conservative quality view, not the raw selection.

## Cases

| Primary-host slice | Events, unchanged | Typed reference matches after review |
|---|---:|---:|
| copykatz-20190509-host2 | 2,705,805 | 39 |
| drakon-20190517-host1 | 720,174 | 6 |

## Remaining target gaps

These UUIDs were reviewed but were not accepted as typed published-reference
matches. The machine-readable report records every target and source position.

| Case | UUID | Expected native kind | Result |
|---|---|---|---|
| copykatz-20190509-host2 | `02224a0f80d54570a271bfa2b65163c1` | `RECORD_SUBJECT` | `no_native_definition_in_reviewed_local_sources` |
| copykatz-20190509-host2 | `5b11193839a542538400c6cb43557dad` | `RECORD_SUBJECT` | `no_native_definition_in_reviewed_local_sources` |

Missing here means absent from the reviewed local publishing-host sources,
not absent from all DARPA data. The cached Host/Principal/Subject index was
validated across all 37 downloaded archives. File-object recovery additionally
uses 18 freshly read same-host archives and the eight complete pilot scans.
The 11 other-host archives were not searched for file-object definitions.

## Validation and reproducibility

- Complete Avro block record totals agree with the existing source audit;
  gzip exhaustion/footer checks passed. Source sizes/modification times were
  validated before and after the scan. This filtered pass does not recount
  every CDM type; the prior complete decoding audit remains the type-count source.
- Exact comparisons found zero changed native Event, source-occurrence,
  relationship, path-observation, case-membership or entity-identity rows.
- Exactly 24 target nodes changed metadata; no non-target node changed.
- SQLite integrity passed. Original Event annotation SHA-256 is unchanged.
- All 24 recovered definitions were independently redecoded with the ordinary Avro
  reader: original positions, full raw fingerprints, host, UUID, kind and
  payload agree exactly with the filtered search.
- Fourteen graph/recovery software checks passed, including six new recovery
  tests for exact positions/fingerprints, host rejection, both block layouts,
  truncation/count failures, native type mismatch/conflict handling and an
  end-to-end build preserving the original graph and unknown labels.

The original pilot database was preserved. The separate enriched artifact is:

```text
C:\codes\PBL sem 7\tracegraph\.cache\ml-runs\compact-metadata-recovery-20261028\graph.sqlite
```

The enriched SQLite database, full native evidence and caches stay local and
ignored by Git. Code, tests, this summary and the
[machine-readable report](metadata_recovery_report_20261028.json) are published.
Follow the [recovery guide](../../../../../research/ml/node_benchmark/METADATA_RECOVERY.md)
to reproduce the search and its evidence rules.

Enriched SQLite SHA-256:

```text
41b41c9482bb19f3c8db57e5bcf33591d810edf7f5279442156213e4f4753a17
```

## Training boundary and next step

This was annotation-directed evidence recovery. The enriched graph is a
review artifact: only these unresolved published references received the
additional type search. Before feature construction or graph sampling, use
the same metadata rules for all sampled nodes independently of annotations;
otherwise metadata availability or newly usable edges could reveal which
nodes were selected for annotation review.

Unlisted, missing, conflicting and mismatched labels remain NULL. Published
reference membership is not an expert Event label or a model detection.
The original Event-level ML-02.4 gate is unchanged. No feature vectors,
background labels, train/validation/test partitions or trained models were
created. The next preparation step is to review a uniform metadata, background
sampling and label/split protocol before implementing training features.
