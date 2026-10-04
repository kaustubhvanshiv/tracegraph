# Candidate Dataset Comparison — ML/GNN Suitability

> **Purpose**: Select the most suitable candidate dataset for subsequent ML/GNN research tasks.
> This document synthesises findings from the four individual dataset analyses and graph
> assessments. For detailed schema, record counts, and data quality notes, see the per-dataset
> `analysis.md` and `data/ml/graph/*.md` files.

---

## 1. Datasets Under Comparison

| ID | Dataset | Semantic class | Local path |
|----|---------|---------------|-----------|
| **D1** | DARPA TC Engagement 5 (CDM) | Raw event / provenance | `../datasets/Darpa/` |
| **D2** | LANL Unified Host and Network | Raw event / log | `../datasets/LANL_Cybersecurity_Dataset/` |
| **D3** | UNSW-NB15 | Flow-aggregated statistics | `../datasets/UNSW-NB15/` |
| **D4** | CIC-IDS2017 | Flow-aggregated statistics | `../datasets/CIC-IDS2017/` |

---

## 2. Comparative Assessment

### 2.1 Event / Row Semantics

| Dataset | Row represents | Typed actions? |
|---------|---------------|----------------|
| D1 DARPA | One CDM `Event` record — a discrete, timestamped, typed system-call or OS event | Yes — `Event.type` is a 58-value enum (see `darpa/analysis.md §12`) |
| D2 LANL | One discrete timestamped entry: an auth attempt, DNS lookup, flow, or process start/stop | Partial — auth orientation and proc Start/End typed; DNS and flows have no explicit action field (see `lanl/analysis.md §12`) |
| D3 UNSW | One aggregated network flow — 47 pre-computed statistical features over a completed connection | No — `proto`, `service`, `state` are proxies, not discrete actions (see `unsw_nb15/analysis.md §12`) |
| D4 CIC | One aggregated network flow — 84 pre-computed statistical features | No — ` Label` encodes attack intent, not event semantics (see `cic_ids2017/analysis.md §12`) |

D1 and D2 are event-oriented. D3 and D4 are flow-aggregated and lack the discrete action field that TraceGraph's relationship extraction requires.

---

### 2.2 Entity Information

| Dataset | Entity types constructible | Notes |
|---------|--------------------------|-------|
| D1 DARPA | All 6: Host, User, Process, File, IP, Server | Only dataset covering the full entity vocabulary; see `darpa/graph.md §1` |
| D2 LANL | User, Host, Process (partial) | IP and File absent; all identifiers fully anonymised (`C<N>`, `U<N>`, `P<N>`); see `lanl/graph.md §1` |
| D3 UNSW | IP only | IPs dropped in official train/test splits; see `unsw_nb15/graph.md §1` |
| D4 CIC | IP only | IPs present in all files; see `cic_ids2017/graph.md §1` |

---

### 2.3 Action / Relationship Information

| Dataset | TraceGraph relationship types supported |
|---------|-----------------------------------------|
| D1 DARPA | All 5: LOGGED_INTO, AUTHENTICATED_TO, EXECUTED, CONNECTED_TO, ACCESSED (see `darpa/graph.md §3`) |
| D2 LANL | 4 of 5 partially: LOGGED_INTO, AUTHENTICATED_TO, EXECUTED, CONNECTED_TO — ACCESSED not possible (see `lanl/graph.md §3`) |
| D3 UNSW | 1 of 5 partially: CONNECTED_TO only, via IP-to-IP edges; action cannot be derived (see `unsw_nb15/graph.md §3`) |
| D4 CIC | 1 of 5 partially: CONNECTED_TO only, via IP-to-IP edges; action cannot be derived (see `cic_ids2017/graph.md §3`) |

---

### 2.4 Ground Truth Quality

