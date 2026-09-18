# Requirements Document: TraceGraph

## 1. Introduction

**TraceGraph** is an AI-assisted, graph-based security investigation platform designed to help SOC analysts reconstruct incidents from scattered security evidence.

The system is positioned as an **investigation-assistance layer**, not as a replacement for a SIEM, EDR, IDS/IPS, or the SOC analyst. Existing security platforms and log sources may detect suspicious activity and provide relevant evidence; TraceGraph receives a selected set of that evidence, converts it into a common structure, identifies entities and relationships, correlates related events over time, and presents the resulting investigation context as an interactive graph and chronological timeline.

The primary goal is to reduce the manual effort required to answer questions such as:

- What happened before and after an alert?
- Which user, host, process, server, IP, or file is connected to this event?
- Are several apparently separate events part of the same activity sequence?
- What evidence supports or contradicts the current investigation hypothesis?
- Is there a legitimate explanation for the observed activity?
- What sequence of events should the analyst examine next?

The first implementation focuses on an organization's internal enterprise environment and selected event categories: authentication, endpoint/process activity, network connections, and file access. The initial demonstration scenario emphasizes lateral-movement-style investigation because it naturally produces relationship chains such as:

`User → Endpoint → Process → Network Destination → Server → File/Resource`

TraceGraph must preserve the original evidence and its provenance so that graph relationships and AI-generated summaries can always be traced back to source events. The analyst remains responsible for the final interpretation, escalation, or closure of an investigation.

---

## 2. Goals

TraceGraph shall:

1. Accept selected security evidence from multiple possible sources without requiring a specific SIEM vendor.
2. Parse raw security events into structured fields.
3. Normalize vendor-specific field names into a common event schema.
4. Validate normalized events before they enter the investigation pipeline.
5. Extract relevant entities such as users, hosts, IP addresses, processes, servers, and files.
6. Extract explicit relationships such as login, process execution, network connection, authentication, and file access.
7. Correlate events using explainable temporal and contextual rules.
8. Build an investigation graph in Neo4j.
9. Provide a chronological timeline of correlated events.
10. Allow the analyst to pivot from graph entities to supporting evidence.
11. Generate an evidence-grounded AI/LLM incident summary.
12. Keep the analyst in control of the final decision.
13. Preserve evidence references and correlation metadata so that the investigation remains auditable.
14. Provide a reproducible prototype that can be demonstrated with controlled scenarios and/or public security datasets.

TraceGraph shall **not** claim that graph visualization alone detects attacks, that every correlated event is malicious, or that the system replaces established security monitoring platforms.

---

## 3. Glossary

- **System**: The TraceGraph investigation platform as a whole.
- **Investigation**: A bounded analysis session containing a set of security evidence, a graph, a timeline, analyst observations, and an optional conclusion.
- **Evidence_Source**: A source from which security events originate, such as an SIEM export, EDR export, Sysmon data, firewall/network telemetry, authentication logs, direct application/system logs, a public dataset, or a controlled simulation.
- **Raw_Event**: An event in its source-specific/original format before normalization.
- **Parser**: A component that reads a raw event and extracts meaningful fields from it.
- **Normalization**: Mapping source-specific fields and representations into the common TraceGraph event schema.
- **SecurityEvent**: The validated internal representation of a security event.
- **Entity**: An identifiable object represented in the investigation graph, such as User, Host, IP, Process, Server, or File.
- **Relationship**: A directed relationship between entities supported by one or more events.
- **Correlation**: The process of determining whether separate events are meaningfully related based on shared context, temporal proximity, and compatible activity.
- **Correlation_Signal**: An explainable factor contributing to a relationship, such as shared user, shared host, host continuity, or temporal proximity.
- **Relationship_Strength**: A configurable representation of how strongly the available evidence supports a relationship. It is not an attack probability or maliciousness score.
- **Investigation_Graph**: The Neo4j representation of entities and evidence-backed relationships.
- **Timeline**: Chronological presentation of correlated events for an investigation.
- **Evidence_Reference**: A pointer to the originating event or source record supporting a graph entity/relationship.
- **Pivot**: Moving from one entity or event to related entities/events to expand or narrow an investigation.
- **Correlation_Window**: The time range within which candidate events are considered for correlation.
- **Case_Metadata**: Investigation information that is not itself part of the graph, such as case ID, title, status, analyst notes, timestamps, and source information.
- **LLM_Summary**: An AI-generated narrative derived from selected structured evidence and graph/timeline context.
- **Human_Decision**: The analyst's final interpretation, escalation, continuation, or closure decision.
- **Source_Agnostic**: Designed so that the investigation engine does not depend on one specific SIEM/EDR vendor.

