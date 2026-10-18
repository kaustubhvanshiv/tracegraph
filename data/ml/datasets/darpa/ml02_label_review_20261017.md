# ML-02.4 — reviewed labels, coverage and preparation

This continues the authorized DARPA task. It does not choose an architecture,
train a detector, substitute synthetic samples, or weaken the existing split
policy. Raw downloads remain read-only in `D:\Deep Learning`.

## Evidence reviewed

Sources are the downloaded `TA51_Final_report_E5.pdf` (Revision 1.0) and
`Engagement-5-Event-Log.md`, with their hashes recorded in
[the activity search specification](label_review_activities_20261017.json).
Report pages 26 and 135 were also rendered and visually checked. The narrative
on page 26 mentions host 1, while its schedule, explicit target/IP and later
console hostname identify host 2; that inconsistent sentence cannot justify
labeling host-1 events. The quoted benign SCP alarm on page 135 has an
unspecified timezone, so its broad search window is not an annotation window.

The search specification separates seven documented activities by publishing
host UUID, UTC search window, evidence source and uncertainty. Indicator hits
are review candidates only. Missing hits, generic Firefox/SCP processes and
unannotated time periods do not supply benign labels.

## One additional reviewed benign action

The operational log's May 7 host-2 recovery entry explicitly documents
`BCDEDIT /set nointegritychecks ON`. A full-record reread finds that command in
Subject `bc21a86f5e5e462180e5479d4ff2ffdb`, PID 4948, on publishing host
`223cbbce1bc5451e9d2e5b3a762f31c7` (`ta1-fivedirections-2`). Its direct
`EVENT_EXECUTE` is:

| Field | Source value |
|---|---|
| Event UUID | `fce7334c4dc6494b82d4f35cd1b2f8d6` |
| Archive | `ta1-fivedirections-2-e5-official-1.bin.1.gz` |
| Record index, one-based | 5,847,598 |
| Raw timestamp | `1557265116204000000` |
| Raw UTC representation | `2019-05-07T21:38:36.204000000Z` |
| Publishing session | 10513 |
| Executed image basename | `bcdedit.exe` |

The execution points directly to the command-bearing Subject and starts at
the same raw timestamp as that process. Its parent process starts earlier.
This supports **label 0 for this administrative execution only**, using the
specific documented recovery purpose, host and command/action evidence.
This is Codex's manual source alignment, not an expert or STARC annotation.
No surrounding event, shutdown, SCP operation, or complete maintenance period
inherits the label. See [the bounded evidence summary](ml02_bcdedit_evidence_20261017.json)
and [the annotation](review_annotations.json).

### Clock uncertainty prevents supervised use

The operational log explicitly describes a temporary four-hour clock change
around the host-2 reboot recovery. In the bounded reread of records
5,800,001–6,300,000, 2,139 adjacent Event timestamps regress by more than three
hours, interleaving roughly 17:38 and 21:38 UTC. This statistic describes only
that 500,000-record slice. Publication is nonchronological, so it does not
identify one global correction or the precise transition boundary.

The same PID also occurs under another Subject UUID with a different timestamp;
those definitions are **not merged by PID**. Raw timestamps are preserved.
The new benign annotation has `split_eligible: false` and a mandatory exclusion
reason. Its reviewed action label does not establish reliable chronological or
causal-context boundaries. It stays in review output and is excluded from
**all train/validation/test partitions** until its time alignment is established.

`prepare_dataset.py` now reports both reviewed and eligible label/group counts,
plus explicit excluded event IDs/reasons. A regression test proves that an
excluded sample cannot supply a missing class in an otherwise evaluable
partition. Unknown labels remain outside supervised loss and metrics.

## Reproduce the work

Use the environment and source paths in
[the ML README](../../../../research/ml/README.md). All directories below must
be fresh. Retain the `.gz` compression and stream the Avro containers directly.

```powershell
$MlPython = '.\research\ml\.venv\Scripts\python.exe'
$DataSource = 'D:\Deep Learning\fivedirections-20261010T174625Z-1-049\fivedirections'
$Activities = 'data/ml/datasets/darpa/label_review_activities_20261017.json'
$Annotations = 'data/ml/datasets/darpa/review_annotations.json'

# The original host's complete metadata audit.
& $MlPython -m research.ml.data_prep.resolve_references `
  --source $DataSource --annotations $Annotations `
  --file-pattern 'ta1-fivedirections-1-*.gz' `
  --output .cache/ml-runs/my-ml02-host1 --records-per-file 0

# Full coverage and candidate searches for the other downloaded streams.
& $MlPython -m research.ml.data_prep.audit_label_evidence `
  --source $DataSource --activities $Activities `
  --file-pattern 'ta1-fivedirections-2-*.gz' `
  --output .cache/ml-runs/my-ml02-host2

& $MlPython -m research.ml.data_prep.audit_label_evidence `
  --source $DataSource --activities $Activities `
  --file-pattern 'ta1-fivedirections-3-*.gz' `
  --output .cache/ml-runs/my-ml02-host3

# Merge disjoint, completed caches and join the reviewed events.
& $MlPython -m research.ml.data_prep.resolve_references `
  --source $DataSource --annotations $Annotations `
  --reuse-audit .cache/ml-runs/my-ml02-host1 `
  --reuse-audit .cache/ml-runs/my-ml02-host2 `
  --reuse-audit .cache/ml-runs/my-ml02-host3 `
  --output .cache/ml-runs/my-ml02-all-references --records-per-file 0

# Six million records reach the administrative execution in its source file.
& $MlPython -m research.ml.data_prep.prepare_dataset `
  --source $DataSource --annotations $Annotations `
  --reference-audit .cache/ml-runs/my-ml02-all-references `
  --output .cache/ml-runs/my-ml02-preparation --records-per-file 6000000 `
  --split-output data/ml/splits
```

