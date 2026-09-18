# Requirements Document

## Introduction

TraceGraph is a modular security investigation platform that converts scattered security evidence — logs, alerts, and telemetry from disparate sources — into a structured, explainable investigation context. The system ingests raw security events, extracts entities and typed relationships, correlates events temporally through named rule-based signals, persists the result as a traversable graph in Neo4j, and surfaces that context through a React investigation workspace with an optional AI-assisted narrative summary.

The platform is designed for explainability first: every relationship traces back to concrete evidence, every correlation signal is named and inspectable, and the AI summary layer is constrained to only what the evidence actually contains. Analysts retain full control — they can pivot through the graph, annotate findings, and record investigation outcomes. The system degrades gracefully if any component (including AI) is unavailable.

---

## Glossary

- **TraceGraph**: The complete security investigation platform described in this document.
- **API**: The FastAPI HTTP backend that accepts requests and orchestrates the processing pipeline.
- **Pipeline**: The sequential processing chain: ingest → parse → normalize → validate → extract → correlate → persist → query → summarize.
- **Ingestion_API**: The FastAPI endpoint layer responsible for accepting raw security events.
- **Parser**: A source-type-specific adapter that converts raw event dicts into `ParsedEvent` objects.
- **Adapter_Registry**: The registry that maps `source_type` strings to their corresponding Parser implementations.
- **Normalization_Engine**: The component that maps parsed fields to the Common Security Event Model and canonicalizes identifiers.
- **SecurityEvent**: The common, normalized representation of a security event (the Common Security Event Model).
- **Entity_Extractor**: The component that identifies and deduplicates security entities from normalized events.
- **Relationship_Extractor**: The component that derives typed relationships between entities from event semantics.
- **Candidate_Retrieval**: The component that identifies temporally proximate event pairs as candidates for correlation.
- **Correlation_Engine**: The temporal correlation engine that evaluates candidate pairs against named signals.
- **Graph_Repository**: The Neo4j persistence layer for entities and relationships.
- **Graph_Service**: The query and traversal layer over Neo4j.
- **Timeline_Service**: The chronological event retrieval service for a given investigation.
- **Evidence_Service**: The service that returns full evidence records for individual events.
- **AI_Context_Builder**: The component that assembles a bounded, structured investigation context for the AI layer.
- **AI_Summary_Service**: The component that generates evidence-grounded narrative summaries using an LLM.
- **Investigation_Service**: The CRUD and lifecycle management service for investigation metadata.
- **Workspace**: The React investigation workspace, consisting of Graph Panel, Timeline Panel, Evidence Panel, AI Summary Panel, and Analyst Decision Panel.
- **Graph_Panel**: The Cytoscape.js-based graph visualization component within the Workspace.
- **Timeline_Panel**: The chronological event list component within the Workspace.
- **Evidence_Panel**: The component that displays full evidence detail for a selected event.
- **AI_Summary_Panel**: The component that displays the AI-generated narrative summary.
- **Analyst_Decision_Panel**: The component through which analysts record outcomes and notes.
- **Investigation**: A named investigation case with lifecycle status (OPEN, UNDER_REVIEW, CLOSED).
- **Entity**: A deduplicated security entity of one of six types: User, Host, Server, IP, Process, File.
- **Relationship**: A typed, evidence-backed directed connection between two entities (LOGGED_INTO, AUTHENTICATED_TO, EXECUTED, CONNECTED_TO, ACCESSED).
- **Correlation_Signal**: A named rule evaluated between two candidate events to determine if they are meaningfully related.
- **Combined_Score**: A weighted sum of fired correlation signals, normalized to [0, 1]. Explicitly NOT an attack probability.
- **CandidatePair**: Two events within the configured time window that are candidates for temporal correlation.
- **CorrelatedRelationship**: A relationship produced by the Correlation_Engine, carrying signal names, scores, and a human-readable explanation.
- **ParsedEvent**: The intermediate representation produced by a Parser before normalization.
- **EvidenceDetail**: The full record for a single event, including normalized fields, raw_data, entities, relationships, and correlation metadata.
- **InvestigationContext**: The bounded, structured context assembled by the AI_Context_Builder for the AI_Summary_Service.
- **SummaryResult**: The structured output of the AI_Summary_Service, including overview, evidence references, uncertainty statement, and error status.
- **JWT**: JSON Web Token used for authentication on all API endpoints.
- **PostgreSQL**: The relational database storing investigation metadata and normalized security events.
- **Neo4j**: The graph database storing entities, relationships, and correlation data.
- **Docker_Compose**: The container orchestration configuration for local deployment.

