# DARPA Transparent Computing Engagement 5 — Dataset Analysis

## 1. Dataset Overview

| Field | Value |
|-------|-------|
| **Name** | DARPA Transparent Computing Engagement 5 (TC E5) |
| **Version / release** | Engagement 5; CDM schema version 2.0 (CDM20.avdl, tag `0.1.2 — November 1, 2019`) |
| **Local source path** | `/home/kaustubh/Documents/Projects/TraceGraph/tracegraph/../datasets/Darpa/` |
| **Semantic classification** | **Raw event / provenance-oriented** — typed CDM security/system events, entity records, and provenance-related records suitable for constructing a directed provenance graph |
| **Streams present** | CADETS (FreeBSD, topic `ta1-cadets-1-e5-official-2`) and FiveDirections (Windows, topic `ta1-fivedirections-1-e5-official-1`) |
| **Total directory size** | ~14 GB (du-reported) |

---

## 2. File Format

- **Encoding:** Apache Avro binary (object container format), serialized using the CDM 2.0 schema.
- **Schema files:**
  - `../datasets/Darpa/Schema/TCCDMDatum.avsc` — generated Avro JSON schema (51,115 bytes); use this with any Avro reader.
  - `../datasets/Darpa/Schema/CDM20.avdl` — human-readable Avro IDL (53,312 bytes); reference this when interpreting field semantics.
- **Variants:** Each stream has raw `.bin` files and gzip-recompressed `.bin.gz` companions. The `.bin.gz` files are recompressed Avro containers — they must be decompressed before being passed to an Avro reader; they are not natively gzip-wrapped Avro.
- **Tooling required:** An Avro reader that accepts `TCCDMDatum.avsc`. The bundled `ta3-java-consumer` tooling (referenced in the dataset README) is the reference implementation. Python's `fastavro` library also works if given the resolved schema.
- **Record counts:** Cannot be determined without full Avro deserialization. No manifest or index file documents record counts. Binary format precludes line-counting. Estimation requires sampling the binary stream.

---

## 3. Dataset Structure

```
../datasets/Darpa/
├── Data/
│   ├── cadets/
│   │   ├── ta1-cadets-1-e5-official-2.bin.1     2,236,081,836 B  (2.08 GB)  2019-05-21
│   │   ├── ta1-cadets-1-e5-official-2.bin.1.gz    296,577,011 B  (283 MB)
│   │   ├── ta1-cadets-1-e5-official-2.bin.2     2,192,271,963 B  (2.04 GB)
│   │   ├── ta1-cadets-1-e5-official-2.bin.2.gz    289,019,603 B  (276 MB)
│   │   ├── ta1-cadets-1-e5-official-2.bin.3     2,180,081,464 B  (2.03 GB)
│   │   └── ta1-cadets-1-e5-official-2.bin.3.gz    278,769,830 B  (266 MB)
│   └── fivedirections/
│       ├── ta1-fivedirections-1-e5-official-1.bin.1     1,965,575,203 B  (1.83 GB)  2019-05-21
│       ├── ta1-fivedirections-1-e5-official-1.bin.1.gz    305,438,193 B  (291 MB)   2019-11-24
│       ├── ta1-fivedirections-1-e5-official-1.bin.2     2,016,669,976 B  (1.88 GB)
│       ├── ta1-fivedirections-1-e5-official-1.bin.2.gz    309,025,261 B  (295 MB)
│       ├── ta1-fivedirections-1-e5-official-1.bin.3     2,020,513,451 B  (1.88 GB)
│       └── ta1-fivedirections-1-e5-official-1.bin.3.gz    308,754,439 B  (295 MB)
├── Ground_Truth/
│   ├── TA51_Final_report_E5.pdf     ← attack scenario narratives (primary ground truth)
│   └── TA51_Final_report_E5.docx
├── Schema/
│   ├── CDM20.avdl         53,312 B — human-readable IDL
│   ├── TCCDMDatum.avsc    51,115 B — generated Avro schema
│   └── cdm.pdf
├── Engagement-5-Event-Log.md        ← operational issues log
├── Engagement-5-Local-Analysis.md   ← pre-existing detailed local analysis
├── README.md
└── README.pdf
```