An existing completed host-1 cache can replace the first command; Shlok's
run reuses `.cache/ml-runs/expanded-host1-reference-20261017`. Cache reuse
checks source sizes/modification times, per-file metadata counts and disjoint
filenames. It never resumes an interrupted cache or rescans unchanged archives
merely to combine indexes. A fresh clone needs its own SQLite caches; JSON
reports are not substitutes for entity definitions.

The candidate auditor searches complete Subject command lines and Event paths,
not every possible field. It retains full Host/Principal/Subject metadata
locally, counts raw timestamps by publishing host and exports bounded candidate
references. Event-to-known-subject search sees only preceding definitions, so
zero string matches do not establish an entity's absence. Whole-file time
coverage is measured independently of those string matches.

Preparation retains only annotation-listed review events. Binary labels require
reviewed evidence and a group; excluded samples additionally require a boolean
flag and a reason. Only validated split IDs may be used for supervised training.
Exit code 2 means training gates failed, not that splits were produced.
Annotation/reference digests use UTF-8 text with LF newlines so Windows/Linux
Git conversion does not invalidate provenance. Raw event nanoseconds stay intact.

## Validation

The research suite passes **43 tests**, including host/time candidate scoping,
bounded candidate output, preserved unknown labels, disjoint cache merging,
changed-source/cache rejection, exclusion validation and partition class checks.
Synthetic test fixtures are software checks, not DARPA training examples.

## Completed coverage audit

All **28 downloaded archives** are fully decoded across the completed caches:
**280,000,000 records**, including **268,396,798 Event records**. The current
task decoded the remaining 180 million records from hosts 2 and 3; the earlier
100-million-record host-1 audit was reused. These are raw record counts,
not unique labeled samples or a complete scan of the entire DARPA release.

See the [coverage matrix](ml02_activity_coverage_20261017.json),
[host-2 activity audit](ml02_host2_evidence_audit_20261017.json),
[host-3 activity audit](ml02_host3_evidence_audit_20261017.json) and
[combined reference report](ml02_full_reference_report_20261017.json).
Reference reports deliberately assign no labels; their null label fields are
identity-audit placeholders. Actual reviewed labels are in the annotation file
and preparation manifest.

| Documented activity | Relevant downloaded-stream coverage |
|---|---|
| Host 2, May 7 recovery | Exact command-bearing Subject and execution found; its broad search window contains 32,714,555 raw Events, which are not labeled benign as a block |
| Host 2, May 9 Drakon/Copykatz | Zero Events in the configured attack search window |
| Host 2, May 10 benign SCP example | Zero Events in either searched timezone interpretation |
| Host 2, May 15 BITS/Micro APT | Zero Events in the configured attack search window |
| Host 1, May 16 benign driver setup | Every downloaded host-1 file's Event range is outside the setup search window |
| Host 3, May 10 SSH/SCP and May 17 Drakon | Zero Events in either configured attack search window |

Host 2's last downloaded Event is May 8 at 16:00:34.238 UTC; host 3's is May 8
at 13:58:31.522 UTC. Host 3 also contains older May 3 records. Stream-level
minimum/maximum dates are bounding ranges, not continuous coverage. In
particular, host 1's May 7–17 bounds do not fill the missing May 16 setup gap.
The reported missing windows do not create negative labels.

## Completed preparation and remaining requirement

The real rerun imports **1,445,850 definition records** from the validated
combined index and reads **12,000,000 source records**: six-million-record
prefixes of segment 121 and host-2 segment 1. This produces four selected
`SecurityEvent` records with no missing or conflicting selected events:
three file/access actions and one process/execute action. Hostnames resolve
for 4/4, linked usernames for 2/4, and actors for 2/4. These are selected-event
coverage rates, not population-wide estimates.

| Quantity | Actual result |
|---|---:|
| Reviewed attack actions | 1 |
| Reviewed benign actions | 1 |
| Unknown candidates | 2 |
| Split-eligible attack actions / groups | 1 / 1 |
| Split-eligible benign actions / groups | 0 / 0 |
| Excluded reviewed actions | 1, for uncalibrated clock epochs |
| Supervised train/validation/test splits | None |

See [the preparation manifest](ml02_label_preparation_manifest_20261017.json).
The benign label is retained for evidence review and is absent from the split
input. The two original unknowns still lack their host-1 parent definition;
other hosts' metadata cannot fill that gap. The execution target is the actual
typed `bcdedit.exe` image, not an invented process inferred from a filename.

**ML-02.4 remains incomplete for real supervised partitions.** Its reader,
normalization, reviewed-label import, quality exclusions, deterministic split
checks and ID-only export are implemented and tested. The actual data still
cannot satisfy the required independent groups and both classes in every
partition. No split directory, model, training run or detector metric was
created. The pipeline correctly returns `blocked_for_training`.

To complete that remaining requirement, obtain matching telemetry for the
documented benign and additional attack cases, independently review their
actions/group relationships, and resolve clock uncertainty before admitting
affected events to chronological/context splits. The activity specification
gives verified hosts and search times; it does not establish which unavailable
archive numbers contain them. Download choices must be checked against actual
coverage, rather than inferred from adjacent filenames. Continue on DARPA;
no substitute dataset or architecture is selected here.