---

## Requirements

### Requirement 1: Evidence Ingestion

**User Story:** As a security analyst, I want to ingest raw security events from multiple source types into an investigation, so that I can consolidate evidence from disparate security tools into a single context.

#### Acceptance Criteria

1. WHEN a client submits a single raw event to `POST /api/investigations/{id}/events`, THE Ingestion_API SHALL validate that the investigation exists before processing the event.
2. IF the referenced investigation does not exist, THEN THE Ingestion_API SHALL return HTTP 404 with error code `INVESTIGATION_NOT_FOUND` and SHALL NOT process the event.
3. WHEN a client submits a single raw event with a valid `source_type`, THE Ingestion_API SHALL route the event to the corresponding Parser via the Adapter_Registry and return an `IngestionResponse` with `accepted=1`.
4. WHEN a client submits a batch of raw events to `POST /api/investigations/{id}/events/batch`, THE Ingestion_API SHALL process each event independently and return an `IngestionResponse` where `accepted + rejected` equals the total number of submitted events.
5. IF one or more events in a batch fail parsing or validation, THEN THE Ingestion_API SHALL continue processing the remaining events and include each failure in `IngestionResponse.errors` with a field-level reason.
6. IF the `source_type` field is not registered in the Adapter_Registry, THEN THE Ingestion_API SHALL reject the entire batch immediately with error code `INVALID_SOURCE_TYPE` and SHALL NOT partially process any events.
7. THE Ingestion_API SHALL enforce investigation ownership via authorization middleware before processing any event.
8. THE Ingestion_API SHALL support the following `source_type` values: `siem`, `edr`, `sysmon`, `auth`, `network`, `public_dataset`.

---

### Requirement 2: Parsing Pipeline

**User Story:** As a developer, I want raw security events from different source types to be parsed into a common intermediate representation, so that the normalization stage receives consistently structured input regardless of the original log format.

#### Acceptance Criteria

1. WHEN a raw event dict is passed to a Parser, THE Parser SHALL return a `ParsedEvent` with all recognized fields populated and all unrecognized fields preserved in `extra_fields`.
2. THE Parser SHALL preserve the original `event_id` value from the raw event unchanged in the `ParsedEvent`.
3. IF a raw event cannot be parsed, THEN THE Parser SHALL return a `ParseError` with the field name and reason and SHALL NOT raise an exception.
4. THE Parser SHALL NOT mutate the input raw event dict during parsing.
5. WHEN a `source_type` is registered in the Adapter_Registry, THE Adapter_Registry SHALL dispatch parsing to exactly the registered Parser for that `source_type`.
6. THE Adapter_Registry SHALL support runtime registration of new Parser adapters without requiring code changes to the registry itself.

---

### Requirement 3: Normalization Engine

**User Story:** As a developer, I want parsed events to be normalized to a Common Security Event Model with canonical field names, UTC timestamps, and standardized identifiers, so that downstream components operate on consistent, well-typed data.

#### Acceptance Criteria

1. WHEN a `ParsedEvent` is passed to the Normalization_Engine, THE Normalization_Engine SHALL return a `SecurityEvent` with `timestamp` as a UTC-aware ISO-8601 datetime.
2. IF the `timestamp_raw` field of a `ParsedEvent` cannot be parsed to a datetime, THEN THE Normalization_Engine SHALL reject the event with a `VALIDATION_ERROR`.
3. WHEN normalizing a `ParsedEvent`, THE Normalization_Engine SHALL lowercase all `source_host` and `destination_host` values.
4. WHEN normalizing a `ParsedEvent`, THE Normalization_Engine SHALL strip domain prefixes (e.g., `DOMAIN\user` or `user@domain`) from username fields.
5. WHEN normalizing a `ParsedEvent`, THE Normalization_Engine SHALL convert IP address fields to dotted-decimal IPv4 or compressed IPv6 notation.
6. THE Normalization_Engine SHALL store the original parsed fields unmodified in `SecurityEvent.raw_data`.
7. THE Normalization_Engine SHALL preserve the `event_id` value from the `ParsedEvent` unchanged in the resulting `SecurityEvent`.
8. WHEN a `SecurityEvent` is validated, THE Normalization_Engine SHALL enforce that `severity`, if present, is one of: `low`, `medium`, `high`, `critical`.
9. THE Normalization_Engine SHALL use configurable field-name mapping tables and SHALL NOT hardcode source-specific field mappings.

