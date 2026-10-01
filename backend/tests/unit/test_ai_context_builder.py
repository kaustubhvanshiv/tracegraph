"""Unit tests for AIContextBuilder (Task 19.2).

Tests:
  - Size limit enforcement (max_events)
  - Severity and connectivity prioritization
  - Graph-only entity inclusion
  - Evidence-referencing relationship filtering
  - total_events count accuracy
  - JSON serializability (no circular references)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.schemas.entity import Entity, EntityType
from app.schemas.graph import GraphResult
from app.schemas.relationship import CorrelatedRelationship, RelationshipType
from app.schemas.security_event import SecurityEvent
from app.schemas.summary import InvestigationContext
from app.services.ai_context_builder import AIContextBuilder


@pytest.fixture
def builder() -> AIContextBuilder:
    return AIContextBuilder()


@pytest.fixture
def sample_entity() -> Entity:
    return Entity(
        entity_id="user:alice",
        entity_type=EntityType.USER,
        canonical_key="alice",
        aliases=["alice"],
        event_ids=["evt-001"],
        investigation_id="inv-100",
    )


@pytest.fixture
def sample_relationship() -> CorrelatedRelationship:
    return CorrelatedRelationship(
        relationship_id="rel-001",
        source_entity_id="user:alice",
        target_entity_id="host:workstation1",
        relationship_type=RelationshipType.EXECUTED,
        investigation_id="inv-100",
        timestamp=datetime.now(timezone.utc),
        event_ids=["evt-001"],
        source="sysmon",
        signal_names=["shared_user"],
        signal_scores={"shared_user": 0.5},
        combined_score=0.5,
        explanation="Alice executed process",
    )


def test_build_context_basic(
    builder: AIContextBuilder,
    sample_entity: Entity,
    sample_relationship: CorrelatedRelationship,
) -> None:
    graph = GraphResult(
        investigation_id="inv-100",
        nodes=[sample_entity],
        edges=[sample_relationship],
    )
    event = SecurityEvent(
        event_id="evt-001",
        source_type="sysmon",
        timestamp=datetime.now(timezone.utc),
        event_type="process_creation",
        action="execute",
        severity="high",
        raw_data={"Image": "cmd.exe"},
    )

    context = builder.build_context(
        investigation_id="inv-100",
        graph=graph,
        timeline=[event],
        max_events=10,
    )

    assert isinstance(context, InvestigationContext)
    assert context.investigation_id == "inv-100"
    assert context.total_events == 1
    assert len(context.entities) == 1
    assert context.entities[0].entity_id == "user:alice"
    assert len(context.relationships) == 1
    assert context.relationships[0].relationship_id == "rel-001"
    assert len(context.sampled_events) == 1
    assert context.sampled_events[0].event_id == "evt-001"


def test_build_context_severity_prioritization(
    builder: AIContextBuilder,
    sample_entity: Entity,
) -> None:
    graph = GraphResult(investigation_id="inv-100", nodes=[sample_entity], edges=[])
    events = [
        SecurityEvent(
            event_id="evt-low",
            source_type="sysmon",
            timestamp=datetime.now(timezone.utc),
            event_type="logon",
            action="login",
            severity="low",
        ),
        SecurityEvent(
            event_id="evt-critical",
            source_type="sysmon",
            timestamp=datetime.now(timezone.utc),
            event_type="malware",
            action="detect",
            severity="critical",
        ),
        SecurityEvent(
            event_id="evt-medium",
            source_type="sysmon",
            timestamp=datetime.now(timezone.utc),
            event_type="network",
            action="connect",
            severity="medium",
        ),
    ]

    context = builder.build_context(
        investigation_id="inv-100",
        graph=graph,
        timeline=events,
        max_events=2,
    )

    assert context.total_events == 3
    assert len(context.sampled_events) == 2
    # Critical and Medium (higher severity weights) should be sampled first
    sampled_ids = [e.event_id for e in context.sampled_events]
    assert "evt-critical" in sampled_ids
    assert "evt-medium" in sampled_ids
    assert "evt-low" not in sampled_ids


def test_build_context_connectivity_prioritization(
    builder: AIContextBuilder,
    sample_entity: Entity,
) -> None:
    rel1 = CorrelatedRelationship(
        relationship_id="rel-1",
        source_entity_id="user:alice",
        target_entity_id="host:w1",
        relationship_type=RelationshipType.EXECUTED,
        investigation_id="inv-100",
        timestamp=datetime.now(timezone.utc),
        event_ids=["evt-connected"],
        source="sysmon",
        combined_score=0.8,
        explanation="Connected event",
    )
    graph = GraphResult(investigation_id="inv-100", nodes=[sample_entity], edges=[rel1])

    events = [
        SecurityEvent(
            event_id="evt-unconnected",
            source_type="sysmon",
            timestamp=datetime.now(timezone.utc),
            event_type="logon",
            action="login",
            severity="low",
        ),
        SecurityEvent(
            event_id="evt-connected",
            source_type="sysmon",
            timestamp=datetime.now(timezone.utc),
            event_type="process",
            action="execute",
            severity="low",
        ),
    ]

    context = builder.build_context(
        investigation_id="inv-100",
        graph=graph,
        timeline=events,
        max_events=1,
    )

    assert len(context.sampled_events) == 1
    assert context.sampled_events[0].event_id == "evt-connected"


def test_build_context_relationship_filtering(
    builder: AIContextBuilder,
    sample_entity: Entity,
) -> None:
    rel_no_evidence = CorrelatedRelationship(
        relationship_id="rel-no-ev",
        source_entity_id="user:alice",
        target_entity_id="host:w1",
        relationship_type=RelationshipType.EXECUTED,
        investigation_id="inv-100",
        timestamp=datetime.now(timezone.utc),
        event_ids=[],  # zero evidence references
        source="sysmon",
        combined_score=0.5,
        explanation="No evidence",
    )
    rel_with_evidence = CorrelatedRelationship(
        relationship_id="rel-with-ev",
        source_entity_id="user:alice",
        target_entity_id="host:w1",
        relationship_type=RelationshipType.EXECUTED,
        investigation_id="inv-100",
        timestamp=datetime.now(timezone.utc),
        event_ids=["evt-001"],
        source="sysmon",
        combined_score=0.8,
        explanation="With evidence",
    )
    graph = GraphResult(
        investigation_id="inv-100",
        nodes=[sample_entity],
        edges=[rel_no_evidence, rel_with_evidence],
    )

    context = builder.build_context(
        investigation_id="inv-100",
        graph=graph,
        timeline=[],
    )

    assert len(context.relationships) == 1
    assert context.relationships[0].relationship_id == "rel-with-ev"


def test_build_context_json_serializable(
    builder: AIContextBuilder,
    sample_entity: Entity,
    sample_relationship: CorrelatedRelationship,
) -> None:
    graph = GraphResult(
        investigation_id="inv-100",
        nodes=[sample_entity],
        edges=[sample_relationship],
    )
    event = SecurityEvent(
        event_id="evt-001",
        source_type="sysmon",
        timestamp=datetime.now(timezone.utc),
        event_type="process_creation",
        action="execute",
        severity="medium",
    )

    context = builder.build_context(
        investigation_id="inv-100",
        graph=graph,
        timeline=[event],
    )

    json_str = context.model_dump_json()
    assert isinstance(json_str, str)
    data = json.loads(json_str)
    assert data["investigation_id"] == "inv-100"
    assert data["total_events"] == 1