| Partition | Raw .bin (3 files) | .gz (3 files) | du total |
|-----------|-------------------|---------------|----------|
| CADETS | ~6.3 GB | ~825 MB | 7.0 GB |
| FiveDirections | ~5.6 GB | ~913 MB | 6.5 GB |
| **Total** | **~11.9 GB** | **~1.7 GB** | **14 GB** |

---

## 4. Record / Event Count

**Unknown.** Record counts cannot be determined without deserializing the Avro binary streams. No manifest, index, or count file exists locally. The binary format precludes line-counting or sampling without an Avro deserializer and the `TCCDMDatum.avsc` schema. The `EndMarker` record type in CDM does include per-type record counts for a session, but accessing it requires reading to the end of each binary stream with a fully resolved schema.

---

## 5. Schema

### Top-level datum: `TCCDMDatum`

Every Avro record decoded from the `.bin` files is a `TCCDMDatum`. It wraps one of the CDM node/edge types.

| Field | Type | Description |
|-------|------|-------------|
| `datum` | union (see record types below) | The actual CDM record |
| `CDMVersion` | string | Schema version string (e.g., `"20"`) |
| `type` | RecordType enum | Discriminates the union without full decode |
| `hostId` | UUID (fixed 16) | UUID of the host that published this record |
| `sessionNumber` | int | Kafka session/segment number |
| `source` | InstrumentationSource enum | Telemetry source (see enum values below) |

### CDM Record Types (datum union members)

| Record type | Role | Key fields |
|-------------|------|------------|
| `Host` | Machine/node entity | `uuid`, `hostName`, `osDetails`, `hostType` (MOBILE/SERVER/DESKTOP/OTHER), `interfaces[]`, `hostIP[]`, `ta1Version` |
| `Principal` | OS user account | `uuid`, `type`, `userId` (integer OS uid), `username` (optional string), `groupIds[]`, `properties` |
| `Subject` | Execution context (process/thread/unit) | `uuid`, `type` (SubjectType), `cid` (OS pid/tid), `parentSubject` (optional UUID), `localPrincipal` (optional UUID), `startTimestampNanos`, `cmdLine` (optional), `privilegeLevel` (optional), `importedLibraries[]`, `exportedLibraries[]` |
| `Event` | Typed security/system event — **primary edge record** | `uuid`, `sequence`, `type` (EventType enum), `threadId`, `subject` (UUID), `predicateObject` (optional UUID), `predicateObjectPath` (optional string), `predicateObject2` (optional UUID), `predicateObject2Path` (optional string), `timestampNanos`, `parameters`, `location`, `size`, `programPoint`, `properties` |
| `FileObject` | File entity | `uuid`, `type` (FileObjectType), `fileDescriptor`, `localPrincipal`, `size`, `peInfo`, `hashes[]` |
| `NetFlowObject` | Network flow endpoint pair | `uuid`, `localAddress`, `localPort`, `remoteAddress`, `remotePort`, `ipProtocol`, `fileDescriptor`, `initTcpSeqNum` (optional — cross-host tracking) |
| `IpcObject` | IPC channel (pipe, socket pair) | `uuid`, `type` (IpcObjectType), `uuid1`, `uuid2`, `fileDescriptor` |
| `MemoryObject` | Memory region | `uuid`, `memoryAddress`, `pageNumber`, `pageOffset`, `size` |
| `RegistryKeyObject` | Windows registry key | `uuid`, `key`, `value`, `size` |
| `PacketSocketObject` | Packet socket | `uuid`, `protocol`, `ifIndex`, `hatype`, `pkttype`, `addr` |
| `SrcSinkObject` | Abstract source/sink | `uuid`, `type` (SrcSinkType) |
| `ProvenanceTagNode` | Data-flow provenance tag | `tagId`, `flowObject`, `subject`, `prevTagId`, `opcode`, `tagIds[]`, `itag`, `ctag` |
| `ProvenanceAssertion` | Asserts data provenance | `asserter`, `sources[]` |
| `UnitDependency` | Unit-level dependency edge | — |
| `TimeMarker` | Session timing marker | — |
| `EndMarker` | Stream end marker with per-type record counts | — |

