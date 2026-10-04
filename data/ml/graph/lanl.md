# LANL Unified Host and Network Dataset — Graph Constructibility Assessment

## 1. Node / Entity Fields

| TraceGraph Entity | Dataset File(s) | Field(s) | Notes |
|-------------------|----------------|---------|-------|
| User | auth, proc, redteam | `source_user@domain`, `destination_user@domain`, `user@domain` | Fully anonymised as `U<N>@DOM1`; machine accounts as `C<N>$@DOM1`; opaque tokens with no semantic content |
| Host | auth, dns, flows, proc, redteam | `source_computer`, `destination_computer`, `computer`, `resolved_computer` | Fully anonymised as `C<N>`; consistent across all files — cross-file joins are possible |
| Process | proc | `process_name`, `computer`, `user@domain` | Fully anonymised as `P<N>`; no PID, no parent-child links, no command lines |
| IP | — | **Absent.** | No IP addresses anywhere in the dataset; network endpoints use `C<N>` identifiers |
| File | — | **Absent.** | No file-level events, paths, or metadata in any file |
| Server | — | Cannot be distinguished from other hosts without external topology knowledge |

User and Host nodes are constructible from multiple files. Process nodes exist but are semantically opaque. IP, File, and Server entity types are unavailable.

---

## 2. Edge / Relationship / Action Fields

Action semantics are available for authentication and process events only:

| File | Action fields | Values | TraceGraph `action` mapping |
|------|--------------|--------|----------------------------|
| auth | `auth_orientation` | LogOn, LogOff, AuthMap, TGT, TGS | `LogOn` → `login`; TGT/TGS → `auth` |
| auth | `auth_type` | NTLM, Kerberos, Negotiate, `?` | Supplements `auth_orientation`; Kerberos TGT/TGS → `auth` |
| auth | `success` | Success, Fail | Outcome filter; Fail events still valid for graph edges |
| proc | `start_or_end` | Start, End | `Start` → `execute`; `End` → process termination (no direct TraceGraph mapping) |
| dns | — | Implicit: one record = one DNS lookup | No explicit action field; can be modelled as a `connect`-like edge |
| flows | — | Implicit: one record = one completed connection | No explicit action field; `protocol` (6=TCP, 17=UDP) available |

The `action` field can be derived for auth events (`login`/`auth`) and process start events (`execute`). For DNS and flow events, `connect` must be inferred from record type with no confirming action field.

---

## 3. Compatibility with TraceGraph Relationship Types

| Relationship Type | Status | Reason |
|-------------------|--------|--------|
| `LOGGED_INTO` | **Partial** | `source_user@domain` + `destination_computer` + `auth_orientation==LogOn` in auth file; all identifiers are anonymised opaque tokens — no semantic meaning can be assigned to node labels |
| `AUTHENTICATED_TO` | **Partial** | `source_user@domain` + `destination_computer` + `auth_orientation` ∈ {TGT, TGS, AuthMap}; Kerberos ticket events directly map; NTLM `LogOn` also applicable |
| `EXECUTED` | **Partial** | `user@domain` + `process_name` + `computer` + `start_or_end==Start` in proc file; `P<N>` names are anonymised — no command line, no PID, no parent-child process links |
| `CONNECTED_TO` | **Partial** | `source_computer` → `destination_computer` edges constructible from flows and dns files; no IP addresses — edges link `C<N>` host tokens rather than IPs; some ports anonymised as `N<N>` strings |
| `ACCESSED` | **Not supported** | No file events in any file; `ACCESSED` relationship cannot be constructed |

---

## 4. Compatibility with TraceGraph SecurityEvent Model

