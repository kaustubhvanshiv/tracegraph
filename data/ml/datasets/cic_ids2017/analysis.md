# CIC-IDS2017 — Dataset Analysis

## 1. Dataset Overview

| Field | Value |
|-------|-------|
| **Name** | Canadian Institute for Cybersecurity Intrusion Detection Dataset 2017 (CIC-IDS2017) |
| **Version / release** | CIC-IDS2017; collected July 3–7, 2017 (Monday–Friday) |
| **Local source path** | `/home/kaustubh/Documents/Projects/TraceGraph/tracegraph/../datasets/CIC-IDS2017/` |
| **Semantic classification** | **Flow-oriented** — each row is an aggregated network flow with 84 pre-computed statistical features (85 header columns including `Flow ID` and ` Label`) extracted from raw PCAPs by CICFlowMeter |
| **Total size** | ~1.2 GB (du-reported) |

---

## 2. File Format

- **Encoding:** Flat CSV with header row. Files use the suffix `.pcap_ISCX.csv` indicating extraction from PCAPs by CICFlowMeter.
- **Header rows:** Present in all files (one header row per file).
- **No compression.** All files are uncompressed flat CSV.
- **Known parsing hazards:**
  - Several field names have a **leading space** (e.g., ` Source IP`, ` Destination IP`) due to CICFlowMeter's CSV generation format. Strip whitespace from column names on read.
  - `Timestamp` uses **day-first format** (`DD/MM/YYYY HH:MM:SS`), not ISO-8601 or US month-first. Must explicitly specify `dayfirst=True` when parsing.
  - 288,602 rows in `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` have a **blank Label field** — a data quality issue in that specific file (see §18).
  - `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` also contains **Windows-1252 / Latin-1 encoded bytes** (byte `0x96`, an en-dash in Windows-1252) in the attack-category label strings (e.g., `Web Attack – Brute Force`). Reading the file as plain UTF-8 raises a `UnicodeDecodeError`; open with `encoding='latin-1'` or `encoding='cp1252'` (see §18).

---

## 3. Dataset Structure

```
../datasets/CIC-IDS2017/
└── TrafficLabelling/
    ├── Monday-WorkingHours.pcap_ISCX.csv                          268,649,908 B  (256 MB)
    ├── Tuesday-WorkingHours.pcap_ISCX.csv                         174,696,560 B  (167 MB)
    ├── Wednesday-workingHours.pcap_ISCX.csv                       285,642,925 B  (272 MB)
    ├── Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv      92,030,223 B  (87.8 MB)
    ├── Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv 108,723,183 B  (104 MB)
    ├── Friday-WorkingHours-Morning.pcap_ISCX.csv                   75,386,737 B  (71.9 MB)
    ├── Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv       101,874,777 B  (97.1 MB)
    └── Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv            96,101,069 B  (91.7 MB)
```

| File | Size | Data rows | Primary attack scenario |
|------|------|----------|------------------------|
| Monday | 256 MB | 529,918 | Benign only (baseline) |
| Tuesday | 167 MB | 445,909 | FTP-Patator, SSH-Patator |
| Wednesday | 272 MB | 692,703 | DoS (Hulk, GoldenEye, slowloris, Slowhttptest), Heartbleed |
| Thursday Morning | 87.8 MB | 458,968 | Web attacks (Brute Force, XSS, SQL Injection) + 288,602 blank-label rows ⚠ |
| Thursday Afternoon | 104 MB | 288,602 | Infiltration |
| Friday Morning | 71.9 MB | 191,033 | Botnet (ARES) |
| Friday PortScan | 97.1 MB | 286,467 | PortScan |
| Friday DDoS | 91.7 MB | 225,745 | DDoS (LOIT) |
| **Total** | **~1.2 GB** | **3,119,345** | |

---

## 4. Record / Event Count

Record counts verified by line count (including header):

