# LANL Unified Host and Network Dataset — Dataset Analysis

## 1. Dataset Overview

| Field | Value |
|-------|-------|
| **Name** | Los Alamos National Laboratory (LANL) Unified Host and Network Dataset |
| **Version / release** | "LANL Cyber1" / 2017 release; no version file present locally |
| **Local source path** | `/home/kaustubh/Documents/Projects/TraceGraph/tracegraph/../datasets/LANL_Cybersecurity_Dataset/` |
| **Semantic classification** | **Raw event / log-oriented** — individual discrete events (authentication attempts, DNS lookups, network connections, process start/stop) timestamped in relative seconds |
| **Coverage** | 58 consecutive days of internal enterprise network activity with embedded red-team events |
| **Total compressed size** | ~10.7 GB (du reports 11 GB) |

---

## 2. File Format

- **Encoding:** Gzip-compressed plain text (CSV without header row). Fields are comma-separated.
- **Header rows:** None in any file. Field order is defined by the paper (Turcotte et al., 2018 DSN Workshop).
- **Decompression:** Standard `gzip -d` or streaming via `zcat` / Python `gzip` module. Each file decompresses to a flat CSV.
- **Record delimiters:** One event per line.

---

## 3. Dataset Structure

```
../datasets/LANL_Cybersecurity_Dataset/
├── auth.txt.gz     7,626,505,167 B  (7.1 GB compressed)
├── dns.txt.gz        185,104,948 B  (177 MB compressed)
├── flows.txt.gz    1,083,479,100 B  (1.03 GB compressed)
├── proc.txt.gz     2,358,611,883 B  (2.2 GB compressed)
└── redteam.txt.gz          4,858 B  (4.8 KB compressed)
```

| File | Compressed size | Record count |
|------|----------------|--------------|
| auth.txt.gz | 7.1 GB | 1,051,430,459 (exact) |
| dns.txt.gz | 177 MB | 40,821,591 (exact) |
| flows.txt.gz | 1.03 GB | 129,977,412 (exact) |
| proc.txt.gz | 2.2 GB | 426,045,096 (exact) |
| redteam.txt.gz | 4.8 KB | 749 (exact) |

---

## 4. Record / Event Count

| File | Count | Method |
|------|-------|--------|
| `dns.txt.gz` | **40,821,591** | Full decompression + line count |
| `flows.txt.gz` | **129,977,412** | Full decompression + line count |
| `redteam.txt.gz` | **749** | Full decompression + line count (`zcat redteam.txt.gz | wc -l`) |
| `auth.txt.gz` | **1,051,430,459** | Full decompression + line count (`zcat auth.txt.gz | wc -l`) |
| `proc.txt.gz` | **426,045,096** | Full decompression + line count (`zcat proc.txt.gz | wc -l`) |

`auth.txt.gz` is the dominant file by volume with 1,051,430,459 records. The combined total across all five files is **1,648,275,307** records (verified: 1,051,430,459 + 40,821,591 + 129,977,412 + 426,045,096 + 749).

---

## 5. Schema

No file has a header row. Field order is fixed per file.

### auth.txt.gz (9 fields)

| Position | Field name | Type | Example | Description |
|----------|-----------|------|---------|-------------|
| 1 | `time` | integer | `1` | Seconds since dataset start epoch (relative) |
| 2 | `source_user@domain` | string | `ANONYMOUS LOGON@C586` | Anonymised source user identity |
| 3 | `destination_user@domain` | string | `ANONYMOUS LOGON@C586` | Anonymised destination user identity |
| 4 | `source_computer` | string | `C1250` | Anonymised source computer name |
| 5 | `destination_computer` | string | `C586` | Anonymised destination computer name |
| 6 | `auth_type` | string | `NTLM` | Authentication protocol: NTLM, Kerberos, Negotiate, or `?` |
| 7 | `logon_type` | string | `Network` | Logon session type: Network, Interactive, Service, Batch, etc. |
| 8 | `auth_orientation` | string | `LogOn` | Event orientation: LogOn, LogOff, AuthMap, TGT, TGS |
| 9 | `success` | string | `Success` | Outcome: `Success` or `Fail` |