---

### Requirement 4: Entity Extraction

**User Story:** As a security analyst, I want security entities (users, hosts, servers, IPs, processes, files) to be automatically extracted and deduplicated from normalized events, so that I can see a clean entity graph without manual data entry.

#### Acceptance Criteria

1. WHEN `extract_entities` is called on a list of `SecurityEvent` objects, THE Entity_Extractor SHALL produce exactly one `Entity` per distinct `(entity_type, canonical_key)` pair.
2. WHEN `extract_entities` is called, THE Entity_Extractor SHALL assign each `Entity` a deterministic `entity_id` computed as a hash of `(entity_type, canonical_key)`.
3. WHEN multiple events reference the same entity under different name variants, THE Entity_Extractor SHALL merge them into a single `Entity` and list all observed variants in `entity.aliases`.
4. FOR ALL events that contain at least one extractable entity field, THE Entity_Extractor SHALL produce at least one `Entity` such that the event's `event_id` is present in `entity.event_ids`.
5. THE Entity_Extractor SHALL NOT create an entity unless at least one event field supports its extraction.
6. THE Entity_Extractor SHALL apply the following identity keys: User → normalized username; Host → normalized hostname; Server → normalized hostname + role hint; IP → dotted-decimal or compressed IPv6; Process → `(host, process_name, pid)` tuple; File → `(host, absolute_path)` tuple.
7. WHEN `extract_entities` is called multiple times on the same input, THE Entity_Extractor SHALL produce entities with identical `entity_id` values on each invocation.

---

### Requirement 5: Relationship Extraction

**User Story:** As a security analyst, I want typed relationships between entities to be automatically derived from event semantics, so that I can understand how entities are connected without manually correlating individual log lines.

#### Acceptance Criteria

1. WHEN `extract_relationships` is called, THE Relationship_Extractor SHALL produce only relationships of the five defined types: `LOGGED_INTO`, `AUTHENTICATED_TO`, `EXECUTED`, `CONNECTED_TO`, `ACCESSED`.
2. FOR ALL extracted relationships, THE Relationship_Extractor SHALL include at least one `event_id` in `relationship.event_ids`.
3. WHEN the same relationship is observed in multiple events, THE Relationship_Extractor SHALL merge them into a single relationship and accumulate all contributing `event_ids`.
4. THE Relationship_Extractor SHALL apply the following mapping rules: `LOGGED_INTO` ← user + source_host + action=login; `AUTHENTICATED_TO` ← user + destination_host + action=auth; `EXECUTED` ← process + host; `CONNECTED_TO` ← source_ip + destination_ip; `ACCESSED` ← process/user + file.
5. THE Relationship_Extractor SHALL NOT infer a relationship type that is not supported by the event fields present.
6. WHEN a relationship is extracted, THE Relationship_Extractor SHALL store the `source` (parser source_type) and `investigation_id` on the relationship.

---

### Requirement 6: Candidate Retrieval

**User Story:** As a developer, I want candidate event pairs for temporal correlation to be efficiently identified within a configurable time window, so that the correlation engine only evaluates events that are plausibly related.

#### Acceptance Criteria

1. WHEN `retrieve_candidates` is called with a list of events and a `window_minutes` value, THE Candidate_Retrieval SHALL return all pairs `(a, b)` where `|a.timestamp - b.timestamp| ≤ window_minutes`.
2. THE Candidate_Retrieval SHALL deduplicate candidate pairs such that `(a, b)` and `(b, a)` are treated as the same pair and only one is returned.
3. IF no two events fall within the time window, THEN THE Candidate_Retrieval SHALL return an empty list.
4. THE Candidate_Retrieval SHALL filter candidates to the same `investigation_id`.
5. THE Candidate_Retrieval SHALL default to a time window of 10 minutes when no `window_minutes` is provided.
6. THE Candidate_Retrieval SHALL require that input events are sorted by timestamp ascending.

---

### Requirement 7: Temporal Correlation Engine

**User Story:** As a security analyst, I want event pairs to be evaluated against named, explainable correlation signals, so that I can understand why two events are considered related and trace each signal back to the underlying evidence.