---

# 4. Functional Requirements

## Requirement 1: Investigation Creation

**User Story:** As a SOC analyst, I want to create an investigation around a defined set of security evidence, so that related events can be analyzed within one bounded context.

### Acceptance Criteria

1. WHEN an analyst creates an investigation with a valid title, THE System SHALL create an investigation record with a unique identifier.
2. WHEN an investigation is created, THE System SHALL record its creation timestamp.
3. THE System SHALL support investigation states at minimum: `OPEN`, `UNDER_REVIEW`, and `CLOSED`.
4. WHEN an investigation is opened, THE System SHALL allow evidence to be associated with it.
5. THE System SHALL keep investigation metadata separate from the underlying graph entities.
6. THE System SHALL allow an investigation to contain events from more than one evidence source.
7. THE System SHALL not require all events to originate from the same vendor or tool.

---

## Requirement 2: Security Evidence Input

**User Story:** As a SOC analyst, I want TraceGraph to accept security evidence from different sources, so that the investigation engine is not tied to one monitoring platform.

### Acceptance Criteria

1. THE System SHALL accept structured security-event input in JSON format for the initial implementation.
2. THE System MAY support CSV input through an adapter without changing the internal investigation pipeline.
3. THE System SHALL treat SIEM, EDR, Sysmon, authentication logs, network telemetry, direct host logs, datasets, and controlled simulations as possible upstream sources.
4. THE System SHALL record the originating source type for each accepted event.
5. THE System SHALL preserve the original raw event representation when available.
6. THE investigation engine SHALL operate on the normalized common event schema rather than directly on vendor-specific fields.
7. THE System SHALL not require Splunk as a runtime dependency.
8. A source adapter SHALL be responsible only for converting source data into the common event representation and SHALL not contain investigation-specific business logic.

---

## Requirement 3: Raw Event Parsing

**User Story:** As an analyst, I want raw events converted into structured fields, so that TraceGraph can process them consistently.

### Acceptance Criteria

1. WHEN a raw event is received, THE Parser SHALL identify fields required by the applicable source format.
2. THE Parser SHALL extract available timestamps, event identifiers, event type, action, users, hosts, IP addresses, processes, and files where present.
3. THE Parser SHALL preserve unrecognized source fields under the raw-data portion of the event where practical.
4. WHEN a required field cannot be parsed, THE Parser SHALL return a structured parsing error rather than silently inventing a value.
5. THE Parser SHALL distinguish between a missing field and a field whose value is explicitly null or empty.
6. THE Parser SHALL attach source information to the parsed event.
7. Parsing SHALL occur before normalization and correlation.

---

## Requirement 4: Event Normalization

**User Story:** As a developer, I want events from different sources represented using common field names and formats, so that the downstream engine can remain source-agnostic.

### Acceptance Criteria

1. THE Normalization_Service SHALL map vendor-specific fields to the common TraceGraph schema.
2. Equivalent fields such as `UserName`, `AccountName`, and `user` SHALL be normalized to the internal `user` field when appropriate.
3. Timestamps SHALL be converted into a consistent timezone representation; the preferred storage representation is UTC.
4. Host, IP, process, and file identifiers SHALL be normalized consistently enough for correlation.
5. THE System SHALL retain the original source field mapping where practical so analysts can inspect provenance.
6. Normalization SHALL NOT infer a maliciousness verdict.
7. Normalization SHALL NOT create relationships by itself.
8. An event SHALL not enter the correlation stage until normalization and schema validation succeed.