Sample: `1,ANONYMOUS LOGON@C586,ANONYMOUS LOGON@C586,C1250,C586,NTLM,Network,LogOn,Success`

### dns.txt.gz (3 fields)

| Position | Field name | Type | Example | Description |
|----------|-----------|------|---------|-------------|
| 1 | `time` | integer | `2` | Seconds since dataset start epoch |
| 2 | `computer` | string | `C4653` | Anonymised computer initiating DNS lookup |
| 3 | `resolved_computer` | string | `C5030` | Anonymised resolved computer/hostname |

Sample: `2,C4653,C5030`

### flows.txt.gz (9 fields)

| Position | Field name | Type | Example | Description |
|----------|-----------|------|---------|-------------|
| 1 | `time` | integer | `1` | Seconds since dataset start epoch |
| 2 | `duration` | integer | `0` | Flow duration in seconds |
| 3 | `source_computer` | string | `C1065` | Anonymised source computer |
| 4 | `source_port` | string | `389` | Source port (integer or anonymised name e.g., `N10451`) |
| 5 | `destination_computer` | string | `C3799` | Anonymised destination computer |
| 6 | `destination_port` | string | `N10451` | Destination port (integer or anonymised name) |
| 7 | `protocol` | integer | `6` | IP protocol number (6=TCP, 17=UDP) |
| 8 | `packet_count` | integer | `10` | Number of packets |
| 9 | `byte_count` | integer | `5323` | Total bytes transferred |

Sample: `1,0,C1065,389,C3799,N10451,6,10,5323`

**Note on ports:** Well-known ports appear as integers; ports that could re-identify services appear as anonymised names (e.g., `N10451`).

### proc.txt.gz (5 fields)

| Position | Field name | Type | Example | Description |
|----------|-----------|------|---------|-------------|
| 1 | `time` | integer | `1` | Seconds since dataset start epoch |
| 2 | `user@domain` | string | `C1$@DOM1` | Anonymised user running the process |
| 3 | `computer` | string | `C1` | Anonymised computer |
| 4 | `process_name` | string | `P16` | Anonymised process name |
| 5 | `start_or_end` | string | `Start` | Event type: `Start` or `End` |

Sample: `1,C1$@DOM1,C1,P16,Start`

### redteam.txt.gz (4 fields)

| Position | Field name | Type | Example | Description |
|----------|-----------|------|---------|-------------|
| 1 | `time` | integer | `150885` | Seconds since dataset start epoch |
| 2 | `source_user@domain` | string | `U620@DOM1` | Anonymised source user |
| 3 | `source_computer` | string | `C17693` | Anonymised source computer |
| 4 | `destination_computer` | string | `C1003` | Anonymised destination computer |

Sample: `150885,U620@DOM1,C17693,C1003`

These 749 records are the labelled red-team authentication events. They match the schema of `auth.txt.gz` (minus destination user and auth fields) and must be joined by `(time, source_computer, destination_computer)` against `auth.txt.gz` to retrieve full authentication details.

---

## 6. Timestamp Fields

| Field | File(s) | Format | Timezone | Range |
|-------|---------|--------|----------|-------|
| `time` | auth, dns, flows, proc, redteam | Integer — seconds since dataset start epoch (relative, not absolute Unix epoch) | UTC (relative) | auth/dns/flows/proc: 1 to ~5,011,200 (58 days); redteam: 150,885 to 2,557,047 |

**Caveats:**
- `time` is a **relative counter**, not an absolute Unix timestamp. The dataset start date is not published in the local files. Published papers reference the dataset as spanning 2010 (approximate), but the exact epoch is not documented locally.
- No sub-second precision. Granularity is 1 second.
- Simultaneous events at the same second are indistinguishable in ordering.

---

## 7. User Fields

