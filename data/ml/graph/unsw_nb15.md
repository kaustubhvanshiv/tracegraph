# UNSW-NB15 — Graph Constructibility Assessment

## 1. Node / Entity Fields

| TraceGraph Entity | Dataset Field | Notes |
|-------------------|--------------|-------|
| IP | `srcip` | Source IP — present in main CSVs only; **dropped in official train/test splits** |
| IP | `dstip` | Destination IP — same constraint |
| User | — | **Absent.** No user, account, or authentication field of any kind |
| Host | — | **Absent.** No hostname or machine name — IPs are the only endpoint identifiers |
| Process | — | **Absent.** No process names, PIDs, or command lines |
| File | — | **Absent.** No file paths or file operations |
| Server | — | Cannot be distinguished from IP without external topology knowledge |

Only two of the six TraceGraph entity types (`IP`) are representable. The node universe is a flat IP-to-IP multigraph with no richer entity types.

---

## 2. Edge / Relationship / Action Fields

No discrete action field exists. The closest approximation is the combination of:

- `proto` (tcp/udp/sctp/ospf/unas/…) — transport protocol
- `service` (http/ftp/smtp/ssh/dns/ftp-data/irc/`-`) — application service
- `state` (CON/FIN/INT/REQ/RST/…) — connection state at flow completion

None of these carry the action semantics TraceGraph requires (`login`, `auth`, `execute`, `connect`, `access`). The `service` field can suggest a `connect`-like action for all flows, but this is an inference, not a discrete event type. The dataset is flow-aggregated — there is no per-event action log.

---

## 3. Compatibility with TraceGraph Relationship Types

| Relationship Type | Status | Reason |
|-------------------|--------|--------|
| `LOGGED_INTO` | **Not supported** | No `user` field; no login event |
| `AUTHENTICATED_TO` | **Not supported** | No `user` field; no auth event |
| `EXECUTED` | **Not supported** | No `process` field; no execution event |
| `CONNECTED_TO` | **Partial** | `srcip` → `dstip` edge constructible from main CSVs; impossible with official train/test splits (IPs dropped); edge attributes are statistical aggregates, not typed actions |
| `ACCESSED` | **Not supported** | No `process`, `user`, or `file` field |

---

## 4. Compatibility with TraceGraph SecurityEvent Model

| SecurityEvent Field | Populatable? | Source | Notes |
|--------------------|-------------|--------|-------|
| `event_id` | Partial | Row index / 5-tuple | No stable unique ID in main CSVs; training set has `id` (sequential row number only) |
| `source_type` | Yes | Hardcode `"unsw_nb15"` | |
| `timestamp` | Partial | `Stime` (Unix epoch) | Absent from official splits; present in main CSVs only |
| `event_type` | No | — | No discrete event type; `service`/`proto` are poor proxies |
| `action` | No | — | **Cannot be reliably derived**; no action semantics in the data |
| `user` | No | — | Absent |
| `source_host` | No | — | Absent; `srcip` is the only identifier |
| `destination_host` | No | — | Absent |
| `source_ip` | Partial | `srcip` | Main CSVs only |
| `destination_ip` | Partial | `dstip` | Main CSVs only |
| `process` | No | — | Absent |
| `file` | No | — | Absent |
| `severity` | Partial | `attack_cat` / `Label` | Binary label available; not a severity measure |

`action` is required for relationship extraction and cannot be populated — this is the critical gap.

---

## 5. Investigation Grouping

No investigation or session grouping field exists. Flows can be implicitly grouped by the 5-tuple `(srcip, dstip, sport, dsport, proto)`, but this is not an explicit column. `attack_cat` enables category-level grouping of attack flows. The nine attack categories (Fuzzers, Exploits, DoS, etc.) can form coarse scenario boundaries but are not investigation IDs.

The official train/test split methodology re-balances class distributions non-representatively (Normal drops from 87.4% → 31.9% in training), creating artificial grouping that does not reflect temporal or campaign structure.

---

## 6. Train/Test Leakage Considerations

- **IP-based leakage:** `srcip`/`dstip` are the primary entity identifiers; if the test set contains IPs from the same small synthetic testbed as training, the model may memorise IP-based patterns rather than behavioural ones.
- **Feature leakage:** `attack_cat` and `Label` must be excluded from features. `attack_cat` is blank (not null) for normal flows — silent inclusion is a risk.
- **Temporal leakage:** `Stime`/`Ltime` are absent from official splits, so temporal ordering is lost. Splits are random by row, not by time window, meaning future attack patterns can appear in training data.
- **Distribution shift:** The official training set is heavily re-balanced (Normal: 87.4% → 31.9%); models trained on it will not generalise to the true class distribution. Evaluation metrics on the official test set are similarly misleading.
- **BOM on UNSW-NB15_1.csv first row:** Silent parsing error if not opened with `encoding='utf-8-sig'`.

---

## 7. Overall Graph Suitability

**Low.**

UNSW-NB15 supports only a single, impoverished graph type: an IP-to-IP flow multigraph. With only `srcip` and `dstip` as entity identifiers — both absent from the official train/test splits — the dataset cannot populate the TraceGraph `action` field (required for all relationship extraction), cannot produce User, Host, Process, or File nodes, and cannot support four of the five TraceGraph relationship types at all. The one partially supportable type (`CONNECTED_TO`) requires working directly with the four main CSVs and accepting that edges carry only statistical flow aggregates rather than typed actions. This dataset is suitable for IP-connectivity anomaly detection but is architecturally incompatible with TraceGraph's entity-relationship model.