| File | Total lines | Data rows (lines − 1 header) |
|------|------------|------------------------------|
| Monday | 529,919 | **529,918** |
| Tuesday | 445,910 | **445,909** |
| Wednesday | 692,704 | **692,703** |
| Thursday Morning | 458,969 | **458,968** (includes 288,602 blank-label) |
| Thursday Afternoon | 288,603 | **288,602** |
| Friday Morning | 191,034 | **191,033** |
| Friday PortScan | 286,468 | **286,467** |
| Friday DDoS | 225,746 | **225,745** |
| **Grand total** | **3,119,353** | **3,119,345** |

---

## 5. Schema

### Header fields (85 columns / 84 features, from Monday file)

| # | Field name | Type | Description |
|---|-----------|------|-------------|
| 1 | `Flow ID` | string | Composite identifier: `srcIP-dstIP-srcPort-dstPort-protocol` |
| 2 | ` Source IP` | nominal | Source IP address (leading space in column name) |
| 3 | ` Source Port` | integer | Source port |
| 4 | ` Destination IP` | nominal | Destination IP address (leading space in column name) |
| 5 | ` Destination Port` | integer | Destination port |
| 6 | ` Protocol` | integer | IP protocol number (6=TCP, 17=UDP, 0=Other) |
| 7 | ` Timestamp` | datetime | Flow start time — format `DD/MM/YYYY HH:MM:SS` |
| 8 | ` Flow Duration` | integer | Duration in microseconds |
| 9 | ` Total Fwd Packets` | integer | Forward (src→dst) packet count |
| 10 | ` Total Backward Packets` | integer | Backward (dst→src) packet count |
| 11 | ` Total Length of Fwd Packets` | float | Total bytes in forward packets |
| 12 | ` Total Length of Bwd Packets` | float | Total bytes in backward packets |
| 13 | ` Fwd Packet Length Max` | float | Max forward packet size |
| 14 | ` Fwd Packet Length Min` | float | Min forward packet size |
| 15 | ` Fwd Packet Length Mean` | float | Mean forward packet size |
| 16 | ` Fwd Packet Length Std` | float | Std dev of forward packet size |
| 17 | ` Bwd Packet Length Max` | float | Max backward packet size |
| 18 | ` Bwd Packet Length Min` | float | Min backward packet size |
| 19 | ` Bwd Packet Length Mean` | float | Mean backward packet size |
| 20 | ` Bwd Packet Length Std` | float | Std dev of backward packet size |
| 21 | `Flow Bytes/s` | float | Bytes per second (total flow) |
| 22 | ` Flow Packets/s` | float | Packets per second (total flow) |
| 23 | ` Flow IAT Mean` | float | Mean inter-arrival time between flow packets |
| 24 | ` Flow IAT Std` | float | Std dev of flow inter-arrival time |
| 25 | ` Flow IAT Max` | float | Max inter-arrival time |
| 26 | ` Flow IAT Min` | float | Min inter-arrival time |
| 27 | `Fwd IAT Total` | float | Total forward IAT |
| 28 | ` Fwd IAT Mean` | float | Mean forward IAT |
| 29 | ` Fwd IAT Std` | float | Std dev forward IAT |
| 30 | ` Fwd IAT Max` | float | Max forward IAT |
| 31 | ` Fwd IAT Min` | float | Min forward IAT |
| 32 | `Bwd IAT Total` | float | Total backward IAT |
| 33 | ` Bwd IAT Mean` | float | Mean backward IAT |
| 34 | ` Bwd IAT Std` | float | Std dev backward IAT |
| 35 | ` Bwd IAT Max` | float | Max backward IAT |
| 36 | ` Bwd IAT Min` | float | Min backward IAT |
| 37 | `Fwd PSH Flags` | integer | Forward PSH flag count |
| 38 | ` Bwd PSH Flags` | integer | Backward PSH flag count |
| 39 | ` Fwd URG Flags` | integer | Forward URG flag count |
| 40 | ` Bwd URG Flags` | integer | Backward URG flag count |
| 41 | ` Fwd Header Length` | integer | Total forward header bytes |
| 42 | ` Bwd Header Length` | integer | Total backward header bytes |
| 43 | `Fwd Packets/s` | float | Forward packets per second |
| 44 | ` Bwd Packets/s` | float | Backward packets per second |
| 45 | ` Min Packet Length` | float | Minimum packet size in flow |
| 46 | ` Max Packet Length` | float | Maximum packet size in flow |
| 47 | ` Packet Length Mean` | float | Mean packet size |
| 48 | ` Packet Length Std` | float | Std dev of packet size |
| 49 | ` Packet Length Variance` | float | Variance of packet size |
| 50 | `FIN Flag Count` | integer | FIN flag occurrences |
| 51 | ` SYN Flag Count` | integer | SYN flag occurrences |
| 52 | ` RST Flag Count` | integer | RST flag occurrences |
| 53 | ` PSH Flag Count` | integer | PSH flag occurrences |
| 54 | ` ACK Flag Count` | integer | ACK flag occurrences |
| 55 | ` URG Flag Count` | integer | URG flag occurrences |
| 56 | ` CWE Flag Count` | integer | CWE (ECN) flag occurrences |
| 57 | ` ECE Flag Count` | integer | ECE flag occurrences |
| 58 | ` Down/Up Ratio` | float | Download/upload ratio |
| 59 | ` Average Packet Size` | float | Average size of all packets |
| 60 | ` Avg Fwd Segment Size` | float | Average forward segment size |
| 61 | ` Avg Bwd Segment Size` | float | Average backward segment size |
| 62 | ` Fwd Header Length` | integer | Duplicate of field 41 (CICFlowMeter artifact) |
| 63 | `Fwd Avg Bytes/Bulk` | float | Forward average bulk bytes |
| 64 | ` Fwd Avg Packets/Bulk` | float | Forward average bulk packet count |
| 65 | ` Fwd Avg Bulk Rate` | float | Forward average bulk rate |
| 66 | ` Bwd Avg Bytes/Bulk` | float | Backward average bulk bytes |
| 67 | ` Bwd Avg Packets/Bulk` | float | Backward average bulk packet count |
| 68 | ` Bwd Avg Bulk Rate` | float | Backward average bulk rate |
| 69 | `Subflow Fwd Packets` | integer | Subflow forward packet count |
| 70 | ` Subflow Fwd Bytes` | integer | Subflow forward byte count |
| 71 | ` Subflow Bwd Packets` | integer | Subflow backward packet count |
| 72 | ` Subflow Bwd Bytes` | integer | Subflow backward byte count |
| 73 | `Init_Win_bytes_forward` | integer | TCP initial window bytes (forward) |
| 74 | ` Init_Win_bytes_backward` | integer | TCP initial window bytes (backward) |
| 75 | ` act_data_pkt_fwd` | integer | Count of packets with ≥1 byte of TCP data (forward) |
| 76 | ` min_seg_size_forward` | integer | Minimum segment size (forward) |
| 77 | `Active Mean` | float | Mean active state duration |
| 78 | ` Active Std` | float | Std dev of active state duration |
| 79 | ` Active Max` | float | Max active state duration |
| 80 | ` Active Min` | float | Min active state duration |
| 81 | `Idle Mean` | float | Mean idle state duration |
| 82 | ` Idle Std` | float | Std dev of idle state duration |
| 83 | ` Idle Max` | float | Max idle state duration |
| 84 | ` Idle Min` | float | Min idle state duration |
| 85 | ` Label` | nominal | `BENIGN` or attack category name (last column) |

