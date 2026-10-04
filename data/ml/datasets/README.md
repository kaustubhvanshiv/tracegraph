# ML Dataset Catalogue

This file catalogues all candidate datasets considered for the TraceGraph ML/GNN research track.
Raw dataset files are stored **outside** the Git repository under `../datasets/` (one level above the
`tracegraph/` root). Nothing under that path may be copied into this repository or deleted.

---

## Dataset Index

| # | Dataset | Local source path | Primary format | Ground truth | Graph constructible |
|---|---------|-------------------|----------------|--------------|---------------------|
| 1 | DARPA TC Engagement 5 | `../datasets/Darpa/` | Avro/CDM binary (`.bin.gz`) | Yes — narrative attack report + schema | Yes — provenance graph schema |
| 2 | LANL Cybersecurity Dataset | `../datasets/LANL_Cybersecurity_Dataset/` | Gzipped CSV | Yes — `redteam.txt.gz` | Partial — no raw process-level events |
| 3 | UNSW-NB15 | `../datasets/UNSW-NB15/` | CSV (flow-level) | Yes — per-record `Label` + `attack_cat` | Limited — flow-oriented, light entity semantics |
| 4 | CIC-IDS2017 | `../datasets/CIC-IDS2017/` | CSV (flow-level) | Yes — per-record `Label` column | Limited — flow-oriented, light entity semantics |

---

## 1. DARPA Transparent Computing (TC) Engagement 5

### Dataset name
DARPA Transparent Computing Engagement 5 (TC E5)

### Exact local source path
```
../datasets/Darpa/
```

Subdirectory layout:
```
Darpa/
├── Data/
│   ├── cadets/          # FreeBSD CADETS telemetry — 3 × ~2.1 GB .bin files + .gz companions
│   │   ├── ta1-cadets-1-e5-official-2.bin.1     (2.1 GB, dated 2019-05-21)
│   │   ├── ta1-cadets-1-e5-official-2.bin.1.gz  (283 MB)
│   │   ├── ta1-cadets-1-e5-official-2.bin.2     (2.1 GB)
│   │   ├── ta1-cadets-1-e5-official-2.bin.2.gz  (276 MB)
│   │   ├── ta1-cadets-1-e5-official-2.bin.3     (2.1 GB)
│   │   └── ta1-cadets-1-e5-official-2.bin.3.gz  (266 MB)
│   └── fivedirections/  # Windows FiveDirections telemetry — 3 × ~1.9 GB .bin files + .gz companions
│       ├── ta1-fivedirections-1-e5-official-1.bin.1     (1.9 GB, dated 2019-05-21)
│       ├── ta1-fivedirections-1-e5-official-1.bin.1.gz  (292 MB, dated 2019-11-24)
│       ├── ta1-fivedirections-1-e5-official-1.bin.2     (1.9 GB)
│       ├── ta1-fivedirections-1-e5-official-1.bin.2.gz  (295 MB)
│       ├── ta1-fivedirections-1-e5-official-1.bin.3     (1.9 GB)
│       └── ta1-fivedirections-1-e5-official-1.bin.3.gz  (295 MB)
├── Ground_Truth/
│   ├── TA51_Final_report_E5.pdf   # Full attack-scenario narratives from TA5.1
│   └── TA51_Final_report_E5.docx
├── Schema/
│   ├── CDM20.avdl          # Human-readable CDM 2.0 Avro IDL schema
│   ├── TCCDMDatum.avsc     # Generated Avro schema (top-level datum)
│   └── cdm.pdf
├── Engagement-5-Event-Log.md    # Operational incident log (outages, restarts, data gaps)
├── Engagement-5-Local-Analysis.md  # Pre-existing detailed analysis of local files
├── README.md               # Tooling / Data Annotation Stack README
└── README.pdf
```

Total local data volume (raw .bin files): ~12 GB (CADETS ~6.3 GB + FiveDirections ~5.7 GB).
Compressed .gz files total ~1.7 GB.

### Public source URL
The DARPA TC dataset is distributed through the DARPA program infrastructure.
The most commonly cited public references are:

- DARPA Transparent Computing program: https://www.darpa.mil/program/transparent-computing
- Academic papers citing the TC dataset use the label "DARPA TC Engagement 5" or "TC E5"
- The CDM schema is versioned; this local copy uses **CDM 2.0** (filename `CDM20.avdl`)

No single canonical public download URL is documented in the local files.

### Exact version or release identifier
- Engagement: **Engagement 5**
- Schema version: **CDM 2.0** (confirmed by `CDM20.avdl` and the README Version tag `0.1.2 — November 1, 2019`)
- CADETS stream topic: `ta1-cadets-1-e5-official-2` (topic renamed mid-engagement due to duplicate records)
- FiveDirections stream topic: `ta1-fivedirections-1-e5-official-1`
- Data files dated: **2019-05-21** (raw .bin); FiveDirections .gz files re-compressed **2019-11-24**

