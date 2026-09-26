# Implementation Plan: TraceGraph

## Overview

TraceGraph is implemented as a Python/FastAPI backend with a Neo4j graph database, PostgreSQL metadata store, and a React.js + Cytoscape.js frontend. Tasks follow the dependency chain defined in the design: core schemas and infrastructure first, then the processing pipeline stage by stage, then query/AI services, then the frontend workspace, and finally deployment, instrumentation, and evaluation.

---

## Tasks

- [x] 1. Project scaffolding and core infrastructure
  - Create the `tracegraph/` monorepo directory structure exactly as specified in the design's package structure section
  - Initialize `backend/` as a Python package with `pyproject.toml` (or `requirements.txt`) pinning all backend dependencies: `fastapi`, `pydantic>=2`, `pydantic-settings`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `neo4j`, `python-jose[cryptography]`, `bcrypt`, `pytest-asyncio`, `hypothesis`, `pytest`, `httpx`
  - Initialize `frontend/` with a React project (Vite or CRA) and install pinned frontend dependencies: `react`, `react-router-dom`, `cytoscape`, `cytoscape-fcose`, `axios`, `date-fns`, `tailwindcss`
  - Create `backend/app/core/config.py` using Pydantic `BaseSettings` from `pydantic-settings` (separate package in v2) to load all secrets exclusively from environment variables
  - Create `.env.example` documenting every required environment variable with placeholder values
  - Add `.env` to `.gitignore`
  - Create docker-compose.yml and Dockerfiles early (Task 1) so integration tests in tasks 13+ have live databases
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 15.4_

- [x] 2. Core Pydantic schemas and SQLAlchemy models
  - [x] 2.1 Implement Pydantic schemas for the Common Security Event Model and supporting types
    - Create `backend/app/schemas/security_event.py` using Pydantic v2 `@field_validator` (NOT deprecated `@validator`). Add `source_type` field. `event_id` non-empty, `timestamp` (UTC datetime), `event_type`, `action`, optional fields (`user`, `source_host`, `destination_host`, `source_ip`, `destination_ip`, `process`, `file`), `severity` (enum validator: low/medium/high/critical), `raw_data`
    - Create `backend/app/schemas/entity.py` with `Entity`, `EntityType` enum, and identity key constants
    - Create `backend/app/schemas/relationship.py` with `RawRelationship`, `CorrelatedRelationship`, `RelationshipType` enum
    - Create `backend/app/schemas/investigation.py` with `Investigation`, `InvestigationStatus` enum, `CreateInvestigationPayload`, `OutcomePayload`, `NotePayload`
    - Create `backend/app/schemas/common.py` with generic `SuccessResponse[T]` and `ErrorResponse` envelopes matching the design's standard error codes table
    - Create `backend/app/schemas/graph.py`, `timeline.py`, `summary.py` with `GraphResult`, `GraphFilter`, `TimelineResult`, `TimelineFilter`, `InvestigationContext`, `SummaryResult`
    - _Requirements: 3.1, 3.8, 4.1, 5.1, 7.1, 11.1, 11.4, 16.1, 16.4_

  - [x] 2.2 Implement SQLAlchemy ORM models and database connection management
    - Create `backend/app/models/investigation.py`, `security_event.py` (with source_type column, composite unique key on event_id+investigation_id), `note.py`, `event_entity_map.py` matching the PostgreSQL schema in the design exactly (including all `CHECK` constraints and indexes)
    - Create `backend/app/core/database.py` with connection factories for both PostgreSQL (SQLAlchemy async engine) and Neo4j (official driver), startup health checks, and connection error logging
    - _Requirements: 11.5, 17.5_

  - [x]* 2.3 Write unit tests for schema validators
    - Test `event_id` non-empty validator, `severity` enum validator, UTC timestamp coercion
    - Test `SuccessResponse` and `ErrorResponse` envelope serialization
    - _Requirements: 3.1, 3.8, 16.1, 16.4_

- [x] 3. Error handling and structured error codes
  - [x] 3.1 Implement global error handling middleware and error code constants
    - Create `backend/app/core/errors.py` defining all standard error code strings: `VALIDATION_ERROR`, `INVALID_SOURCE_TYPE`, `UNAUTHORIZED`, `FORBIDDEN`, `INVESTIGATION_NOT_FOUND`, `EVENT_NOT_FOUND`, `PARSE_ERROR`, `AI_UNAVAILABLE`, `GRAPH_UNAVAILABLE`
    - Implement a FastAPI exception handler that converts all application exceptions to `ErrorResponse` JSON with the correct HTTP status code
    - Implement a `GRAPH_UNAVAILABLE` handler that returns HTTP 503 when Neo4j is unreachable
    - _Requirements: 16.1, 16.2, 16.5_

  - [x] 3.2 Write unit tests for error handler
    - Test each error code maps to the correct HTTP status
    - Test `ErrorResponse` envelope shape matches the schema
    - _Requirements: 16.1, 16.2_

- [x] 4. JWT authentication and authorization middleware
  - [x] 4.1 Implement JWT middleware and investigation ownership enforcement
    - Create `backend/app/core/auth.py` with a FastAPI dependency that validates JWT tokens on every request and returns HTTP 401 (`UNAUTHORIZED`) for missing or invalid tokens
    - Implement an `require_investigation_owner` dependency that checks the authenticated caller owns the referenced `investigation_id` and returns HTTP 403 (`FORBIDDEN`) otherwise
    - Ensure no secrets are hardcoded; all keys are read from `config.py`
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

  - [x] 4.2 Write property test for authorization isolation (Property 17)
    - **Property 17: Authorization Isolation**
    - **Validates: Requirements 15.2, 11.8**
    - Use `hypothesis` to generate arbitrary investigation IDs and user pairs; assert every request by a non-owner receives HTTP 403

- [x] 5. Parser adapter infrastructure and source-type adapters
  - [x] 5.1 Implement the `ParserAdapter` protocol and `AdapterRegistry`
    - Create `backend/app/adapters/base.py` with the `ParserAdapter` Protocol: `source_type: str` and `parse(raw: dict) -> ParsedEvent | ParseError`; include pre/postcondition docstrings from the design
    - Create `backend/app/services/parser_registry.py` implementing `AdapterRegistry` with `register(adapter)` and `dispatch(source_type, raw)` methods; support runtime registration without code changes to the registry
    - Define `ParsedEvent` and `ParseError` Pydantic models in `backend/app/schemas/`
    - _Requirements: 2.5, 2.6, 1.8_

  - [x] 5.2 Implement the six source-type parser adapters
    - Create `backend/app/adapters/siem.py`, `edr.py`, `sysmon.py`, `auth.py`, `network.py`, `public_dataset.py` — one adapter per source type
    - Each adapter must: map recognized fields to `ParsedEvent`, preserve all unrecognized fields in `extra_fields`, never mutate the input dict, return `ParseError` (not raise) on failure, preserve `event_id` unchanged
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 1.8_

  - [x]* 5.3 Write property test for parser non-mutation (Property 16)
    - **Property 16: Parser Non-Mutation**
    - **Validates: Requirements 2.1, 2.4**
    - Use `hypothesis` to generate arbitrary raw event dicts; assert every key is present in either recognized fields or `extra_fields` after parsing

  - [x]* 5.4 Write unit tests for each parser adapter
    - Test field mapping, `extra_fields` preservation, `ParseError` return on malformed input, `event_id` passthrough for each of the six adapters
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 6. Normalization engine
  - [x] 6.1 Implement the `NormalizationEngine`
    - Create `backend/app/services/normalization.py` with `NormalizationEngine.normalize(parsed: ParsedEvent) -> SecurityEvent`
    - Implement configurable field-name mapping tables (loaded from config, not hardcoded)
    - Implement timestamp normalization: parse multiple formats, convert to UTC-aware datetime, reject unparseable timestamps with `VALIDATION_ERROR`
    - Implement identifier canonicalization: lowercase `source_host` and `destination_host`; strip domain prefixes (`DOMAIN\user`, `user@domain`) from username fields; convert IPs to dotted-decimal IPv4 or compressed IPv6
    - Store original parsed fields in `SecurityEvent.raw_data`; preserve `event_id` unchanged
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.9_

  - [ ]* 6.2 Write property test for normalization canonical forms (Property 13)
    - **Property 13: Normalization Canonical Forms**
    - **Validates: Requirements 3.1, 3.3, 3.4, 3.5**
    - Use `hypothesis` to generate arbitrary `ParsedEvent` objects; assert output `source_host` equals `source_host.lower()` and `timestamp` is UTC-aware

  - [ ]* 6.3 Write property test for identity stability (Property 1)
    - **Property 1: Identity Stability**
    - **Validates: Requirements 2.2, 3.7**
    - Use `hypothesis` to generate arbitrary raw events; assert `normalize(parse(event)).event_id == event["event_id"]`

  - [ ]* 6.4 Write unit tests for the normalization engine
    - Test timestamp parsing for multiple formats and timezones, hostname lowercasing, domain-prefix stripping, IP normalization, severity validation, `raw_data` preservation
    - _Requirements: 3.1–3.9_

