# Implementation Plan: TraceGraph

## Overview

This implementation plan converts the TraceGraph requirements and design into a dependency-ordered engineering plan.

The implementation is intentionally incremental. Each stage produces a testable result that becomes the input to the next stage.

The build order is:

```text
Common Event Contract
        ↓
Evidence Input
        ↓
Parsing
        ↓
Normalization
        ↓
Validation
        ↓
Entity Extraction
        ↓
Relationship Extraction
        ↓
Temporal Correlation
        ↓
Neo4j Graph
        ↓
Timeline + Evidence APIs
        ↓
React Investigation Workspace
        ↓
AI Summary
        ↓
End-to-End Scenario
        ↓
Evaluation
```

The MVP does not begin with a GNN. The first objective is to establish a correct, explainable, evidence-traceable investigation pipeline. Graph-learning experiments can be added after the baseline has measurable behavior.

---

# Task 1 — Define the Common Security Event Contract

## 1.1 Implement the `SecurityEvent` schema

Create the backend model for the normalized internal event:

```python
class SecurityEvent(BaseModel):
    event_id: str
    timestamp: datetime
    event_type: str
    action: str

    user: str | None = None

    source_host: str | None = None
    destination_host: str | None = None

    source_ip: str | None = None
    destination_ip: str | None = None

    process: str | None = None
    file: str | None = None

    severity: str | None = None
    raw_data: dict | None = None
```

## 1.2 Define validation rules

Implement validation for:

- event ID presence;
- timestamp format;
- event type;
- action;
- valid optional-field types.

## 1.3 Define event fixtures

Create controlled fixtures representing:

- login;
- process execution;
- network connection;
- file access;
- authentication;
- unrelated event.

## Done Criteria

- Schema imports successfully.
- Valid events pass validation.
- Structurally invalid events fail clearly.
- Optional entity fields remain nullable.
- Raw data can be preserved.

---

# Task 2 — Implement Evidence Input

## 2.1 Define ingestion request models

Create API models for:

```text
single event
batch of events
source metadata
investigation ID
```

## 2.2 Implement JSON ingestion

Implement:

```text
POST /api/investigations/{id}/events
POST /api/investigations/{id}/events/batch
```

## 2.3 Preserve source metadata

For each batch record:

- source type;
- source name;
- source record ID when available;
- ingestion timestamp.

## 2.4 Handle malformed input

Return structured errors for:

- invalid JSON;
- missing required fields;
- invalid event shape.

## Done Criteria

- One valid event can enter the pipeline.
- Multiple events can be ingested as a batch.
- Source information remains attached to the event.
- Invalid input does not create partial graph data.

---

# Task 3 — Implement Source Parsing

## 3.1 Create parser interface

Define a common parser contract:

```text
raw event
   ↓
parser
   ↓
parsed fields
```

The parser must be replaceable by source adapters.

## 3.2 Implement first adapter

For the initial prototype, implement the simplest source format used by the team’s controlled scenario.

The first adapter may consume:

- structured JSON;
- or a JSON representation of a dataset row.

Do not implement every possible vendor format before the baseline pipeline works.

## 3.3 Preserve unknown fields

Keep unsupported fields in `raw_data` when possible.

## 3.4 Add parser tests

Test:

- complete event;
- event missing optional fields;
- malformed timestamp;
- unknown field;
- malformed required field.

## Done Criteria

- The selected sample input format is converted into structured fields.
- Parser errors identify the affected event.
- Raw evidence is preserved.

---

# Task 4 — Implement Normalization

## 4.1 Define field mappings

Create explicit mappings for source fields to the common schema.

Example:

```text
AccountName  -> user
ComputerName -> source_host
UtcTime      -> timestamp
Image        -> process
```

## 4.2 Normalize timestamps

Convert accepted timestamps into UTC-aware datetime values.

## 4.3 Normalize identifiers

Implement deterministic normalization for:

- usernames;
- hostnames;
- IP addresses;
- processes;
- file identifiers.

Do not remove information merely to make strings shorter.

## 4.4 Preserve source representation

Retain enough source metadata to inspect the original field mapping.

## Done Criteria

- Equivalent source fields map to the same internal fields.
- Timestamps are normalized consistently.
- Events from the initial source can produce the same `SecurityEvent` representation used by the rest of the system.

---

# Task 5 — Implement Investigation Metadata

## 5.1 Create investigation model

Minimum fields:

```text
investigation_id
title
description
status
created_at
updated_at
created_by
closed_at
analyst_notes
outcome
```

## 5.2 Implement investigation lifecycle

Initial statuses:

```text
OPEN
UNDER_REVIEW
CLOSED
```

## 5.3 Implement APIs

```text
POST  /api/investigations
GET   /api/investigations
GET   /api/investigations/{id}
PATCH /api/investigations/{id}
```

## Done Criteria

- Investigation can be created and retrieved.
- Events can be associated with an investigation.
- Status and notes can be updated.

---

# Task 6 — Implement Entity Extraction

## 6.1 Define entity types

Initial node types:

```text
User
Host
Server
IP
Process
File
```

## 6.2 Build extraction service

For each `SecurityEvent`, extract entities from populated fields.

Example:

```text
user = Rahul
source_host = ENG-PC-27
process = powershell.exe
```

becomes:

```text
User(Rahul)
Host(ENG-PC-27)
Process(powershell.exe)
```

## 6.3 Establish entity identity rules

Define reusable identity functions so the graph layer does not implement inconsistent deduplication.

## 6.4 Test extraction

Tests must verify:

- expected entities created;
- missing fields produce no fabricated nodes;
- duplicate entity appearances are recognized as the same entity where identity rules allow;
- source event IDs are preserved.

## Done Criteria

- Every supported event fixture produces the expected entities.
- No maliciousness classification is embedded in entity extraction.

---

# Task 7 — Implement Relationship Extraction

## 7.1 Define relationship types

Initial relationships:

```text
LOGGED_INTO
AUTHENTICATED_TO
EXECUTED
CONNECTED_TO
ACCESSED
```

## 7.2 Implement event-to-relationship rules

Examples:

```text
login event:
User -> LOGGED_INTO -> Host

process execute:
Host -> EXECUTED -> Process

network connection:
Host -> CONNECTED_TO -> Host/Server/IP

file access:
Host/Server -> ACCESSED -> File
```

## 7.3 Attach evidence metadata

Every derived relationship must record:

```text
event_id
timestamp
source
relationship_type
```

## 7.4 Support multiple supporting events

Do not overwrite an earlier event reference if another event supports the same logical relationship.

## Done Criteria

- Each supported event can produce expected relationship types.
- Every relationship references source evidence.
- Unsupported or ambiguous events are not forced into an incorrect relationship.

---

# Task 8 — Implement Candidate Event Retrieval

## 8.1 Define the correlation window

Use a configurable prototype default.

Initial baseline:

```text
10 minutes
```

The value must not be treated as a universal security constant.

## 8.2 Retrieve candidates

For each new event, search for nearby events using:

- same investigation;
- time window;
- user;
- host;
- IP;
- other relevant identifiers.

## 8.3 Separate retrieval from correlation

Candidate retrieval only determines which events are worth evaluating.

It does not decide whether the events are truly related.

## Done Criteria

- Candidate events can be retrieved by time and context.
- Retrieval is bounded.
- Unrelated distant events are not loaded unnecessarily.

---

# Task 9 — Implement Rule-Based Temporal Correlation

## 9.1 Define correlation signals

Initial signals:

```text
shared user
shared host
shared IP
host continuity
temporal proximity
compatible action sequence
process/file context
```

## 9.2 Implement explainable correlation output

A correlation result should include something conceptually similar to:

```json
{
  "related": true,
  "signals": [
    "shared_host",
    "temporal_proximity",
    "compatible_sequence"
  ]
}
```

## 9.3 Add optional relationship strength

If a numeric value is used, define it as evidence-support strength.

Do not name it:

```text
attack_probability
malware_probability
compromise_probability
```

unless a separately evaluated model is introduced.

## 9.4 Tune only after testing

Do not guess final weights.

Start with deterministic conditions and use controlled scenarios to evaluate false links and missed links.

## 9.5 Correlation test cases

Implement at minimum:

1. Same user + nearby login events.
2. Same host + nearby process/network events.
3. Host continuity across multiple actions.
4. Compatible multi-stage sequence.
5. Same event type but unrelated hosts.
6. Same user but far outside the time window.
7. Events with missing optional identifiers.

## Done Criteria

- Correlations are explainable.
- Correlation metadata identifies why events were linked.
- Unrelated fixture events remain separate.
- The correlation layer does not claim that a relationship is malicious.

---

# Task 10 — Implement Neo4j Graph Persistence

## 10.1 Define node mapping