#### Acceptance Criteria

1. WHEN `correlate` is called on a list of `CandidatePair` objects, THE Correlation_Engine SHALL evaluate each of the seven named signals independently for each pair: `shared_user`, `shared_host`, `shared_ip`, `host_continuity`, `temporal_proximity`, `compatible_action_sequence`, `process_file_context`.
2. FOR ALL `CorrelatedRelationship` objects returned by `correlate`, THE Correlation_Engine SHALL set `combined_score` to a value in the closed interval `[0.0, 1.0]`.
3. FOR ALL `CorrelatedRelationship` objects returned by `correlate`, THE Correlation_Engine SHALL set `signal_names` to a non-empty list containing at least one fired signal name.
4. IF a candidate pair triggers zero correlation signals, THEN THE Correlation_Engine SHALL NOT produce a `CorrelatedRelationship` for that pair.
5. FOR ALL `CorrelatedRelationship` objects returned by `correlate`, THE Correlation_Engine SHALL set `explanation` to a non-empty, human-readable string describing which signals fired and the evidence behind them.
6. THE Correlation_Engine SHALL document that `combined_score` is a weighted-sum relevance indicator and is NOT an attack probability score.
7. THE Correlation_Engine SHALL use configurable signal weights and SHALL NOT hardcode weight values in business logic.
8. WHEN signal weights are configured, THE Correlation_Engine SHALL compute `combined_score` as the weighted sum of fired signal scores, normalized to `[0, 1]`.

---

### Requirement 8: Neo4j Graph Persistence

**User Story:** As a developer, I want entities and relationships to be persisted to Neo4j with idempotent upsert semantics, so that re-ingesting the same events does not produce duplicate nodes, inflated evidence counts, or lost data.

#### Acceptance Criteria

1. WHEN `upsert_entity` is called for an entity that does not exist, THE Graph_Repository SHALL create a new node with all entity properties.
2. WHEN `upsert_entity` is called for an entity that already exists (matched by `entity_id`), THE Graph_Repository SHALL merge new aliases into the existing node without duplicating existing aliases.
3. WHEN `upsert_relationship` is called for a relationship that does not exist (matched by `source_id + target_id + type + investigation_id`), THE Graph_Repository SHALL create a new relationship with all properties.
4. WHEN `upsert_relationship` is called for a relationship that already exists, THE Graph_Repository SHALL append new `event_ids` to the existing list without duplicating existing entries and SHALL append new `signal_names` without duplicating existing entries.
5. THE Graph_Repository SHALL NEVER remove previously stored `event_ids` or `signal_names` from a relationship during an upsert.
6. THE Graph_Repository SHALL store `investigation_id`, `timestamp`, `event_ids`, `source`, `signal_names`, `signal_scores`, `combined_score`, and `explanation` on every relationship.
7. THE Graph_Repository SHALL use parameterized Cypher queries and SHALL NOT interpolate user-controlled strings directly into Cypher.
8. THE Graph_Repository SHALL support filtered graph retrieval by entity type, relationship type, and time range.
9. THE Graph_Repository SHALL support multi-hop pivot traversal from a given `entity_id` with configurable hop depth.
10. WHILE the Neo4j connection is unavailable, THE Graph_Repository SHALL return a `GRAPH_UNAVAILABLE` error and SHALL NOT silently succeed.

---

### Requirement 9: Timeline Service

**User Story:** As a security analyst, I want to view all events in an investigation in chronological order with filtering capabilities, so that I can reconstruct the sequence of activity and navigate between related events and graph entities.

#### Acceptance Criteria

1. WHEN `get_timeline` is called for a valid investigation, THE Timeline_Service SHALL return events sorted ascending by `timestamp`.
2. THE Timeline_Service SHALL return all timestamps as UTC ISO-8601 strings.
3. FOR ALL events returned by `get_timeline`, THE Timeline_Service SHALL include `entity_ids` referencing the entities extracted from that event.
4. WHEN a filter is applied to `get_timeline`, THE Timeline_Service SHALL return only events that are a subset of the unfiltered timeline (no events may appear in a filtered result that are not in the full timeline).
5. THE Timeline_Service SHALL support filtering by: time range, `entity_id`, `event_type`, and `severity`.
6. FOR ALL events successfully stored for an investigation, THE Timeline_Service SHALL include that event in the timeline for that investigation.
7. FOR ALL entities in the graph for an investigation, THE Timeline_Service SHALL return at least one timeline event whose `entity_ids` includes that entity's `entity_id`.