---

## Requirement 5: Common Security Event Schema

**User Story:** As the investigation engine, I need a stable internal event model, so that every later stage operates on predictable data.

### Acceptance Criteria

1. THE System SHALL define a validated `SecurityEvent` model.
2. THE model SHALL include at minimum:
   - `event_id`
   - `timestamp`
   - `event_type`
   - `action`
   - `user`
   - `source_host`
   - `destination_host`
   - `source_ip`
   - `destination_ip`
   - `process`
   - `file`
   - `severity`
   - `raw_data`
3. Optional fields SHALL be represented as nullable rather than filled with fabricated placeholders.
4. THE System SHALL validate timestamp format and event identity.
5. THE System SHALL reject structurally invalid events before graph construction.
6. THE System SHALL permit event-type-specific fields to be absent when they are not applicable.
7. THE schema SHALL support future extension without breaking existing events.

---

## Requirement 6: Entity Extraction

**User Story:** As an analyst, I want important entities extracted from events, so that I can see who, what, and where were involved in the activity.

### Acceptance Criteria

1. THE Entity_Extraction_Service SHALL extract supported entity types from normalized events.
2. Initial entity types SHALL include:
   - User
   - Host
   - Server
   - IP
   - Process
   - File
3. THE System SHALL preserve the source event ID for every extracted entity occurrence.
4. THE System SHALL avoid creating duplicate graph nodes for the same normalized entity within one investigation when identity can be established.
5. Entity identity rules SHALL be explicit and configurable rather than hidden inside visualization code.
6. The extraction stage SHALL not classify an entity as malicious or benign.
7. THE System SHALL support entities that occur in multiple events and multiple relationships.

---

## Requirement 7: Relationship Extraction

**User Story:** As an analyst, I want relationships between entities extracted from events, so that the investigation can be represented as an activity graph.

### Acceptance Criteria

1. THE Relationship_Extraction_Service SHALL create only relationships supported by event evidence.
2. Initial relationship types SHALL include:
   - `LOGGED_INTO`
   - `AUTHENTICATED_TO`
   - `EXECUTED`
   - `CONNECTED_TO`
   - `ACCESSED`
3. A relationship SHALL retain at minimum:
   - relationship type
   - source entity
   - destination entity
   - timestamp
   - supporting event ID
4. Example event:
   `user=Rahul, host=ENG-PC-27, action=login`
   MAY produce:
   `Rahul LOGGED_INTO ENG-PC-27`
5. Example event:
   `host=ENG-PC-27, process=powershell.exe, action=execute`
   MAY produce:
   `ENG-PC-27 EXECUTED powershell.exe`
6. Relationship extraction SHALL not automatically label the relationship as an attack.
7. When a relationship is supported by multiple events, THE System SHOULD preserve all relevant supporting event references rather than discarding evidence.

---

## Requirement 8: Temporal Event Correlation

**User Story:** As an analyst, I want related events grouped using time and context, so that scattered logs can be reconstructed into an activity sequence.

### Acceptance Criteria

1. THE Correlation_Service SHALL consider temporal proximity as one signal when evaluating candidate relationships.
2. THE default prototype correlation window SHALL be configurable and MAY use 10 minutes as the initial baseline.
3. THE Correlation_Service SHALL consider shared context such as:
   - shared user
   - shared host
   - shared IP
   - host continuity
   - compatible event/action sequence
   - related process or file context where applicable
4. THE Correlation_Service SHALL produce explainable correlation metadata indicating which signals supported a relationship.
5. THE Correlation_Service SHALL not treat temporal proximity alone as sufficient evidence of an attack.
6. THE Correlation_Service SHALL not assign fixed universal cyber weights without evaluation.
7. Any numerical relationship-strength representation SHALL describe evidence support for the relationship and SHALL NOT be presented as an attack probability.
8. Candidate retrieval and relationship-correlation logic SHALL remain separate so that event retrieval can be optimized independently from correlation rules.
9. THE System SHALL allow correlation rules and thresholds to be tuned through configuration or code without rewriting the graph layer.

