# UNSW-NB15 — Dataset Analysis

## 1. Dataset Overview

| Field | Value |
|-------|-------|
| **Name** | UNSW-NB15 Network Intrusion Detection Dataset |
| **Version / release** | UNSW-NB15 (2015 release); collected January 22 – February 17, 2015 |
| **Local source path** | `/home/kaustubh/Documents/Projects/TraceGraph/tracegraph/../datasets/UNSW-NB15/` |
| **Semantic classification** | **Flow-oriented** — each row is an aggregated network flow record with 49 pre-computed statistical features extracted by IXIA PerfectStorm |
| **Total size** | ~759 MB (du-reported) |

---

## 2. File Format

- **Encoding:** Flat CSV (comma-separated).
- **Header rows:**
  - Main data files (`UNSW-NB15_1.csv` through `UNSW-NB15_4.csv`): **no header row**. Column order matches the 49-feature dictionary in `NUSW-NB15_features.csv`.
  - Training and testing sets (`UNSW_NB15_training-set.csv`, `UNSW_NB15_testing-set.csv`): **have a header row** with different field names (srcip/dstip/sport/dsport dropped; `id` added — see §5).
  - `NUSW-NB15_features.csv`: feature dictionary mapping feature number → name, type, description.
  - `NUSW-NB15_GT.csv`: ground truth file (82.4 MB).
- **No compression.** All files are uncompressed flat CSV.

---

## 3. Dataset Structure

```
../datasets/UNSW-NB15/
├── CSV_Files/
│   ├── NUSW-NB15_features.csv              4,044 B  — feature dictionary (49 features)
│   ├── NUSW-NB15_GT.csv             86,426,111 B  — ground truth file (82.4 MB)
│   ├── The UNSW-NB15 description.pdf
│   ├── UNSW-NB15_1.csv             168,979,718 B  — 161 MB, 700,001 physical rows
│   ├── UNSW-NB15_2.csv             165,221,021 B  — 158 MB, 700,001 physical rows
│   ├── UNSW-NB15_3.csv             154,588,103 B  — 147 MB, 700,001 physical rows
│   ├── UNSW-NB15_4.csv              97,588,754 B  —  93 MB, 440,044 physical rows
│   ├── UNSW-NB15_LIST_EVENTS.csv        4,639 B  — per-category event counts
│   └── Training_and_Testing_Sets/
│       ├── UNSW_NB15_training-set.csv   (175,341 data rows + 1 header)
│       └── UNSW_NB15_testing-set.csv    ( 82,332 data rows + 1 header)
├── Reports/
│   ├── report 17-2-2015.pdf
│   └── report 22-1-2015.pdf
└── ReadMe.pdf
```

| File group | Files | Data rows | Size |
|-----------|-------|----------|------|
| Main CSVs | 4 | 2,540,044 unique records (2,540,047 physical rows — 3 duplicated boundary rows; see §4) | ~559 MB |
| Ground truth | 1 | — | 82.4 MB |
| Official train/test split | 2 | 257,673 total | ~117 MB |
| **Total** | | **2,540,044 unique records (main)** | **~759 MB** |

---

## 4. Record / Event Count

| File | Count | Method |
|------|-------|--------|
| UNSW-NB15_1.csv | **700,001** physical rows | `wc -l` (file has no header row; every line is a data record) |
| UNSW-NB15_2.csv | **700,001** physical rows | `wc -l` |
| UNSW-NB15_3.csv | **700,001** physical rows | `wc -l` |
| UNSW-NB15_4.csv | **440,044** physical rows | `wc -l` |
| **Physical total (4 files)** | **2,540,047** | Sum of per-file `wc -l` |
| **Duplicated boundary rows** | **−3** | Last row of _N_.csv == first row of _(N+1)_.csv for files 1→2, 2→3, 3→4 (verified by direct comparison) |
| **Unique / canonical records** | **2,540,044** | 2,540,047 − 3; matches LIST_EVENTS total exactly |

