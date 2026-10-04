# DARPA TC E5 — Graph Constructibility Assessment

## 1. Node / Entity Fields

| TraceGraph Entity | CDM Record Type | Key Fields | Notes |
|-------------------|----------------|-----------|-------|
| Host | `Host` | `hostName`, `hostIP[]`, `uuid` | Real hostnames and IPs present; `TCCDMDatum.hostId` on every record provides reliable cross-record host linkage |
| User | `Principal` | `userId` (OS uid integer), `username` (optional string) | Real OS uid present; `username` optional and not guaranteed populated |
| Process | `Subject` (SUBJECT_PROCESS) | `cid` (pid), `cmdLine` (optional), `parentSubject` (optional UUID), `startTimestampNanos` | Process tree constructible via `parentSubject`; `cmdLine` optional and stream-dependent |
| File | `FileObject` | `uuid`, `type`, `size`, `hashes[]` | File paths on `Event.predicateObjectPath`, not on `FileObject` itself; paths optional |
| IP | `NetFlowObject` | `localAddress`, `localPort`, `remoteAddress`, `remotePort` | Full IP:port endpoint pairs available |
| Server | `Host` (hostType=SERVER) | `hostType` enum (MOBILE/SERVER/DESKTOP/OTHER) | Server vs. desktop distinction available via `hostType` |

All six TraceGraph entity types are representable. This is the only dataset in the candidate set that supports the full entity vocabulary.

---

## 2. Edge / Relationship / Action Fields

The `Event` record is the primary edge source. `Event.type` is a 58-value enum providing typed action semantics — the closest direct equivalent to TraceGraph's `action` field:

| TraceGraph `action` | CDM EventType(s) |
|--------------------|-----------------|
| `login` | `EVENT_LOGIN`, `EVENT_LOGOUT` |
| `auth` | `EVENT_CHANGE_PRINCIPAL`, `EVENT_LOGIN` |
| `execute` | `EVENT_EXECUTE`, `EVENT_FORK`, `EVENT_CLONE`, `EVENT_CREATE_THREAD` |
| `connect` | `EVENT_CONNECT`, `EVENT_ACCEPT`, `EVENT_BIND`, `EVENT_SENDTO`, `EVENT_RECVFROM` |
| `access` | `EVENT_READ`, `EVENT_WRITE`, `EVENT_OPEN`, `EVENT_CLOSE`, `EVENT_MMAP`, `EVENT_RENAME`, `EVENT_UNLINK` |

`Event.subject` (UUID → `Subject`) provides the acting process. `Event.predicateObject` (UUID → `FileObject`, `NetFlowObject`, etc.) provides the target entity. `Event.timestampNanos` provides nanosecond-precision UTC timestamps.

---

## 3. Compatibility with TraceGraph Relationship Types

| Relationship Type | Status | Reason |
|-------------------|--------|--------|
| `LOGGED_INTO` | **Supported** | `EVENT_LOGIN` + `Subject.localPrincipal` → `Principal` (user) + `Host` via `TCCDMDatum.hostId` |
| `AUTHENTICATED_TO` | **Supported** | `EVENT_LOGIN` / `EVENT_CHANGE_PRINCIPAL` + cross-host `NetFlowObject` linkage |
| `EXECUTED` | **Supported** | `EVENT_EXECUTE` / `EVENT_FORK` with `Subject.parentSubject` for process lineage; `cmdLine` optional |
| `CONNECTED_TO` | **Supported** | `EVENT_CONNECT` / `EVENT_ACCEPT` + `NetFlowObject.localAddress` → `remoteAddress`; cross-host correlation via IP:port matching |
| `ACCESSED` | **Supported** | `EVENT_READ` / `EVENT_WRITE` / `EVENT_OPEN` + `Event.predicateObject` → `FileObject` + `Event.predicateObjectPath` for file path |

---

## 4. Compatibility with TraceGraph SecurityEvent Model