- [x] 7. Investigation management service and API
  - [x] 7.1 Implement `InvestigationService` and `InvestigationRepository`
    - Create `backend/app/repositories/investigation_repository.py` with CRUD operations against PostgreSQL using parameterized SQLAlchemy queries (no string interpolation)
    - Create `backend/app/services/investigation.py` implementing `create`, `get`, `list` (paginated), `update_status`, `record_outcome`, `add_note`, `list_notes`
    - Enforce the lifecycle state machine: `OPEN → UNDER_REVIEW`, `UNDER_REVIEW → OPEN`, `UNDER_REVIEW → CLOSED`; reject all other transitions with a descriptive error
    - Accept only valid outcome values: `TRUE_POSITIVE`, `FALSE_POSITIVE`, `INCONCLUSIVE`, `ESCALATED`
    - Enforce ownership: only the owner (or explicitly granted user) can modify or view an investigation
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 15.6_

  - [x] 7.2 Implement Investigation Management API routes
    - Create `backend/app/api/investigations.py` with routes: `POST /api/investigations`, `GET /api/investigations` (paginated), `GET /api/investigations/{id}`, `PATCH /api/investigations/{id}` (status/outcome)
    - Create `backend/app/api/notes.py` with `POST /api/investigations/{id}/notes` and `GET /api/investigations/{id}/notes`
    - Apply JWT middleware and ownership checks to all routes
    - Return `SuccessResponse` envelopes on success and `ErrorResponse` on failure
    - _Requirements: 11.1–11.8, 15.1, 15.2, 16.1, 16.4_

  - [ ]* 7.3 Write unit tests for investigation state machine
    - Test all valid transitions, all invalid transitions, outcome recording, paginated list, note persistence with author/timestamp
    - _Requirements: 11.2, 11.3, 11.4, 11.7_

- [x] 8. Entity extraction service
  - [x] 8.1 Implement `EntityExtractor`
    - Create `backend/app/services/entity_extractor.py` with `EntityExtractor.extract(events: list[SecurityEvent]) -> list[Entity]`
    - Apply identity key rules from the design: User → normalized username; Host → normalized hostname; Server → hostname (only when server_role field is set); IP → canonical IP; Process → "{source_host}::{process_name}" (pid is metadata, NOT in canonical_key); File → (host, absolute_path) tuple
    - Assign deterministic `entity_id` as a hash of `(entity_type, canonical_key)`
    - Deduplicate by `entity_id`: merge aliases, accumulate `event_ids`
    - Never create an entity without at least one evidence reference
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 8.2 Write property test for entity uniqueness (Property 4)
    - **Property 4: Entity Uniqueness**
    - **Validates: Requirements 4.1, 4.2**
    - Use `hypothesis` to generate lists of `SecurityEvent`; assert no two entities in the result share the same `entity_id`

  - [ ]* 8.3 Write property test for entity coverage (Property 3)
    - **Property 3: Entity Coverage**
    - **Validates: Requirements 4.4**
    - Use `hypothesis`; for every event with at least one extractable field, assert at least one returned entity carries that event's `event_id`

  - [ ]* 8.4 Write unit tests for entity extraction
    - Test each of the six entity types, alias merging, deduplication, deterministic `entity_id` across multiple calls with identical input
    - _Requirements: 4.1–4.7_

- [x] 9. Relationship extraction service
  - [x] 9.1 Implement `RelationshipExtractor`
    - Create `backend/app/services/relationship_extractor.py` with `RelationshipExtractor.extract(events, entities) -> list[RawRelationship]`
    - Implement declarative rule table mapping event fields to the five relationship types using the trigger-field rules from the design
    - Merge duplicate relationships (same source/target/type): accumulate `event_ids`
    - Store `source` (parser source_type) and `investigation_id` on every relationship
    - Never infer a relationship type not supported by the present event fields
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x]* 9.2 Write property test for relationship evidence (Property 5)
    - **Property 5: Relationship Evidence**
    - **Validates: Requirements 5.2**
    - Use `hypothesis`; assert every relationship in the output has `len(event_ids) >= 1`

  - [x]* 9.3 Write unit tests for relationship extraction
    - Test each of the five relationship types, multi-event accumulation (deduplication of event_ids), rejection of unsupported field combinations
    - _Requirements: 5.1–5.6_

- [x] 10. Candidate retrieval service
  - [x] 10.1 Implement `CandidateRetrieval`
    - Create `backend/app/services/candidate_retrieval.py` with `CandidateRetrieval.retrieve(events, window_minutes=10) -> list[CandidatePair]`
    - Implement the sliding-window algorithm from the design's pseudocode: O(n) inner-loop break when delta exceeds window
    - Deduplicate pairs: `(a, b)` and `(b, a)` treated as the same pair
    - Filter to same `investigation_id`; return empty list when no events fall within window
    - Require (and document) that input events are sorted by timestamp ascending
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 10.2 Write property test for candidate window completeness (Property 14)
    - **Property 14: Candidate Window Completeness**
    - **Validates: Requirements 6.1, 6.2**
    - Use `hypothesis` to generate sorted event lists and window values; assert every pair within the window is returned, and no pair outside is included

  - [ ]* 10.3 Write unit tests for candidate retrieval
    - Test deduplication, empty-window case, boundary conditions (events exactly at window edge), investigation_id scoping
    - _Requirements: 6.1–6.6_

