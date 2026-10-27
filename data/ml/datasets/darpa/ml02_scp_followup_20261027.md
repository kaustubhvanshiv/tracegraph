# ML-02.4 SCP coverage follow-up - 2026-10-27

**Next-step audit completed:** see the [clock/identity resolution audit](ml02_alignment_resolution_20261027.md)
for tested hypotheses, the additional existing-data check and the precise
annotation information needed. No new labels or downloads resulted.

**Batch review completed; no additional download batch is requested now.**
Parts 18, 19 and 20 are received, checksum-verified and fully decoded.
The remaining obstacle is trustworthy labels and independent cases, not merely
raw dataset volume. ML-02.4 is still incomplete for supervised training.

The official Drive source was also checked: its current ground-truth PDF is
byte-identical (SHA-256 verified) to the existing local report, the Ground_Truth
folder lists only the PDF and DOCX, and STARC remains empty. No separately
named updated report or STARC annotation file was found in those folders.
See [source availability and hash verification](scp_source_availability_20261027.json).

## What was verified

Raw folder:
`D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections`.

| Host-2 part | Records | Event records | Latest Event, UTC |
|---|---:|---:|---|
| 18 | 10,000,000 | 9,555,998 | May 9 23:06:47.488 |
| 19 | 10,000,000 | 9,563,830 | May 10 00:59:00.325 |
| 20 | 10,000,000 | 9,593,598 | May 10 04:17:00.759 |

All three match the publisher's expected MD5 and byte size. See
[acquisition verification](host2_scp_download_verification_20261027.json).
The local inventory now has **37 archives, 10,956,483,982 compressed bytes**.

The completed [37-file reference audit](scp_full_reference_report_20261027.json)
covers **345,099,571 raw records**, including **330,788,968 Event records**.
The 30 million new records are counted once; the targeted reread below is not
another 10 million unique records. The merge reuses the prior 34-file index
and the three completed new caches, validating sizes, modification times and
metadata counts. It does not rescan older archives. All six existing
annotation-listed identity chains are unchanged.

Bounds do not imply continuous coverage: these files also publish older
timestamps. The full data release has not been downloaded or fully audited.

## Focused search and full-record review

The [focused activity configuration](scp_review_activity_20261027.json)
searches the exact basename `www.army.mil.nz.docx`, on host 2, within the
broad May 10 UTC/EDT review window. It excludes generic SCP-name matches and
assigns no labels. Completed search reports:

- [Part 18](host2_part18_scp_audit_20261027.json): zero Events in the window,
  zero exact-basename matches.
- [Part 19](host2_part19_scp_audit_20261027.json): 208 exact-basename Event
  matches; 200 references retained, including six WRITE references.
- [Part 20](host2_part20_scp_audit_20261027.json): 510 exact-basename Event
  matches; initially 200 references retained.

The candidate-reference cap is not proof of absence. To inspect later matches,
a second **complete part-20 read** retained all 510 matching raw Events locally
and reviewed all **12 WRITE actions**, using the 37-file host-scoped subject
index. This avoids treating the earliest 200 candidates as a complete review.

The filename appears in three locations: `Users/admin/Documents/Pictures`
(275 Events), `Users/admin/Pictures` (174) and `Windows/Temp/Pictures` (61).
These are counts of matching Event records, not unique files or benign labels.

The source report's page 135 example specifies a Windows/Temp/Pictures WRITE,
PID 680 and time 03:38:26.71, without a timezone suffix. The reviewed part-20
writes have other process IDs and times. The SCP receiver writing the Temp path
at 01:49:38.675 UTC has PID 1656; the nearby System write has PID 4. Neither is
silently substituted for the source example. All matching WRITE actors were
resolved before comparison.

There is no matching WRITE within 60 seconds of 03:38:26.71 UTC and no matching
WRITE actor PID 680 among these 12 actions. If the report time is EDT, it would
instead correspond to 07:38 UTC, beyond part 20's latest measured timestamp.
The report's timezone and whether its alarm timestamp equals the source-event
timestamp remain unverified. Extra telemetry is only one possible missing
piece; this ambiguity does not justify prescribing more files blindly.

[The review report](scp_candidate_review_20261027.json) preserves source
positions, Event/actor UUIDs, times, decisions and raw-record fingerprints.
The review is a failure to establish the specific documented benign case,
not a claim that the other transfers are malicious or that no matching event
exists elsewhere. Filename, ordinary program name and time-window membership
alone do not establish a benign action.

No matching predicate definitions were found among FileObject definitions
in part 20 itself. That is not an absence claim across the other archives,
and no object type was invented from a path string.

## Labels and training gate

No new label or normalization was added. The unchanged six prepared review
rows still match the exact annotation digest and unchanged identity chains;
they pass canonical schema validation. Rechecking `make_splits` still refuses
training. See [the follow-up gate report](scp_split_gate_report_20261027.json).

| Category | Count |
|---|---:|
| Reviewed attack actions | 3 |
| Reviewed benign actions | 1 |
| Unknown selected actions | 2 |
| Eligible attack actions / incident groups | 3 / 2 |
| Eligible benign actions | 0 |
| New splits / models trained | 0 / 0 |

The May 7 benign action remains excluded for uncertain clock alignment.
The earlier six-row preparation is reused; this follow-up does not claim
a fresh Avro normalization of those rows. Current annotations remain unchanged.

## Reproduce the focused audit

Use the ML guide's fastavro environment. Use fresh output names and keep raw
downloads read-only. This task ran the three file audits concurrently; the
following equivalent API calls run sequentially:

~~~powershell
@'
from pathlib import Path
from research.ml.data_prep.audit_label_evidence import audit
raw = Path(r'D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections')
config = Path('data/ml/datasets/darpa/scp_review_activity_20261027.json')
for part in (18, 19, 20):
    audit(raw, config, Path(f'.cache/ml-runs/my-scp-part{part}'),
          file_pattern=f'ta1-fivedirections-2-e5-official-1.bin.{part}.gz',
          candidate_cap=200)
'@ | & '.\research\ml\.venv\Scripts\python.exe' -
~~~

Merge a completed prior 34-file reference cache and the three completed new
caches through `resolve_references --reuse-audit` (repeat once per cache).
They must be disjoint and match the same current raw files. JSON reports alone
do not replace the local SQLite metadata indexes. The actual merged cache is
`.cache/ml-runs/ml02-scp-all-references-20261027`.

For the source review, stream all part-20 records, filter Event paths by the
configuration's exact-basename regex, retain all matches, then select
`EVENT_WRITE` and use `resolve_chain` on each subject UUID and its raw timestamp.
Compare the complete path, process identity and source timing; preserve unknown
labels when the documented action is not established. The local review cache
is `.cache/ml-runs/scp-source-review-20261027`; it contains the full matching
records, object-definition check and the 12-action review.

## Are more downloads necessary?

**Not as an automatic next step.** This batch already adds 30 million records,
but it does not establish an eligible benign label. First clarify the source
example's time/identity mapping and identify enough independent documented
attack and benign cases. Then request only telemetry needed for confirmed
gaps, if any. The available evidence does not show that all remaining archives
are required, or that raw downloads alone can complete the split requirements.

The [earlier queue](host2_download_queue_20261027.json) is now marked received.
The next planned work is source-annotation/time clarification and independent
case review, not another broad download batch or premature GPU training.