| Dataset | Label type | Granularity | Known issues |
|---------|-----------|-------------|-------------|
| D1 DARPA | Narrative PDF only — no machine-readable per-record label | Per-host/time-window narrative; labelling requires manual alignment against `TA51_Final_report_E5.pdf` | No structured UUID→label mapping; attack class stereotyping in controlled lab (see `darpa/analysis.md §13–19`) |
| D2 LANL | Per-authentication-event binary label in `redteam.txt.gz` (749 records) | Per-auth-row; DNS/flows/proc unlabelled | Extreme imbalance: 749 / 1,051,430,459 ≈ 0.000071%; no cross-file labels (see `lanl/analysis.md §16, §19`) |
| D3 UNSW | Per-flow binary + 9-category label on every row | Per-flow; both `Label` and `attack_cat` present | Official train/test splits artificially re-balanced; testbed synthetic traffic; label noise (see `unsw_nb15/analysis.md §19`) |
| D4 CIC | Per-flow 14-category label on almost every row | Per-flow; 288,602 blank-label rows in Thursday Morning file | Post-hoc IP/time-window labelling noise; Windows-1252 encoding issue; testbed synthetic traffic (see `cic_ids2017/analysis.md §19`) |

D3 and D4 offer the densest, per-row labels but were generated from closed testbed environments with known label noise. D1 is the most realistic but requires substantial labelling effort. D2 has verifiable labels for auth events only.

---

### 2.5 Graph Constructibility

| Dataset | Graph suitability | Graph type achievable |
|---------|------------------|-----------------------|
| D1 DARPA | **High** | Full provenance graph: typed entities × 6, typed relationships × 5, process lineage tree, file access subgraph (see `darpa/graph.md §7`) |
| D2 LANL | **Medium** | User–Host auth graph + Host–Host flow graph + User–Process–Host graph; cross-file joins via `C<N>` (see `lanl/graph.md §7`) |
| D3 UNSW | **Low** | IP-to-IP flow multigraph only; IPs absent from official splits (see `unsw_nb15/graph.md §7`) |
| D4 CIC | **Low** | IP-to-IP flow multigraph only; richer than UNSW in feature count but same structural limitation (see `cic_ids2017/graph.md §7`) |

---

### 2.6 SecurityEvent Compatibility

How well each dataset populates the TraceGraph `SecurityEvent` model fields (see `design.md`, Component 3):

| Field | D1 DARPA | D2 LANL | D3 UNSW | D4 CIC |
|-------|----------|---------|---------|--------|
| `event_id` | ✅ `Event.uuid` | ⚠ composite key | ⚠ row index / `id` | ⚠ `Flow ID` not globally unique |
| `timestamp` | ✅ nanosecond UTC | ⚠ relative seconds, epoch unknown | ⚠ absent from official splits | ⚠ day-first format, start only |
| `event_type` | ✅ 58-value enum | ⚠ partial per file | ❌ no discrete type | ❌ no discrete type |
| `action` | ✅ derived from `Event.type` | ⚠ auth/proc only | ❌ cannot derive | ❌ cannot derive |
| `user` | ⚠ `username` optional | ⚠ anonymised `U<N>` | ❌ absent | ❌ absent |
| `source_host` | ✅ via `Host.hostName` | ⚠ anonymised `C<N>` | ❌ absent | ❌ absent |
| `source_ip` | ✅ `NetFlowObject.localAddress` | ❌ absent | ⚠ main CSVs only | ✅ present all files |
| `destination_ip` | ✅ `NetFlowObject.remoteAddress` | ❌ absent | ⚠ main CSVs only | ✅ present all files |
| `process` | ⚠ `cmdLine` optional | ⚠ anonymised `P<N>` | ❌ absent | ❌ absent |
| `file` | ⚠ `predicateObjectPath` optional | ❌ absent | ❌ absent | ❌ absent |
| `severity` | ❌ must derive | ⚠ `success` weak proxy | ⚠ `Label` not severity | ⚠ `Label` not severity |

✅ = natively available and well-typed   ⚠ = available with caveats   ❌ = absent or cannot be derived

`action` is the critical field for TraceGraph relationship extraction. Only D1 can populate it reliably. D2 can derive it for auth and process events only. D3 and D4 cannot populate it at all.

---

### 2.7 Investigation / Attack-Scenario Grouping