---

## Requirement 9: Investigation Graph

**User Story:** As an analyst, I want correlated entities and relationships stored as a graph, so that I can understand connections that are difficult to see in isolated logs.

### Acceptance Criteria

1. THE System SHALL store the investigation graph in Neo4j.
2. THE graph SHALL represent supported entities as nodes.
3. THE graph SHALL represent evidence-backed relationships as directed edges.
4. Relationships SHALL retain timestamps and supporting event references.
5. THE graph SHALL support multiple relationships between the same entities when they occur at different times or arise from different evidence.
6. THE graph SHALL support traversal from any supported entity to related entities.
7. THE System SHALL allow filtering of graph results by investigation, time range, entity type, and relationship type where applicable.
8. Graph persistence SHALL not modify the original raw evidence.
9. A graph view SHALL remain traceable to source events.

---

## Requirement 10: Investigation Graph Querying and Pivots

**User Story:** As an analyst, I want to pivot through related entities, so that I can expand an investigation from one alert or event.

### Acceptance Criteria

1. THE System SHALL allow an analyst to select an entity and retrieve related entities.
2. THE System SHALL support time-bounded graph traversal.
3. THE System SHALL support relationship-type filtering.
4. THE System SHALL support entity-type filtering.
5. THE System SHALL expose the supporting event references behind retrieved relationships.
6. THE System SHALL distinguish direct relationships from multi-hop traversal results.
7. The System MAY use graph traversal algorithms such as BFS for navigation after the graph has been constructed; traversal SHALL not be treated as attack detection logic.
8. Pivoting SHALL not alter evidence or correlation results.

---

## Requirement 11: Investigation Timeline

**User Story:** As an analyst, I want a chronological timeline alongside the graph, so that I can understand the order in which activities occurred.

### Acceptance Criteria

1. THE System SHALL present correlated events in chronological order.
2. THE timeline SHALL show at minimum timestamp, event type, action, involved entities, and event ID/reference.
3. THE timeline SHALL support filtering by time range.
4. THE timeline SHALL support filtering by entity where practical.
5. Selecting a timeline event SHALL reveal the evidence associated with it.
6. The timeline SHALL preserve event order based on normalized timestamps.
7. The timeline SHALL make clear which entries are source events and which entries are derived relationships or summaries.

---

## Requirement 12: Evidence Context and Provenance

**User Story:** As an analyst, I want every graph relationship and AI summary claim traceable to evidence, so that I can verify the investigation rather than blindly trust automation.

### Acceptance Criteria

1. THE System SHALL retain event IDs for derived relationships.
2. THE System SHALL allow an analyst to inspect the raw or normalized representation of a supporting event.
3. THE System SHALL display the evidence source where available.
4. THE System SHALL record correlation signals used to form derived relationships.
5. THE System SHALL not remove or overwrite the original evidence as a result of normalization.
6. THE AI summary pipeline SHALL receive evidence that can be mapped back to source events.
7. THE System SHALL make it possible to identify whether a statement is source evidence, derived correlation, or AI-generated narrative.

---

## Requirement 13: AI-Assisted Incident Summary

**User Story:** As an analyst, I want an AI-generated summary of the investigated evidence, so that I can quickly understand the reconstructed activity sequence without manually reading every event.

### Acceptance Criteria

1. THE AI_Service SHALL generate a summary from selected structured evidence, graph context, and timeline context.
2. THE AI_Service SHALL not be treated as the primary attack-detection mechanism in the initial implementation.
3. THE AI_Service SHALL receive only investigation-relevant evidence selected by the system rather than an unrestricted dump of all raw logs.
4. THE generated summary SHOULD identify:
   - the entities involved
   - the chronological sequence
   - the important relationships
   - supporting evidence references
   - notable context
   - unresolved uncertainty
