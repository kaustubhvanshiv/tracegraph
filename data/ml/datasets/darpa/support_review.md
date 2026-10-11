# FiveDirections support archive review and ground-truth alignment

This records the initial support review. The later
[full reference and label review](reference_review.md) supersedes its initial
all-unknown label status: one event is now a report-reviewed positive, two
remain unknown, and training is still blocked.

Reviewed 2026-10-11. Original support files remain under:

```text
D:\Deep Learning\darpa-tc-e5-support
```

## Files actually received

| Original file | Contents read |
|---|---|
| `Ground_Truth-20261011T062242Z-1-001.zip` | `Ground_Truth/TA51_Final_report_E5.pdf` (158 pages); DOCX companion inventoried, not needed for this review |
| `Schema-20261011T062309Z-1-001.zip` | `Schema/TCCDMDatum.avsc`, `Schema/CDM20.avdl`, `Schema/cdm.pdf` (6 pages) |
| `Engagement-5-Event-Log.md` | Operational issues log |

The actual report is **Revision 1.0, June 28, 2019**. It is not named
`tc_ground_truth_report_e5_update.pdf`. Its content clearly covers Engagement 5;
do not silently describe it as a later updated report. Archive/member SHA-256
hashes and actual source paths are in [support_inventory.json](support_inventory.json).

Selected support members were extracted into ignored `.cache/ml-support/`.
No downloaded archive or raw telemetry was changed. ZIP CRC checks succeeded
for the extracted members. The PDF text reader reported recoverable object
offset warnings; the relevant pages 91 and 126 and diagram page 147 were also
rendered and inspected. The report is a narrative, not a ready-made event-label
table; no STARC event annotations were in these ZIPs.

## Report findings relevant to this stream

The downloaded telemetry is `ta1-fivedirections-1-e5-official-1`. The detailed
report sections 9.4 and 10.11 identify **ta1-fivedirections-1**, IP
**128.55.12.55**. Use detailed target sections, not the overview table alone:
other portions of the report contain inconsistent host labels and times.

- Pages 91–93 (May 16): failed BITS attempts are followed by manual transfer of
  `tester.exe` and `dbgstat.dll`, then Application Verifier persistence inside
  Firefox. The detailed delivery log starts at 14:24, despite the section's
  11:03 heading. Persistence remained enabled through the engagement.
- Pages 126–128 (May 17): the attacker continues the same persistence, opens
  distinctive generated filenames to trigger FileFilter elevation, and reads
  the hosts file. The shell `date` on page 126 explicitly reports **EDT**.
  Therefore 16:11 EDT equals **20:11 UTC**. Page 127's `14:16` entry is
  inconsistent with surrounding `16:15` entries and needs separate treatment.
- Page 135 identifies benign driver-installation activity on May 16 and benign
  SCP examples on **host 2**, not host 1. Those examples cannot automatically
  become negative labels in the current host-1 data.
- The operational log records host-1 publishing backlog and shutdown on May
  13–14, and an unresponsive host/reboot on May 16. Arrival order and collection
  completeness must not be inferred from filenames or publication order.

## Complete scan of segment 121

The [coverage audit](fivedirections_full_coverage.json) fully scanned
`ta1-fivedirections-1-e5-official-1.bin.121.gz`:

- **10,000,000 records**, including **9,650,235 Events**.
- Embedded schema matches the downloaded `TCCDMDatum.avsc` using Avro parsing
  canonical form, which compares decoding structure rather than formatting/docs.
- Event timestamps range from **2019-05-16 20:17:51.316 UTC** through
  **2019-05-17 21:32:40.180 UTC**. The start-of-file prefix did not reveal that
  full range. Events can be out of timestamp order.
- No Host definitions occur in this entire segment. The host UUID below is
  bridged to the report target by stream identity and matching attack markers;
  it is not a hostname read from a Host record.

The other five segments retain prefix inspections. An exploratory full scan of
segment 15 was interrupted; incomplete counts were not included in the report.
`all_files_fully_scanned` is explicitly false. No full-release counts or class
balance are implied.

## Three precise event matches

All three filenames below occur once in segment 121, in `predicateObjectPath`
on `EVENT_OPEN` records. Their basename, action, time, target stream, and sequence
agree with report pages 126–127. Paths were checked directly against source
records, not just matched by a time window.

| Filename in report | CDM Event UUID | UTC event time | Report page |
|---|---|---|---:|
| `PD2GziBJ2wpDwP` | `cba5c7333a594b0b9b6f7b3e6489d9c2` | 2019-05-17 20:12:42.746 | 126 |
| `7B4qoq3yWIKPQh` | `8f5db838a1504f5b9b0ce074a1e356a0` | 2019-05-17 20:13:16.800 | 127 |
| `DXu0yAtkCpuUTo` | `b2f735d934fc4f92ac98996118533f5c` | 2019-05-17 20:14:53.225 | 127 |

Host UUID: `2ab88dcdcbe641dfac699f6d6058e398`.
The first two events share subject UUID `b890ef7a5c86467d95ab7030c9dfa7e3`;
the third uses `8d1252ea10594bb2a5583880fa606aba`.
Both acting subjects resolve to **SUBJECT_THREAD**, not processes, in the first
two million records. Parent process UUIDs must be followed when building process
features. Do not mistake thread IDs 1028 and 6132 for process IDs.

These are strong report-alignment evidence for positive examples, but remain
explicitly **review candidates with `label: null`** in the audit. Publication
of a narrative and three local matches is not a complete supervised labeling
protocol. `dbgstat.dll` appears in 761 event records and `tester.exe` in 12;
those occurrences alone are not automatically malicious actions.

## What this means for ML-02

The missing-document gate is resolved. Preparation is now gated by **label
coverage and independent evaluation groups**, rather than ZIP format.

1. Establish a versioned report-aligned annotation protocol and explicitly
   approve which matching actions qualify as positives. Preserve failed
   attacker actions separately from successful compromise outcomes.
2. Establish verified benign host-1 examples, rather than calling unmatched
   records benign. The report's benign driver setup is one candidate for later
   alignment if corresponding data is available.
3. Resolve thread→process, process→principal, and object references. Missing
   entity metadata stays missing, with coverage measured.
4. Treat May 16 persistence and May 17 continuation as a **single attack group**.
   Three opens from one group cannot supply independent train, validation, and
   test attacks. Additional independent incidents and their telemetry will be
   needed for a defensible supervised benchmark.
5. Confirm exact additional segments from incident-time and entity-coverage
   evidence before asking for more large downloads. No particular missing
   segment numbers have been inferred from filenames alone.

No model has been trained, no binary labels or splits assigned, and no detection
accuracy claimed.

## Reproduction

Support reading and coverage commands are in `research/ml/README.md`.
The coverage tool supports a saved completed-file checkpoint. Use it only with
unchanged source data and unchanged incident/schema inputs. The current stored
audit covers segment 121 completely and the remaining files only by earlier
prefix inspection.
