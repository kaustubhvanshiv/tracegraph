import re

with open(r'd:\tracegraph\backend\app\services\ingestion.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Parse and Normalize
parse_orig = """        accepted_events: list[SecurityEvent] = []
        rejected_events: list[RejectedEvent] = []
        normalizer = NormalizationEngine()

        for raw in raw_events:
            # a. Parse
            parse_result = default_registry.dispatch(source_type, raw)
            if isinstance(parse_result, ParseError):
                logger.debug(
                    "Parse failure for event",
                    extra={
                        "event_id": parse_result.event_id,
                        "field": parse_result.field_name,
                        "reason": parse_result.reason,
                        "investigation_id": investigation_id,
                    },
                )
                rejected_events.append(
                    RejectedEvent(
                        event_id=parse_result.event_id,
                        reason=parse_result.reason,
                        field=parse_result.field_name,
                    )
                )
                continue

            # b. Normalize (validate timestamps, canonicalize identifiers, etc.)
            try:
                security_event = normalizer.normalize(parse_result)
            except (AppValidationError, Exception) as exc:
                logger.debug(
                    "Normalization failure for event",
                    extra={
                        "event_id": parse_result.event_id,
                        "reason": str(exc),
                        "investigation_id": investigation_id,
                    },
                )
                rejected_events.append(
                    RejectedEvent(
                        event_id=parse_result.event_id,
                        reason=str(exc),
                    )
                )
                continue

            accepted_events.append(security_event)"""

parse_new = """        metrics: dict[str, float] = {}
        accepted_events: list[SecurityEvent] = []
        rejected_events: list[RejectedEvent] = []
        normalizer = NormalizationEngine()

        with StageTimer("parse_and_normalize", metrics):
            for raw in raw_events:
                # a. Parse
                parse_result = default_registry.dispatch(source_type, raw)
                if isinstance(parse_result, ParseError):
                    logger.debug(
                        "Parse failure for event",
                        extra={
                            "event_id": parse_result.event_id,
                            "field": parse_result.field_name,
                            "reason": parse_result.reason,
                            "investigation_id": investigation_id,
                        },
                    )
                    rejected_events.append(
                        RejectedEvent(
                            event_id=parse_result.event_id,
                            reason=parse_result.reason,
                            field=parse_result.field_name,
                        )
                    )
                    continue

                # b. Normalize (validate timestamps, canonicalize identifiers, etc.)
                try:
                    security_event = normalizer.normalize(parse_result)
                except (AppValidationError, Exception) as exc:
                    logger.debug(
                        "Normalization failure for event",
                        extra={
                            "event_id": parse_result.event_id,
                            "reason": str(exc),
                            "investigation_id": investigation_id,
                        },
                    )
                    rejected_events.append(
                        RejectedEvent(
                            event_id=parse_result.event_id,
                            reason=str(exc),
                        )
                    )
                    continue

                accepted_events.append(security_event)"""

content = content.replace(parse_orig, parse_new)

# 2. Entity Extraction
entity_orig = """        extractor = EntityExtractor()
        entities = extractor.extract(accepted_events, investigation_id=investigation_id)

        # Build event_id → [entity_id, ...] map for EventRepository
        entity_map: dict[str, list[str]] = {}
        for entity in entities:
            for eid in entity.event_ids:
                entity_map.setdefault(eid, []).append(entity.entity_id)"""

entity_new = """        with StageTimer("entity_extraction", metrics):
            extractor = EntityExtractor()
            entities = extractor.extract(accepted_events, investigation_id=investigation_id)

            # Build event_id → [entity_id, ...] map for EventRepository
            entity_map: dict[str, list[str]] = {}
            for entity in entities:
                for eid in entity.event_ids:
                    entity_map.setdefault(eid, []).append(entity.entity_id)"""

content = content.replace(entity_orig, entity_new)

# 3. Relationship Extraction
rel_orig = """        rel_extractor = RelationshipExtractor()
        raw_rels = rel_extractor.extract(
            accepted_events,
            entities,
            investigation_id=investigation_id,
        )"""

rel_new = """        with StageTimer("relationship_extraction", metrics):
            rel_extractor = RelationshipExtractor()
            raw_rels = rel_extractor.extract(
                accepted_events,
                entities,
                investigation_id=investigation_id,
            )"""
            
content = content.replace(rel_orig, rel_new)

# 4. Candidate Retrieval
cand_orig = """        sorted_events = sorted(accepted_events, key=lambda e: e.timestamp)

        candidate_retrieval = CandidateRetrieval()
        candidates = candidate_retrieval.retrieve(
            sorted_events,
            window_minutes=10,
            investigation_id=investigation_id,
        )"""
        
cand_new = """        with StageTimer("candidate_retrieval", metrics):
            sorted_events = sorted(accepted_events, key=lambda e: e.timestamp)

            candidate_retrieval = CandidateRetrieval()
            candidates = candidate_retrieval.retrieve(
                sorted_events,
                window_minutes=10,
                investigation_id=investigation_id,
            )"""
            
content = content.replace(cand_orig, cand_new)

# 5. Temporal correlation
corr_orig = """        corr_engine = TemporalCorrelationEngine()
        correlated_rels = corr_engine.correlate(candidates)"""

corr_new = """        with StageTimer("correlation", metrics):
            corr_engine = TemporalCorrelationEngine()
            correlated_rels = corr_engine.correlate(candidates)"""

content = content.replace(corr_orig, corr_new)

# 6. Graph Persistence
graph_orig = """        graph_repo = GraphRepository(self._neo4j_driver)

        # Upsert all entities
        for entity in entities:
            await graph_repo.upsert_entity(entity)  # raises GraphUnavailableError on failure

        # Build a set of (source, target, type) keys for correlated rels to
        # detect which raw_rels have no correlated counterpart.
        corr_keys: set[tuple[str, str, str]] = {
            (r.source_entity_id, r.target_entity_id, r.relationship_type.value)
            for r in correlated_rels
        }

        # Upsert correlated relationships (carry signal metadata)
        for rel in correlated_rels:
            await graph_repo.upsert_relationship(rel)

        # Upsert raw relationships that were NOT enriched by correlation
        # (single-event evidence with no temporal pairing partner).
        # Convert RawRelationship → CorrelatedRelationship with zero signal metadata.
        from app.schemas.relationship import CorrelatedRelationship  # noqa: PLC0415

        for raw_rel in raw_rels:
            key = (
                raw_rel.source_entity_id,
                raw_rel.target_entity_id,
                raw_rel.relationship_type.value,
            )
            if key not in corr_keys:
                # Promote to CorrelatedRelationship with no signal data
                promoted = CorrelatedRelationship(
                    relationship_id=raw_rel.relationship_id,
                    source_entity_id=raw_rel.source_entity_id,
                    target_entity_id=raw_rel.target_entity_id,
                    relationship_type=raw_rel.relationship_type,
                    investigation_id=raw_rel.investigation_id,
                    timestamp=raw_rel.timestamp,
                    event_ids=raw_rel.event_ids,
                    source=raw_rel.source,
                    signal_names=[],
                    signal_scores={},
                    combined_score=0.0,
                    explanation="Directly extracted relationship (no temporal correlation).",
                )
                await graph_repo.upsert_relationship(promoted)"""

graph_new = """        with StageTimer("graph_persistence", metrics):
            graph_repo = GraphRepository(self._neo4j_driver)

            # Upsert all entities
            for entity in entities:
                await graph_repo.upsert_entity(entity)  # raises GraphUnavailableError on failure

            # Build a set of (source, target, type) keys for correlated rels to
            # detect which raw_rels have no correlated counterpart.
            corr_keys: set[tuple[str, str, str]] = {
                (r.source_entity_id, r.target_entity_id, r.relationship_type.value)
                for r in correlated_rels
            }

            # Upsert correlated relationships (carry signal metadata)
            for rel in correlated_rels:
                await graph_repo.upsert_relationship(rel)

            # Upsert raw relationships that were NOT enriched by correlation
            # (single-event evidence with no temporal pairing partner).
            # Convert RawRelationship → CorrelatedRelationship with zero signal metadata.
            from app.schemas.relationship import CorrelatedRelationship  # noqa: PLC0415

            for raw_rel in raw_rels:
                key = (
                    raw_rel.source_entity_id,
                    raw_rel.target_entity_id,
                    raw_rel.relationship_type.value,
                )
                if key not in corr_keys:
                    # Promote to CorrelatedRelationship with no signal data
                    promoted = CorrelatedRelationship(
                        relationship_id=raw_rel.relationship_id,
                        source_entity_id=raw_rel.source_entity_id,
                        target_entity_id=raw_rel.target_entity_id,
                        relationship_type=raw_rel.relationship_type,
                        investigation_id=raw_rel.investigation_id,
                        timestamp=raw_rel.timestamp,
                        event_ids=raw_rel.event_ids,
                        source=raw_rel.source,
                        signal_names=[],
                        signal_scores={},
                        combined_score=0.0,
                        explanation="Directly extracted relationship (no temporal correlation).",
                    )
                    await graph_repo.upsert_relationship(promoted)"""

content = content.replace(graph_orig, graph_new)

# 7. Postgres persistence
pg_orig = """        from app.repositories.event_repository import EventRepository  # noqa: PLC0415

        ev_repo = EventRepository(self._db)
        await ev_repo.store(
            accepted_events,
            investigation_id=investigation_id,
            entity_map=entity_map,
        )"""

pg_new = """        with StageTimer("pg_persistence", metrics):
            from app.repositories.event_repository import EventRepository  # noqa: PLC0415

            ev_repo = EventRepository(self._db)
            await ev_repo.store(
                accepted_events,
                investigation_id=investigation_id,
                entity_map=entity_map,
            )"""

content = content.replace(pg_orig, pg_new)

# 8. Add metrics to return and logger
ret_orig = """        logger.info(
            "Ingestion pipeline complete",
            extra={
                "investigation_id": investigation_id,
                "accepted": len(accepted_events),
                "entities": len(entities),
                "correlated_relationships": len(correlated_rels),
            },
        )

        return IngestionResponse(
            accepted=len(accepted_events),
            rejected=len(rejected_events),
            errors=rejected_events,
        )"""

ret_new = """        logger.info(
            "Ingestion pipeline complete",
            extra={
                "investigation_id": investigation_id,
                "accepted": len(accepted_events),
                "entities": len(entities),
                "correlated_relationships": len(correlated_rels),
                "timing_metrics": metrics,
            },
        )

        return IngestionResponse(
            accepted=len(accepted_events),
            rejected=len(rejected_events),
            errors=rejected_events,
            timing_metrics=metrics,
        )"""

content = content.replace(ret_orig, ret_new)

with open(r'd:\tracegraph\backend\app\services\ingestion.py', 'w', encoding='utf-8') as f:
    f.write(content)