### Access / acquisition notes
- Data was acquired as part of the DARPA TC program delivery. Requires programme affiliation or
  institutional access to obtain.
- The raw binary `.bin` files are Avro-serialized CDM records. Deserialisation requires the
  `TCCDMDatum.avsc` schema (present locally under `Schema/`).
- The `Engagement-5-Event-Log.md` documents significant operational issues during data collection:
  - CADETS produced **duplicate records** on 2019-05-07 and moved to a new Kafka topic.
  - CADETS experienced **large publishing gaps** on 2019-05-08 to 2019-05-09.
  - FiveDirections hosts were **shut down and rebooted** on multiple occasions.
  - MARPLE hosts frequently published **only UI events**.
  - THEIA had **fine-grained recording disabled** for portions of the engagement.
  - These issues mean field population cannot be assumed to be complete or consistent.
- A pre-existing `Engagement-5-Local-Analysis.md` contains a detailed analysis of the local schema,
  ground truth, graph constructibility, and download recommendations. Key conclusion: the local
  package contains Avro CDM tooling, schema, and ground-truth documentation; the raw `.bin` telemetry
  files **are** present for CADETS (official-2) and FiveDirections (official-1) streams only.

### Licence and usage constraints
- Access is restricted to DARPA TC programme participants and authorised researchers.
- No open-access licence is documented in the local files.
- Raw telemetry must not be redistributed without DARPA authorisation.
- The ground-truth report (`TA51_Final_report_E5.pdf`) and CDM schema files carry no explicit
  open-source licence in the local copies.

---

## 2. LANL Unified Host and Network Dataset

### Dataset name
Los Alamos National Laboratory (LANL) Unified Host and Network Dataset

### Exact local source path
```
../datasets/LANL_Cybersecurity_Dataset/
```

File listing:
```
LANL_Cybersecurity_Dataset/
├── auth.txt.gz    (7.2 GB compressed)
├── dns.txt.gz     (177 MB compressed)
├── flows.txt.gz   (1.1 GB compressed)
├── proc.txt.gz    (2.2 GB compressed)
└── redteam.txt.gz (4.8 KB compressed — red-team event labels)
```

Total compressed size: ~10.7 GB.

Sample rows (uncompressed):

**auth.txt.gz** — authentication events:
```
time,source_user@domain,destination_user@domain,source_computer,destination_computer,auth_type,logon_type,auth_orientation,success
1,ANONYMOUS LOGON@C586,ANONYMOUS LOGON@C586,C1250,C586,NTLM,Network,LogOn,Success
```

**dns.txt.gz** — DNS lookups:
```
time,computer,resolved_computer
2,C4653,C5030
```

**flows.txt.gz** — network flows:
```
time,duration,source_computer,source_port,destination_computer,destination_port,protocol,packet_count,byte_count
1,0,C1065,389,C3799,N10451,6,10,5323
```

**proc.txt.gz** — process start/stop events:
```
time,user@domain,computer,process_name,start_or_end
1,C1$@DOM1,C1,P16,Start
```

**redteam.txt.gz** — labelled red-team (attack) events, format same as auth.txt.gz:
```
time,source_user@domain,source_computer,destination_computer
150885,U620@DOM1,C17693,C1003
```

### Public source URL
- Primary: https://csr.lanl.gov/data/cyber1/
- Dataset paper: M. Turcotte et al., "Unified Host and Network Data Set", DSN Workshop on Data-Driven Security (2018)
- Alternative mirror reference often cited in literature: https://doi.org/10.1145/3180445.3180465

### Exact version or release identifier
- Referred to in the literature as **"LANL Cyber1"** or **"LANL Unified Host and Network Dataset (2017 release)"**
- No explicit version file is present in the local directory.
- The dataset covers **58 consecutive days** of internal enterprise network activity, with red-team events
  embedded on specific days (not disclosed in the public documentation; derived from `redteam.txt.gz`).

### Access / acquisition notes
- Obtained from the LANL Cyber Systems Research group public dataset portal (csr.lanl.gov/data/cyber1/).
- As of the last known check the dataset is available for download without registration, but access
  policies may have changed.
- The `redteam.txt.gz` file is very small (4.8 KB) because it contains only the labelled red-team
  authentication events — the file provides timestamps, users, and computer pairs, not the full event
  details.
- Computer names are anonymised (e.g., `C586`, `C1003`); user names are anonymised (e.g., `U620@DOM1`);
  process names are anonymised (e.g., `P16`). No original hostnames, real usernames, or process
  executable paths are present.