### EventType Enum (58 values)

```
EVENT_ACCEPT, EVENT_ADD_OBJECT_ATTRIBUTE, EVENT_BIND, EVENT_BLIND,
EVENT_BOOT, EVENT_CHANGE_PRINCIPAL, EVENT_CHECK_FILE_ATTRIBUTES,
EVENT_CLONE, EVENT_CLOSE, EVENT_CONNECT, EVENT_CORRELATION,
EVENT_CREATE_OBJECT, EVENT_CREATE_THREAD, EVENT_DUP, EVENT_EXECUTE,
EVENT_EXIT, EVENT_FLOWS_TO, EVENT_FCNTL, EVENT_FORK, EVENT_LINK,
EVENT_LOADLIBRARY, EVENT_LOGCLEAR, EVENT_LOGIN, EVENT_LOGOUT,
EVENT_LSEEK, EVENT_MMAP, EVENT_MODIFY_FILE_ATTRIBUTES,
EVENT_MODIFY_PROCESS, EVENT_MOUNT, EVENT_MPROTECT, EVENT_OPEN,
EVENT_OTHER, EVENT_READ, EVENT_READ_SOCKET_PARAMS, EVENT_RECVFROM,
EVENT_RECVMSG, EVENT_RENAME, EVENT_SENDTO, EVENT_SENDMSG,
EVENT_SERVICEINSTALL, EVENT_SHM, EVENT_SIGNAL, EVENT_STARTSERVICE,
EVENT_TRUNCATE, EVENT_UMOUNT, EVENT_UNIT, EVENT_UNLINK, EVENT_UPDATE,
EVENT_WAIT, EVENT_WRITE, EVENT_WRITE_SOCKET_PARAMS, EVENT_TEE,
EVENT_SPLICE, EVENT_VMSPLICE, EVENT_INIT_MODULE, EVENT_FINIT_MODULE
```

### SubjectType Enum

```
SUBJECT_PROCESS, SUBJECT_THREAD, SUBJECT_UNIT, SUBJECT_BASIC_BLOCK
```

### InstrumentationSource Enum (relevant values)

```
SOURCE_FREEBSD_DTRACE_CADETS, SOURCE_FREEBSD_TESLA_CADETS,
SOURCE_FREEBSD_LOOM_CADETS, SOURCE_FREEBSD_MACIF_CADETS,   ← CADETS stream
SOURCE_WINDOWS_FIVEDIRECTIONS,                              ← FiveDirections stream
SOURCE_WINDOWS_MARPLE,
SOURCE_LINUX_THEIA,
SOURCE_LINUX_AUDIT, SOURCE_LINUX_PROC, SOURCE_LINUX_BEEP
```

---

## 6. Timestamp Fields

| Field | Record type | Format | Timezone | Notes |
|-------|-------------|--------|----------|-------|
| `Event.timestampNanos` | `Event` | int64, nanoseconds since Unix epoch | UTC | Primary event timestamp |
| `Subject.startTimestampNanos` | `Subject` | int64, nanoseconds since Unix epoch | UTC | Optional; process start time |

**Caveats:**
- Nanosecond precision but actual clock resolution depends on the host OS and instrumentation layer.
- Publishing gaps and host restarts (see §18) can produce non-monotonic or missing timestamp ranges.
- Duplicate records on the CADETS stream before the topic rename introduce duplicate timestamps.

---

## 7. User Fields