**Note on field 62:** ` Fwd Header Length` (with leading space, position 41) and ` Fwd Header Length` (position 62) share the same column name — a known CICFlowMeter artifact. The header therefore has 85 columns but only 84 distinct feature names. pandas renames the second occurrence to `Fwd Header Length.1` on read. Use positional indexing if both columns are needed.

---

## 6. Timestamp Fields

| Field | Format | Timezone | Notes |
|-------|--------|----------|-------|
| ` Timestamp` | `DD/MM/YYYY HH:MM:SS` | Local (dataset captured in Canada; assumed EDT, UTC-4) | **Day-first ordering** — `03/07/2017` = July 3, not March 7. Specify `dayfirst=True` in pandas or equivalent. Precision is one second — the format carries no sub-second component. |

Dataset collected: **July 3–7, 2017** (Monday–Friday). No flow end timestamp — only flow start. ` Flow Duration` in microseconds can be added to derive an approximate end time.

---

## 7. User Fields

**None.** No user, account, or authentication information.

---

## 8. Host / Machine Fields

**None.** Hosts are identified only by IP address. No hostnames or machine names.

The test environment used private IP ranges (192.168.x.x) for victim machines and specific IP addresses for attacker machines, but this structure is not explicitly labelled in the CSV. It can be inferred from the IP patterns but requires external documentation of the lab topology.