| SecurityEvent Field | Populatable? | Source | Notes |
|--------------------|-------------|--------|-------|
| `event_id` | Partial | Row index or `(time, source_computer, destination_computer)` composite | No stable unique ID field; composite key required per file |
| `source_type` | Yes | Hardcode `"lanl"` per file (auth/dns/flows/proc) | |
| `timestamp` | Partial | `time` (integer) | Relative seconds since undisclosed epoch — not absolute UTC; no wall-clock correlation possible |
| `event_type` | Partial | File type + `auth_orientation` / `start_or_end` | Auth and process events have typed actions; DNS and flow events do not |
| `action` | Partial | `auth_orientation`, `start_or_end` | Derivable for auth (LogOn → `login`) and proc (Start → `execute`) events; not derivable for dns/flows |
| `user` | Partial | `source_user@domain`, `user@domain` | Anonymised `U<N>@DOM1` tokens — structurally present but semantically opaque |
| `source_host` | Partial | `source_computer`, `computer` | Anonymised `C<N>` tokens — present, consistent across files, but opaque |
| `destination_host` | Partial | `destination_computer`, `resolved_computer` | Same `C<N>` anonymisation |
| `source_ip` | No | — | Absent |
| `destination_ip` | No | — | Absent |
| `process` | Partial | `process_name` (`P<N>`) | Present but fully anonymised and semantically meaningless |
| `file` | No | — | Absent |
| `severity` | Partial | `success` (auth) | Fail outcome is a weak severity signal; no direct severity field |

`timestamp` cannot be converted to absolute UTC, and `source_ip`/`destination_ip` are unavailable — these are structural constraints, not parsing issues.

---

## 5. Investigation Grouping

No investigation, incident, or session grouping field. Available grouping mechanisms:

- **`redteam.txt.gz` join to `auth.txt.gz`** on `(time, source_computer, destination_computer)` identifies 749 labelled red-team authentication events — the only ground truth. These form a sparse, auth-only attack marker set.
- **Computer + time window:** Lateral movement chains can be approximated by tracing auth events where the `destination_computer` of one event becomes the `source_computer` of the next for the same user.
- **`C<N>` consistency across files:** The same `C<N>` identifier links auth, dns, flows, and proc events for a given host, enabling multi-file investigation timelines per host.

Labels exist only for authentication events. DNS, flow, and process events have no ground truth and cannot be labelled without external annotation of which `C<N>` hosts were compromised and during which time windows.

---

## 6. Train/Test Leakage Considerations

- **Extreme class imbalance:** 749 attack events in 1,051,430,459 auth records (~0.000071%). Any accuracy metric is misleading; precision-recall and AUC-PR are required. Standard random splits will almost certainly exclude all attack events from the test set.
- **Temporal leakage:** Red-team events span `time=150,885` to `time=2,557,047` (~29.6 days). Temporal splits must use a cutoff time to prevent future attack events from appearing in training. Relative timestamps complicate this because the epoch is unknown — splits must be made by relative time value.
- **Anonymisation as leakage protection:** Full anonymisation prevents any node-identity leakage (no real IPs or hostnames to memorise), but also means a model trained on `C<N>` patterns will not generalise to any other dataset or real deployment.
- **No labels for dns/flows/proc:** Building a multi-file graph with unlabelled nodes requires unsupervised or semi-supervised methods; supervised leakage analysis applies only to the auth file.
- **`auth.txt.gz` is 7.6 GB compressed (1.05B records):** Chunked streaming reads are mandatory; in-memory loading is not feasible. Data pipeline must not accidentally include future events during windowed feature computation.

---

## 7. Overall Graph Suitability

**Medium.**

LANL is the strongest candidate among the non-DARPA datasets for TraceGraph compatibility. It provides genuine User and Host entity types across multiple correlated files, typed action semantics for authentication (`LogOn` → `login`, TGT/TGS → `auth`) and process events (`Start` → `execute`), and consistent `C<N>` identifiers that enable cross-file graph joins. Four of the five relationship types are at least partially constructible. However, three significant structural constraints limit the rating: (1) complete anonymisation renders all node labels semantically opaque, blocking any threat intelligence enrichment or real-world generalisation; (2) IP addresses are absent, making `CONNECTED_TO` edges host-to-host only and preventing `source_ip`/`destination_ip` population; (3) file events are entirely absent, making `ACCESSED` relationships impossible. The 749-record ground truth is also extremely sparse and restricted to authentication events only, making supervised training on this dataset challenging without extensive unsupervised pre-processing.