---

### Requirement 10: Evidence Detail Service

**User Story:** As a security analyst, I want to retrieve the full evidence record for any event — including raw log data, extracted entities, relationships, and correlation metadata — so that I can verify exactly why an event was included in an investigation and what signals it triggered.

#### Acceptance Criteria

1. WHEN `get_evidence` is called with a valid `event_id`, THE Evidence_Service SHALL return an `EvidenceDetail` containing both the normalized `SecurityEvent` fields and the original `raw_data` dict.
2. WHEN `get_evidence` is called, THE Evidence_Service SHALL include all entities extracted from the event in the `EvidenceDetail`.
3. WHEN `get_evidence` is called, THE Evidence_Service SHALL include all relationships that reference the `event_id` in the `EvidenceDetail`.
4. WHEN `get_evidence` is called, THE Evidence_Service SHALL include correlation metadata — `signal_names`, `combined_score`, and `explanation` — for each correlated relationship referencing the event.
5. THE Evidence_Service SHALL NOT return data belonging to a different investigation than the one that owns the requested `event_id`.
6. IF the `event_id` does not exist, THEN THE Evidence_Service SHALL return HTTP 404 with error code `EVENT_NOT_FOUND`.

---

### Requirement 11: Investigation Management

**User Story:** As a security analyst, I want to create, view, update, and close investigations, so that I can manage the lifecycle of each security case from initial triage through to a recorded outcome.

#### Acceptance Criteria

1. WHEN a client submits a valid `CreateInvestigationPayload` to `POST /api/investigations`, THE Investigation_Service SHALL create an investigation with status `OPEN`, a generated `investigation_id`, and `event_count=0`.
2. THE Investigation_Service SHALL enforce the lifecycle state machine: `OPEN → UNDER_REVIEW`, `UNDER_REVIEW → OPEN`, and `UNDER_REVIEW → CLOSED` are valid transitions; all other status changes SHALL be rejected.
3. IF a status transition is invalid (e.g., attempting to re-open a `CLOSED` investigation), THEN THE Investigation_Service SHALL return an error and SHALL NOT apply the transition.
4. WHEN recording an investigation outcome, THE Investigation_Service SHALL accept only: `TRUE_POSITIVE`, `FALSE_POSITIVE`, `INCONCLUSIVE`, or `ESCALATED`.
5. THE Investigation_Service SHALL persist investigation metadata in PostgreSQL.
6. WHEN `list` is called, THE Investigation_Service SHALL support paginated retrieval of investigations.
7. WHEN a note is added to an investigation via `add_note`, THE Investigation_Service SHALL persist the note with `author_id`, `timestamp`, and the free-text body.
8. THE Investigation_Service SHALL enforce that only the owner of an investigation (or an explicitly granted user) can modify or view it.

---

### Requirement 12: AI Context Builder

**User Story:** As a developer, I want the AI Context Builder to assemble a bounded, structured context from graph, timeline, and evidence data, so that the AI Summary Service receives only verified, serializable evidence without exceeding LLM context limits.

#### Acceptance Criteria

1. WHEN `build_context` is called, THE AI_Context_Builder SHALL include only entities present in the investigation graph.
2. WHEN `build_context` is called, THE AI_Context_Builder SHALL include only relationships that have at least one evidence reference.
3. WHEN `build_context` is called, THE AI_Context_Builder SHALL set `context.total_events` to the actual count of events in the investigation.
4. THE AI_Context_Builder SHALL apply configurable size limits (maximum token count or maximum event count) to prevent LLM context overflow.
5. WHEN sampling events for the evidence sample, THE AI_Context_Builder SHALL prioritize events with `severity` of `high` or `critical`, and then the most-connected events, up to the configured maximum.
6. THE AI_Context_Builder SHALL produce a serializable `InvestigationContext` with no circular references.
7. THE AI_Context_Builder SHALL NOT include secrets, credentials, or PII in the context beyond what is already present in normalized event fields.

---

### Requirement 13: AI Summary Service

**User Story:** As a security analyst, I want an AI-generated narrative summary of the investigation that is grounded exclusively in evidence from the investigation, so that I can quickly understand the investigation without risking misleading AI-invented details.

#### Acceptance Criteria