- The dataset does **not** contain file-level events, command-line arguments, parent-process
  relationships, or file paths. It is limited to authentication, DNS, network flow, and process
  start/stop events.

### Licence and usage constraints
- Distributed under a LANL open data policy for research use.
- Attribution required: cite the 2018 DSN workshop paper and the LANL data portal.
- No commercial redistribution without LANL approval.
- No explicit open-source licence file is present locally.

---

## 3. UNSW-NB15

### Dataset name
UNSW-NB15 Network Intrusion Dataset

### Exact local source path
```
../datasets/UNSW-NB15/
```

Directory layout:
```
UNSW-NB15/
├── CSV_Files/
│   ├── NUSW-NB15_features.csv          # Feature dictionary: 49 features, names, types, descriptions
│   ├── NUSW-NB15_GT.csv                # Ground truth file (83 MB)
│   ├── The UNSW-NB15 description.pdf   # Dataset description paper
│   ├── UNSW-NB15_1.csv                 # Main data part 1 (162 MB, 700,000 rows)
│   ├── UNSW-NB15_2.csv                 # Main data part 2 (158 MB, 700,000 rows)
│   ├── UNSW-NB15_3.csv                 # Main data part 3 (148 MB, 700,000 rows)
│   ├── UNSW-NB15_4.csv                 # Main data part 4 (94 MB, 440,043 rows)
│   ├── UNSW-NB15_LIST_EVENTS.csv       # Event counts per attack category and subcategory
│   └── Training_and_Testing_Sets/
│       ├── UNSW_NB15_training-set.csv  # Official training split (175,341 rows)
│       └── UNSW_NB15_testing-set.csv   # Official test split (82,332 rows)
├── Reports/
│   ├── report 17-2-2015.pdf
│   └── report 22-1-2015.pdf
└── ReadMe.pdf
```

Total rows across 4 main CSVs: **2,540,043** (plus header rows).
Official pre-split training set: 175,341 rows; test set: 82,332 rows.

Feature schema (49 features, key ones):

| Field | Type | Description |
|-------|------|-------------|
| `srcip` | nominal | Source IP address |
| `sport` | integer | Source port |
| `dstip` | nominal | Destination IP address |
| `dsport` | integer | Destination port |
| `proto` | nominal | Protocol (TCP, UDP, etc.) |
| `state` | nominal | Connection state (CON, FIN, INT, etc.) |
| `dur` | float | Flow duration |
| `sbytes` / `dbytes` | integer | Byte counts src→dst / dst→src |
| `sttl` / `dttl` | integer | TTL values |
| `service` | nominal | Application service (http, dns, ftp, etc.) |
| `Stime` / `Ltime` | timestamp | Flow start / end timestamps |
| `Spkts` / `Dpkts` | integer | Packet counts |
| `attack_cat` | nominal | Attack category (9 types + normal) |
| `Label` | binary | 0 = normal, 1 = attack |

Attack categories present (from `UNSW-NB15_LIST_EVENTS.csv`):
- Normal (2,218,761 records — ~87.4%)
- Fuzzers, Analysis, Backdoors, DoS, Exploits, Generic, Reconnaissance, Shellcode, Worms

### Public source URL
- Homepage: https://research.unsw.edu.au/projects/unsw-nb15-dataset
- Paper: N. Moustafa and J. Slay, "UNSW-NB15: A Comprehensive Data Set for Network Intrusion Detection
  Systems", MilCIS 2015.
- Direct download page: https://www.unsw.adfa.edu.au/unsw-canberra-cyber/cybersecurity/ADFA-NB15-Datasets/

### Exact version or release identifier
- **UNSW-NB15** (year 2015 release). No further version tag is present in the local files.
- The dataset was collected from January 22 to February 17, 2015 using the IXIA PerfectStorm tool
  in the Cyber Range Lab at UNSW Canberra.

### Access / acquisition notes
- Freely available for download from the UNSW research portal.
- The local copy includes the full 4-part main CSV dataset (~562 MB total CSV), ground truth file,
  feature dictionary, official pre-defined training/test splits, and supporting PDFs.
- No raw PCAP files are present locally (only CSV feature-extracted flow records).
- The dataset contains **no process-level events**, **no file paths**, **no command-line data**, and
  **no parent-process relationships**. It consists entirely of aggregated network flow statistics
  with pre-computed features.
- Entity semantics are limited: only IP addresses and ports identify "entities"; no host names,
  user names, or process names are present.

### Licence and usage constraints
- Available for academic and research use.
- Attribution required: cite the MilCIS 2015 paper.
- No commercial redistribution.
- No explicit open-source licence file is present locally.

---

## 4. CIC-IDS2017