**Note on boundary duplicates:** The UNSW-NB15 dataset was originally split into four files at round boundaries. The last data row of each of files 1–3 is identical to the first row of the following file. These three rows must be deduplicated before counting unique records or computing class distributions. All three duplicated rows are normal flows (Label=0).

| Training set | **175,341** | Header row + 175,341 data rows |
| Testing set | **82,332** | Header row + 82,332 data rows |

---

## 5. Schema

### Main data files (UNSW-NB15_1.csv through _4.csv) — 49 features, no header row

| No. | Name | Type | Description |
|-----|------|------|-------------|
| 1 | `srcip` | nominal | Source IP address |
| 2 | `sport` | integer | Source port number |
| 3 | `dstip` | nominal | Destination IP address |
| 4 | `dsport` | integer | Destination port number |
| 5 | `proto` | nominal | Transaction protocol (tcp/udp/unas/sctp/ospf/etc.) |
| 6 | `state` | nominal | Connection state (CON/FIN/INT/REQ/RST/etc.) |
| 7 | `dur` | float | Total flow duration (seconds) |
| 8 | `sbytes` | integer | Source→destination transaction bytes |
| 9 | `dbytes` | integer | Destination→source transaction bytes |
| 10 | `sttl` | integer | Source-to-destination IP TTL value |
| 11 | `dttl` | integer | Destination-to-source IP TTL value |
| 12 | `sloss` | integer | Source packets retransmitted or dropped |
| 13 | `dloss` | integer | Destination packets retransmitted or dropped |
| 14 | `service` | nominal | Application service (http/ftp/smtp/ssh/dns/ftp-data/irc or `-`) |
| 15 | `Sload` | float | Source bits per second |
| 16 | `Dload` | float | Destination bits per second |
| 17 | `Spkts` | integer | Source→destination packet count |
| 18 | `Dpkts` | integer | Destination→source packet count |
| 19 | `swin` | integer | Source TCP window advertisement value |
| 20 | `dwin` | integer | Destination TCP window advertisement value |
| 21 | `stcpb` | integer | Source TCP base sequence number |
| 22 | `dtcpb` | integer | Destination TCP base sequence number |
| 23 | `smeansz` | integer | Mean packet size transmitted by source |
| 24 | `dmeansz` | integer | Mean packet size transmitted by destination |
| 25 | `trans_depth` | integer | HTTP request/response pipeline depth |
| 26 | `res_bdy_len` | integer | Uncompressed HTTP response body size (bytes) |
| 27 | `Sjit` | float | Source jitter (milliseconds) |
| 28 | `Djit` | float | Destination jitter (milliseconds) |
| 29 | `Stime` | timestamp | Flow record start time (Unix epoch integer, UTC) |
| 30 | `Ltime` | timestamp | Flow record last/end time (Unix epoch integer, UTC) |
| 31 | `Sintpkt` | float | Source inter-packet arrival time (milliseconds) |
| 32 | `Dintpkt` | float | Destination inter-packet arrival time (milliseconds) |
| 33 | `tcprtt` | float | TCP connection setup round-trip time (seconds) |
| 34 | `synack` | float | TCP SYN→SYN_ACK interval (seconds) |
| 35 | `ackdat` | float | TCP SYN_ACK→ACK interval (seconds) |
| 36 | `is_sm_ips_ports` | binary | 1 if source IP = destination IP and source port = destination port |
| 37 | `ct_state_ttl` | integer | Count of flows with same state and TTL range in last 100 |
| 38 | `ct_flw_http_mthd` | integer | Count of flows with HTTP GET or POST in last 100 |
| 39 | `is_ftp_login` | binary | 1 if FTP session used user+password authentication |
| 40 | `ct_ftp_cmd` | integer | Count of flows with FTP commands in last 100 |
| 41 | `ct_srv_src` | integer | Count of connections with same service + srcip in last 100 |
| 42 | `ct_srv_dst` | integer | Count of connections with same service + dstip in last 100 |
| 43 | `ct_dst_ltm` | integer | Count of connections with same dstip in last 100 |
| 44 | `ct_src_ltm` | integer | Count of connections with same srcip in last 100 |
| 45 | `ct_src_dport_ltm` | integer | Count of connections with same srcip + dstport in last 100 |
| 46 | `ct_dst_sport_ltm` | integer | Count of connections with same dstip + srcport in last 100 |
| 47 | `ct_dst_src_ltm` | integer | Count of connections with same srcip + dstip in last 100 |
| 48 | `attack_cat` | nominal | Attack category name (see §15); blank for normal flows |
| 49 | `Label` | binary | 0 = normal, 1 = attack |