5. THE AI_Service SHALL not state that activity is malicious unless the supplied evidence and system context support such a statement; where evidence is insufficient, the summary SHALL express uncertainty.
6. THE AI_Service SHOULD distinguish observed facts from interpretation.
7. THE System SHALL retain the evidence/context used to produce a summary for auditability.
8. An analyst SHALL be able to inspect the evidence behind the generated narrative.
9. AI output SHALL not automatically close, escalate, or declare an incident without analyst action.

---

## Requirement 14: Human Analyst Decision

**User Story:** As a SOC analyst, I want the system to assist rather than replace my judgment, so that the final investigation decision remains under analyst control.

### Acceptance Criteria

1. THE System SHALL allow the analyst to review graph, timeline, and supporting evidence before making a final decision.
2. THE System SHALL allow an analyst to record an investigation outcome or note.
3. THE System SHALL support at minimum:
   - continue investigation
   - escalate
   - close as investigated
4. The exact operational workflow MAY be expanded after the MVP.
5. The System SHALL not automatically declare normal or malicious activity solely from graph structure.
6. The System SHALL preserve analyst-entered notes separately from machine-generated summaries.

---

## Requirement 15: Investigation Interface

**User Story:** As an analyst, I want one workspace combining graph, timeline, evidence, and summary information, so that I do not need to manually switch between unrelated views.

### Acceptance Criteria

1. THE frontend SHALL provide a dedicated investigation workspace.
2. THE workspace SHALL include:
   - investigation header/context
   - graph visualization
   - timeline
   - evidence/event details
   - AI summary area
3. Selecting a graph node SHALL provide access to its related events.
4. Selecting a graph relationship SHALL expose its supporting evidence.
5. Selecting a timeline event SHALL provide the same evidence context where applicable.
6. The interface SHALL support loading and error states for backend requests.
7. The interface SHALL clearly distinguish generated content from source evidence.

---

## Requirement 16: Input Validation and Data Integrity

**User Story:** As a system operator, I want malformed and inconsistent events rejected or quarantined, so that invalid data does not silently distort the investigation.

### Acceptance Criteria

1. THE System SHALL validate event IDs, timestamps, and supported field types at the API boundary.
2. THE System SHALL reject events with structurally invalid required fields.
3. THE System SHALL return structured error information for validation failures.
4. THE System SHALL distinguish parsing failures from schema-validation failures.
5. THE System SHALL not fabricate missing users, hosts, IPs, processes, or files.
6. THE System SHALL preserve raw input separately from normalized values.
7. A failed event SHALL not create a partial graph relationship.

---

## Requirement 17: Security, Privacy, and Access Control

**User Story:** As a system operator, I want investigation data protected, because security logs can contain sensitive enterprise information.

### Acceptance Criteria

1. THE System SHALL require authentication for protected investigation APIs in production deployments.
2. THE System SHALL prevent unauthorized users from reading investigation evidence.
3. THE System SHALL not expose secrets, database credentials, or LLM API keys in source code.
4. THE System SHALL externalize environment-specific secrets through environment variables or equivalent secret management.
5. THE System SHALL avoid logging sensitive raw event payloads unnecessarily.
6. THE System SHALL apply least-privilege access to Neo4j and PostgreSQL credentials where applicable.
7. THE System SHALL use HTTPS for production client-to-server communication.
8. Raw evidence retained by the system SHALL be treated as sensitive security data.
9. Data retention and deletion behavior SHALL be configurable for the deployment environment.

---

## Requirement 18: Error Handling

**User Story:** As an API consumer, I want consistent errors, so that parsing, correlation, graph, and AI failures can be handled without ambiguous responses.

### Acceptance Criteria

1. THE System SHALL return structured errors for invalid requests.
2. Parsing failures SHALL identify the affected event where possible.
3. Correlation failures SHALL not corrupt successfully processed events.
4. Graph database failures SHALL be surfaced as infrastructure/service errors rather than silently ignored.
5. AI-service failures SHALL not prevent analysts from accessing graph and timeline evidence already built.
6. Unexpected internal failures SHALL be logged server-side without returning stack traces to clients.
7. The API SHALL use consistent HTTP status conventions.