### Dataset name
Canadian Institute for Cybersecurity Intrusion Detection Dataset 2017 (CIC-IDS2017)

### Exact local source path
```
../datasets/CIC-IDS2017/
```

Directory layout:
```
CIC-IDS2017/
└── TrafficLabelling/
    ├── Monday-WorkingHours.pcap_ISCX.csv                    (257 MB — benign baseline)
    ├── Tuesday-WorkingHours.pcap_ISCX.csv                   (167 MB — FTP-Patator, SSH-Patator)
    ├── Wednesday-workingHours.pcap_ISCX.csv                 (273 MB — Heartbleed, DoS/DDoS variants)
    ├── Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv (88 MB  — Web attacks)
    ├── Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv (104 MB — Infiltration)
    ├── Friday-WorkingHours-Morning.pcap_ISCX.csv            (72 MB  — Botnet)
    ├── Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv (98 MB  — PortScan)
    └── Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv     (92 MB  — DDoS)
```

Total rows across all CSVs: **~3,119,352** (including headers).
Total CSV size: ~1.2 GB.

Feature schema (83 features). Key fields (from the Monday header row):

| Field | Type | Description |
|-------|------|-------------|
| `Flow ID` | string | Composite flow identifier |
| `Source IP` | nominal | Source IP address |
| `Source Port` | integer | Source port |
| `Destination IP` | nominal | Destination IP address |
| `Destination Port` | integer | Destination port |
| `Protocol` | integer | Protocol number |
| `Timestamp` | datetime | Flow start time (`DD/MM/YYYY HH:MM:SS`) |
| `Flow Duration` | integer | Duration in microseconds |
| `Total Fwd Packets` / `Total Backward Packets` | integer | Packet counts |
| `Total Length of Fwd Packets` / `...Bwd...` | float | Byte counts |
| 70+ statistical features | float | IAT, packet length stats, flag counts, etc. |
| `Label` | nominal | `BENIGN` or attack name (e.g., `DDoS`, `PortScan`, `Bot`, etc.) |

Attack scenarios covered (one per day/file):
- Monday: BENIGN only (baseline traffic)
- Tuesday: FTP-Patator, SSH-Patator (brute force)
- Wednesday: DoS (GoldenEye, Hulk, Slowloris, Slowhttptest), Heartbleed
- Thursday morning: Web attacks (Brute Force, XSS, SQL Injection)
- Thursday afternoon: Infiltration
- Friday morning: Botnet (ARES)
- Friday afternoon: PortScan, DDoS (LOIT)

### Public source URL
- Homepage: https://www.unb.ca/cic/datasets/ids-2017.html
- Paper: I. Sharafaldin, A. H. Lashkari, A. A. Ghorbani, "Toward Generating a New Intrusion Detection
  Dataset and Intrusion Traffic Characterization", ICISSP 2018.

### Exact version or release identifier
- **CIC-IDS2017** (collected July 3–7, 2017).
- CSV files are labelled with the suffix `.pcap_ISCX.csv` indicating they were extracted from PCAPs
  using the CICFlowMeter tool.
- No local version metadata file is present.

### Access / acquisition notes
- Available for free download from the University of New Brunswick CIC website.
- The local copy contains only the `TrafficLabelling/` CSV files (feature-extracted from PCAPs).
  No raw PCAP files are present locally.
- The dataset contains **no process-level events**, **no file paths**, **no command-line data**,
  and **no parent-process relationships**. Like UNSW-NB15 it is entirely flow-oriented with
  pre-computed statistical features.
- Entity semantics are limited to IP addresses and ports. No host names, user identities, or
  process information is available in the CSV exports.
- The `Timestamp` field uses the format `DD/MM/YYYY HH:MM:SS` — note day-before-month ordering
  which differs from ISO-8601.
- Monday is benign-only traffic; attack-free traffic is not distributed across all days, which
  can affect class-balance calculations per-file.

### Licence and usage constraints
- Available for academic and research use under the UNB CIC terms.
- Attribution required: cite the ICISSP 2018 paper.
- No commercial redistribution without permission.
- No explicit open-source licence file is present locally.

---

## Selected Primary Dataset

_To be determined in task ML-01.6 after completing the full dataset analysis (ML-01.2 through ML-01.5)._

---

## Notes

- Raw dataset files must **never** be copied into this repository.
- Every analysis task that reads a raw dataset must record the exact local source path used.
- Large files must be accessed using memory-conscious methods (streaming, chunked reads, sampling,
  or metadata-only inspection).
- The `Engagement-5-Local-Analysis.md` file under `../datasets/Darpa/` contains a pre-existing
  detailed analysis of the DARPA TC dataset; it should be consulted before writing the DARPA
  `analysis.md` in task ML-01.2.