Sample row (from UNSW-NB15_1.csv):
`59.166.0.0,1390,149.171.126.6,53,udp,CON,0.001055,132,164,31,29,0,0,dns,...,,0`

### Training / testing set schema

Header fields (different from main CSVs — `srcip`, `dstip`, `sport`, `dsport` are **dropped**; `id` is **added**):

```
id, dur, proto, service, state, spkts, dpkts, sbytes, dbytes, rate, sttl, dttl,
sload, dload, sloss, dloss, sinpkt, dinpkt, sjit, djit, swin, stcpb, dtcpb, dwin,
tcprtt, synack, ackdat, smean, dmean, trans_depth, response_body_len, ct_srv_src,
ct_state_ttl, ct_dst_ltm, ct_src_dport_ltm, ct_dst_sport_ltm, ct_dst_src_ltm,
is_ftp_login, ct_ftp_cmd, ct_flw_http_mthd, ct_src_ltm, ct_srv_dst,
is_sm_ips_ports, attack_cat, label
```

**⚠ Breaking difference:** `srcip` and `dstip` are absent from the official training and testing split files. Any model trained on the pre-split sets cannot use IP-based features. Also note `sinpkt`/`dinpkt` (vs `Sintpkt`/`Dintpkt`), `smean`/`dmean` (vs `smeansz`/`dmeansz`), and `response_body_len` (vs `res_bdy_len`) — field name inconsistencies between main CSVs and official splits. `sport` and `dsport` are simply absent from the official splits; `spkts` and `dpkts` are the packet-count fields and are unrelated to source/destination port.

---

## 6. Timestamp Fields

| Field | Type | Format | Timezone | Notes |
|-------|------|--------|----------|-------|
| `Stime` | integer | Unix epoch (seconds) | UTC | Flow start time; present in main CSVs, absent from official train/test sets |
| `Ltime` | integer | Unix epoch (seconds) | UTC | Flow last/end time; present in main CSVs, absent from official train/test sets |

Dataset collected: **January 22 to February 17, 2015** (27 days).

`Stime`/`Ltime` are absent from the official training and testing set files. Temporal analysis requires working directly with the 4 main CSVs.

---

## 7. User Fields

**None.** No user, account, or authentication information exists in this dataset.

---

## 8. Host / Machine Fields

**None.** Hosts are identified only by IP address (`srcip`, `dstip`). No hostnames, FQDNs, or machine names.

---

## 9. Source and Destination IP Fields

| Field | Type | Description | Present in |
|-------|------|-------------|-----------|
| `srcip` | nominal (string) | Source IP address | Main CSVs (features 1, 3) only |
| `dstip` | nominal (string) | Destination IP address | Main CSVs only |
| `sport` | integer | Source port | Main CSVs only — absent (not renamed) in official train/test splits |
| `dsport` | integer | Destination port | Main CSVs only (dropped in official splits) |

`srcip` and `dstip` are the **only entity identifiers** in this dataset. They are dropped in the official training and testing set files, which is a significant structural constraint.

---

## 10. Process Fields

**None.** No process names, PIDs, command lines, or process events.

---

## 11. File Fields

**None.** No file paths, file operations, or file metadata.

---

## 12. Event Type / Action Fields

No discrete event action field. Each row represents an aggregated flow, not a single system event.

| Field | Type | Semantics |
|-------|------|-----------|
| `proto` | nominal | Transport protocol (tcp/udp/sctp/ospf/unas/etc.) |
| `service` | nominal | Application-layer service (http/ftp/smtp/ssh/dns/ftp-data/irc/`-`) |
| `state` | nominal | Connection state at flow completion (CON/FIN/INT/REQ/RST/etc.) |