Map extracted entities to Neo4j labels:

```text
:User
:Host
:Server
:IP
:Process
:File
```

## 10.2 Define relationship mapping

Map relationships to:

```text
:LOGGED_INTO
:AUTHENTICATED_TO
:EXECUTED
:CONNECTED_TO
:ACCESSED
```

## 10.3 Store relationship metadata

At minimum:

```text
timestamp
event_ids
source
investigation_id
correlation_signals
```

## 10.4 Implement repository methods

Conceptual methods:

```python
create_entity(...)
merge_entity(...)
create_relationship(...)
get_investigation_graph(...)
get_related_entities(...)
get_supporting_events(...)
```

## 10.5 Prevent destructive overwrites

Graph writes must preserve evidence from multiple observations.

## Done Criteria

- Sample scenario creates the expected graph.
- Relationships retain event references.
- Duplicate entity observations do not produce uncontrolled node duplication.
- Graph can be queried by investigation.

---

# Task 11 — Implement Graph Query and Pivot APIs

## 11.1 Implement investigation graph endpoint

```text
GET /api/investigations/{id}/graph
```

Support filters for:

- time range;
- entity type;
- relationship type;
- result limit.

## 11.2 Implement pivot endpoint

```text
GET /api/investigations/{id}/graph/pivot
```

Inputs may include:

```text
entity
depth
start_time
end_time
relationship_type
```

## 11.3 Return evidence references

Graph responses must identify supporting event IDs.

## 11.4 Test multi-hop traversal

Verify:

```text
User
 ↓
Host
 ↓
Process
 ↓
Server
 ↓
File
```

can be returned as a connected investigation path.

## Done Criteria

- UI/API can retrieve a bounded graph.
- Pivot results are time- and type-filterable.
- Supporting evidence remains accessible.

---

# Task 12 — Implement Timeline Service

## 12.1 Build chronological event retrieval

```text
GET /api/investigations/{id}/timeline
```

## 12.2 Timeline fields

At minimum:

```text
timestamp
event_id
event_type
action
user
source_host
destination_host
process
file
source
```

## 12.3 Filtering

Support:

- time range;
- entity;
- event type;
- action.

## 12.4 Graph/timeline consistency

The same event IDs must appear in both graph evidence and timeline evidence.

## Done Criteria

- Events are shown in correct chronological order.
- Timeline selection can retrieve full evidence.
- Graph and timeline refer to the same underlying event records.

---

# Task 13 — Implement Evidence Detail Retrieval

## 13.1 Event detail endpoint

```text
GET /api/events/{event_id}
```

## 13.2 Response content

Return:

```text
event ID
normalized event
raw event
source
timestamp
extracted entities
derived relationships
correlation metadata
```

## 13.3 Ensure provenance

A graph edge selected by the analyst must resolve to supporting events.

## Done Criteria

- Every demonstrated graph edge can be traced to evidence.
- Raw/normalized views are available for supported fixtures.

---

# Task 14 — Build the Investigation Workspace Backend Contract

Before implementing the full frontend, stabilize the API contract required by the main investigation screen.

Required frontend data:

```text
investigation
graph
timeline
selected event
AI summary
analyst notes
status/outcome
```

Create response schemas so frontend components do not depend on arbitrary backend dictionary structures.

## Done Criteria

- Frontend can request all core workspace information using documented schemas.
- API responses remain stable across frontend implementation work.

---

# Task 15 — Implement React Investigation Workspace

## 15.1 Investigation list/page

Create a page that lists available investigations.

## 15.2 Investigation workspace

Create the primary workspace with:

```text
Header
Graph
Timeline
Evidence
AI Summary
Analyst Decision
```

## 15.3 Create graph component

Integrate Cytoscape.js.

Display different entity types distinctly.

Support:

- pan;
- zoom;
- node selection;
- edge selection;
- filtering;
- expansion/pivot.

## 15.4 Create timeline component

Support:

- chronological events;
- selection;
- filtering;
- evidence lookup.

## 15.5 Create evidence panel

Display normalized and source event data.

## 15.6 Create analyst decision panel

Support:

- notes;
- status;
- outcome.

## Done Criteria

- Analyst can load an investigation.
- Graph and timeline display the same investigation.
- Selecting graph/timeline items displays evidence.
- Analyst can record notes/status.

---

# Task 16 — Implement Graph/Timeline Synchronization

The graph and timeline are complementary views.

Required interactions:

```text
Click timeline event
        ↓
highlight/reveal supporting graph relationship

Click graph edge
        ↓
show supporting timeline event(s)

Click graph node
        ↓
filter or focus related timeline entries
```

The exact animation can be simple in the MVP; correctness and evidence linkage are more important.

## Done Criteria

- Selected event/relationship can be traced across graph and timeline.
- No interaction produces fabricated evidence.

---

# Task 17 — Implement AI Evidence Context Builder

## 17.1 Select relevant context

The backend should gather:

- investigation description;
- relevant timeline events;
- graph entities;
- relationship paths;
- correlation signals;
- evidence references.

## 17.2 Bound the context

Do not send unrestricted raw logs to the model.

Use only evidence relevant to the requested investigation/summary.

## 17.3 Define summary prompt contract

The summary instructions should explicitly require:

- evidence-grounded statements;
- chronological ordering;
- distinction between observation and interpretation;
- uncertainty when evidence is incomplete;
- event-reference preservation.

## Done Criteria

- A deterministic structured context object can be generated without the LLM.
- Context can be inspected for correctness before sending it to a model.

---

# Task 18 — Implement AI Summary Service

## 18.1 Create provider abstraction

Use a service interface so the application is not tied to one model provider.

Conceptual:

```python
class SummaryProvider:
    def generate_summary(self, context: InvestigationContext) -> str:
        ...
```

## 18.2 Generate summary

Input:

```text
InvestigationContext
```

Output:

```text
InvestigationSummary
```

## 18.3 Handle AI failure

If model generation fails:

```text
Graph remains available
Timeline remains available
Evidence remains available
Summary status = unavailable/error
```

## 18.4 Avoid hallucinated claims

Test prompts/outputs for:

- invented events;
- invented entities;
- unsupported maliciousness conclusions;
- missing uncertainty.

## Done Criteria

- A summary can be produced for the controlled scenario.
- Supporting event IDs are represented.
- Model failure does not break the rest of the investigation.

---

# Task 19 — Implement Analyst Notes and Decision Workflow

## 19.1 Notes

Allow creation/update of analyst notes.

## 19.2 Status

Implement:

```text
OPEN
UNDER_REVIEW
CLOSED
```

## 19.3 Outcome

Initial options:

```text
CONTINUE_INVESTIGATION
ESCALATE
CLOSE_AS_INVESTIGATED
```

These labels are workflow states, not machine classifications.

## Done Criteria

- Analyst can record a decision without overwriting AI output.
- Decision and notes persist with investigation metadata.

---

# Task 20 — Implement Security Controls

## 20.1 Authentication

Add authentication around protected APIs before production use.

## 20.2 Authorization

Ensure a user can only access investigations they are permitted to access.

## 20.3 Secrets

Use environment variables for:

```text
NEO4J_URI
NEO4J_USERNAME
NEO4J_PASSWORD
POSTGRES credentials
LLM API key
JWT secret
```

Do not commit real secrets.

## 20.4 Sensitive logs

Avoid logging full raw security-event payloads by default.

## Done Criteria

- Protected endpoints reject unauthenticated requests in production mode.
- Secrets are externalized.
- Unauthorized investigation access is denied.

---

# Task 21 — Implement Structured Error Handling

Create common error responses for:

```text
400 Validation Error
401 Authentication Error
403 Authorization Error
404 Resource Not Found
409 Business/State Conflict
422 Parsing/Schema Validation
500 Internal Error
503 Dependency Unavailable
```

AI and Neo4j failures must be distinguishable from malformed input.

## Done Criteria

- Frontend receives predictable errors.
- Backend logs sufficient diagnostic information without exposing sensitive data.

---

# Task 22 — Add Unit and Integration Tests

## 22.1 Schema tests

Test all event-validation branches.

## 22.2 Parser tests

Use representative fixtures.

## 22.3 Normalization tests

Test equivalent vendor fields.

## 22.4 Extraction tests

Test expected entities/relationships.

## 22.5 Correlation tests

Test both expected and unexpected links.

## 22.6 Graph tests

Verify:

```text
create
merge
query
pivot
evidence lookup
```

## 22.7 API tests

Test the investigation flow:

```text
create investigation
    ↓
ingest events
    ↓
process events
    ↓
retrieve graph
    ↓
retrieve timeline
    ↓
retrieve evidence
    ↓
generate summary
    ↓
record analyst outcome
```

## 22.8 End-to-End Scenario

