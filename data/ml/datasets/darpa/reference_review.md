# ML-02 reference and label review — 2026-10-11

## Evidence sources and scope

Review uses the six downloaded FiveDirections gzip/Avro containers, CDM 2.0
schema, and the local `TA51_Final_report_E5.pdf` (Revision 1.0, June 28, 2019).
PDF page numbers below are one-based physical pages. This is manual
report-to-event evidence, not a downloaded STARC event-label annotation.

The offline reference auditor indexes subject, principal and host definitions
across available segments. It rejects ambiguous definitions and distinguishes
thread CIDs from process CIDs. Process start times are compared to event times.
The local index contains raw entity metadata; committed reports exclude full
command lines and principal names.

## Host evidence

A separate 2,000,000-record prefix audit of segment 121 found 388 network-flow
objects. Of these, 268 have CDM `localAddress: 128.55.12.55` and publishing
host UUID `2ab88dcdcbe641dfac699f6d6058e398`. This is the IP identified for
FiveDirections host 1 in the report, pages 91 and 126.

See [network evidence](network_host_review.json). The schema defines
`localAddress` separately from `remoteAddress`; remote-address matches are
not used to identify the publishing host. This supports a host/IP association
within the inspected segment, not a universal hostname mapping or proof that
every flow field was populated correctly. The report contains other local,
loopback, multicast and IPv6 addresses; the host may have multiple interfaces.

## Attack-action evidence

Event `b2f735d934fc4f92ac98996118533f5c` opens a path ending in
`DXu0yAtkCpuUTo` under `Users\admin\Documents\Pictures` at
`2019-05-17T20:14:53.225000000Z`. Its subject is thread
`8d1252ea10594bb2a5583880fa606aba`, CID 6132. The parent process UUID is
`27a66853adc240d8a7ac6788cc6cfd6b`, PID 5432, with a Firefox content-process
command line and start timestamp `1558124066644000000` (before the event).

Report page 127 associates that exact generated filename with an `elevate3`
attempt followed by SYSTEM identity, at approximately 16:15 EDT. EDT converts
to UTC with a four-hour offset; the report has minute-level timing and the
telemetry has nanosecond timestamps. Pages 91–93 and 126 establish the Firefox
Verifier/Drakon attack context. A Firefox process alone is not attack evidence;
the generated artifact, path, host/IP and compatible time are used together.

Other candidates are `PD2GziBJ2wpDwP` (page 126) and `7B4qoq3yWIKPQh`
(page 127). All three are phases of the same Verifier/FileFilter campaign and
must remain in one split group. These matches do not label every Firefox
event, every event on the host, or an entire attack-time window.

## Benign evidence and independence

Page 135 describes benign setup of `filemon.inf` using
`InfDefaultInstall.exe` and `sc start filemon`, around 11 AM on May 16. This
can justify only specific setup actions with matching host, actor and time
evidence. The later exploit of the installed driver is malicious; a filename
match alone cannot distinguish setup from exploitation.

May 10 SCP/SSHD benign examples in the report concern a different host and
cannot automatically label the current host's telemetry. Missing attack
annotations are not negative labels. No independent verified benign event or
additional independent positive campaign has yet been established here.

## Completed review decision

The full audit decoded 60,000,000 records (58,037,343 Events) and indexed
257,164 Subject definitions. All six containers were fully read. No Host or
Principal definitions or the missing parent
`1fca97f4e4134d05869b31eb09df8770` are present. The Firefox actor has no
conflicting definition and starts before its event. See
[the full reference audit](full_reference_report.json).

The first five segments' event ranges end by May 10. Segment 121 starts on
May 16 at 20:17 UTC, after the documented 11 AM EDT driver setup. Thus that
benign interval is outside this subset; zero benign labels are established.

Assign **label 1** only to event `b2f735d934fc4f92ac98996118533f5c`, based on
the combined report/artifact/path/time/actor/host-IP evidence above. This is
Codex's manual source alignment, not an expert-supplied STARC label. Report
timing is approximate, host identity is inferred from netflows, and principal
identity remains unavailable. The annotation records these limitations. The
other two candidates remain **null** due to the missing actor parent.

The preparation rerun retains one positive and two unknowns. No supervised
split or model metric is produced: no verified negatives or independent
positive groups are available. Remaining work requires missing entity-bearing
telemetry, host-1 benign setup coverage, and independently reviewed incidents.