- [x] 11. Temporal correlation engine
  - [x] 11.1 Implement `TemporalCorrelationEngine`
    - Create `backend/app/services/correlation.py` with `TemporalCorrelationEngine.correlate(candidates) -> list[CorrelatedRelationship]`
    - Implement all seven signals: `shared_user`, `shared_host`, `shared_ip`, `host_continuity`, `temporal_proximity`, `compatible_action_sequence`, `process_file_context`
    - Load signal weights from config (not hardcoded); default weights from design table
    - Compute `combined_score` = sum(fired weights) / sum(ALL weights) — never divide by fired-only weights (that always gives 1.0). Reject pairs where temporal_proximity is the only signal fired
    - Generate a human-readable `explanation` listing fired signals and evidence
    - Filter out candidate pairs that trigger zero signals
    - Add explicit code comment documenting that `combined_score` is NOT an attack probability
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [ ]* 11.2 Write property test for correlation score bounds (Property 6)
    - **Property 6: Correlation Score Bounds**
    - **Validates: Requirements 7.2, 7.8**
    - Use `hypothesis` to generate arbitrary `CandidatePair` lists; assert every result has `0.0 <= combined_score <= 1.0`

  - [ ]* 11.3 Write property test for correlation signal presence (Property 7)
    - **Property 7: Correlation Signal Presence**
    - **Validates: Requirements 7.3, 7.4**
    - Use `hypothesis`; assert every returned `CorrelatedRelationship` has `len(signal_names) >= 1`, and no result is produced for zero-signal pairs

  - [ ]* 11.4 Write unit tests for each correlation signal
    - Test each of the seven signals in isolation; test combined scoring; test zero-signal filtering; test configurable weights
    - _Requirements: 7.1–7.8_

- [ ] 12. Checkpoint — core pipeline
  - Ensure all unit and property tests for tasks 2–11 pass. Run `pytest tests/unit/` and fix any failures before proceeding to persistence.

- [ ] 13. Neo4j graph repository
  - [ ] 13.1 Implement `GraphRepository` with idempotent upsert semantics
    - Create `backend/app/repositories/graph_repository.py` with `upsert_entity`, `upsert_relationship`, `get_graph`, `pivot`, `get_entity`
    - Use parameterized Cypher queries exclusively (no string interpolation of user-controlled values) using the MERGE patterns from the design
    - `upsert_entity`: MERGE on `(canonical_key, investigation_id)` — nodes are scoped per investigation, never shared; ON MATCH append only new aliases
    - `upsert_relationship`: MERGE on `(source_id, target_id, type, investigation_id)`; ON MATCH append new `event_ids` and `signal_names` (no duplicates); NEVER remove existing entries
    - Store all required relationship properties: `investigation_id`, `timestamp`, `event_ids`, `source`, `signal_names`, `signal_scores`, `combined_score`, `explanation`
    - Implement `get_graph` with filters by entity type, relationship type, time range
    - Implement `pivot` with configurable hop depth
    - Return `GRAPH_UNAVAILABLE` error (not silently succeed) when Neo4j is unreachable
    - _Requirements: 8.1–8.10, 15.7_

  - [ ]* 13.2 Write property test for idempotent ingestion (Property 2)
    - **Property 2: Idempotent Ingestion**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**
    - Use `hypothesis` to generate entity and relationship batches; call upsert twice with same input; assert graph state is identical after second call

  - [ ]* 13.3 Write property test for no destructive overwrites (Property 11)
    - **Property 11: No Destructive Overwrites**
    - **Validates: Requirements 8.4, 8.5**
    - Use `hypothesis`; after upserting a relationship, assert `post_upsert.event_ids ⊇ pre_upsert.event_ids`

  - [ ]* 13.4 Write unit tests for graph repository
    - Test entity creation, alias merge, relationship creation, event_id accumulation, signal_name accumulation, filtered retrieval, `GRAPH_UNAVAILABLE` error path
    - _Requirements: 8.1–8.10_

- [ ] 14. Evidence ingestion API and pipeline orchestration
  - [ ] 14.1 Implement `IngestionService` pipeline orchestration
    - Create `backend/app/services/ingestion.py` implementing the full `process_event_batch` algorithm from the design's pseudocode
    - Validate investigation existence before any processing; return `INVESTIGATION_NOT_FOUND` if missing
    - Reject immediately with `INVALID_SOURCE_TYPE` if `source_type` is not in the registry
    - Process each event independently in batch mode; collect partial failures without stopping
    - Wire together: parse → normalize → validate → extract_entities → extract_relationships (upsert immediately) → sort_by_timestamp → retrieve_candidates → correlate → enrich relationships with signals → upsert_graph → store_events + event_entity_map
    - Return `IngestionResponse` with `accepted`, `rejected`, and `errors` (field-level reasons)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 16.3_

  - [ ] 14.2 Implement `EventRepository` for PostgreSQL event storage
    - Create `backend/app/repositories/event_repository.py` with `store(events, investigation_id, entity_map)` and `get(event_id, investigation_id)`. Also INSERT into `event_entity_map`. Use ON CONFLICT DO NOTHING for idempotent re-ingestion using parameterized SQLAlchemy queries
    - _Requirements: 15.6_

  - [ ] 14.3 Implement ingestion API routes
    - Create `backend/app/api/events.py` with `POST /api/investigations/{id}/events` (single) and `POST /api/investigations/{id}/events/batch`
    - Apply JWT and ownership middleware
    - Log only `event_id` and `investigation_id` at INFO level (never raw event data)
    - Return `SuccessResponse[IngestionResponse]` or `ErrorResponse`
    - _Requirements: 1.1–1.8, 15.5, 16.1–16.4_

  - [ ] 14.4 Write integration tests for the ingestion pipeline
    - Test single event success, batch partial failure, `INVESTIGATION_NOT_FOUND`, `INVALID_SOURCE_TYPE`, ownership enforcement, and round-trip `event_id` preservation
    - _Requirements: 1.1–1.8_

- [ ] 15. Timeline service
  - [ ] 15.1 Implement `TimelineService`
    - Create `backend/app/services/timeline.py` with `TimelineService.get_timeline(investigation_id, filters) -> TimelineResult`
    - Return events sorted ascending by `timestamp`; all timestamps as UTC ISO-8601 strings
    - Include `entity_ids` on each timeline event for graph cross-linking
    - Support filters: time range, `entity_id`, `event_type`, `severity`
    - Guarantee the filter-is-subset invariant: filtered results are always a subset of unfiltered results
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [ ] 15.2 Implement timeline API route
    - Create `backend/app/api/timeline.py` with `GET /api/investigations/{id}/timeline` supporting all filter parameters
    - _Requirements: 9.1–9.7_

  - [ ]* 15.3 Write property test for timeline completeness (Property 8)
    - **Property 8: Timeline Completeness**
    - **Validates: Requirements 9.6**
    - Use `hypothesis`; for arbitrary sets of stored events, assert every stored event appears in the timeline result

  - [ ]* 15.4 Write property test for timeline filter subset (Property 15)
    - **Property 15: Timeline Filter Subset**
    - **Validates: Requirements 9.4**
    - Use `hypothesis` to generate filters; assert `get_timeline(inv, filter) ⊆ get_timeline(inv, no_filter)`

  - [ ]* 15.5 Write property test for graph/timeline consistency (Property 9)
    - **Property 9: Graph/Timeline Consistency**
    - **Validates: Requirements 9.7**
    - Assert every entity in the graph has at least one matching timeline event via `entity_ids`

- [ ] 16. Evidence detail service and API
  - [ ] 16.1 Implement `EvidenceDetailService`
    - Create `backend/app/services/evidence.py` with `EvidenceDetailService.get_evidence(event_id) -> EvidenceDetail`
    - Return both normalized `SecurityEvent` fields and original `raw_data`
    - Include all entities extracted from the event and all relationships referencing the `event_id`
    - Include correlation metadata: `signal_names`, `combined_score`, `explanation` for each correlated relationship
    - Enforce investigation isolation: never return data belonging to a different investigation
    - Return HTTP 404 with `EVENT_NOT_FOUND` if `event_id` does not exist
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ] 16.2 Implement evidence detail API route
    - Create `backend/app/api/` evidence endpoint: `GET /api/investigations/{id}/events/{eid}`
    - Apply JWT and ownership middleware
    - _Requirements: 10.1–10.6, 15.1, 15.2_

  - [ ]* 16.3 Write unit tests for evidence detail service
    - Test full record return, investigation isolation, `EVENT_NOT_FOUND`, correlation metadata inclusion
    - _Requirements: 10.1–10.6_