1. WHEN `generate_summary` is called with a valid `InvestigationContext`, THE AI_Summary_Service SHALL return a `SummaryResult` whose `evidence_refs` list contains only `event_id` values that exist in the context.
2. FOR ALL successful `SummaryResult` objects, THE AI_Summary_Service SHALL set `uncertainty` to a non-empty string explicitly stating what cannot be determined from the evidence.
3. IF the LLM call fails or times out, THEN THE AI_Summary_Service SHALL return a `SummaryResult` with `error_flag=True` and a non-empty `error_message`, and SHALL NOT raise an exception.
4. THE AI_Summary_Service SHALL cache summaries keyed by `(investigation_id, context_hash)` to avoid redundant LLM calls.
5. WHEN `generate_summary` is called with `force_refresh=True`, THE AI_Summary_Service SHALL bypass the cache and generate a fresh summary.
6. THE AI_Summary_Service SHALL abstract the LLM provider behind a `LLMProvider` protocol, supporting provider substitution without changing business logic.
7. THE AI_Summary_Service SHALL validate post-generation that all `evidence_refs` in the returned summary exist in the context, and SHALL set `error_flag=True` if any invalid reference is found.
8. THE AI_Summary_Service SHALL use a system prompt that explicitly prohibits the LLM from inventing events, entities, or maliciousness claims not present in the context.

---

### Requirement 14: React Investigation Workspace

**User Story:** As a security analyst, I want a unified React workspace with synchronized graph, timeline, evidence, AI summary, and analyst decision panels, so that I can conduct a complete investigation without switching between separate tools.

#### Acceptance Criteria

1. WHEN an analyst opens an investigation in the Workspace, THE Workspace SHALL render all five panels simultaneously: Graph Panel, Timeline Panel, Evidence Panel, AI Summary Panel, and Analyst Decision Panel.
2. WHEN an analyst selects a node in the Graph_Panel, THE Workspace SHALL highlight the corresponding events in the Timeline_Panel whose `entity_ids` include the selected node's `entity_id`.
3. WHEN an analyst selects an event in the Timeline_Panel, THE Workspace SHALL highlight the corresponding nodes in the Graph_Panel whose `entity_id` is referenced by the selected event.
4. THE Graph_Panel SHALL render entity nodes and relationships using Cytoscape.js with the fCoSE force-directed layout.
5. WHEN an analyst clicks an evidence item in the Evidence_Panel, THE Evidence_Panel SHALL display the full `EvidenceDetail` including normalized fields, raw_data, and correlation metadata.
6. WHEN the AI_Summary_Panel loads for an investigation, THE AI_Summary_Panel SHALL display the cached summary if available, or trigger generation if no summary exists.
7. IF the AI Summary Service is unavailable, THE AI_Summary_Panel SHALL display a graceful error message and SHALL NOT prevent the analyst from using the other panels.
8. WHEN an analyst submits an outcome via the Analyst_Decision_Panel, THE Analyst_Decision_Panel SHALL call the `PATCH /api/investigations/{id}/outcome` endpoint and reflect the updated status in the UI.
9. WHEN an analyst adds a note via the Analyst_Decision_Panel, THE Analyst_Decision_Panel SHALL call `POST /api/investigations/{id}/notes` and display the note in the notes list immediately.

---

### Requirement 15: Security Controls

**User Story:** As a platform operator, I want all API endpoints to be protected by JWT authentication and investigation-level authorization, so that analysts can only access their own investigations and sensitive credentials are never exposed.

#### Acceptance Criteria

1. THE API SHALL require a valid JWT token on all endpoints; requests without a valid token SHALL receive HTTP 401 with error code `UNAUTHORIZED`.
2. WHEN a request references an investigation not owned by the authenticated caller, THE API SHALL return HTTP 403 with error code `FORBIDDEN`.
3. THE API SHALL validate JWT tokens via middleware applied globally before route handlers execute.
4. THE API SHALL store all secrets (LLM API keys, database credentials, JWT secret) exclusively in environment variables and SHALL NOT hardcode any secret value.
5. THE API SHALL NOT log raw event data at INFO level; only `event_id` and `investigation_id` SHALL be logged.
6. THE API SHALL use parameterized queries for all PostgreSQL operations and SHALL NOT use string interpolation to construct SQL statements.
7. THE API SHALL use parameterized Cypher queries for all Neo4j operations and SHALL NOT interpolate user-controlled strings into Cypher.
8. THE AI_Summary_Service SHALL pass investigation context as structured data to the LLM and SHALL NOT construct prompts by directly concatenating unvalidated user input.