| Field | Record type | Description |
|-------|-------------|-------------|
| `Principal.userId` | `Principal` | Integer OS uid |
| `Principal.username` | `Principal` | Optional string username (not guaranteed populated) |
| `Subject.localPrincipal` | `Subject` | UUID reference to the owning `Principal` record |

No anonymisation — real OS uid integers and usernames (where populated) appear in the data.

---

## 8. Host / Machine Fields

| Field | Record type | Description |
|-------|-------------|-------------|
| `Host.hostName` | `Host` | Hostname string |
| `Host.hostIP[]` | `Host` | Array of IP address strings |
| `TCCDMDatum.hostId` | Every record | UUID identifying the publishing host; present on all records |

`hostId` is the most reliable cross-record host link because `Host` records may not be emitted for every session.

---

## 9. Source and Destination IP Fields

| Field | Record type | Description |
|-------|-------------|-------------|
| `NetFlowObject.localAddress` | `NetFlowObject` | Local IP address (string) |
| `NetFlowObject.localPort` | `NetFlowObject` | Local port (int) |
| `NetFlowObject.remoteAddress` | `NetFlowObject` | Remote IP address (string) |
| `NetFlowObject.remotePort` | `NetFlowObject` | Remote port (int) |
| `Host.hostIP[]` | `Host` | IP(s) assigned to the host |

Cross-host flow correlation requires matching `NetFlowObject.localAddress:localPort` on one host against `remoteAddress:remotePort` on another. `initTcpSeqNum` is available on `NetFlowObject` for more precise TCP-level correlation but is optional and not consistently populated.

---

## 10. Process Fields

| Field | Record type | Description |
|-------|-------------|-------------|
| `Subject.cid` | `Subject` | OS process ID (pid) or thread ID (tid) |
| `Subject.type` | `Subject` | SUBJECT_PROCESS / SUBJECT_THREAD / SUBJECT_UNIT / SUBJECT_BASIC_BLOCK |
| `Subject.parentSubject` | `Subject` | Optional UUID of parent `Subject` — enables process tree construction |
| `Subject.cmdLine` | `Subject` | Optional command-line string |
| `Subject.privilegeLevel` | `Subject` | Optional privilege level |
| `Subject.importedLibraries[]` | `Subject` | Optional loaded library list |
| `Subject.startTimestampNanos` | `Subject` | Optional process start timestamp |

`parentSubject` is the primary field for building process lineage trees. It is optional and may be absent, especially for processes that were already running when instrumentation started.

---

## 11. File Fields

| Field | Record type | Description |
|-------|-------------|-------------|
| `FileObject.uuid` | `FileObject` | File entity UUID |
| `FileObject.type` | `FileObject` | FileObjectType enum (FILE_OBJECT_FILE, FILE_OBJECT_DIR, FILE_OBJECT_SOCKET, etc.) |
| `FileObject.size` | `FileObject` | Optional file size |
| `FileObject.hashes[]` | `FileObject` | Optional cryptographic hashes |
| `FileObject.peInfo` | `FileObject` | Optional PE header info (Windows) |
| `Event.predicateObjectPath` | `Event` | Optional file path string on the event accessing the file |
| `Event.predicateObject2Path` | `Event` | Optional secondary file path (e.g., rename target) |

**Important:** File paths are on `Event` records, not on `FileObject` records. A given `FileObject` UUID may be accessed with different paths across events (e.g., hardlinks, bind mounts). Paths are optional and not guaranteed populated.

---

## 12. Event Type / Action Fields

`Event.type` — EventType enum (58 values). This is the primary semantic action field.

Semantically important groupings:

| Category | Event types |
|----------|-------------|
| Process lifecycle | EVENT_FORK, EVENT_CLONE, EVENT_EXECUTE, EVENT_EXIT, EVENT_CREATE_THREAD |
| File I/O | EVENT_OPEN, EVENT_READ, EVENT_WRITE, EVENT_CLOSE, EVENT_MMAP, EVENT_TRUNCATE, EVENT_RENAME, EVENT_LINK, EVENT_UNLINK |
| Network | EVENT_CONNECT, EVENT_ACCEPT, EVENT_BIND, EVENT_SENDTO, EVENT_RECVFROM, EVENT_SENDMSG, EVENT_RECVMSG, EVENT_READ_SOCKET_PARAMS, EVENT_WRITE_SOCKET_PARAMS |
| IPC / memory | EVENT_SHM, EVENT_MPROTECT, EVENT_DUP, EVENT_FCNTL, EVENT_LSEEK, EVENT_TEE, EVENT_SPLICE, EVENT_VMSPLICE |
| Authentication | EVENT_LOGIN, EVENT_LOGOUT, EVENT_CHANGE_PRINCIPAL |
| Module / service | EVENT_LOADLIBRARY, EVENT_INIT_MODULE, EVENT_FINIT_MODULE, EVENT_SERVICEINSTALL, EVENT_STARTSERVICE |
| Provenance | EVENT_FLOWS_TO, EVENT_CORRELATION |
| Other | EVENT_OTHER, EVENT_BOOT, EVENT_MOUNT, EVENT_UMOUNT, EVENT_SIGNAL, EVENT_WAIT, EVENT_UNIT, EVENT_UPDATE, EVENT_MODIFY_PROCESS, EVENT_MODIFY_FILE_ATTRIBUTES, EVENT_CHECK_FILE_ATTRIBUTES, EVENT_ADD_OBJECT_ATTRIBUTE, EVENT_LOGCLEAR, EVENT_BLIND, EVENT_CREATE_OBJECT |

---

## 13. Label Fields

**No machine-readable per-record attack label exists in the CDM binary data.**

Ground truth is provided exclusively as a narrative document:
- `../datasets/Darpa/Ground_Truth/TA51_Final_report_E5.pdf` — TA5.1 Engagement 5 final report.
- Describes attack scenarios by: host identity, approximate time window, attacker actions, and affected software/processes.
- No mapping file from `Event.uuid` or `Subject.uuid` to attack category exists.

Labelling any CDM record as malicious requires aligning the record's `hostId`, `timestampNanos`, and event semantics against the narrative time windows in the PDF.

---

## 14. Incident, Session, or Scenario ID Fields

| Field | Description |
|-------|-------------|
| `TCCDMDatum.sessionNumber` | Kafka session/segment number assigned by the publisher — identifies a continuous publishing session, not a security incident |
| `TCCDMDatum.hostId` | Groups records by publishing host |

No incident or investigation ID is embedded. The five TA1 performers (CADETS, FiveDirections, THEIA, MARPLE, ClearScope) are identified by stream topic name, not by a field inside the records.

---

## 15. Attack Category Annotations

**None embedded in CDM.** Attack categories must be derived manually from the ground-truth PDF.

Known attack scenarios from `TA51_Final_report_E5.pdf`:

| Performer / host | Attack scenario |
|-----------------|-----------------|
| FiveDirections | Firefox Drakon attack; BITS micro-APT; privilege escalation; Copykatz/Mimikatz credential harvesting from `lsass.exe`; C2 communication |
| CADETS | Nginx Drakon attack (May 16); Nginx Drakon attack (May 17) |
| THEIA | SSH/SCP lateral movement; kernel module insertion; `/etc/shadow` reads |
| MARPLE | Firefox Drakon (significant telemetry gaps — low reliability) |
| ClearScope | Android APK attacks (AppStarter, Lockwatch) — devices stopped publishing |

Attack categories present: APT lateral movement, credential harvesting, C2 communication, kernel module rootkit, web server exploitation, browser exploitation.

---

## 16. Class Balance

Not directly applicable — no per-record binary label.

Balance is entirely dependent on how an analyst defines the attack window from the ground-truth PDF. No quantitative label distribution can be computed without (a) full Avro deserialization and (b) manual or automated time-window annotation against the narrative PDF.