- [ ] 17. Graph query API
  - [ ] 17.1 Implement graph query API routes
    - Create `backend/app/api/graph.py` with:
      - `GET /api/investigations/{id}/graph` — full investigation graph with filter query params (entity type, relationship type, time range)
      - `GET /api/investigations/{id}/graph/pivot` — multi-hop pivot from `entity_id` with configurable `hops` param
      - `GET /api/investigations/{id}/entities/{eid}` — entity detail with evidence
    - Return `GRAPH_UNAVAILABLE` (503) when Neo4j is unreachable; do not return empty results silently
    - Apply JWT and ownership middleware on all routes
    - _Requirements: 8.8, 8.9, 8.10, 16.5_

  - [ ]* 17.2 Write unit tests for graph query routes
    - Test filtered retrieval, multi-hop pivot, `GRAPH_UNAVAILABLE` 503 response, entity detail
    - _Requirements: 8.8, 8.9, 8.10_

- [ ] 18. Checkpoint — backend services complete
  - Run `pytest tests/unit/ tests/integration/` and ensure all tests pass. Verify the complete ingestion→graph→timeline→evidence pipeline with a small sample dataset before starting the AI and frontend layers.

- [ ] 19. AI Context Builder
  - [ ] 19.1 Implement `AIContextBuilder`
    - Create `backend/app/services/ai_context_builder.py` with `AIContextBuilder.build_context(investigation_id, graph, timeline, evidence_sample) -> InvestigationContext`
    - Include only entities present in the investigation graph and only relationships with at least one evidence reference
    - Apply configurable size limits (default `max_events=50`): prioritize `high` and `critical` severity events, then most-connected events; deduplicate
    - Set `context.total_events` to the actual count (not the sampled count)
    - Produce a fully JSON-serializable `InvestigationContext` with no circular references
    - Never include secrets, credentials, or PII beyond what is already in normalized event fields
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [ ]* 19.2 Write unit tests for AI context builder
    - Test size limit enforcement, high-severity prioritization, graph-only entity inclusion, serialization (no circular refs)
    - _Requirements: 12.1–12.7_

- [ ] 20. AI Summary Service
  - [ ] 20.1 Implement `LLMProvider` protocol and `AISummaryService`
    - Create `backend/app/services/ai_summary.py` with `LLMProvider` Protocol (enables provider substitution)
    - Implement `AISummaryService.generate_summary(context) -> SummaryResult`
    - Implement a system prompt that explicitly prohibits the LLM from inventing events, entities, or maliciousness claims not in context; pass context as structured data, never as raw concatenated user text
    - Set `uncertainty` as a mandatory non-empty field in every successful response
    - On any LLM exception/timeout: return `SummaryResult(error_flag=True, error_message=...)` — never raise to caller
    - Cache summaries by `(investigation_id, context_hash)`; support `force_refresh=True` to bypass cache
    - Post-generation validation: verify all `evidence_refs` exist in context; set `error_flag=True` if any invalid reference is found
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 15.8_

  - [ ] 20.2 Implement AI Summary API routes
    - Create `backend/app/api/summary.py` with:
      - `POST /api/investigations/{id}/summary` — generate or force-refresh summary
      - `GET /api/investigations/{id}/summary` — retrieve cached summary
    - Return `AI_UNAVAILABLE` (503) when LLM is unreachable; other panels must remain functional
    - Apply JWT and ownership middleware
    - _Requirements: 13.3, 13.4, 13.5, 16.2_

  - [ ]* 20.3 Write property test for graceful AI failure (Property 12)
    - **Property 12: Graceful AI Failure**
    - **Validates: Requirements 13.3**
    - Use `hypothesis` with a mock LLM that always raises exceptions; assert `generate_summary` always returns a `SummaryResult` and never raises

  - [ ]* 20.4 Write property test for summary grounding (Property 10)
    - **Property 10: Summary Grounding**
    - **Validates: Requirements 13.1, 13.7**
    - Use `hypothesis`; assert every `evidence_ref` in the result exists in `context.event_ids`

  - [ ]* 20.5 Write unit tests for AI summary service
    - Test cache hit, cache miss, `force_refresh`, LLM failure graceful return, post-generation evidence_ref validation, `uncertainty` field presence
    - _Requirements: 13.1–13.8_

- [ ] 21. Structured logging
  - [ ] 21.1 Implement structured logging configuration
    - Create `backend/app/core/logging.py` with JSON-structured log output
    - Enforce log level controls: raw event data is NEVER logged at INFO level; only `event_id` and `investigation_id` are logged for event-processing operations
    - _Requirements: 15.5_

- [ ] 22. Checkpoint — backend complete
  - Run the full backend test suite (`pytest`). Confirm all 19 requirements are covered by passing tests. Review that no secrets are hardcoded and no raw event data leaks into INFO-level logs.

- [ ] 23. React frontend — project setup and API client layer
  - [ ] 23.1 Set up the React project structure and Tailwind CSS
    - Create `frontend/src/` directory tree matching the design's package structure: `components/`, `pages/`, `services/`, `hooks/`, `utils/`
    - Configure Tailwind CSS and set up React Router with routes for `/investigations` (list) and `/investigations/:id` (workspace)
    - _Requirements: 14.1_

  - [ ] 23.2 Implement typed API client services
    - Create `frontend/src/services/investigationsApi.ts`, `eventsApi.ts`, `graphApi.ts`, `timelineApi.ts`, `summaryApi.ts`
    - Define TypeScript interfaces matching all backend response shapes (Investigation, GraphResult, TimelineResult, EvidenceDetail, SummaryResult)
    - Use `axios` with a base URL from environment config; handle `SuccessResponse` and `ErrorResponse` envelopes
    - _Requirements: 14.1, 16.1, 16.4_

- [ ] 24. React frontend — Investigation List page
  - [ ] 24.1 Implement `InvestigationList` component and `InvestigationsPage`
    - Create `frontend/src/components/InvestigationList/` with a paginated list view of investigations
    - Create `frontend/src/pages/InvestigationsPage.tsx` rendering the list and a "New Investigation" form
    - Implement `useInvestigation` hook in `frontend/src/hooks/useInvestigation.ts` for CRUD operations
    - _Requirements: 11.1, 11.6_

- [ ] 25. React frontend — Workspace panels
  - [ ] 25.1 Implement `GraphPanel` with Cytoscape.js fCoSE layout
    - Create `frontend/src/components/Workspace/GraphPanel.tsx`
    - Render entity nodes and relationships using Cytoscape.js with the fCoSE force-directed layout (via `cytoscape-fcose`)
    - Configure node styles per entity type and relationship labels; implement node click handler emitting selected `entity_id`
    - Create `frontend/src/utils/cytoscapeConfig.ts` for layout and style configuration
    - Implement `useGraph` hook in `frontend/src/hooks/useGraph.ts` fetching graph data
    - _Requirements: 14.1, 14.4_

  - [ ] 25.2 Implement `TimelinePanel`
    - Create `frontend/src/components/Workspace/TimelinePanel.tsx`
    - Render a chronologically sorted, filterable event list (filter by time range, entity, event type, severity)
    - Implement event click handler emitting selected `entity_ids`
    - Implement `useTimeline` hook in `frontend/src/hooks/useTimeline.ts`
    - Create `frontend/src/utils/timelineHelpers.ts` for UTC timestamp formatting using `date-fns`
    - _Requirements: 14.1, 14.5_

  - [ ] 25.3 Implement `EvidencePanel`
    - Create `frontend/src/components/Workspace/EvidencePanel.tsx`
    - Display the full `EvidenceDetail` for a selected event: normalized fields, `raw_data`, extracted entities, relationships, and correlation metadata (signal names, combined score, explanation)
    - _Requirements: 14.1, 14.5_

  - [ ] 25.4 Implement `AISummaryPanel` with graceful degradation
    - Create `frontend/src/components/Workspace/AISummaryPanel.tsx`
    - On mount, display cached summary if available or trigger generation
    - If AI Summary Service is unavailable (503 / `AI_UNAVAILABLE`), display a graceful error message and do NOT prevent use of other panels
    - _Requirements: 14.1, 14.6, 14.7_

  - [ ] 25.5 Implement `AnalystDecisionPanel`
    - Create `frontend/src/components/Workspace/AnalystDecisionPanel.tsx`
    - Submit outcome via `PATCH /api/investigations/{id}/outcome`; reflect updated status in UI immediately
    - Add notes via `POST /api/investigations/{id}/notes`; display the new note in the list immediately (optimistic update)
    - _Requirements: 14.1, 14.8, 14.9_