---

## Requirement 19: Performance and Scalability

**User Story:** As a system architect, I want the investigation pipeline to remain usable as event volume increases, so that the prototype can evolve beyond a small demonstration.

### Acceptance Criteria

1. THE System SHALL process events in bounded batches rather than requiring the entire source dataset to remain in application memory when practical.
2. THE System SHALL use indexed or constrained queries for frequent event retrieval operations.
3. THE System SHALL avoid loading an unrestricted graph when an analyst requests a small pivot.
4. THE System SHALL support time-bounded and entity-bounded graph queries.
5. THE System SHALL keep AI context bounded to the evidence relevant to the current investigation.
6. The prototype SHALL record processing times for parsing, correlation, graph persistence, and summary generation to support evaluation.
7. Performance targets SHALL be established after measuring representative event sizes and hardware conditions rather than invented without baseline evidence.

---

## Requirement 20: API Design and Documentation

**User Story:** As a developer integrating TraceGraph, I want a documented API so that each pipeline stage and frontend feature can be tested independently.

### Acceptance Criteria

1. THE System SHALL expose documented REST endpoints for the core investigation workflow.
2. The initial endpoint groups SHALL cover:
   - investigation creation/retrieval
   - evidence ingestion
   - event retrieval
   - graph retrieval/pivoting
   - timeline retrieval
   - AI summary generation
   - analyst decision/notes
3. THE API SHALL define request and response schemas.
4. THE API SHALL return documented HTTP status codes.
5. THE API SHALL expose machine-readable OpenAPI documentation.
6. API documentation SHALL identify required and optional fields.

---

## Requirement 21: Testing

**User Story:** As a developer, I want automated tests around each investigation stage, so that changes do not silently break correlation or evidence traceability.

### Acceptance Criteria

1. THE System SHALL include unit tests for the common event schema and validation.
2. THE System SHALL include parser tests using representative raw event samples.
3. THE System SHALL include normalization tests covering vendor-field mappings.
4. THE System SHALL include entity-extraction tests.
5. THE System SHALL include relationship-extraction tests.
6. THE System SHALL include correlation tests covering:
   - shared user
   - shared host
   - host continuity
   - temporal proximity
   - compatible event sequences
   - unrelated events that should remain separate
7. THE System SHALL include Neo4j integration tests for graph creation and retrieval.
8. THE System SHALL include API integration tests covering evidence ingestion through graph/timeline retrieval.
9. THE System SHALL test AI-summary input construction independently from the external model provider.
10. THE System SHALL verify that every derived relationship remains traceable to source event IDs.
11. THE test suite SHALL include at least one controlled end-to-end investigation scenario.

---

## Requirement 22: Deployment and Reproducibility

**User Story:** As a development team, we want the complete TraceGraph stack reproducible across machines, so that the project can be demonstrated and evaluated consistently.

### Acceptance Criteria

1. THE System SHALL provide containerized services for the core runtime where appropriate.
2. THE deployment configuration SHALL include the FastAPI backend and Neo4j.
3. PostgreSQL SHALL be included when case metadata persistence is enabled.
4. Environment-specific secrets SHALL be supplied through environment variables.
5. THE System SHALL provide an `.env.example` describing required configuration values without containing real secrets.
6. THE System SHALL expose required service ports through documented configuration.
7. THE deployment SHALL allow the frontend to connect to the backend through configurable API URLs.
8. A clean environment SHALL be able to start the required services using the documented deployment process.

---

## Requirement 23: Evaluation and Success Criteria

**User Story:** As a project team, we want measurable evidence that TraceGraph helps investigation work, so that project claims are based on evaluation rather than assumption.

### Acceptance Criteria