---

## 17. Dataset Semantics and Graph Constructibility

### Semantic classification
**Raw event / provenance-oriented.** CDM provides typed entities, events, objects, and provenance relationships that support construction of a typed provenance graph. The raw Avro stream is not a ready-made graph — it must be deserialized, entity records assembled into nodes, and Event records resolved into typed edges before a graph representation is available.

### Node types constructible from CDM

| CDM record | Graph node type | Primary identifier |
|------------|----------------|--------------------|
| `Host` | Machine | `uuid` |
| `Principal` | OS user | `uuid` |
| `Subject` (PROCESS) | Process | `uuid`; linked to host via `hostId`, to user via `localPrincipal` |
| `FileObject` | File | `uuid` |
| `NetFlowObject` | Network endpoint pair | `uuid` |
| `IpcObject` | IPC channel | `uuid` |
| `MemoryObject` | Memory region | `uuid` |
| `RegistryKeyObject` | Registry key (Windows) | `uuid` |

### Edge types constructible from CDM

| Source → destination | Edge type | CDM basis |
|---------------------|-----------|-----------|
| Subject → FileObject | File read/write/execute/open/close | `Event.type` ∈ FILE_* + `predicateObject` UUID |
| Subject → NetFlowObject | Network send/recv/connect | `Event.type` ∈ NETWORK_* |
| Subject → Subject | Process fork/exec/clone | `Event.type` ∈ EVENT_FORK/CLONE/EXECUTE; also `Subject.parentSubject` |
| Subject → IpcObject | IPC operations | `Event.type` ∈ IPC_* |
| Subject → MemoryObject | Memory map/protect | `Event.type` ∈ EVENT_MMAP/MPROTECT |
| Subject → RegistryKeyObject | Registry read/write | `Event.type` ∈ EVENT_READ/EVENT_WRITE on registry objects |
| Provenance | Data-flow tag propagation | `ProvenanceTagNode`, `EVENT_FLOWS_TO` |
| Process lineage | Parent → child process | `Subject.parentSubject` UUID |

### Limitations

- **Field population is not guaranteed.** Many fields are optional (`cmdLine`, `predicateObjectPath`, `parentSubject`). Actual population rates are unknown without full deserialization.
- **No automatic attack labelling.** UUID-to-attack-label mapping must be constructed manually from the ground-truth PDF.
- **Cross-host process correlation** requires matching `NetFlowObject` endpoints (local ↔ remote), and `initTcpSeqNum` (for TCP-level precision) is optional.
- **Record counts unknown** — total graph scale cannot be estimated without deserializing the binary streams.
- **Only two performer streams present locally** (CADETS, FiveDirections). THEIA, MARPLE, and ClearScope data are not in the local `Data/` directory.

---

## 18. Key Limitations and Data Quality Notes

| Issue | Detail |
|-------|--------|
| **Duplicate CADETS records** | Topic `ta1-cadets-1-e5-official-1` produced duplicates on 2019-05-07. The local files use the renamed topic `ta1-cadets-1-e5-official-2` which was the clean stream — but duplicate records from before the rename may still be present in the binary files. Deduplication by `Event.uuid` and `Event.sequence` is required. |
| **CADETS publishing gaps** | Large gaps reported 2019-05-08 to 2019-05-09 due to translator outages. Absence of records in this window does not imply no activity. |
| **FiveDirections host restarts** | Hosts were shut down and rebooted multiple times. Process UUID continuity is broken across restarts. `Subject.parentSubject` links will be severed. |
| **MARPLE telemetry quality** | Only UI events were frequently published; process-level system-call telemetry is largely absent. Do not use MARPLE data for process lineage. |
| **THEIA fine-grained recording disabled** | Fine-grained (syscall-level) recording was disabled during portions of the engagement. Gaps are significant. |
| **ClearScope devices stopped publishing** | Android devices were removed during the engagement. ClearScope data is absent from local files. |
| **Optional fields unpopulated** | `cmdLine`, `username`, `predicateObjectPath`, `parentSubject` are optional. Actual population rates are stream- and performer-dependent and unknown without sampling. |
| **No per-record attack labels** | All labelling requires manual alignment with the narrative PDF. There is no structured, machine-readable ground-truth mapping. |
| **Binary format** | Cannot inspect, line-count, or grep the data without an Avro deserializer and the `TCCDMDatum.avsc` schema. |
| **Access restrictions** | DARPA TC data requires programme affiliation. Do not redistribute. |