- [ ] 26. React frontend — bidirectional graph/timeline synchronization
  - [ ] 26.1 Implement `useGraphTimelineSync` hook and wire workspace panels
    - Create `frontend/src/hooks/useGraphTimelineSync.ts` managing bidirectional highlight state between `GraphPanel` and `TimelinePanel`
    - When a node is selected in `GraphPanel`: highlight all `TimelinePanel` events whose `entity_ids` include the selected `entity_id`
    - When an event is selected in `TimelinePanel`: highlight all `GraphPanel` nodes whose `entity_id` is referenced in the selected event's `entity_ids`
    - Create `frontend/src/pages/WorkspacePage.tsx` composing all five panels with the sync hook
    - Create `frontend/src/components/Workspace/Header.tsx`
    - _Requirements: 14.2, 14.3_

- [ ] 27. Docker Compose and deployment configuration
  - [ ] 27.1 Create Docker Compose configuration
    - Create `docker-compose.yml` defining four services: React frontend, FastAPI backend, Neo4j 5.x, PostgreSQL 15.x
    - Configure inter-service networking; set health checks on Neo4j and PostgreSQL
    - Configure the backend to fail with a clear error message on startup if either DB connection cannot be established
    - Mount the `.env` file for secrets; ensure `.env` is in `.gitignore`
    - _Requirements: 17.1, 17.2, 17.4, 17.5_

  - [ ] 27.2 Create Dockerfiles for backend and frontend
    - Create `backend/Dockerfile` and `frontend/Dockerfile`
    - Backend Dockerfile installs pinned dependencies, runs `uvicorn` on the configured port
    - Frontend Dockerfile builds the React app and serves via a static server (e.g., nginx)
    - _Requirements: 17.1, 17.2_

- [ ] 28. Performance instrumentation
  - [ ] 28.1 Add per-stage timing instrumentation to the pipeline
    - In `backend/app/services/ingestion.py`, wrap each pipeline stage (parse, normalize, entity extraction, relationship extraction, candidate retrieval, correlation, graph persistence) with a timing decorator or context manager
    - Expose per-stage elapsed times in the `IngestionResponse` or a separate metrics log entry
    - Ensure timing data is accessible for profiling without code changes (e.g., via structured log output or a metrics endpoint)
    - _Requirements: 18.1, 18.6_

  - [ ]* 28.2 Write performance benchmark tests
    - Write pytest benchmarks measuring p95 latency for: single-event ingestion (target < 500ms), 100-event batch (target < 5s), full graph retrieval (target < 200ms), multi-hop pivot (target < 500ms)
    - _Requirements: 18.2, 18.3, 18.4, 18.5_

- [ ] 29. Evaluation scenarios
  - [ ] 29.1 Create evaluation scenario datasets and test runner
    - Create `data/scenarios/basic_attack_sequence/`, `unrelated_events/`, `legitimate_access/`, `multi_user_host/` directories each containing: a JSON fixture file of labeled events and a `ground_truth.json` defining expected entities, relationships, and non-relationships
    - Create `tests/evaluation/test_scenarios.py` implementing the evaluation test runner that ingests each scenario, queries the resulting graph, and computes precision and recall for expected vs. produced vs. missed relationships
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_

  - [ ] 29.2 Validate evaluation scenario expected outputs
    - Run the four scenarios through the full pipeline and assert:
      - `basic_attack_sequence`: graph contains the expected attack path entities and relationship types
      - `unrelated_events`: graph contains no relationships between unrelated entities
      - `legitimate_access`: relationships are created without inflating correlation scores beyond the evidence
      - `multi_user_host`: entity deduplication is correct; no cross-contamination between investigations
    - _Requirements: 19.1, 19.2, 19.3, 19.4_

- [ ] 30. Final checkpoint — all tests pass
  - Run the complete test suite: `pytest tests/unit/ tests/integration/ tests/evaluation/`
  - Verify Docker Compose starts all four services cleanly with `docker-compose up`
  - Confirm `.env` is not committed and `.env.example` is present
  - Ask the user if any questions or edge cases need clarification before sign-off.

---

## ML/DL/GNN Research Track

These tasks form a parallel research track that builds on the deterministic pipeline above. They are labeled `ML-NN` and do NOT replace or renumber Tasks 1–31. The dependency chain is: Tasks 1–27 → ML-01 onward.

**Critical distinctions to maintain throughout this track:**
- Rule-based correlation (`combined_score`) is a deterministic relevance indicator — NOT an attack probability.
- GNN output is a learned signal — NOT a replacement for rule-based correlation.
- LLM summary is a grounded narrative explanation — NOT proof that an attack occurred.
- These three layers must remain implemented, evaluated, and documented separately.

---

- [ ] ML-01. Dataset Analysis
  - [ ] ML-01.1 Identify and acquire candidate datasets
    - Identify at least one publicly available security event dataset suitable for graph construction (e.g., DARPA TC, LANL Netflow, CERT Insider Threat, CIC-IDS, CTU-13, or similar)
    - Download or link to the dataset; record exact version, URL, and access date in `data/ml/datasets/README.md`
    - _Requirements: ML-01_

  - [ ] ML-01.2 Inspect raw structure of each candidate dataset
    - For each dataset, record in `data/ml/datasets/<dataset_name>/analysis.md`:
      - File format (CSV, JSON, PCAP, syslog, etc.)
      - Total record/event count
      - Schema: all column/field names and types
      - Timestamp fields and format
      - User fields
      - Host / machine fields
      - Source and destination IP fields
      - Process fields
      - File fields
      - Event type / action fields
      - Label fields (if present)
      - Incident or session ID fields
      - Attack category annotations (if present)
    - _Requirements: ML-01_

  - [ ] ML-01.3 Assess ground truth availability
    - For each candidate dataset, document:
      - Whether ground truth labels exist
      - What "positive" means (attack event, malicious connection, anomalous behavior, etc.)
      - What "negative" means (benign, normal, background traffic)
      - Class balance: count and percentage of positive vs. negative examples
      - Whether labels are per-event, per-connection, per-session, or per-scenario
      - Any known labelling issues or inconsistencies in the dataset
    - _Requirements: ML-01, ML-02_

  - [ ] ML-01.4 Assess graph constructibility
    - For each candidate dataset, document:
      - Whether a node-edge graph can be constructed without inventing relationships
      - What fields identify nodes (entities)
      - What fields identify edges (relationships / actions)
      - Whether constructed edges correspond to any of the five TraceGraph relationship types
      - Whether the dataset can be converted to the TraceGraph `SecurityEvent` model via an adapter
      - Whether related events can be grouped into investigations or attack scenarios
    - _Requirements: ML-01_

  - [ ] ML-01.5 Answer the dataset analysis questions
    - For the selected dataset, produce a written answer in `data/ml/datasets/<dataset_name>/analysis.md` for each question:
      1. What is one event/row?
      2. What does that event represent in a real security context?
      3. Which fields identify entities?
      4. Which fields describe actions between entities?
      5. Which fields describe relationships between entities?
      6. What labels exist and how are they assigned?
      7. What is considered a positive example? A negative example?
      8. Can a graph be constructed without inventing relationships?
      9. What could be a realistic prediction target?
      10. What information could leak between train and test sets if splits are random?
    - _Requirements: ML-01_

  - [ ] ML-01.6 Select the primary dataset and document the selection rationale
    - Choose one dataset as the primary ML/GNN research dataset
    - Document: name, reason for selection, limitations, known biases, licence/usage terms
    - Do NOT choose a GNN architecture or ML task at this step — that comes after ground truth definition
    - _Requirements: ML-01_