Use a controlled sequence such as:

```text
10:00 Rahul logs into ENG-PC-27
10:02 ENG-PC-27 executes PowerShell
10:04 ENG-PC-27 connects to FIN-SRV-02
10:06 FIN-SRV-02 accesses FinancialReport.xlsx
```

Expected output:

```text
Rahul
  ↓ LOGGED_INTO
ENG-PC-27
  ↓ EXECUTED
PowerShell
  ↓ CONNECTED_TO
FIN-SRV-02
  ↓ ACCESSED
FinancialReport.xlsx
```

And timeline:

```text
10:00 Login
10:02 Process execution
10:04 Network connection
10:06 File access
```

## Done Criteria

- Tests pass.
- Every relationship in the controlled scenario has supporting event IDs.
- An unrelated fixture does not become part of the scenario accidentally.

---

# Task 23 — Containerized Local Environment

Create a reproducible local environment containing the core services required by the current implementation.

Expected service set:

```text
frontend
backend
neo4j
postgres
```

PostgreSQL is included when case/investigation metadata persistence is enabled.

## 23.1 Environment Configuration

Provide `.env.example` documenting:

```text
BACKEND_URL
FRONTEND_API_URL

NEO4J_URI
NEO4J_USERNAME
NEO4J_PASSWORD

POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_HOST

LLM_PROVIDER
LLM_API_KEY

JWT_SECRET
```

Do not place actual credentials in the file.

## 23.2 Service Startup

The environment must permit:

```text
docker compose up
```

followed by the documented application startup/check process.

## Done Criteria

- Neo4j is reachable.
- Backend is reachable.
- Backend can write/read the graph.
- Backend can store/read investigation metadata where PostgreSQL is enabled.
- Frontend can communicate with backend.

---

# Task 24 — API Documentation

Document:

```text
Investigation APIs
Evidence APIs
Graph APIs
Timeline APIs
Summary APIs
Analyst Decision APIs
```

For every endpoint document:

- purpose;
- request;
- parameters;
- response;
- error codes.

Provide OpenAPI/Swagger access.

## Done Criteria

- A developer can understand the backend contract without reading service code.
- Frontend implementation uses the documented API schemas.

---

# Task 25 — Performance Instrumentation

Before making scalability claims, add measurements.

Record:

```text
ingestion time
parsing time
normalization time
entity extraction time
relationship extraction time
correlation time
Neo4j write time
graph query time
timeline query time
AI generation time
```

Also measure event counts:

```text
input events
valid events
rejected events
entities
relationships
correlated links
```

## Done Criteria

- A controlled scenario produces a measurable processing report.
- Results can be compared between future implementations.

---

# Task 26 — Evaluation Dataset and Scenario Preparation

Prepare a small controlled dataset before using large public datasets.

## 26.1 Scenario A — Basic Login-to-File Sequence

```text
Login
→ Process Execution
→ Network Connection
→ File Access
```

## 26.2 Scenario B — Unrelated Events

Events are deliberately separated by:

- different user;
- different host;
- large time gap.

Expected result:

```text
No investigation relationship
```

## 26.3 Scenario C — Legitimate Access Context

Create a sequence that initially looks unusual but has a documented legitimate explanation.

Purpose:

- test that the system does not automatically call activity malicious;
- demonstrate why context and analyst review matter.

## 26.4 Scenario D — Multi-User / Multi-Host Investigation

Include multiple users and hosts with only a subset related.

Purpose:

- test graph filtering;
- test pivoting;
- test unrelated-event separation.

## Done Criteria

- All scenarios have expected outputs documented.
- Test data supports repeatable evaluation.

---

# Task 27 — Evaluate Correlation Quality

Measure:

### Expected relationships

Relationships that should be created according to the scenario specification.

### Unsupported relationships

Relationships that the rules created without sufficient evidence.

### Missed relationships

Relationships expected by the scenario that were not created.

Useful evaluation outputs:

```text
Expected relationships
Produced relationships
Correct relationships
Unsupported relationships
Missed relationships
```

Derived measurements may include precision/recall for relationship extraction if the scenario annotations are sufficiently well defined.

Do not claim system-wide security-detection accuracy from a small prototype dataset.

---

# Task 28 — Evaluate Investigation Utility

The primary benefit being evaluated is investigation assistance.

Possible measurements:

```text
time to reconstruct sequence
number of manual pivots
number of evidence sources checked
number of events inspected
```