---

## 9. Source and Destination IP Fields

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| ` Source IP` | nominal (string) | Source IP address | Leading space in column name |
| ` Destination IP` | nominal (string) | Destination IP address | Leading space in column name |
| ` Source Port` | integer | Source port | |
| ` Destination Port` | integer | Destination port | |
| `Flow ID` | string | Composite `srcIP-dstIP-srcPort-dstPort-protocol` | Not a stable key across files |

Source and destination IP are available in all files (unlike UNSW-NB15 official splits). They are the primary entity identifiers alongside ports.

---

## 10. Process Fields

**None.** No process names, PIDs, command lines, or process-level events.

---

## 11. File Fields

**None.** No file paths, file operations, or file metadata.

---

## 12. Event Type / Action Fields

No discrete event action field. Each row is an aggregated flow summary.

| Field | Type | Semantics |
|-------|------|-----------|
| ` Protocol` | integer | Transport protocol (6=TCP, 17=UDP) |
| ` Label` | nominal | Attack category (serves as implicit event classification) |

Flow direction is inferred from `Fwd`/`Bwd` statistics but is not an explicit action field. No application-layer action (e.g., HTTP method, FTP command) is present as a separate field.

---

## 13. Label Fields

| Field | Type | Values |
|-------|------|--------|
| ` Label` | nominal string | See table below |

Label values:

| Label value | Category |
|-------------|----------|
| `BENIGN` | Normal traffic |
| `DDoS` | Distributed denial of service |
| `PortScan` | Port scanning |
| `Bot` | Botnet (ARES) |
| `Infiltration` | Infiltration attack |
| `Heartbleed` | Heartbleed TLS exploit |
| `FTP-Patator` | FTP brute-force |
| `SSH-Patator` | SSH brute-force |
| `DoS Hulk` | DoS Hulk HTTP flood |
| `DoS GoldenEye` | DoS GoldenEye |
| `DoS slowloris` | DoS Slowloris |
| `DoS Slowhttptest` | DoS Slow HTTP test |
| `Web Attack \u2013 Brute Force` | Web brute-force |
| `Web Attack \u2013 XSS` | Cross-site scripting |
| `Web Attack \u2013 Sql Injection` | SQL injection |
| `` (empty string) | **Data quality issue** — 288,602 rows in Thursday Morning file |

---

## 14. Incident, Session, or Scenario ID Fields

No incident or investigation ID. The closest grouping mechanisms are:

| Mechanism | Description |
|-----------|-------------|
| `Flow ID` | Composite `srcIP-dstIP-srcPort-dstPort-protocol` — identifies a flow 5-tuple within a file; the same 5-tuple can recur across different files on different days |
| File (day/scenario) | Each CSV corresponds to one collection day and typically one primary attack scenario; some files contain multiple attack classes alongside benign traffic (see §15) |

Temporal grouping within a file is possible via ` Timestamp` + ` Flow Duration`. Cross-file incident correlation requires linking by IP and time, with awareness of the day-first timestamp format.

---

## 15. Attack Category Annotations

` Label` field. Files are organized by collection day, with each day's primary attack scenario named in the filename. Several files contain multiple attack classes alongside benign traffic:

| File | Attack scenario(s) |
|------|--------------------|
| Monday | BENIGN only |
| Tuesday | FTP-Patator, SSH-Patator |
| Wednesday | DoS Hulk, DoS GoldenEye, DoS slowloris, DoS Slowhttptest, Heartbleed |
| Thursday Morning | Web Attack–Brute Force, Web Attack–XSS, Web Attack–SQL Injection (+ 288,602 blank-label) |
| Thursday Afternoon | Infiltration |
| Friday Morning | Bot (Botnet ARES) |
| Friday Afternoon (PortScan) | PortScan |
| Friday Afternoon (DDoS) | DDoS |

---

## 16. Class Balance

### Per-file breakdown (exact counts)

| File | BENIGN | Attack class(es) | Attack count | Attack % |
|------|--------|-----------------|--------------|----------|
| Monday | 529,918 | — | 0 | 0% |
| Tuesday | 432,074 | FTP-Patator: 7,938 / SSH-Patator: 5,897 | 13,835 | 3.1% |
| Wednesday | 440,031 | DoS Hulk: 231,073 / DoS GoldenEye: 10,293 / DoS slowloris: 5,796 / DoS Slowhttptest: 5,499 / Heartbleed: 11 | 252,672 | 36.5% |
| Thursday Morning | 168,186 | Web BruteForce: 1,507 / Web XSS: 652 / Web SQL: 21 | 2,180 labelled attacks; 288,602 blank | — ⚠ |
| Thursday Afternoon | 288,566 | Infiltration: 36 | 36 | 0.012% |
| Friday Morning | 189,067 | Bot: 1,966 | 1,966 | 1.0% |
| Friday PortScan | 127,537 | PortScan: 158,930 | 158,930 | 55.5% |
| Friday DDoS | 97,718 | DDoS: 128,027 | 128,027 | 56.7% |

### Overall class balance (3,119,345 total rows)

| Label | Count | Percentage |
|-------|-------|-----------|
| BENIGN | 2,273,097 | 72.9% |
| (blank) ⚠ | 288,602 | 9.3% |
| DoS Hulk | 231,073 | 7.4% |
| PortScan | 158,930 | 5.1% |
| DoS GoldenEye | 10,293 | 0.33% |
| DDoS | 128,027 | 4.1% |
| FTP-Patator | 7,938 | 0.25% |
| SSH-Patator | 5,897 | 0.19% |
| DoS slowloris | 5,796 | 0.19% |
| DoS Slowhttptest | 5,499 | 0.18% |
| Bot | 1,966 | 0.06% |
| Web Attack–Brute Force | 1,507 | 0.05% |
| Web Attack–XSS | 652 | 0.02% |
| Infiltration | 36 | 0.00% |
| Web Attack–SQL Injection | 21 | 0.00% |
| Heartbleed | 11 | 0.00% |
| **Total** | **3,119,345** | 100% |

**Extreme imbalance:** Infiltration (36 records), Heartbleed (11 records), and SQL Injection (21 records) are effectively unusable for standalone classification without severe oversampling. PortScan and DDoS files are nearly 50/50 due to the per-day segregation design, which inflates their effective representation if files are sampled individually.

---

## 17. Dataset Semantics and Graph Constructibility

### Semantic classification
**Flow-oriented.** Each row is a pre-computed statistical summary of a complete network flow, extracted from raw PCAPs by CICFlowMeter. 84 features per flow (85 header columns — one feature name is duplicated; see §5). Not individual discrete system events.

### Graph construction possibilities

IP-to-IP flow graphs can be constructed using ` Source IP` and ` Destination IP` as nodes:

| Element | Basis | Limitation |
|---------|-------|------------|
| Nodes | Source IP, Destination IP | Only IP addresses — no host, user, process, or file node types |
| Edges | One per flow row | 84 statistical features as attributes (85 columns — one name duplicated); no discrete semantic action |
| Labels | ` Label` on each edge | All files have labels; 288,602 blank rows must be filtered |
| Temporal ordering | ` Timestamp` | Day-first format trap; only start time available |

`Flow ID` is a composite 5-tuple string. The same combination of source IP, destination IP, ports, and protocol can appear in multiple files (different days), so `Flow ID` is not a globally unique record key.