| SecurityEvent Field | Populatable? | CDM Source | Notes |
|--------------------|-------------|-----------|-------|
| `event_id` | Yes | `Event.uuid` | Globally unique UUID per event; deduplication by `Event.sequence` required for CADETS duplicates |
| `source_type` | Yes | `TCCDMDatum.source` (InstrumentationSource enum) | Distinguishes CADETS (FreeBSD), FiveDirections (Windows), etc. |
| `timestamp` | Yes | `Event.timestampNanos` | Nanosecond-precision UTC; gaps in CADETS stream (2019-05-08–09) |
| `event_type` | Yes | `Event.type` (EventType enum) | 58 values; maps cleanly to TraceGraph event categories |
| `action` | Yes | `Event.type` | Direct derivation from EventType enum — see §2 mapping |
| `user` | Partial | `Principal.username` or `Principal.userId` | `username` optional; `userId` (integer uid) always present when `Principal` record is emitted |
| `source_host` | Yes | `Host.hostName` via `TCCDMDatum.hostId` | Hostname string; `hostId` present on every record |
| `destination_host` | Partial | `NetFlowObject.remoteAddress` matched to `Host.hostIP[]` | Requires cross-record join; destination may be external (no `Host` record) |
| `source_ip` | Yes | `Host.hostIP[]` or `NetFlowObject.localAddress` | |
| `destination_ip` | Yes | `NetFlowObject.remoteAddress` | |
| `process` | Partial | `Subject.cmdLine` or `Subject.cid` | `cmdLine` optional; `cid` (pid) always present |
| `file` | Partial | `Event.predicateObjectPath` | Optional on `Event`; population rate stream-dependent |
| `severity` | No | — | No severity field in CDM; must derive from attack-window annotation |

All required fields (`event_id`, `source_type`, `timestamp`, `event_type`, `action`) are populatable. Optional fields are largely available with stream-dependent population rates.

---

## 5. Investigation Grouping

No embedded investigation or incident ID in CDM. Grouping is possible via:

- **`TCCDMDatum.hostId`** — groups all records by publishing host; attack-host identification comes from the ground-truth PDF.
- **`TCCDMDatum.sessionNumber`** — identifies a continuous publishing session (Kafka segment), not a security incident.
- **Time-window annotation from `Ground_Truth/TA51_Final_report_E5.pdf`** — the PDF describes attack scenarios with approximate host + time window boundaries. Mapping these to records requires aligning `Event.timestampNanos` against the narrative windows.

Known scenarios: Firefox Drakon (FiveDirections), Nginx Drakon (CADETS), Copykatz/Mimikatz credential harvesting from `lsass.exe`, BITS micro-APT, C2 communication, SSH/SCP lateral movement, kernel module insertion. These form natural investigation groupings but require manual annotation — no machine-readable label exists in the binary data.

---

## 6. Train/Test Leakage Considerations

- **No machine-readable labels:** All labelling requires time-window annotation from the PDF narrative. Any train/test split must be constructed manually; there is no off-the-shelf label column to misuse.
- **Host identity leakage:** CADETS (FreeBSD) and FiveDirections (Windows) streams are distinct hosts. If splits are made by stream, the model learns host-OS differences rather than attack behaviours. Splits should be made within streams by time window.
- **Duplicate CADETS records:** `Event.uuid` + `Event.sequence` must be used for deduplication before splitting; duplicates will inflate attack-window event counts.
- **Publishing gaps:** CADETS has a ~24-hour gap (2019-05-08 to 2019-05-09). A temporal split crossing this gap will have an artificial discontinuity — training and test windows should not straddle it.
- **Optional field availability:** `cmdLine`, `username`, and `predicateObjectPath` have stream-dependent population rates. A model trained on CADETS (which may populate these differently than FiveDirections) may not generalise across streams.
- **Only two streams locally:** THEIA, MARPLE, and ClearScope data are absent. Attack scenarios covered by those streams (SSH lateral movement, Firefox Drakon variant) are not available for training or testing.

---

## 7. Overall Graph Suitability

**High.**

DARPA TC E5 is the only candidate dataset that natively supports all six TraceGraph entity types and all five relationship types. The CDM schema provides typed events (58 EventType values), process lineage via `Subject.parentSubject`, file access paths via `Event.predicateObjectPath`, and full IP:port endpoint pairs via `NetFlowObject`. The `action` field can be directly derived from `Event.type` without inference. The primary constraints are operational: the binary Avro format requires a custom deserializer with `TCCDMDatum.avsc`, ground-truth labels are narrative-only (no machine-readable per-record label), optional CDM fields have stream-dependent population rates, and only two of the five TA1 streams are available locally. These are engineering challenges, not structural incompatibilities — the dataset is architecturally well-matched to TraceGraph's provenance graph model.
