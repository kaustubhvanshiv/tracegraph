# Offline FiveDirections CDM normalization

Mapping version 1, verified 2026-10-13. `prepare_dataset.py` registers
`CDMReviewAdapter` in a private backend `AdapterRegistry`; production ingestion
and relationship extraction are unchanged. The adapter's output is validated
against the actual backend `SecurityEvent` schema.

## Source and joins

Stream gzip-wrapped Avro containers using their embedded schema. Index entity
definitions on disk in SQLite by **publishing host UUID and entity UUID**.
Index subjects, principals, hosts, files, flows, memory, registry, IPC and
source/sink objects from the selected annotation-source files. Normalize the
selected events after that scan so nonchronological publication does not hide
an available definition. A conflicting definition is withheld, not arbitrarily
selected. This index is local and is rebuilt for each fresh run.

Host scoping prevents another host's same textual UUID from supplying fields.
Process joins follow thread parent references until a process is reached. Every
visited subject must have a known start timestamp at or before the event;
missing/future start times, cycles and unresolved parents prevent process-field
population. Thread CID is never used as a process PID.

Object typing is an identity join. Network endpoints describe the referenced
flow, and file paths come from the event itself. These fields do not constitute
past-window event counts or a graph feature extractor. A future ML graph
implementation still needs its own causal availability and partition audits.
No time-varying properties, permission histories, labels, or annotation
indicators are converted into model features here.

## Canonical mapping policy

| CDM evidence | `SecurityEvent` representation |
|---|---|
| OPEN/READ/WRITE/CHECK_FILE_ATTRIBUTES with a resolved FileObject | `file / access`; file path from `predicateObjectPath` |
| File CLOSE/CREATE_OBJECT/UNLINK/TRUNCATE/MODIFY_FILE_ATTRIBUTES | `file / close, create, delete, truncate, modify` respectively; preserve distinct operations |
| Same object operations on memory/registry/flow/IPC objects | Corresponding category with the original operation name in lowercase; never file access |
| CONNECT with a referenced NetFlowObject | `network / connect`; local source IP, remote destination IP |
| ACCEPT/RECVFROM/RECVMSG | `network / accept or receive`; remote source and local destination when a flow is resolved; local hostname is destination host |
| SENDTO/SENDMSG/BIND | `network / send or bind`; local-to-remote fields when a flow is resolved |
| LOGIN / LOGOUT | `authentication / login` or `authentication / logout`; no inferred remote authentication |
| CREATE_THREAD | `thread / create_thread`, distinct from execution |
| FORK / CLONE / EXIT | `process / fork, clone, exit`; never mapped automatically to execute |
| EXECUTE with a resolved FileObject | `process / execute`; process field is the executed target path, not the issuing parent image |
| Unknown/unsupported object/action combination | `cdm_event` and original CDM action; unsupported optional fields remain null |

Networking actions have a known category even when their flow cannot be
resolved; IP fields remain null. EXECUTE has a process category but no target
image without a typed target. Missing file definitions cannot be substituted
by an annotation's generated filename or a path-shaped string.

For non-EXECUTE actions, `process` is an unambiguous executable token from the
resolved process's creation command line. Full command lines remain only in
local raw metadata. `user` requires a linked Principal username; a SID or
principal UUID is not substituted for a username. A publishing host requires
a Host definition for a hostname; report IP evidence does not create a guessed
hostname. Invalid IP strings are withheld. Severity is not fabricated.

Original CDM payload, action, object references and integer nanoseconds are
preserved in `raw_data.cdm`; Pydantic's datetime may have microsecond precision.
Resolution status, predicate kind and mapping version are audit metadata.
They must not be mistaken for attack labels or training-ready graph features.

## Measured run

The 2026-10-13 rerun streamed **2,000,000 segment-121 records**, with 1,901,311
Events and 153 FileObject definitions. All three annotation-listed review
events normalize as file access with their actual event paths. One supplies a
valid Firefox process image; user, hostname and network endpoint fields remain
null for these file events. No label changed: one report-reviewed positive,
two unknowns, no verified negatives. No supervised split was generated.

The **32 research tests** cover mapping distinctions, host scoping, conflicting
definitions, temporal process checks, network direction, ambiguous executable
parsing and existing ingestion/split/archive checks. Synthetic fixtures validate
the implementation and are not DARPA training examples.