---

- [ ] ML-02. Ground Truth and Label Definition
  - [ ] ML-02.1 Define the prediction target precisely
    - Based on the dataset analysis, write a formal definition in `data/ml/ground_truth.md`:
      - Prediction target (what the model will predict)
      - Positive example definition (concrete, falsifiable)
      - Negative example definition (concrete, falsifiable)
      - Sample unit (one event? one session? one graph? one subgraph?)
      - Graph unit (what constitutes one graph input to the model?)
    - _Requirements: ML-02_

  - [ ] ML-02.2 Define leakage-safe train/validation/test splits
    - Document the splitting strategy in `data/ml/ground_truth.md`:
      - Why random per-event splitting is or is not safe for this dataset
      - Chosen split strategy: incident-aware, scenario-aware, host-aware, or time-aware
      - Split proportions (e.g., 70/15/15 or 60/20/20)
      - How to verify that no positive incident has events in both train and test
    - _Requirements: ML-02_

  - [ ] ML-02.3 Reuse the TraceGraph evaluation scenarios as a labelled validation set
    - Verify that the four evaluation scenarios from Task 29 (`basic_attack_sequence`, `unrelated_events`, `legitimate_access`, `multi_user_host`) can serve as a controlled validation or test set for the ML experiments
    - Document which scenarios are usable and any limitations
    - _Requirements: ML-02, 19.1–19.5_

  - [ ] ML-02.4 Implement dataset preparation scripts
    - Create `research/ml/data_prep/prepare_dataset.py` that:
      - Loads the raw dataset
      - Converts events to `SecurityEvent` format via the existing adapter (or a new one registered in the adapter registry)
      - Assigns labels according to the ground truth definition
      - Produces deterministic train/validation/test splits (seeded, reproducible)
      - Saves prepared splits to `data/ml/splits/`
    - _Requirements: ML-02_

---

- [ ] ML-03. ML Fundamentals and Optional Classical Baseline
  - [ ] ML-03.1 Assess whether a classical ML baseline is appropriate
    - Determine whether the dataset and prediction target support a meaningful tabular/feature-based ML baseline
    - Document the decision in `research/ml/baseline/README.md`: either the baseline is justified (with feature plan) or it is not justified (with reasoning)
    - Do not implement a baseline purely for complexity — only if it provides a useful comparison point
    - _Requirements: ML-03_

  - [ ] ML-03.2 (Optional) Engineer tabular features
    - If the classical baseline is justified, engineer features that do NOT use raw graph structure:
      - Event frequency counts per entity
      - Temporal gap between events
      - Entity occurrence counts (degree-like statistics)
      - Rule-signal counts from the deterministic correlation engine
      - Severity distribution
    - Document each feature: name, derivation formula, expected predictive value
    - _Requirements: ML-03_

  - [ ] ML-03.3 (Optional) Train and evaluate a classical baseline model
    - Choose at most one of: Logistic Regression, Random Forest, XGBoost
    - Train on the training split, tune on the validation split, evaluate on the test split
    - Report: precision, recall, F1, PR-AUC, ROC-AUC, false-positive count, false-negative count
    - Do NOT use accuracy as the primary metric if the dataset is imbalanced
    - Save the trained model to `research/ml/baseline/models/`
    - _Requirements: ML-03_

---

- [ ] ML-04. Neural Network Fundamentals
  - [ ] ML-04.1 Implement and study a small feed-forward neural network on a simple task
    - Create `research/ml/nn_fundamentals/feedforward_demo.py` demonstrating:
      - Tensor creation and shapes
      - A two-layer feed-forward network (manually or via PyTorch/TensorFlow)
      - Forward pass
      - Loss computation (binary cross-entropy or MSE)
      - Backpropagation and gradient descent
      - Training loop with epochs and batches
      - Validation loss monitoring
    - This demo should use a toy dataset (e.g., synthetic binary classification), not the security dataset
    - _Requirements: ML-04_

  - [ ] ML-04.2 Demonstrate understanding of training dynamics
    - Add a notebook or script `research/ml/nn_fundamentals/training_dynamics.ipynb` that shows:
      - Effect of learning rate (too high, too low, appropriate)
      - Overfitting on a small dataset
      - Effect of a simple regularization technique (dropout or weight decay)
      - Train vs. validation loss curves
      - Checkpoint saving and loading
    - _Requirements: ML-04_

---

- [ ] ML-05. GNN Fundamentals
  - [ ] ML-05.1 Study and document core GNN concepts
    - Create `research/ml/gnn_fundamentals/concepts.md` covering:
      - Graph representation: adjacency matrix vs. edge list
      - Node features and edge features
      - Message passing and neighborhood aggregation
      - Node embeddings and graph embeddings
      - Transductive vs. inductive learning
      - Heterogeneous graphs (multiple node and edge types — relevant to TraceGraph)
      - Temporal graphs (dynamic edges — relevant to security event data)
    - _Requirements: ML-05_

  - [ ] ML-05.2 Implement a minimal GCN on a standard benchmark
    - Create `research/ml/gnn_fundamentals/gcn_demo.py` implementing a two-layer GCN on a standard small graph dataset (e.g., Cora citation network via PyTorch Geometric or DGL)
    - Demonstrate: graph loading, node feature construction, forward pass, training loop, accuracy on held-out nodes
    - This is a fundamentals exercise — use the standard dataset, not the security dataset
    - _Requirements: ML-05_

  - [ ] ML-05.3 Study candidate GNN families and document trade-offs
    - Create `research/ml/gnn_fundamentals/architecture_survey.md` comparing:
      - GCN: spectral convolution, transductive, fixed graph
      - GraphSAGE: inductive, neighborhood sampling, scales to large graphs
      - GAT: attention-weighted aggregation, interpretable weights, more parameters
    - For each architecture, note: inductive/transductive, scalability, heterogeneous graph support, ease of debugging
    - Do NOT select an architecture yet — that happens after task ML-06
    - _Requirements: ML-05_

---

- [ ] ML-06. GNN Task Selection
  - [ ] ML-06.1 Define candidate GNN tasks and evaluate against the dataset
    - Based on the dataset analysis (ML-01) and ground truth definition (ML-02), evaluate the feasibility of:
      - **Node classification**: classify individual entity nodes as malicious/benign
      - **Edge classification**: classify individual relationships as malicious/benign
      - **Link prediction**: predict missing or future relationships
      - **Graph/subgraph classification**: classify an entire investigation graph or subgraph
      - **Anomaly detection**: score entities or subgraphs as anomalous
    - For each candidate task, document: available labels, graph structure fit, number of labelled examples, evaluation reliability
    - _Requirements: ML-06_

  - [ ] ML-06.2 Select and formally specify the GNN task
    - Write a task specification in `research/ml/task_spec.md` that records:
      1. Chosen task (one of the five candidates above)
      2. Why it matches the dataset and labels
      3. Target variable / label definition
      4. Graph representation (nodes, edges, features)
      5. Required node features
      6. Required edge features (if applicable)
      7. Evaluation metrics (must include at minimum precision, recall, F1; add PR-AUC or ROC-AUC if appropriate)
      8. Known limitations and risks (class imbalance, label noise, leakage risks)
    - This specification must be written before any GNN code is written
    - _Requirements: ML-06_

