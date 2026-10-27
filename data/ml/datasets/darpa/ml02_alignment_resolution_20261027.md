# ML-02.4 source-alignment resolution audit - 2026-10-27

**Public-web follow-up:** [subsequent research](ml02_public_source_research_20261027.md)
found third-party E5 FiveDirections node annotations with 19 Subject matches
in our metadata. They add case evidence but do not supply the SCP alarm's
time/CDL mapping or verified benign Event labels. The gate below is unchanged.

**Audit completed; the SCP source-to-CDM mapping remains unresolved.**
No timestamp repair, PID reinterpretation, benign label, model or new download
batch was introduced. The current eligible set remains three attack actions
across two incident groups and zero benign actions.

## Source meaning and tested hypotheses

The original PDF page 135 was rendered and visually checked. The printed
03:38:26.71, PID 680, CDL Subject 119657 and Object 835986 agree with the extracted
text. The line is explicitly a **MARPLE TA2 alarm quoted in the ACT report**.
It does not declare its timezone, hour-format convention, PID number base or
whether the timestamp is occurrence, receipt or alert-generation time.

CDM20 defines Event timestamps as occurrence times in Unix-epoch nanoseconds
and distinguishes process CIDs from thread CIDs. Its schema notes that clock
sources across clocks still need definition. TimeMarker describes stream read
position; it is not an independent UTC calibration. These contracts do not
define the external MARPLE alarm formatter.

[The hypothesis audit](scp_alignment_hypotheses_20261027.json) records exact
queries, scopes, source hashes and outcomes:

| Hypothesis/check | Observed result | Consequence |
|---|---|---|
| Printed time is UTC | Part 20's bounds include 03:38 UTC, but none of the 12 fully reviewed matching-file WRITEs matches the exact Temp path, PID and time within 60 seconds | No verified source match |
| Printed time is EDT | Would mean 07:38 UTC; no downloaded host-2 archive's Event bounds include that instant | Untestable with current coverage, not disproved |
| PID token is decimal | 680; no compatible May 10 SCP process instance seen in the completed metadata index or reviewed writes | Cannot establish the quoted actor |
| PID token is hexadecimal | 0x680 = 1664; three SCP instances seen on May 9, none on May 10; no reviewed write actor has this PID | A different numeric interpretation does not resolve this case |
| PID token is actually a thread CID | None of the reviewed write subjects has CID 680 or 1664 | Do not substitute thread IDs for process IDs |
| Reported host was wrong | No May 10 SCP process with either PID interpretation found in any downloaded host's metadata | No supported replacement host; identities remain host-scoped |
| Carry May 7's four-hour clock change into May 10 | Operational log says the temporary May 7 change auto-corrected within minutes; May 10 section supplies no host-2/MARPLE calibration | No global four-hour correction justified |

Absence from the downloaded index is not absence from unprovided telemetry.
Bounds do not establish continuous coverage. These checks do not prove the
report is wrong; they show that the available materials do not identify its
specific event. No best-fit offset is selected to force a filename match.

The schema uses 16-byte UUIDs; the published materials provide no mapping from
the quoted CDL integer IDs to CDM UUIDs. Zero-padding or converting those
integers is not a valid identity join.

## Additional existing-data check: May 15 MicroAPT

The earlier May 15 search documented that C2 addresses might occur only in
network objects. To close that search gap, the already-downloaded host-2
part 101 was fully reread: **3,890,348 existing records**, including **141
NetFlowObject records**. This is not an increase in the corpus's unique
record count and requires no new archive.

The expanded scan checks string fields and ordinary/base-object properties
across CDM kinds for `ctfhost2.exe`, `113.165.213.253` and the documented
download-server address `68.149.51.179`.

It finds 12 Event records referring to
`Windows/Prefetch/CTFHOST2.EXE-5AB43F1F.pf` on **May 17**. These are OPEN,
CLOSE, FCNTL and attribute checks, not the report's May 15 malware execution
or C2 connection. Historical malware names do not turn later Prefetch accesses
into attack actions, and no benign purpose is inferred from the filename either.

The configured May 15 window has 207 available Events, all OPEN actions across
72 subject UUIDs. All 207 final actor chains are unresolved; five also contain
a chain member whose start is later than the Event timestamp. The temporal
guards are preserved, not bypassed. There is no literal C2-address hit in the
network-object fields inspected in this file.

See [the expanded case audit](may15_existing_case_audit_20261027.json) for source
positions, raw-record fingerprints, temporal examples and scope limits.
This does not prove absence of the attack from the full release.

## What is needed to unblock supervised preparation

A provider or qualified reviewer needs to establish at least one of the
following, with independently documented case/group provenance:

1. The quoted alarm's timezone and hour format, whether its time denotes the
   Event or alarm creation, its PID number base/meaning, and an authoritative
   mapping for CDL Subject 119657/Object 835986 to native CDM UUIDs.
2. Alternative explicitly verified benign Event annotations that identify
   publishing host UUID, Event UUID, source filename/record position, raw
   timestamp, CDM action, evidence/provenance and independent scenario/group.

For a source clarification request, the exact outstanding questions are:

- In the page-135 line, is 03:38:26.71 UTC, EDT or another clock? Is the formatter
  24-hour, and does it print occurrence, receipt or alarm-generation time?
- Does `pid=680` mean decimal process ID 680, hexadecimal 0x680, a thread ID or
  an internal identifier?
- Which native CDM host, Event, Subject and predicate UUIDs correspond to that
  example? Is there a released UUID/label mapping or independent benign-case
  annotation that resolves it?

This is a review packet, not a message sent to any third party.
The current Drive PDF was already verified byte-identical to the local copy,
and STARC was empty in the [source availability check](scp_source_availability_20261027.json).

## Current gate and next action

[The alignment gate report](alignment_gate_report_20261027.json) confirms
unchanged annotation and reference provenance. Six selected review rows remain:
three attacks, one clock-excluded benign action and two unknowns. Eligible
labels remain **three attacks / zero benign**, with two attack incident groups.
The independent-group and both-class split checks still fail.

**ML-02.4 is not complete; no training is claimed.** Further raw files may be
useful after a time/identity gap is confirmed, but another broad download
batch alone does not supply trustworthy labels. No additional batch is queued.
Do not fabricate normal labels, reinterpret IDs, correct clocks by matching
a desired answer, or treat later cached artifacts as live attack events.

## Reproduce without new downloads

Use the current 37-file reference cache and the prior fully reread
[12-action SCP review](scp_candidate_review_20261027.json).
Read-only process-instance checks use the `entities` table:

~~~sql
SELECT uuid, host, payload, filename, record_index
FROM entities
WHERE kind = 'RECORD_SUBJECT'
  AND json_extract(payload, '$.type') = 'SUBJECT_PROCESS'
  AND json_extract(payload, '$.cid') IN (680, 1664);
~~~

Filter by the expected publishing host and SCP image; examine each instance's
start time and direct UUID chain. For reviewed write subjects, inspect their
own CID separately from the resolved process CID. Do not join by CID alone.
Compare source UTC/EDT hypotheses with per-file bounds, not stream-wide min/max.

For the expanded May 15 check, stream the complete part-101 Avro container,
search the fields and indicators listed above on the expected host, then inspect
both the matched records and all Events in 17:10-19:00 UTC on May 15. Evaluate
their subject chains with the completed index and preserve missing/future starts.
The local run `.cache/ml-runs/scp-time-identity-20261027` retains the full
indicator records, 207 window records and temporal-review details.
