# ML-02.4 continuation - 2026-10-27

**Outcome: two additional manually reviewed attack actions prepared; supervised
training remains blocked.** The current annotation set has six events: three
attack actions, one benign execution excluded for uncertain clock alignment,
and two unknowns. The three eligible attack actions occupy two incident groups.
There are zero eligible benign examples.

## Source coverage and integrity

Raw source: `D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections`.
The user supplied the two previously requested host-2 archives. Both match the
publisher's `bins.md5sum` entries:

| Newly audited archive | Compressed bytes | MD5 | Complete records | Event records |
|---|---:|---|---:|---:|
| `ta1-fivedirections-2-e5-official-1.bin.15.gz` | 325,830,490 | `3b48a5eb1d052d8ca7fe695006ce96bd` | 10,000,000 | 9,486,685 |
| `ta1-fivedirections-2-e5-official-1.bin.17.gz` | 323,153,443 | `06ca656bb655b281ae161067ec1299c8` | 10,000,000 | 9,580,055 |

Part 15's Event bounds are May 8 14:58:27.762 through May 9 17:48:04.179 UTC.
Part 17's are May 8 14:01:20.747 through May 9 21:49:20.894 UTC.
Older timestamps appear within later-published files; bounds do not establish
continuous coverage. Both files contain **zero Events** in the configured
May 10 benign SCP search window.

The [combined reference audit](full_reference_report_20261027.json) reuses five
completed, disjoint caches and validates file sizes, modification times and
metadata counts. It covers all **34 local archives, 315,099,571 raw records
and 302,075,542 Event records**, with **1,614,479 definition records** retained
locally. These are record counts, not unique labeled samples. The merge newly
scans zero files. The prior four annotation-listed identity chains are unchanged.

Per-file broad-search reports:
[part 15](host2_part15_evidence_audit_20261027.json) and
[part 17](host2_part17_evidence_audit_20261027.json).
Their configurations and the October 18 reports remain historical snapshots.

## Candidate review and narrower searches

A full-record reread of all 30 retained broad-search candidates from part 16
finds `CorperfmonExt.dll` paths. These matched the old `perfmon` substring;
they are not the report's `perfmon` device. Those 30 events remain unknown,
not benign. See the source fingerprints and decisions in
[candidate review](candidate_review_decisions_20261027.json).

The [new activity configuration](label_review_activities_20261027.json) uses
exact artifact/device basenames and adds the report-documented `virtuous`
Sysinfo output. Assertions verify that the documented paths match and the
.NET DLL does not. Complete rechecks of parts 15 and 16 find respectively
**zero and 134** focused path matches:
[part 15](host2_part15_precise_audit_20261027.json),
[part 16](host2_part16_precise_audit_20261027.json).
The first 30 focused part-16 references all concern `tropical`.
Search counts are not classifier performance or verified attack counts.
The narrower and older patterns differ, including the newly added artifact.

Only Subject command lines and Event paths are searched by this auditor.
Zero matches do not establish absence in other fields or unavailable records.
All matching events require full-record reread and source alignment.

## Two reviewed attack actions

The downloaded E5 report, Revision 1.0, pages 27-28 documents the host-2 Firefox
session (PID 6208), `tropical` credential-output logfile setup around 13:49 EDT
and password collection around 13:50 EDT. Both pages were rendered and visually
checked. Page 26's conflicting host-1 sentence is not used to override its
explicit host-2 target, IP and console hostname.

Pages 27-28 show console times without a timezone suffix. Their UTC-04:00
interpretation is an inference supported by the report's surrounding ACT
terminal logs displaying EDT and the matching artifact/action sequence. It is
not a timezone declaration on those pages or a correction of the guest clock.
Raw event nanoseconds are retained. Host, artifact, action and process UUID
evidence are required in addition to this compatible time alignment.

| Event UUID | Action | Raw UTC time | Source part-16 record |
|---|---|---|---:|
| `1d92d20361b242f7984f23422ef135be` | CREATE_OBJECT: tropical output file | 2019-05-09 17:49:37.826 | 50,998 |
| `fb20dd62334c48e9a9ea6972c43501f0` | WRITE: tropical output file | 2019-05-09 17:50:13.551 | 73,037 |

Both directly reference FileObject `c9a119fb914d4051a113972088156308`, whose
`FILE_OBJECT_FILE` definition is at record 50,997. The exact event path is
`\Device\HarddiskVolume2\Users\admin\tropical`.

Their thread UUIDs resolve to Firefox process
`e9ac31c9c0404626821064a39dfaf516`, PID 6208, defined in part 15 at record
9,494,889 and started at 17:42:01.679 UTC. The actor and linked Principal resolve
on the publishing host, and all subject starts precede or equal the actions.
The same PID earlier identifies a different `smartscreen.exe` process:
**PID alone is not used to join or label events**.

These are **Codex manual report alignments, not expert/STARC annotations**.
Labels apply only to the two specific actions. Other Firefox, tropical,
library-access or PID-6208 events do not inherit a label. Both new actions share
one incident/group, `e5-fivedirections2-drakon-copykatz-may9`.
[Annotations](review_annotations.json) record exact identities, times, source
pages, raw-record fingerprints and limitations. No native binary labels or
training features are inferred from the search patterns.