| Field | File(s) | Format | Notes |
|-------|---------|--------|-------|
| `source_user@domain` | auth, redteam | `U<N>@DOM1` or `ANONYMOUS LOGON@<computer>` or `SYSTEM@<computer>` | **Fully anonymised** — no real usernames |
| `destination_user@domain` | auth | Same anonymised format | **Fully anonymised** |
| `user@domain` | proc | `C<N>$@DOM1` (machine accounts) or `U<N>@DOM1` | **Fully anonymised** |

All user identities are anonymised. `U<N>@DOM1` format uses sequential integer IDs. Machine accounts follow `C<N>$@DOM1`. No real usernames, display names, or email addresses appear anywhere.

---

## 8. Host / Machine Fields

| Field | File(s) | Format | Notes |
|-------|---------|--------|-------|
| `source_computer` | auth, flows, redteam | `C<N>` | **Fully anonymised** — sequential integer IDs |
| `destination_computer` | auth, flows, redteam | `C<N>` | **Fully anonymised** |
| `computer` | dns, proc | `C<N>` | **Fully anonymised** |
| `resolved_computer` | dns | `C<N>` | **Fully anonymised** |

No real hostnames, FQDNs, or IP addresses appear. All computer names use the `C<N>` scheme. No mapping from `C<N>` to real hostnames is available.

---

## 9. Source and Destination IP Fields

**None.** No IP addresses exist anywhere in the dataset.

`source_computer` / `destination_computer` in `flows.txt.gz` use anonymised computer names (`C<N>`), not IP addresses. Ports in flows are present but partially anonymised (`N<N>` format for some values).

This is a significant structural gap for IP-based correlation or for constructing IP-level network flow graphs.

---

## 10. Process Fields

| Field | File | Description |
|-------|------|-------------|
| `process_name` | proc | Anonymised process name (`P<N>` format, e.g., `P16`, `P4`) |
| `start_or_end` | proc | `Start` or `End` only |
| `user@domain` | proc | User running the process (anonymised) |
| `computer` | proc | Host where the process runs (anonymised) |

**No real process names, executable paths, command lines, PIDs, or parent-process IDs.** The `P<N>` identifiers are anonymised and carry no semantic meaning. Process genealogy (parent-child relationships) cannot be reconstructed. No process-to-file operations exist.

---

## 11. File Fields

**None.** No file-level events, file paths, file names, file read/write operations, or file metadata appear in any file. This is a fundamental gap relative to process-level telemetry datasets (e.g., DARPA TC CDM).

---

## 12. Event Type / Action Fields

| File | Action field(s) | Values |
|------|----------------|--------|
| auth | `auth_orientation` | LogOn, LogOff, AuthMap, TGT, TGS |
| auth | `logon_type` | Network, Interactive, Service, Batch, Unlock, RemoteInteractive, etc. |
| auth | `success` | Success, Fail |
| proc | `start_or_end` | Start, End |
| dns | (none explicit) | Implicit: DNS lookup (one record = one query) |
| flows | (none explicit) | Implicit: completed network connection |

No rich action semantics beyond authentication orientation, process start/stop, and implicit connection types. `auth_type` (NTLM/Kerberos/Negotiate) provides additional context for auth events.

---

## 13. Label Fields

| Field | File | Description |
|-------|------|-------------|
| (none) | auth, dns, flows, proc | No per-record label |
| (all fields = label context) | redteam | 749 records identifying red-team authentication events by time + computer pair |

Labels exist **only** for a subset of authentication events. `dns.txt.gz`, `flows.txt.gz`, and `proc.txt.gz` have no labels at all. Labelling requires joining redteam records against `auth.txt.gz` on `(time, source_computer, destination_computer)`.

---

## 14. Incident, Session, or Scenario ID Fields

**None.** No session ID, investigation ID, incident ID, or attack campaign identifier exists in any file. Events can only be grouped by `(computer, time)` proximity. The dataset does not document which computers were compromised, only the red-team auth events.

---

## 15. Attack Category Annotations