| Dataset | Natural grouping unit | Investigation simulation quality |
|---------|----------------------|----------------------------------|
| D1 DARPA | Host + time-window from ground-truth PDF; five distinct multi-stage attack scenarios | High — multi-step APT scenarios with process lineage; requires manual PDF alignment |
| D2 LANL | Lateral-movement chain by auth sequence across `C<N>` hosts | Medium — 749 auth-only attack markers span 29.6 days; no campaign structure documented |
| D3 UNSW | 9 attack categories; no temporal campaign grouping | Low — isolated flows; no multi-step scenario structure |
| D4 CIC | Per-day scenario files; 14 attack categories | Low-medium — day-level segregation approximates scenarios but each day is a single independent attack class, not a multi-stage campaign |

D1 is the only dataset that natively contains multi-stage attack narratives matching the TraceGraph investigation model. D4's day-level segregation is the closest proxy among the flow datasets.

---

### 2.8 Candidate Prediction Targets

These are structural observations only — no prediction target is finalised here.

| Dataset | Observable candidate targets |
|---------|------------------------------|
| D1 DARPA | Node/edge anomaly in provenance graph; attack phase classification; process/entity involvement in a known attack scenario |
| D2 LANL | Binary lateral-movement label on auth edges; user/host anomaly score from auth sequence; temporal community detection |
| D3 UNSW | Binary flow classification (normal vs. attack); multi-class attack category; IP-pair anomaly score |
| D4 CIC | Binary or multi-class flow classification; attack category per flow; IP-pair anomaly score |

D3 and D4 offer immediate, per-row supervised classification targets. D1 and D2 require graph-level or sequence-level target construction before training.

---

### 2.9 Train/Test Leakage Risks

| Dataset | Primary leakage risks |
|---------|-----------------------|
| D1 DARPA | Stream-identity leakage (CADETS vs. FiveDirections model host-OS differences); duplicate CADETS records inflate attack windows; publishing gaps create artificial temporal discontinuities (see `darpa/graph.md §6`) |
| D2 LANL | Anonymised identifiers prevent IP leakage but also prevent generalisation; extreme class imbalance means random splits will almost certainly exclude all 749 attack events from test; temporal split requires relative-time cutoff (see `lanl/graph.md §6`) |
| D3 UNSW | IP-based memorisation in small testbed; official splits lose temporal ordering (`Stime`/`Ltime` dropped); re-balanced distribution misrepresents real-world ratios (see `unsw_nb15/graph.md §6`) |
| D4 CIC | IP-based leakage from fixed lab topology (attacker/victim IPs identifiable); per-day file segregation inflates minority class representation when files are sampled individually; 288,602 blank-label rows silently inflate negatives if untreated (see `cic_ids2017/graph.md §6`) |

---

### 2.10 Known Limitations and Biases

| Dataset | Key limitations |
|---------|----------------|
| D1 DARPA | Binary Avro format requires deserializer + schema; no machine-readable per-record label; controlled lab reduces real-world realism; only 2 of 5 TA1 streams locally (THEIA/MARPLE/ClearScope absent); optional CDM fields have stream-dependent population rates |
| D2 LANL | Full anonymisation blocks threat-intelligence enrichment and cross-dataset generalisation; no IP addresses; no file events; no process hierarchy; 749 attack labels cover only auth events; relative timestamps prevent absolute time correlation |
| D3 UNSW | Synthetic testbed traffic with known statistical artefacts (Kenyon et al., 2020; Engelen et al., 2021); srcip/dstip dropped in official splits; UTF-8 BOM on first file; 3 duplicated boundary rows; Worms class has only 174 records |
| D4 CIC | Post-hoc labelling noise (Engelen et al., IEEE TNSM 2021); 288,602 blank-label rows; Windows-1252 encoding issue; day-first timestamp format trap; `Infinity`/`NaN` tokens in rate features; Infiltration (36 rows), Heartbleed (11 rows), SQL Injection (21 rows) are unusable for standalone classification |

---

### 2.11 Computational Feasibility