## 19. Ground Truth Assessment

### 19.1 Ground Truth Availability

Partial — narrative only. Ground truth is provided as a PDF narrative document (`Ground_Truth/TA51_Final_report_E5.pdf`). No machine-readable per-record label exists in the CDM binary data. Labelling any CDM record requires manual or automated alignment of the record's `hostId`, `timestampNanos`, and event semantics against attack time windows described in the PDF.

### 19.2 Definition of Positive

A CDM `Event` record (or sequence of records) that corresponds to an attacker action described in the TA5.1 engagement report — e.g., Firefox Drakon exploit, Mimikatz/Copykatz credential harvesting from `lsass.exe`, BITS micro-APT, C2 communication, Nginx web server exploit, SSH/SCP lateral movement, kernel module insertion.

### 19.3 Definition of Negative

Any CDM `Event` record that falls outside the attack time windows and attack-involved hosts described in the PDF. Because no binary label exists, "negative" is operationally defined as "not within a documented attack window on a documented attack host."

### 19.4 Class Balance Summary

| Class | Count | Percentage |
|-------|-------|-----------|
| Attack (positive) | Unknown — binary Avro format, no deserialization performed | — |
| Benign (negative) | Unknown — binary Avro format, no deserialization performed | — |
| **Total** | **Unknown** | — |

Not directly computable. Total record count is unknown without full Avro deserialization. Attack-involved records are a small fraction of the stream — the vast majority of CDM events are benign system activity. No quantitative ratio can be stated without full deserialization and manual time-window annotation from the ground-truth PDF.

### 19.5 Label Granularity

Per-scenario / per-host. The PDF describes attack scenarios at the level of "host X was compromised during time window T1–T2 using technique Y." No per-event binary label exists in the data. Deriving per-event labels requires constructing temporal and host-based windows from the narrative document.

### 19.6 Known Labelling Issues and Controversies

| Issue | Detail |
|-------|--------|
| **No structured, machine-readable ground truth** | All labelling requires manual effort against a PDF narrative. There is no structured mapping from `Event.uuid` or `Subject.uuid` to attack category. |
| **Controlled lab environment** | DARPA TC datasets have been criticised for being generated in a controlled lab, making attack patterns stereotyped and easier to detect relative to real APT activity (Alsaheel et al., USENIX Security 2021; Milajerdi et al., IEEE S&P 2019). |
| **Incomplete stream coverage** | Only CADETS (FreeBSD) and FiveDirections (Windows) streams are present locally. THEIA, MARPLE, and ClearScope data are absent, limiting the attack scenario coverage available for labelling. |
| **Data quality issues in present streams** | CADETS has duplicate records and large publishing gaps (2019-05-08 to 2019-05-09). FiveDirections has host restarts that sever process UUID continuity. Both issues complicate reliable per-record labelling. |
| **Poor MARPLE telemetry quality** | MARPLE published UI events only — syscall-level data is largely absent, making process-lineage-based labelling impossible for that stream. |
| **Binary Avro format** | Ground truth alignment cannot be performed with standard CSV tooling. Full deserialization with the `TCCDMDatum.avsc` schema is required before any labelling step. |
| **Access restriction** | DARPA TC data requires programme affiliation. Data cannot be redistributed, limiting reproducibility. |