## Actual preparation and split check

The new-case preparation imports the completed 34-file Host/Principal/Subject
index and rereads a **100,000-record prefix of part 16**, not the whole file.
Both selected events pass the normal adapter and `SecurityEvent` validation:
`file/create` and `file/access`, with process, file, user and hostname populated.
No selected UUIDs are missing or conflicting. See
[the actual new-case manifest](host2_case_preparation_manifest_20261027.json).

The local combined review run reuses the four unchanged October 17 prepared
rows after verifying their original annotation digest and unchanged resolution
chains. It appends the two newly prepared rows, checks all six against the
current annotations and `SecurityEvent` schema, rejects duplicate IDs, and
reruns `make_splits`. This is incremental assembly, not a claim that all six
events were reread from Avro during this task. Source-run manifest hashes and
annotation hashes are retained in [the combined split-gate report](split_gate_report_20261027.json).

Current counts:

| Category | Count |
|---|---:|
| Reviewed attack actions | 3 |
| Reviewed benign actions | 1 |
| Unknown actions | 2 |
| Eligible attack actions / incident groups | 3 / 2 |
| Eligible benign actions | 0 |
| Supervised splits / models trained | 0 / 0 |

The May 7 benign execution remains excluded for clock uncertainty. The gate
requires at least three independent labeled groups and both verified classes
in every partition. Different Event UUIDs in one incident do not supply
independent cases. Further group-independence review is required as data grows.
**ML-02.4 is still partial.**

All **43 existing research tests pass**. Real-data checks additionally verify
the new source hashes, exact annotation identities, typed object/actor joins,
canonical schema validation, normalized actions and blocked split behavior.
These are engineering/evidence checks, not ML validation accuracy.

## Reproduce

Use the Python environment setup in [the ML guide](../../../../research/ml/README.md).
Raw archives, SQLite indexes and canonical review JSONL remain local. Output
directories must be fresh. The two new complete audits can be reproduced with:

~~~powershell
$Raw = 'D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections'
$MlPython = '.\research\ml\.venv\Scripts\python.exe'
$OldActivities = 'data/ml/datasets/darpa/label_review_activities_20261017.json'
$PreciseActivities = 'data/ml/datasets/darpa/label_review_activities_20261027.json'
& $MlPython -m research.ml.data_prep.audit_label_evidence --source $Raw --activities $OldActivities --file-pattern 'ta1-fivedirections-2-e5-official-1.bin.15.gz' --output .cache/ml-runs/my-host2-part15
& $MlPython -m research.ml.data_prep.audit_label_evidence --source $Raw --activities $OldActivities --file-pattern 'ta1-fivedirections-2-e5-official-1.bin.17.gz' --output .cache/ml-runs/my-host2-part17
& $MlPython -m research.ml.data_prep.audit_label_evidence --source $Raw --activities $PreciseActivities --file-pattern 'ta1-fivedirections-2-e5-official-1.bin.15.gz' --output .cache/ml-runs/my-host2-part15-precise
& $MlPython -m research.ml.data_prep.audit_label_evidence --source $Raw --activities $PreciseActivities --file-pattern 'ta1-fivedirections-2-e5-official-1.bin.16.gz' --output .cache/ml-runs/my-host2-part16-precise
~~~

To rebuild a complete reference index on a fresh computer, run
`resolve_references` against the raw source with the current annotations and
`--records-per-file 0`. Existing completed caches can be reused with repeated
`--reuse-audit` arguments. This run used the old combined 28-file cache,
the three-file Drive cache, old part-16 cache and the two new complete caches;
overlapping caches must not be combined.

For an independent complete six-event preparation, the command below reads
six-million-record prefixes of the three annotation-source archives. It is
slower than the incremental run above but produces the same reviewed selection.
Use a fresh full reference index from your own computer:

~~~powershell
$env:PYTHONPATH = (Resolve-Path '.\research\ml\.venv\Lib\site-packages').Path
$BackendPython = '.\backend\.venv\Scripts\python.exe'
& $BackendPython -m research.ml.data_prep.prepare_dataset --source $Raw --annotations data/ml/datasets/darpa/review_annotations.json --reference-audit .cache/ml-runs/my-all-references --output .cache/ml-runs/my-complete-review --records-per-file 6000000 --split-output data/ml/splits
~~~

An installed ML environment containing both fastavro and Pydantic can be used
directly instead. Expected outcome is `blocked_for_training` (CLI exit 2);
a successful review preparation does not imply that splits were exported.
The 34-file reference cache in Shlok's actual run is
`.cache/ml-runs/ml02-all-references-20261027`.
JSON reports alone do not replace the local entity SQLite index.

## Remaining external dependency

The downloaded host-2 stream still lacks May 10 telemetry. The next manual
coverage probes are host-2 parts **18, 19 and 20**, approximately **966 MB**
combined. Their exact dates are unverified; their source links and publisher
checksums are in [the next download queue](host2_download_queue_20261027.json).
This batch does not guarantee that the documented benign action is present or
that all independent split groups can be completed.

The previously observed browser permission block and connector 256 MiB cap
prevent automated acquisition of these larger files. Existing support documents
and part 15/17 need not be downloaded again. Do not create benign labels from
unannotated records while waiting for matching evidence.