### Limitations

- **No process, user, file, or hostname entities** — graph is restricted to IP-level topology.
- **84 statistical features (85 columns)** — not interpretable as typed semantic actions; one feature name (`Fwd Header Length`) is duplicated.
- **288,602 blank-label rows** — these must be explicitly handled; they cannot be used as labelled training data.
- **Day-first timestamp format** — incorrect parsing produces wildly wrong timestamps silently.
- **Leading spaces in column names** — a common parsing error; column name strip is required.
- **No raw PCAPs locally** — cannot re-extract features or inspect payload.
- **Duplicate `Fwd Header Length` column** — two columns with the same name; position-based indexing safer than name-based.
- **Per-file scenario segregation** — each file corresponds to one collection day; some files contain multiple attack classes (e.g., Wednesday has five distinct DoS/Heartbleed labels). Combining files naively inflates benign count (Monday: 529k benign-only rows).

---

## 18. Key Limitations and Data Quality Notes

| Issue | Detail |
|-------|--------|
| **288,602 blank-label rows in Thursday Morning** | The `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` file contains 288,602 rows with an empty ` Label` field. These rows cannot be classified as benign or attack. The file also contains 168,186 benign rows and 2,180 labelled attack rows. Options: drop blank-label rows, treat as benign (risky), or exclude the entire file. |
| **Non-UTF-8 encoding in Thursday Morning file** | `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` contains byte `0x96` (an en-dash in Windows-1252/Latin-1) in the `Web Attack – Brute Force`, `Web Attack – XSS`, and `Web Attack – Sql Injection` label strings. Opening the file with `encoding='utf-8'` (the pandas default) raises `UnicodeDecodeError`. Use `encoding='latin-1'` or `encoding='cp1252'`. All other files in the dataset are clean UTF-8. |
| **Day-first timestamp format** | ` Timestamp` uses `DD/MM/YYYY HH:MM:SS` — e.g., `03/07/2017` is July 3, not March 7. Using default pandas `parse_dates` without `dayfirst=True` will silently produce wrong dates for days 1–12 of a month where the day-month swap is valid. |
| **Leading spaces in column names** | Column names from CICFlowMeter have inconsistent leading spaces. Strip column names with `.str.strip()` or equivalent on read. Accessing columns by exact name (including the space) works but is error-prone. |
| **Duplicate `Fwd Header Length` column** | ` Fwd Header Length` appears at position 41 and again at position 62 — a CICFlowMeter artifact resulting in 85 header columns for 84 distinct feature names. pandas renames the second occurrence to `Fwd Header Length.1`. Use positional indexing if both columns are needed. |
| **Extreme rarity of some attack classes** | Heartbleed: 11 rows; SQL Injection: 21 rows; Infiltration: 36 rows. These classes are insufficient for supervised learning without significant oversampling or synthetic generation. |
| **No raw PCAPs** | Only CICFlowMeter-extracted CSVs are present. Cannot re-derive features, inspect payloads, or validate feature extraction. |
| **Per-day file segregation** | Attack scenarios are not randomly distributed across the week. Monday is benign-only. Combining all files into a single dataset without stratification will produce a skewed class distribution dominated by DoS Hulk (231k rows) and PortScan (159k rows). |
| **Infinity / NaN tokens in flow rate features** | CICFlowMeter generates the literal string `Infinity` (and occasionally `NaN`) in `Flow Bytes/s` and `Flow Packets/s` when flow duration is zero. Locally verified: 2,867 `Infinity`/`NaN` token occurrences across the dataset (not 2,867 rows — a single row can contain at most one affected rate field). These tokens are not IEEE floating-point values; a plain `pd.read_csv` will fail or silently coerce them unless `na_values=['Infinity']` is specified. Numeric pipeline must handle these before model training. |
| **Licence** | Academic research use; cite Sharafaldin, Lashkari & Ghorbani, ICISSP 2018, and the UNB CIC homepage (https://www.unb.ca/cic/datasets/ids-2017.html); no commercial redistribution without permission. |