**None.** The `redteam.txt.gz` file provides binary attack/benign labels for authentication events only — no attack technique or category classification (e.g., MITRE ATT&CK, lateral movement, credential access) is provided.

Red-team events span `time=150,885` to `time=2,557,047` (~29.6 days into the dataset window), indicating attacks occur across a wide temporal range rather than being confined to a single campaign window.

---

## 16. Class Balance

### auth.txt.gz vs redteam.txt.gz

| Class | Count | Notes |
|-------|-------|-------|
| Red-team (attack) auth events | **749** | Exact count (`zcat redteam.txt.gz | wc -l`) |
| Total auth events | **1,051,430,459** | Exact count (`zcat auth.txt.gz | wc -l`) |
| Attack rate | **~0.000071%** (7.1 × 10⁻⁵ %) | 749 / 1,051,430,459 |

**Extreme class imbalance.** The 749 red-team events represent ~0.000071% of the 1,051,430,459 total authentication records.

### dns.txt.gz, flows.txt.gz, proc.txt.gz

| File | Total records | Attack-labelled records |
|------|--------------|------------------------|
| dns.txt.gz | 40,821,591 | 0 (no labels) |
| flows.txt.gz | 129,977,412 | 0 (no labels) |
| proc.txt.gz | 426,045,096 | 0 (no labels) |

These three files have **no attack labels whatsoever**.

---

## 17. Dataset Semantics and Graph Constructibility

### Semantic classification
**Raw event / log-oriented.** Records are individual discrete events (authentication attempts, DNS lookups, network connections, process start/stop) at one-second granularity. Not flow-aggregated statistics. More semantically rich than flow datasets but significantly less rich than process-level provenance datasets (e.g., DARPA TC CDM).

### Graph construction possibilities

| Graph type | Constructible? | Node types | Edge types | Limitations |
|-----------|---------------|-----------|-----------|-------------|
| User–Computer authentication graph | Yes | User, Computer | Authenticates-to (from auth events) | Anonymised identifiers; no IP; labels only for 749 auth events |
| Computer–Computer network flow graph | Yes | Computer | Flows-to (from flows events) | No IP addresses; port semantics partially anonymised |
| Computer–Computer DNS graph | Yes | Computer | Resolves-to (from dns events) | Resolved names are anonymised `C<N>` — may not map to real hosts |
| User–Process–Computer graph | Partial | User, Process, Computer | Runs (proc start/stop) | Anonymised process names; no PID; no parent-child links; no file edges |

**Cross-file linkage:** Computer names (`C<N>`) are consistent across all files, enabling cross-file joins. User names (`U<N>@DOM1`) appear in both auth and proc. Time fields are consistent across files (same relative epoch).

### Limitations

- **No IP addresses** — cannot correlate auth/flow/dns by IP endpoint.
- **No file-level events** — process-to-file edges are impossible.
- **No process hierarchy** — no parent-child process relationships.
- **No command lines** — process `P<N>` names carry no semantic meaning.
- **Anonymised identifiers** — node labels in any constructed graph are opaque identifiers with no semantic content.
- **Labels only for auth events** — proc/dns/flows graphs have no ground truth.
- **Lateral movement inference** — can only be approximated from auth sequences (user `U` authenticates from `C1` to `C2` then from `C2` to `C3`), not from direct process lineage.

---

## 18. Key Limitations and Data Quality Notes

