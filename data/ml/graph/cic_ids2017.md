# CIC-IDS2017 — Graph Constructibility Assessment

## 1. Node / Entity Fields

| TraceGraph Entity | Dataset Field | Notes |
|-------------------|--------------|-------|
| IP | ` Source IP` | Leading space in column name — strip required on read |
| IP | ` Destination IP` | Same leading-space caveat |
| IP | `Flow ID` | Composite `srcIP-dstIP-srcPort-dstPort-protocol` — not a node, but useful for edge keying |
| User | — | **Absent.** No user, account, or authentication field |
| Host | — | **Absent.** No hostname or machine name |
| Process | — | **Absent.** No process names or PIDs |
| File | — | **Absent.** No file paths or file operations |
| Server | — | Cannot be distinguished from IP without external lab topology documentation |

As with UNSW-NB15, the node universe is restricted to IP addresses. The two port fields (` Source Port`, ` Destination Port`) are available as edge attributes but do not introduce new entity types.

---

## 2. Edge / Relationship / Action Fields

No discrete action field. The dataset provides aggregated flow statistics per connection. The closest approximation to an action:

- ` Protocol` (6=TCP, 17=UDP, 0=Other) — transport-layer only; no application semantics
- ` Label` — attack category name (e.g., `FTP-Patator`, `DDoS`, `PortScan`) — encodes attack intent but cannot substitute for a typed action field
- ` Destination Port` — can weakly imply service type (e.g., port 22 → SSH) but this is an inference, not a recorded action

None of these provide the `login`, `auth`, `execute`, `connect`, or `access` semantics required by TraceGraph. All 84 features are statistical summaries of completed flows, not discrete event records.

---

## 3. Compatibility with TraceGraph Relationship Types

| Relationship Type | Status | Reason |
|-------------------|--------|--------|
| `LOGGED_INTO` | **Not supported** | No `user` field; no login event |
| `AUTHENTICATED_TO` | **Not supported** | No `user` field; no auth event |
| `EXECUTED` | **Not supported** | No `process` field; no execution event |
| `CONNECTED_TO` | **Partial** | ` Source IP` → ` Destination IP` edge constructible; edge attributes are statistical aggregates (84 features), not typed actions; `Flow ID` provides a 5-tuple key |
| `ACCESSED` | **Not supported** | No `process`, `user`, or `file` field |

---

## 4. Compatibility with TraceGraph SecurityEvent Model

| SecurityEvent Field | Populatable? | Source | Notes |
|--------------------|-------------|--------|-------|
| `event_id` | Partial | `Flow ID` | Composite string, not globally unique across files — same 5-tuple can repeat across days |
| `source_type` | Yes | Hardcode `"cic_ids2017"` | |
| `timestamp` | Partial | ` Timestamp` | Format is `DD/MM/YYYY HH:MM:SS` — day-first trap; one-second precision; no flow end time |
| `event_type` | No | — | No discrete event type; ` Label` is an attack category, not a system event type |
| `action` | No | — | **Cannot be populated**; no action semantics in the data |
| `user` | No | — | Absent |
| `source_host` | No | — | Absent; ` Source IP` is the only identifier |
| `destination_host` | No | — | Absent |
| `source_ip` | Yes | ` Source IP` | Strip leading space from column name |
| `destination_ip` | Yes | ` Destination IP` | Strip leading space from column name |
| `process` | No | — | Absent |
| `file` | No | — | Absent |
| `severity` | Partial | ` Label` | Attack category available; not a severity rating |

`event_type` and `action` are the critical gaps — neither can be derived from this dataset.

---

## 5. Investigation Grouping

No investigation or session ID field. Grouping options:

- **By file / collection day:** Each CSV corresponds to one day and one primary attack scenario (Monday = benign-only, Wednesday = DoS variants, etc.). This is a coarse scenario boundary, not an investigation ID.
- **By ` Label`:** Attack categories enable class-level grouping but not campaign or investigation grouping.
- **By `Flow ID` + timestamp window:** Flows sharing a source/destination IP pair within a time window can be grouped, but this requires explicit temporal binning.

The 288,602 blank-label rows in the Thursday Morning file are an ungroupable dead zone — they cannot be assigned to any investigation or class without external annotation.

---

## 6. Train/Test Leakage Considerations

- **Label-in-features:** ` Label` must be excluded from all feature sets. The `Flow ID` composite string encodes IP addresses that may correlate with label in the small testbed environment.
- **IP leakage:** The lab topology assigns specific IPs to attacker vs. victim machines. A model can learn IP identity rather than behavioural patterns, producing inflated metrics that do not generalise.
- **Temporal leakage:** Each file corresponds to a single day; random splits within a file mix flow timestamps, allowing future flows into training. Correct splits should be time-ordered within each day's file.
- **Per-day file imbalance:** Monday is benign-only (529k rows). Sampling from individual files rather than the combined dataset produces misleading per-class metrics — Friday PortScan and DDoS files are nearly 50/50 due to the segregation design.
- **Blank-label rows:** 288,602 rows in Thursday Morning cannot be used as labelled data; including them silently (treating blank as benign) would inflate the negative class count.
- **`Infinity`/`NaN` tokens:** `Flow Bytes/s` and `Flow Packets/s` contain the literal string `Infinity` (2,867 occurrences) — these must be handled before training or they will cause dtype errors or silent NaN propagation.

---

## 7. Overall Graph Suitability

**Low.**

CIC-IDS2017 has the same fundamental structural limitation as UNSW-NB15: it is a flow-aggregated statistical dataset with only IP addresses as entity identifiers. The `action` field required by TraceGraph cannot be derived, four of the five relationship types are unsupported, and only a flat IP-to-IP multigraph is constructible. Additional data quality issues — 288,602 blank-label rows, a day-first timestamp format trap, leading spaces in column names, and `Infinity` tokens in rate features — add parsing complexity without providing compensating graph richness. The dataset is suitable for network flow anomaly detection benchmarks but is architecturally incompatible with TraceGraph's multi-entity provenance graph model.
