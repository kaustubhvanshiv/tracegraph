"""Unit tests for EvidenceDetailService (Task 16.3).

Tests:
  - Returning full evidence record (normalized event, raw_data, entities, relationships, correlation_metadata)
  - Investigation isolation (requesting event belonging to another investigation raises EventNotFoundError)
  - EventNotFoundError (404) for non-existent event
  - GraphUnavailableError propagation when Neo4j fails
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.errors import EventNotFoundError, GraphUnavailableError
from app.repositories.event_repository import EventRepository
from app.repositories.graph_repository import GraphRepository
from app.schemas.entity import Entity, EntityType
from app.schemas.relationship import CorrelatedRelationship, RelationshipType
from app.schemas.security_event import SecurityEvent
from app.services.evidence import EvidenceDetailService


@pytest.fixture
def mock_event_repo() -> AsyncMock:
    return AsyncMock(spec=EventRepository)


@pytest.fixture
def mock_graph_repo() -> AsyncMock:
    return AsyncMock(spec=GraphRepository)


@pytest.fixture
def sample_event() -> SecurityEvent:
    return SecurityEvent(
        event_id="evt-001",
        source_type="sysmon",
        timestamp=datetime.now(timezone.utc),
        event_type="process_creation",
        action="execute",
        user="alice",
        source_host="workstation1",
        severity="medium",
        raw_data={"EventID": 1, "Image": "cmd.exe", "User": "alice"},
    )


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
        signal_names=["shared_user", "host_continuity"],
        signal_scores={"shared_user": 0.4, "host_continuity": 0.3},
        combined_score=0.7,
        explanation="User alice executed process on workstation1",
    )


@pytest.mark.asyncio
async def test_get_evidence_success(
    mock_event_repo: AsyncMock,
    mock_graph_repo: AsyncMock,
    sample_event: SecurityEvent,
    sample_entity: Entity,
    sample_relationship: CorrelatedRelationship,
) -> None:
    mock_event_repo.get.return_value = sample_event
    mock_graph_repo.get_entities_for_event.return_value = [sample_entity]
    mock_graph_repo.get_relationships_for_event.return_value = [sample_relationship]

    svc = EvidenceDetailService(event_repo=mock_event_repo, graph_repo=mock_graph_repo)
    result = await svc.get_evidence(event_id="evt-001", investigation_id="inv-100")

    mock_event_repo.get.assert_awaited_once_with("evt-001", "inv-100")
    mock_graph_repo.get_entities_for_event.assert_awaited_once_with("evt-001", "inv-100")
    mock_graph_repo.get_relationships_for_event.assert_awaited_once_with("evt-001", "inv-100")

    assert result.event.event_id == "evt-001"
    assert result.raw_data == {"EventID": 1, "Image": "cmd.exe", "User": "alice"}
    assert len(result.entities) == 1
    assert result.entities[0].entity_id == "user:alice"
    assert len(result.relationships) == 1
    assert result.relationships[0].relationship_id == "rel-001"

    # Check correlation metadata structure
    assert len(result.correlation_metadata) == 1
    meta = result.correlation_metadata[0]
    assert meta["relationship_id"] == "rel-001"
    assert meta["relationship_type"] == "EXECUTED"
    assert meta["combined_score"] == 0.7
    assert meta["signal_names"] == ["shared_user", "host_continuity"]


@pytest.mark.asyncio
async def test_get_evidence_not_found(
    mock_event_repo: AsyncMock,
    mock_graph_repo: AsyncMock,
) -> None:
    mock_event_repo.get.return_value = None

    svc = EvidenceDetailService(event_repo=mock_event_repo, graph_repo=mock_graph_repo)
    with pytest.raises(EventNotFoundError) as exc_info:
        await svc.get_evidence(event_id="evt-nonexistent", investigation_id="inv-100")

    assert "evt-nonexistent" in str(exc_info.value)
    assert exc_info.value.code == "EVENT_NOT_FOUND"
    assert exc_info.value.http_status == 404
    mock_graph_repo.get_entities_for_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_evidence_investigation_isolation(
    mock_event_repo: AsyncMock,
    mock_graph_repo: AsyncMock,
) -> None:
    # Event exists in inv-200 but not inv-100
    mock_event_repo.get.return_value = None

    svc = EvidenceDetailService(event_repo=mock_event_repo, graph_repo=mock_graph_repo)
    with pytest.raises(EventNotFoundError) as exc_info:
        await svc.get_evidence(event_id="evt-001", investigation_id="inv-100")

    assert exc_info.value.http_status == 404
    mock_event_repo.get.assert_awaited_once_with("evt-001", "inv-100")


@pytest.mark.asyncio
async def test_get_evidence_graph_unavailable(
    mock_event_repo: AsyncMock,
    mock_graph_repo: AsyncMock,
    sample_event: SecurityEvent,
) -> None:
    mock_event_repo.get.return_value = sample_event
    mock_graph_repo.get_entities_for_event.side_effect = GraphUnavailableError(
        "Neo4j is unreachable"
    )

    svc = EvidenceDetailService(event_repo=mock_event_repo, graph_repo=mock_graph_repo)
    with pytest.raises(GraphUnavailableError) as exc_info:
        await svc.get_evidence(event_id="evt-001", investigation_id="inv-100")

    assert exc_info.value.code == "GRAPH_UNAVAILABLE"
    assert exc_info.value.http_status == 503