| Issue | Detail |
|-------|--------|
| **No IP addresses** | Computer names replace all network endpoints. IP-based correlation, geolocation, and IP-to-domain mapping are impossible. |
| **Full anonymisation** | User names, computer names, and process names are all replaced with opaque `U<N>`, `C<N>`, `P<N>` identifiers. No semantic meaning can be assigned to node labels. |
| **auth.txt.gz is large** | 7.6 GB compressed; 1,051,430,459 records when fully decompressed. Do not attempt to load into memory in one pass; use streaming or chunked reads. |
| **Labels only for 749 auth events** | Extreme class imbalance for supervised learning on auth (749 / 1,051,430,459 ≈ 0.000071%). No labels for dns, flows, or proc. |
| **Relative timestamps only** | `time` field is seconds since an undisclosed epoch. Cannot correlate to absolute wall-clock time or to other datasets without the epoch anchor. |
| **No process genealogy** | Process start/stop events provide no parent-PID, no child-PID, no command-line arguments. Process `P<N>` names are stable within the dataset (consistent anonymisation) but semantically opaque. |
| **No file events** | Cannot construct any file-access or data-exfiltration behaviour from this dataset alone. |
| **Port anonymisation in flows** | Some port values in `flows.txt.gz` are anonymised as `N<N>` strings instead of integers, complicating numeric port analysis. Check for non-integer port values before casting. |
| **No cross-dataset correlation** | Anonymisation prevents linking this dataset's `C<N>` identifiers to any external threat intelligence, IP reputation feeds, or other datasets. |
| **Licence** | LANL open data policy for research use; attribution required (cite Turcotte et al., 2018 DSN Workshop paper and `csr.lanl.gov/data/cyber1/`); no commercial redistribution. |

## 19. Ground Truth Assessment

### 19.1 Ground Truth Availability

Yes, but extremely limited in scope. Labels exist only for authentication events, in the separate file `redteam.txt.gz` (749 records). The `redteam.txt.gz` file must be joined to `auth.txt.gz` on `(time, source_computer, destination_computer)` to retrieve full authentication context. No labels exist for `dns.txt.gz`, `flows.txt.gz`, or `proc.txt.gz`. Source: Los Alamos National Laboratory red team records (Turcotte et al., 2018 DSN Workshop).

### 19.2 Definition of Positive

A red-team authentication event — a lateral movement action performed by the LANL red team, identified by `(time, source_computer, destination_computer)` in `redteam.txt.gz`.

### 19.3 Definition of Negative

Any authentication event in `auth.txt.gz` that does not match a `redteam.txt.gz` record. All `dns.txt.gz`, `flows.txt.gz`, and `proc.txt.gz` events are unlabelled and are neither positive nor negative in a supervised sense.

### 19.4 Class Balance Summary

| Class | Count | Percentage |
|-------|-------|-----------|
| Red-team / attack (auth only) | 749 | ~0.000071% |
| Benign auth events | ~1,051,429,710 | ~99.999929% |
| **Total auth events** | **1,051,430,459** | 100% |
| DNS records (unlabelled) | 40,821,591 | — |
| Flow records (unlabelled) | 129,977,412 | — |
| Process records (unlabelled) | 426,045,096 | — |

This is one of the most extreme class imbalances of any public cybersecurity dataset.

### 19.5 Label Granularity

Per-authentication-event. Each `redteam.txt.gz` record labels one authentication attempt (one row in `auth.txt.gz`). Labels do not exist at flow, DNS, or process granularity.

### 19.6 Known Labelling Issues and Controversies

| Issue | Detail |
|-------|--------|
| **Extreme class imbalance** | 749 attack events in ~1,051,430,459 auth records (~0.000071%). Standard supervised learning is infeasible without very aggressive undersampling of negatives or oversampling of positives. Accuracy as a metric is meaningless at this ratio. |
| **Labels restricted to auth events only** | DNS, flow, and process files have no labels. The nature of red-team activity on other protocols is unknown and cannot be supervised without external annotation. |
| **Full anonymisation** | All user, computer, and process identifiers are replaced with opaque `U<N>`, `C<N>`, `P<N>` tokens. Node labels in any constructed graph carry no semantic meaning; external threat intelligence cannot be applied. |
| **Relative timestamps only** | The dataset epoch is not published in the local files. Preventing absolute time correlation or comparison with external threat intelligence feeds. |
| **No IP addresses** | Computer names replace all network endpoints, making IP-based correlation and geolocation impossible. |
| **No process genealogy or file events** | Lateral movement can only be inferred from auth sequences, not from process lineage or file-access chains. The absence of these telemetry types limits attack path reconstruction to auth-hop chains only. |