These three fields together provide the closest approximation to an "event type" but represent the summarised state of a completed flow rather than a typed action.

---

## 13. Label Fields

| Field | Type | Values |
|-------|------|--------|
| `Label` | binary integer | 0 = normal, 1 = attack |
| `attack_cat` | nominal string | Attack category name (blank for normal; see §15) |

Both fields are present in main CSVs and official train/test splits. `attack_cat` is blank (empty string) for normal flows, not a null or explicit "Normal" value — check for empty string when filtering.

---

## 14. Incident, Session, or Scenario ID Fields

**None.** No session, investigation, or incident grouping field.

The training/testing sets include an `id` field which is a sequential row number, not a semantic identifier. Flows can be implicitly grouped by `(srcip, dstip, sport, dsport, proto)` as a 5-tuple key, but this is not provided as an explicit column.

---

## 15. Attack Category Annotations

`attack_cat` field (feature 48). Nine attack categories:

| Category | Description |
|----------|-------------|
| Fuzzers | Fuzzing — random/malformed input generation |
| Analysis | Port scanning, spam, HTML file analysis |
| Backdoors | Backdoor connections |
| DoS | Denial of service |
| Exploits | Exploit attempts |
| Generic | Generic attack (cipher-suite attacks) |
| Reconnaissance | Information gathering, scanning |
| Shellcode | Shellcode injection |
| Worms | Self-propagating worm traffic |
| (blank) | Normal flow |

---

## 16. Class Balance

### Full dataset (2,540,044 unique records — verified against LIST_EVENTS)

| Class | Count | Percentage |
|-------|-------|-----------|
| Normal | 2,218,761 | 87.4% |
| Generic | 215,481 | 8.5% |
| Exploits | 44,525 | 1.8% |
| Fuzzers | 24,246 | 1.0% |
| DoS | 16,353 | 0.6% |
| Reconnaissance | 13,987 | 0.6% |
| Analysis | 2,677 | 0.1% |
| Backdoors | 2,329 | 0.1% |
| Shellcode | 1,511 | 0.1% |
| Worms | 174 | <0.01% |
| **Total** | **2,540,044** | 100% |

*(Physical row count across 4 files: 2,540,047. After removing 3 duplicated boundary rows: 2,540,044 unique records. This matches the LIST_EVENTS total exactly.)*

### Official training set (175,341 rows)

| Class | Count | Percentage |
|-------|-------|-----------|
| Normal | 56,000 | 31.9% |
| Generic | 40,000 | 22.8% |
| Exploits | 33,393 | 19.0% |
| Fuzzers | 18,184 | 10.4% |
| DoS | 12,264 | 7.0% |
| Reconnaissance | 10,491 | 6.0% |
| Analysis | 2,000 | 1.1% |
| Backdoor | 1,746 | 1.0% |
| Shellcode | 1,133 | 0.6% |
| Worms | 130 | 0.1% |
| **Total** | **175,341** | 100% |

**Note:** The training set is heavily sub-sampled and re-balanced relative to the full dataset. Normal drops from 87.4% → 31.9%; Generic rises from 8.5% → 22.8%. Class distributions are **not representative** of the full dataset.

### Official testing set (82,332 rows)

| Class | Count | Percentage |
|-------|-------|-----------|
| Normal | 37,000 | 44.9% |
| Generic | 18,871 | 22.9% |
| Exploits | 11,132 | 13.5% |
| Fuzzers | 6,062 | 7.4% |
| DoS | 4,089 | 5.0% |
| Reconnaissance | 3,496 | 4.2% |
| Analysis | 677 | 0.8% |
| Backdoor | 583 | 0.7% |
| Shellcode | 378 | 0.5% |
| Worms | 44 | 0.1% |
| **Total** | **82,332** | 100% |

---

## 17. Dataset Semantics and Graph Constructibility

### Semantic classification
**Flow-oriented.** Each row is a pre-computed summary of a complete network connection, extracted from raw PCAPs by the IXIA PerfectStorm tool. This is not a log of discrete timestamped system events. Records are statistical aggregations — the 47 numerical features (byte counts, packet counts, jitter, IAT, window sizes, TCP timing, etc.) summarise the flow as a whole.