---

### Requirement 16: Structured Error Handling

**User Story:** As a developer integrating with TraceGraph, I want all API errors to return a standard error envelope with a machine-readable error code, so that clients can programmatically handle specific error conditions without parsing human-readable messages.

#### Acceptance Criteria

1. WHEN any API endpoint encounters an error, THE API SHALL return a response matching the `ErrorResponse` schema: `{ status: "error", code: string, message: string, details?: object }`.
2. THE API SHALL use the following standard error codes: `VALIDATION_ERROR` (400), `INVALID_SOURCE_TYPE` (400), `UNAUTHORIZED` (401), `FORBIDDEN` (403), `INVESTIGATION_NOT_FOUND` (404), `EVENT_NOT_FOUND` (404), `PARSE_ERROR` (422), `AI_UNAVAILABLE` (503).
3. WHEN a batch ingestion request contains events that fail validation, THE API SHALL return a partial success response where `IngestionResponse.errors` lists each failed event with its field-level reason.
4. THE API SHALL wrap all successful responses in a `SuccessResponse` envelope: `{ status: "success", data: T }`.
5. IF Neo4j is unavailable, THEN THE API SHALL return HTTP 503 with error code `GRAPH_UNAVAILABLE` for graph-dependent endpoints and SHALL NOT silently return empty results.

---

### Requirement 17: Containerized Deployment

**User Story:** As a developer, I want to run the complete TraceGraph stack — frontend, backend, Neo4j, and PostgreSQL — using a single Docker Compose command, so that I can set up a local development environment without manual service configuration.

#### Acceptance Criteria

1. THE Docker_Compose configuration SHALL define services for: React frontend, FastAPI backend, Neo4j 5.x, and PostgreSQL 15.x.
2. WHEN `docker-compose up` is executed, THE Docker_Compose configuration SHALL start all four services and establish inter-service connectivity.
3. THE Docker_Compose configuration SHALL provide an `.env.example` file documenting all required environment variables with placeholder values.
4. THE Docker_Compose configuration SHALL NOT commit actual secret values to version control; the `.env` file SHALL be listed in `.gitignore`.
5. WHEN the backend service starts, THE API SHALL connect to both Neo4j and PostgreSQL and fail with a clear error message if either connection cannot be established.

---

### Requirement 18: Performance Instrumentation

**User Story:** As a developer, I want per-stage timing metrics exposed for the processing pipeline, so that I can identify bottlenecks and verify that the system meets its performance targets.

#### Acceptance Criteria

1. THE Pipeline SHALL record per-stage elapsed time for: parse, normalize, entity extraction, relationship extraction, candidate retrieval, correlation, and graph persistence.
2. THE API SHALL target a p95 latency of less than 500ms for single-event ingestion.
3. THE API SHALL target a p95 latency of less than 5 seconds for a 100-event batch ingestion.
4. THE Graph_Service SHALL target a p95 latency of less than 200ms for full graph retrieval.
5. THE Graph_Service SHALL target a p95 latency of less than 500ms for multi-hop pivot traversal.
6. THE Pipeline SHALL be instrumented such that per-stage timing data is accessible for evaluation and profiling without requiring code changes.

---

### Requirement 19: Evaluation Scenarios

**User Story:** As a developer, I want a set of labeled evaluation scenarios with known expected outputs, so that I can measure the quality of entity extraction, relationship extraction, and temporal correlation against a ground truth.

#### Acceptance Criteria

1. THE system SHALL provide a `basic_attack_sequence` scenario where lateral movement events are ingested and the graph SHALL contain the expected attack path with the correct entity types and relationship types.
2. THE system SHALL provide an `unrelated_events` scenario where events with no shared entities are ingested and the graph SHALL contain no relationships between them.
3. THE system SHALL provide a `legitimate_access` scenario where a normal authentication sequence is ingested and relationships SHALL be created without inflating correlation scores beyond what the evidence supports.
4. THE system SHALL provide a `multi_user_host` scenario with overlapping events from multiple users and hosts, and entity deduplication SHALL be correct with no cross-contamination between investigations.
5. WHEN evaluation is run, THE Pipeline SHALL expose precision and recall metrics for expected vs. produced vs. missed relationships per scenario.