A controlled comparison MAY be performed:

```text
Manual evidence review
vs.
Manual evidence review + TraceGraph
```

The methodology should define:

- participants;
- scenario;
- available evidence;
- task;
- completion criteria;
- time measurement;
- error measurement.

Only measured findings should be presented as claims.

---

# Task 29 — Validate AI Summary Grounding

For each controlled scenario:

1. Generate summary.
2. List each factual statement.
3. Map statements to source event IDs where possible.
4. Identify unsupported statements.
5. Check whether uncertainty was represented.
6. Confirm that the model did not invent entities/events.

Record:

```text
supported statements
unsupported statements
missing important evidence
incorrect statements
```

## Done Criteria

- Summary is traceable to evidence.
- Unsupported statements are identified before demonstration.

---

# Task 30 — End-to-End Demonstration

The final MVP demonstration should follow this flow:

```text
1. Create investigation
2. Load selected security evidence
3. Parse and normalize events
4. Extract entities
5. Extract relationships
6. Correlate events
7. Store graph
8. Open investigation workspace
9. Inspect graph
10. Inspect timeline
11. Click an entity/relationship
12. Inspect supporting evidence
13. Generate AI summary
14. Review uncertainty/context
15. Record analyst outcome
```

The demonstration should clearly communicate:

```text
Security evidence already exists
        ↓
TraceGraph organizes and connects it
        ↓
Graph shows relationships
Timeline shows sequence
Evidence panel shows proof
AI summarizes context
        ↓
Analyst makes the final decision
```

---

# Task 31 — Definition of Done

The TraceGraph MVP is considered complete when all of the following are true:

### Data Pipeline

- [ ] A defined source format can be ingested.
- [ ] Raw events are parsed.
- [ ] Events are normalized.
- [ ] Events pass common-schema validation.

### Investigation Logic

- [ ] Entities are extracted.
- [ ] Relationships are extracted.
- [ ] Relationships include evidence references.
- [ ] Temporal/contextual correlation works for controlled scenarios.
- [ ] Unrelated scenario events can remain separate.

### Graph

- [ ] Neo4j stores the investigation graph.
- [ ] Graph pivots work.
- [ ] Graph data can be filtered.
- [ ] Every displayed relationship can be traced to evidence.

### Timeline

- [ ] Chronological event timeline works.
- [ ] Timeline supports filtering.
- [ ] Timeline and graph refer to the same event IDs.

### Frontend

- [ ] Investigation workspace loads.
- [ ] Cytoscape graph renders.
- [ ] Timeline renders.
- [ ] Evidence details render.
- [ ] Analyst notes/outcome work.

### AI

- [ ] Structured context is built before LLM invocation.
- [ ] LLM can produce a summary.
- [ ] Summary remains evidence-grounded.
- [ ] LLM failure does not break the core investigation workflow.

### Reliability

- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] End-to-end controlled scenario passes.
- [ ] Error handling is implemented.
- [ ] Secrets are externalized.
- [ ] Deployment is reproducible.

### Evaluation

- [ ] Controlled datasets/scenarios exist.
- [ ] Correlation quality is measured.
- [ ] Evidence traceability is verified.
- [ ] Performance is measured.
- [ ] Any claim about investigation improvement is backed by evaluation.

---

# Task Dependency Summary

```text
Task 1  Common Event Schema
   ↓
Task 2  Evidence Input
   ↓
Task 3  Parsing
   ↓
Task 4  Normalization
   ↓
Task 5  Investigation Metadata
   ↓
Task 6  Entity Extraction
   ↓
Task 7  Relationship Extraction
   ↓
Task 8  Candidate Retrieval
   ↓
Task 9  Temporal Correlation
   ↓
Task 10 Neo4j
   ↓
Task 11 Graph API
   ↓
Task 12 Timeline
   ↓
Task 13 Evidence API
   ↓
Task 14 Workspace API Contract
   ↓
Task 15 React Workspace
   ↓
Task 16 Graph/Timeline Sync
   ↓
Task 17 AI Context
   ↓
Task 18 AI Summary
   ↓
Task 19 Analyst Workflow
   ↓
Task 20 Security
   ↓
Task 21 Error Handling
   ↓
Task 22 Testing
   ↓
Task 23 Deployment
   ↓
Task 24 API Documentation
   ↓
Task 25-29 Evaluation
   ↓
Task 30 Demonstration
   ↓
Task 31 Definition of Done
```