| Dataset | Size | Feasibility concerns |
|---------|------|---------------------|
| D1 DARPA | ~14 GB (two streams, binary Avro) | Full deserialization required before any processing; record count unknown without streaming; graph construction from Avro is an engineering task, not just a read |
| D2 LANL | ~10.7 GB compressed; 1.65B records decompressed | `auth.txt.gz` alone decompresses to 1.05B records — mandatory streaming/chunked reads; feasible with chunked pandas or Spark |
| D3 UNSW | ~759 MB; 2.54M records | Entirely memory-feasible; main CSVs load into pandas on a standard workstation |
| D4 CIC | ~1.2 GB; 3.12M records | Memory-feasible; Thursday Morning file requires `encoding='latin-1'` and blank-label filtering |

D3 and D4 are immediately feasible with standard tooling. D2 requires streaming but is structurally straightforward. D1 requires a custom Avro deserialization pipeline before any ML work can begin.

---

## 3. Summary Scorecard

Scores are relative assessments for GNN/ML suitability within the TraceGraph context (not absolute quality ratings).

| Criterion | D1 DARPA | D2 LANL | D3 UNSW | D4 CIC |
|-----------|----------|---------|---------|--------|
| Event semantics | ★★★★★ | ★★★☆☆ | ★☆☆☆☆ | ★☆☆☆☆ |
| Entity richness | ★★★★★ | ★★★☆☆ | ★☆☆☆☆ | ★☆☆☆☆ |
| Action/relationship coverage | ★★★★★ | ★★★☆☆ | ★☆☆☆☆ | ★☆☆☆☆ |
| Ground truth quality | ★★★☆☆ | ★★☆☆☆ | ★★★★☆ | ★★★☆☆ |
| Graph constructibility | ★★★★★ | ★★★☆☆ | ★☆☆☆☆ | ★☆☆☆☆ |
| SecurityEvent compatibility | ★★★★☆ | ★★★☆☆ | ★☆☆☆☆ | ★★☆☆☆ |
| Investigation grouping | ★★★★★ | ★★★☆☆ | ★☆☆☆☆ | ★★☆☆☆ |
| Leakage risk (lower = better) | ★★★☆☆ | ★★★★☆ | ★★☆☆☆ | ★★☆☆☆ |
| Computational feasibility | ★★★☆☆ | ★★★☆☆ | ★★★★★ | ★★★★★ |

---

## 4. Dataset Selection Recommendation

**Recommended primary dataset: D1 — DARPA TC Engagement 5**

DARPA TC E5 is the only candidate that is architecturally compatible with TraceGraph's provenance graph model. It is the sole dataset providing all six entity types, all five relationship types, typed discrete events, absolute UTC timestamps, and multi-stage attack scenarios that mirror the investigation structure TraceGraph is designed to support. Every field required to populate a `SecurityEvent` and build a TraceGraph provenance graph can, in principle, be derived from CDM records.

The trade-offs are operational, not structural:

- The binary Avro format requires a one-time deserializer pipeline using `TCCDMDatum.avsc`.
- Ground truth labels must be derived by aligning `Event.timestampNanos` and `TCCDMDatum.hostId` against the narrative time windows in `TA51_Final_report_E5.pdf`.
- Optional CDM fields (`cmdLine`, `predicateObjectPath`, `parentSubject`, `username`) have stream-dependent population rates that must be assessed empirically during deserialization.
- Only two of the five TA1 streams are available locally (CADETS/FreeBSD and FiveDirections/Windows).

These are solvable engineering problems. The structural incompatibilities of D3 and D4 (`action` field not derivable, four of five relationship types unsupported) are not.

**Secondary dataset for supplementary experiments: D2 — LANL**

If attack-labelled graph data with less preprocessing overhead is needed for ablation studies or GNN validation benchmarks, LANL provides a real enterprise environment with genuine User and Host entities, typed auth semantics, and verifiable (if sparse and auth-only) ground truth. Its anonymisation limits real-world generalisation but isolates graph-structural signals from IP/hostname memorisation.

**D3 (UNSW-NB15) and D4 (CIC-IDS2017) are not recommended** as primary datasets for TraceGraph GNN research. Both datasets are architecturally incompatible with the TraceGraph entity-relationship model: neither can populate the `action` field required for relationship extraction, neither supports more than one of the five TraceGraph relationship types, and neither can produce any entity type beyond IP. They are suitable for conventional network intrusion detection benchmarks but not for GNN research grounded in the TraceGraph provenance graph.
