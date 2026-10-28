# ML-02.4 benign-label and split readiness - 2026-10-28

**Next-phase decision:** separate node-benchmark preparation has now been
selected. Its [source-intake guide](../../../../research/ml/node_benchmark/README.md)
and preflight are ready. The authors estimate 280 GB for the restored database,
so the 38.6 GB dump download is on hold pending a storage-fitting intake plan.
The Event-level rules and labels described below are unchanged.

**Completed the next readiness check: published training-day membership cannot
currently supply our missing benign Event labels.** The downloaded subset also
lacks the published validation day. No label or split was created.

This follows the [public annotation case review](ml02_public_case_review_20261027.md).
Its six reviewed Events are unchanged: three attacks, one clock-excluded benign
action and two unknowns. Eligible data remain three attack actions across two
incident groups and zero benign actions.

## Benign evidence reviewed

The operational log supplies no additional exact FiveDirections command/UUID
mapping beyond the previously reviewed administrative recovery. The current
documented leads remain:

| Lead | Why it does not yet add an eligible benign Event |
|---|---|
| May 7 BCDEDIT recovery | Exact execution reviewed; mixed clock epochs still exclude it from splits |
| May 10 benign SCP example | Quoted alarm time, PID/CDL IDs and native Event mapping remain unresolved |
| May 16 host-1 filemon installation | Current audited files lack the required setup interval; later exploitation and filename-only matches do not establish benign purpose |
| Other shutdown/recovery notes | Operational purpose is described, but no additional exact action mapping was established |

The source log is the existing `Engagement-5-Event-Log.md`; its SHA-256 remains
`70b111fff7bc4662d4c22664be19c4c08702a36676f31f160d4b3a856ee5c3c9`.
No process name, missing attack annotation or calendar date is assigned label 0.

## Check of the published date configuration

The pinned [PIDSMaker configuration](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/pidsmaker/config/config.py)
assigns five training dates, one validation date and three test dates to E5
FiveDirections. Comparing its May-2019 EDT day windows with the completed
37-archive Event bounds gives:

| Role | Date | Local archives whose raw Event bounds overlap the day |
|---|---|---:|
| Train | May 8 | 19 |
| Train | May 10 | 2 |
| Train | May 11 | 0 |
| Train | May 13 | 0 |
| Train | May 14 | 0 |
| Validation | May 12 | 0 |
| Test | May 9 | 11 |
| Test | May 15 | 2 |
| Test | May 17 | 4 |

Zero overlap rules out native-timestamp Events for that window in these
downloaded archives. Positive overlap establishes only bounds intersection;
it does not measure daily Event counts, continuous coverage or benign intent.
All windows are half-open local days converted using EDT UTC-04:00. No raw
timestamps were adjusted, and no fresh Avro scan was necessary for this check.

The complete reference cache's source sizes/modification times were revalidated.
The reference report and annotation hashes still agree with the previous gate.
Exact file lists, UTC boundaries and hashes are in the
[readiness audit](normal_date_readiness_20261028.json).

### May 10 needs a host/action review

ACT report page 41 lists FiveDirections host 3, `128.55.12.109`, among the
targets of the May 10 stolen-credential SSH/SCP campaign. Page 54 shows SSH
access, `scp passwd` and `ipconfig` in that host's console, followed by more
activity on pages 55-56. Pages 41 and 54 were visually checked.

Therefore May 10 is not an authoritative, universally benign date across all
three FiveDirections hosts. This does not prove that the authors' processed
database contains those actions: its actual host selection and filtering have
not been inspected. Our host-3 files do not cover May 10 either. No current
training contamination is claimed; we have created no training split.

The ACT source is the existing `TA51_Final_report_E5.pdf`, SHA-256
`95785dd6e32e1585e3a3b49f7f69aac785ca9d2db05593ad919b1b627897f0a1`.
This is case-level source evidence, not a new UUID-level attack annotation.

### The published dates use a different evaluation order

The latest training date is May 14, validation is May 12, and the earliest test
date is May 9. These assignments do not satisfy our currently defined
chronological train-before-validation-before-test rule. Disjoint date names
alone do not establish temporal generalization.

This is a protocol difference, not a claim that the authors promised our
specific deployment/evaluation contract. Copying their dates into ML-02.2 would
require an explicit protocol revision and another coverage/label review.
The shared node previously found in Copykatz/BITS is within their test cases;
it is not, by itself, evidence of cross-partition leakage.

## Processed-data option checked without downloading it

The authors' [preprocessing guide](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/dataset_preprocessing/README.md)
points to processed datasets. Their
[download script](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/download_datasets.sh)
names an E5 FiveDirections dump. A genuine Google Drive metadata read returned:

- File: [fivedirections_e5.dump](https://drive.google.com/file/d/1EkxlbReJgMHW4TwAypPggQBA-RTRVxs4/view?usp=drivesdk)
- Size: **38,603,947,024 bytes**, about **38.60 GB / 35.95 GiB**.
- MIME type: `application/octet-stream`; modified January 5, 2026.
- Scope checked: metadata only. File-content access, actual dump format,
  host/day coverage, checksums and label provenance remain unverified.

This is another source of processed DARPA data, outside the user's specified
original release folder. It was not downloaded or imported. It is also much
larger than the Drive connector's previously observed raw-file limit, so no
connector content fetch was attempted. The raw dataset was not modified.

The inspected raw-import helper's
[`get_filelist` function](https://github.com/ubc-provenance/PIDSMaker/blob/438a05a7c55256f639e5b5945cf4828fe3ee078e/dataset_preprocessing/darpa_tc/filelist.py)
handles only THEIA/CADETS E3/E5. It has no FiveDirections branch. That particular
helper does not establish a ready raw-import recipe for this subset; this is
not a claim that the processed dataset or entire framework is unsupported.
No third-party download or database script was executed.

## Concrete choice before the next phase

Two paths are available. Neither starts a model automatically.

1. **Keep the current Event-level task.** Continue only when trustworthy benign
   actions, time/identity mappings and independent groups become available.
   The missing actor parent could improve two positive candidates but would
   not, alone, supply benign samples or independent splits. Another broad raw
   download batch is not justified as a label fix.
2. **Prepare a separate published-label node benchmark.** With the user's
   approval, investigate the authors' processed DARPA file and propose an
   explicit node-level label/split protocol. Check host scope, May 10 activity,
   missing cases, chronological boundaries, unknown/unlisted nodes and source
   traceability before accepting any partitions. Published-list membership must
   not be presented as expert-verified benign/malicious Event ground truth.
   Any model choice and training would remain a later task after readiness passes.

The second path changes the target/evaluation assumptions and uses a different
Drive source with a 38.6 GB file. It therefore needs approval under the user's
earlier instruction to ask before scope changes and additional-source downloads.
The proposal is reviewable here; no protocol change has been applied.

## Reproduce the readiness check

Use the pinned configuration/source files and the current
`scp_full_reference_report_20261027.json` file bounds. For each date, construct
`[00:00 EDT, next-day 00:00 EDT)` and test:

```text
file.min_event_utc < day.end_utc AND file.max_event_utc >= day.start_utc
```

Keep the zero-overlap and bounds-only interpretations separate. Compare maximum
training date with minimum validation date, then maximum validation date with
minimum test date. Inspect the ACT source pages and pinned helper without
executing foreign code. Source blobs/hashes, date windows, the bounded-source
interpretation and processed-file metadata are recorded in the JSON audit.

**Status:** readiness audit completed; ML-02.4 and supervised training remain
blocked under the existing rules. No new label, split, model, package installation
or raw-data download was made in this phase.