---

- [ ] ML-07. Baseline GNN Experiment
  - [ ] ML-07.1 Implement graph construction from the security dataset
    - Create `research/ml/experiments/build_graph.py` that:
      - Loads the prepared dataset splits from `data/ml/splits/`
      - Constructs a graph (or heterogeneous graph) from the events
      - Maps entities to nodes with feature vectors
      - Maps relationships to edges with optional edge features
      - Saves the constructed graphs (one per split) to `data/ml/graphs/`
    - Validate: correct number of nodes, correct number of edges, no missing features, labels present
    - _Requirements: ML-07_

  - [ ] ML-07.2 Implement the baseline GNN model
    - Create `research/ml/experiments/model.py` implementing the selected GNN architecture from ML-06
    - Use PyTorch Geometric or DGL (add to `research/requirements.txt`)
    - Implement: forward pass, configurable number of layers, configurable hidden dimension
    - Keep the initial architecture minimal — one or two GNN layers; complexity can be added after the baseline works
    - _Requirements: ML-07_

  - [ ] ML-07.3 Implement the training and evaluation loop
    - Create `research/ml/experiments/train.py` with:
      - Configurable hyperparameters loaded from `research/ml/experiments/config.yaml`: learning rate, hidden dim, num layers, epochs, batch size, random seed
      - Training loop with per-epoch train loss and validation metric logging
      - Early stopping based on validation metric
      - Checkpoint saving at best validation metric
      - Final evaluation on the test set after training completes
    - _Requirements: ML-07_

  - [ ] ML-07.4 Record the experiment results
    - Create `research/ml/experiments/results/run_001.md` recording:
      - Dataset version
      - Graph construction method
      - Node features (names and shapes)
      - Edge features (if used)
      - Labels
      - Train/validation/test split sizes
      - Model architecture
      - Hyperparameters (all values from config.yaml)
      - Optimizer and learning rate
      - Number of epochs trained
      - Random seed
      - Training loss curve (final value)
      - Validation metric curve (final value)
      - **Test set metrics**: precision, recall, F1, PR-AUC (or ROC-AUC), false positives, false negatives
      - Checkpoint location
      - Inference time per graph
    - _Requirements: ML-07_

  - [ ] ML-07.5 Verify experiment reproducibility
    - Re-run the training script with the same config and seed
    - Verify that test set metrics match `run_001.md` within floating-point tolerance
    - Document any non-determinism and its source (GPU parallelism, data loading order, etc.)
    - _Requirements: ML-07_

---

- [ ] ML-08. GNN Evaluation
  - [ ] ML-08.1 Evaluate the trained GNN on the held-out test set
    - Load the best checkpoint from ML-07
    - Run inference on the test set
    - Compute and record: precision, recall, F1, PR-AUC, ROC-AUC (as appropriate to the task), false positives, false negatives, detection latency (inference time), attack scenario coverage
    - Do NOT use accuracy as the primary metric for imbalanced data
    - _Requirements: ML-08_

  - [ ] ML-08.2 Perform error analysis
    - Inspect false positives and false negatives manually
    - Document patterns: are certain entity types consistently mispredicted? Are false positives clustered around particular graph structures? Are false negatives associated with rare attack patterns?
    - Create `research/ml/experiments/error_analysis/run_001.md` recording findings
    - _Requirements: ML-08_

  - [ ] ML-08.3 Assess and document evaluation limitations
    - In `research/ml/experiments/error_analysis/run_001.md`, state explicitly:
      - Class imbalance and its effect on metrics
      - Label uncertainty or noise
      - Possible data leakage (and evidence it was avoided)
      - Dataset size and generalizability limits
      - Whether results are likely to hold outside this specific dataset/scenario
    - _Requirements: ML-08_

---

- [ ] ML-09. Rule-Based vs. GNN Comparison
  - [ ] ML-09.1 Define a shared evaluation protocol
    - Create `research/ml/comparison/protocol.md` specifying:
      - The common evaluation dataset/scenario (must be the same for both systems)
      - The prediction target (must be comparable across both systems)
      - All metrics to be reported (precision, recall, F1, PR-AUC/ROC-AUC, false positives, false negatives, latency, coverage)
      - How the rule-based `combined_score` will be converted to a binary prediction (threshold selection)
      - How the GNN output will be converted to a binary prediction (threshold selection)
    - _Requirements: ML-09_

  - [ ] ML-09.2 Run the rule-based baseline on the shared evaluation set
    - Use the existing `TemporalCorrelationEngine` from Task 11
    - Ingest the evaluation scenario events through the full pipeline
    - Apply a threshold to `combined_score` to produce binary predictions
    - Record: precision, recall, F1, PR-AUC (if applicable), false positives, false negatives, latency
    - If the classical ML baseline (ML-03) was implemented, run it on the same evaluation set and record its metrics too
    - _Requirements: ML-09_

  - [ ] ML-09.3 Run the GNN on the shared evaluation set
    - Load the best GNN checkpoint from ML-07
    - Run inference on the same evaluation set used in ML-09.2
    - Record the same metrics in the same format
    - _Requirements: ML-09_

  - [ ] ML-09.4 Produce the comparison table and analysis
    - Create `research/ml/comparison/results.md` containing:
      - A side-by-side metric table: rule-based | (classical ML if applicable) | GNN
      - Narrative analysis: where each approach performs better, where it is worse, and why
      - Observations about false positive patterns, false negative patterns, and latency
      - An explicit statement of what the data does and does not support
    - Do NOT write a conclusion that assumes the GNN wins — report what the data shows
    - _Requirements: ML-09_

---

- [ ] ML-10. GNN Integration into the TraceGraph Pipeline
  - [ ] ML-10.1 Design the integration architecture
    - Only begin this task after ML-07 (standalone experiment working) and ML-09 (comparison complete)
    - Write `research/ml/integration/design.md` specifying:
      - Where in the pipeline GNN inference runs (after graph persistence, before or after LLM context building)
      - Model input format: what graph data is passed to the GNN
      - Graph-to-model conversion: how the investigation graph is converted to GNN input tensors
      - Feature construction at inference time
      - Inference service/module location (`backend/app/services/gnn_inference.py`)
      - Model version management (how the model file is referenced)
      - Prediction output format and what it represents
      - How GNN output is distinguished from deterministic `combined_score` in API responses and the analyst UI
      - Failure handling: if GNN inference fails, the investigation workflow continues unchanged
      - Evidence linkage: which graph nodes/edges the prediction applies to
    - _Requirements: ML-10_

  - [ ] ML-10.2 Implement `GNNInferenceService`
    - Create `backend/app/services/gnn_inference.py` with `GNNInferenceService.predict(graph: GraphResult, investigation_id: str) -> GNNPrediction`
    - Load model from a configured path (environment variable, not hardcoded)
    - Convert `GraphResult` to model input tensors using the same feature construction as `build_graph.py`
    - Return `GNNPrediction` carrying: prediction value(s), confidence/score, model version, feature names used, a note that this is a learned signal (not a ground truth label)
    - If model file is missing or inference fails: log the error and return `GNNPrediction(available=False)` — never raise to caller
    - _Requirements: ML-10_

  - [ ] ML-10.3 Extend `InvestigationContext` to include GNN output
    - Add an optional `gnn_signal: GNNPrediction | None` field to `InvestigationContext`
    - Populate it in `AIContextBuilder.build_context()` when `GNNInferenceService` is available and returns a valid prediction
    - The LLM system prompt must be updated to describe the GNN signal accurately: "a learned graph pattern score — not a confirmed attack label"
    - _Requirements: ML-10_

  - [ ] ML-10.4 Expose GNN prediction in the graph API response
    - Add `gnn_signal: GNNPrediction | None` to the `GraphResult` schema
    - Populate it in the `GET /api/investigations/{id}/graph` response when available
    - Document in the API response that this is a learned signal, not a deterministic label
    - _Requirements: ML-10_

  - [ ] ML-10.5 Write integration tests for GNN failure isolation
    - Test that when `GNNInferenceService` raises an exception or returns `available=False`, the rest of the investigation workflow (graph retrieval, timeline, evidence, AI summary) continues to function correctly
    - Test that GNN output does not appear in the `InvestigationContext` when the model is unavailable
    - _Requirements: ML-10_