1. THE project SHALL evaluate whether evidence-backed graph reconstruction can represent the known event sequence of controlled scenarios.
2. THE evaluation SHALL verify whether expected entities and relationships are extracted correctly.
3. THE evaluation SHALL measure correlation errors, including unsupported relationships and missed expected relationships.
4. THE evaluation SHALL verify that every graph relationship can be traced back to supporting evidence.
5. THE evaluation SHALL measure investigation processing time for representative scenarios.
6. THE evaluation MAY compare analyst workflow with and without graph/timeline assistance if participants and methodology are available.
7. THE project SHALL clearly distinguish measured results from proposed benefits.
8. Claims such as "reduces investigation time" SHALL only be made after suitable evaluation.

---

# 5. Initial Data Model

The initial normalized event representation SHALL conceptually contain:

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

The schema is intentionally small for the first implementation. It can be extended after representative data sources and scenarios are validated.

---

# 6. Primary Investigation Scenario

The primary prototype scenario is an enterprise investigation containing a sequence such as:

1. User authenticates to an engineering endpoint.
2. A process executes on that endpoint.
3. The endpoint connects to a finance server.
4. A resource or file is accessed.
5. Additional authentication or network activity provides context.

A conceptual evidence chain is:

```text
Rahul
  │
  │ LOGGED_INTO
  ▼
ENG-PC-27
  │
  │ EXECUTED
  ▼
PowerShell
  │
  │ CONNECTED_TO
  ▼
FIN-SRV-02
  │
  │ ACCESSED
  ▼
FinancialReport.xlsx
```

The existence of this chain SHALL NOT by itself be treated as proof of compromise. The investigation must preserve the evidence and allow legitimate explanations or contradictory evidence to be considered.

---

# 7. Initial Scope

## In Scope

- Enterprise/internal security investigations.
- Authentication events.
- Endpoint/process events.
- Network connection events.
- File-access events.
- JSON-based evidence ingestion.
- Source-specific parsing adapters.
- Common event normalization.
- Entity extraction.
- Relationship extraction.
- Explainable rule-based temporal correlation.
- Neo4j investigation graph.
- Graph pivots and filtering.
- Chronological event timeline.
- Evidence/provenance display.
- AI-assisted evidence-grounded summaries.
- Analyst notes and investigation outcome.
- FastAPI backend.
- React.js frontend.
- Cytoscape.js graph visualization.
- Docker-based reproducibility.
- Automated tests and controlled evaluation.

## Out of Scope for the Initial MVP

- Replacing a SIEM.
- Replacing an EDR.
- Building a complete detection engine.
- Autonomous incident response.
- Automatic malicious/benign classification as the central feature.
- Universal support for every log format.
- Universal correlation weights claimed to work across organizations.
- Real-time enterprise-scale deployment guarantees without measurement.
- Mandatory GNN/GCN/GraphSAGE/GAT models.
- Automatic containment or remediation.
- Automatic analyst decision-making.

---

# 8. Future Scope

| Feature | Description |
|---|---|
| Additional Source Adapters | Add adapters for more SIEM, EDR, firewall, authentication, cloud, and endpoint formats. |
| Advanced Temporal Correlation | Introduce richer temporal pattern matching after baseline rule evaluation. |
| Learned Graph Models | Experiment with GNN/TGNN approaches for research-oriented relationship or attack-path analysis. |
| Attack-Path Analytics | Analyze longer multi-hop activity patterns across enterprise entities. |
| Investigation Templates | Provide reusable workflows for scenarios such as lateral movement and credential misuse. |
| Streaming Ingestion | Process continuous event streams rather than batch evidence. |
| Expanded Entity Model | Add accounts, sessions, registry objects, services, containers, cloud resources, and other entities as justified by datasets. |
| Analyst Feedback Loop | Use analyst-confirmed relationships and investigation outcomes to improve future correlation. |
| Advanced AI Assistance | Add evidence retrieval, hypothesis comparison, and structured investigation questions while preserving analyst control. |
| Graph-Based Risk Research | Explore learned relationship scoring or graph anomaly detection as a separate research extension. |

---