### Graph construction possibilities

A graph can be constructed using `srcip` and `dstip` as nodes, with each flow record as a directed edge:

| Element | Basis | Limitation |
|---------|-------|------------|
| Nodes | `srcip`, `dstip` (IP address strings) | Only 2 entity types (source/destination IP); no host, user, process, or file nodes |
| Edges | One edge per flow row | 83 statistical features as edge attributes — not semantically interpretable as a typed action |
| Labels | `Label` / `attack_cat` on each edge | Available for all rows |

**This produces a flat IP-to-IP multigraph only.** No richer entity types, no process lineage, no file access edges, no user-host associations.

### Limitations

- **No srcip/dstip in official train/test splits** — IP-based graph features cannot be used with the pre-split files.
- **No process, user, file, or hostname entities** — graph is restricted to IP-level topology.
- **Statistical features only** — no discrete action semantics (e.g., "READ file X", "CONNECT to port 443"); features are computed over the completed flow.
- **No session or incident grouping** — flows are independent rows; multi-step attack patterns must be inferred from co-occurring flows by IP.
- **No temporal structure in train/test splits** — `Stime`/`Ltime` are absent, so temporal ordering is lost in the official split files.
- **Class re-balancing in official splits** — if using train/test sets, note the distribution mismatch (see §16).

---

## 18. Key Limitations and Data Quality Notes

| Issue | Detail |
|-------|--------|
| **srcip/dstip dropped in official splits** | The official `UNSW_NB15_training-set.csv` and `UNSW_NB15_testing-set.csv` omit source and destination IP columns. Any feature engineering requiring IP addresses must use the 4 main CSVs with manual splitting. |
| **Stime/Ltime absent from official splits** | Temporal ordering and time-based features cannot be derived from the official train/test sets. |
| **Field name inconsistencies** | Several field names differ between main CSVs and official splits: `Sintpkt`→`sinpkt`, `Dintpkt`→`dinpkt`, `smeansz`→`smean`, `dmeansz`→`dmean`, `res_bdy_len`→`response_body_len`. `sport`/`dsport`/`srcip`/`dstip` are absent entirely (not renamed). Verify column mapping before merging. |
| **attack_cat is blank (not null) for normal** | Normal rows have an empty string for `attack_cat`, not a null or "Normal" string. Filtering for normal rows requires checking `label==0` or `attack_cat==''`. |
| **Main CSVs have no header row** | Column assignment for main CSVs must be done programmatically using the feature dictionary. A mis-ordered read will silently produce wrong feature assignments. |
| **UTF-8 BOM on first row of UNSW-NB15_1.csv** | The very first byte of `UNSW-NB15_1.csv` is a UTF-8 BOM (`\ufeff`), making the first field read as `'\ufeff59.166.0.0'` instead of `'59.166.0.0'` when the file is opened without `encoding='utf-8-sig'`. Open with `encoding='utf-8-sig'` or strip the BOM explicitly. No other file in the set was observed to carry this BOM. |
| **3 duplicated boundary rows across main CSVs** | The last row of UNSW-NB15_1.csv equals the first row of UNSW-NB15_2.csv; similarly for files 2→3 and 3→4. Concatenating all four files without deduplication yields 2,540,047 rows instead of the canonical 2,540,044. Deduplicate on the full 49-field row (or drop first row of files 2, 3, and 4) before computing counts or class distributions. |
| **Extreme rarity of Worms** | Only 174 Worm records in 2.5M rows (0.007%). Standard accuracy metrics are misleading for this class. |
| **Dataset does not contain PCAPs** | Raw packet captures are not present locally — only pre-computed CSV features. No ability to re-run feature extraction or extract payload content. |
| **Flow-level only** | No sub-flow resolution. An attack spanning multiple flows generates multiple rows (one per flow), not a single record. |
| **Licence** | Academic research use; cite Moustafa & Slay, MilCIS 2015; no commercial redistribution. |