---

- [ ] ML-11. Final ML Research Documentation
  - [ ] ML-11.1 Write the final ML research report
    - Create `research/ml/report/final_report.md` documenting:
      - Dataset: name, version, source, access date, licence
      - Reason the dataset was selected over alternatives
      - Problem definition and prediction target
      - Graph representation: nodes, edges, features
      - GNN architecture: layers, hidden dimensions, activation functions, pooling
      - Feature design: all node and edge features used, with derivation formulas
      - Labels: positive/negative definition, source
      - Split strategy: method, proportions, leakage avoidance approach
      - Baseline methods: rule-based correlation, classical ML (if implemented)
      - Metrics used and why they were chosen for this imbalanced task
      - Results table: all systems, all metrics, train/val/test
      - Error analysis summary: false positive patterns, false negative patterns
      - Limitations: dataset size, generalizability, label quality, class imbalance
      - Reproducibility: how to re-run the experiment from scratch
      - Integration design summary
      - What the evidence actually supports — and what it does not
    - _Requirements: ML-11_

  - [ ] ML-11.2 Validate reproducibility of the full research pipeline
    - Document the exact commands to:
      1. Acquire the dataset
      2. Run `prepare_dataset.py`
      3. Run `build_graph.py`
      4. Run `train.py` with the recorded config
      5. Run the evaluation against the evaluation scenarios
      6. Reproduce the comparison table
    - A person who was not involved in the project must be able to reproduce the key results from these instructions
    - _Requirements: ML-11_

---

## ML/DL/GNN Research Track — Dependency Chain

```
Tasks 1–10 (implemented)
        ↓
Tasks 11–25 (core engineering)
        ↓
Task 26 — evaluation dataset / scenarios
        ↓
Task 27 — measurable rule-based baseline (precision/recall)
        ↓
ML-01 — dataset analysis
        ↓
ML-02 — ground truth / label definition
        ↓
ML-03 — optional classical ML baseline
        ↓
ML-04 — neural network fundamentals
        ↓
ML-05 — GNN fundamentals
        ↓
ML-06 — GNN task selection
        ↓
ML-07 — baseline GNN experiment
        ↓
ML-08 — GNN evaluation
        ↓
ML-09 — rule vs. GNN comparison
        ↓
ML-10 — GNN integration (only after standalone experiment is valid)
        ↓
Task 28 — investigation utility evaluation
        ↓
Task 29 — AI summary grounding validation
        ↓
Task 30 — end-to-end demonstration
        ↓
Task 31 — definition of done
```

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP; property-based tests in particular can be added incrementally
- All property tests use the `hypothesis` library; each property is annotated with its property number from the design document
- Every API handler applies JWT middleware and ownership enforcement — never bypass for convenience
- No secrets are ever hardcoded; all credentials are loaded via Pydantic `BaseSettings` from environment variables
- Parameterized queries are mandatory for both PostgreSQL (SQLAlchemy) and Neo4j (Cypher parameters) — string interpolation in queries is a hard requirement violation
- The `combined_score` from the Correlation Engine is explicitly NOT an attack probability — this distinction must appear in code comments and API documentation
- Checkpoints at tasks 12, 18, 22, and 30 ensure incremental validation throughout the build
- ML/DL/GNN research tasks (ML-01 through ML-11) are a separate research track; they do not replace Tasks 1–31 and should not be started before Task 27 (measurable rule-based baseline) is complete
- The GNN is not assumed to outperform the deterministic baseline — the experiment determines the result
- All three reasoning layers (rule-based correlation, GNN learned signal, LLM narrative) must remain implemented, evaluated, and documented separately

---

## Task Dependency Graph

### Engineering Tasks (Tasks 1–30)

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "2.2", "3.1"] },
    { "id": 1, "tasks": ["2.3", "3.2", "4.1", "5.1"] },
    { "id": 2, "tasks": ["4.2", "5.2", "6.1", "7.1"] },
    { "id": 3, "tasks": ["5.3", "5.4", "6.2", "6.3", "6.4", "7.2", "8.1"] },
    { "id": 4, "tasks": ["7.3", "8.2", "8.3", "8.4", "9.1", "10.1"] },
    { "id": 5, "tasks": ["9.2", "9.3", "10.2", "10.3", "11.1"] },
    { "id": 6, "tasks": ["11.2", "11.3", "11.4", "13.1"] },
    { "id": 7, "tasks": ["13.2", "13.3", "13.4", "14.1", "14.2"] },
    { "id": 8, "tasks": ["14.3", "14.4", "15.1", "16.1"] },
    { "id": 9, "tasks": ["15.2", "15.3", "15.4", "15.5", "16.2", "17.1"] },
    { "id": 10, "tasks": ["16.3", "17.2", "19.1", "21.1"] },
    { "id": 11, "tasks": ["19.2", "20.1"] },
    { "id": 12, "tasks": ["20.2", "20.3", "20.4", "20.5", "23.1"] },
    { "id": 13, "tasks": ["23.2", "24.1"] },
    { "id": 14, "tasks": ["25.1", "25.2", "25.3", "25.4", "25.5"] },
    { "id": 15, "tasks": ["26.1", "27.1", "27.2", "28.1"] },
    { "id": 16, "tasks": ["28.2", "29.1"] },
    { "id": 17, "tasks": ["29.2"] }
  ]
}
```

### ML/DL/GNN Research Track Dependencies

```
Tasks 1–10 (✓ implemented)
        ↓
Tasks 11–27 (engineering: correlation → evaluation baseline)
        ↓
ML-01.1 → ML-01.2 → ML-01.3 → ML-01.4 → ML-01.5 → ML-01.6
        ↓
ML-02.1 → ML-02.2 → ML-02.3 → ML-02.4
        ↓
ML-03.1 → ML-03.2* → ML-03.3*    (parallel with ML-04)
        ↓
ML-04.1 → ML-04.2
        ↓
ML-05.1 → ML-05.2 → ML-05.3
        ↓
ML-06.1 → ML-06.2
        ↓
ML-07.1 → ML-07.2 → ML-07.3 → ML-07.4 → ML-07.5
        ↓
ML-08.1 → ML-08.2 → ML-08.3
        ↓
ML-09.1 → ML-09.2 → ML-09.3 → ML-09.4
        ↓
ML-10.1 → ML-10.2 → ML-10.3 → ML-10.4 → ML-10.5
        ↓
ML-11.1 → ML-11.2
        ↓
Tasks 28–30 (investigation utility, AI grounding, demo)
```

`*` denotes optional tasks.
