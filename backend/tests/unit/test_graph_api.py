"""Unit tests for Graph Query API endpoints (Task 17.2).

Tests:
  - GET /api/investigations/{id}/graph with filters
  - GET /api/investigations/{id}/graph/pivot
  - GET /api/investigations/{id}/entities/{eid}
  - 404 ENTITY_NOT_FOUND when entity does not exist
  - 503 GRAPH_UNAVAILABLE when Neo4j is down
  - 403 FORBIDDEN when user does not own investigation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db, get_neo4j_driver
from app.core.errors import ForbiddenError, GraphUnavailableError
from app.main import app
from app.schemas.entity import Entity, EntityType
from app.schemas.graph import EntityDetail, GraphResult
from app.schemas.relationship import CorrelatedRelationship, RelationshipType


@pytest.fixture
def mock_user() -> CurrentUser:
    return CurrentUser(user_id="user-123", payload={"sub": "user-123", "email": "analyst@example.com"})


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
def sample_graph_result(sample_entity: Entity) -> GraphResult:
    return GraphResult(
        investigation_id="inv-100",
        nodes=[sample_entity],
        edges=[],
    )


@pytest.fixture
def sample_entity_detail(sample_entity: Entity) -> EntityDetail:
    return EntityDetail(
        entity=sample_entity,
        relationships=[],
        event_ids=["evt-001"],
    )


@pytest.fixture
# pyrefly: ignore [bad-return]
def client(mock_user: CurrentUser) -> TestClient:
    """TestClient with overridden JWT auth dependency."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_neo4j_driver] = lambda: AsyncMock()
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@patch("app.api.graph._check_investigation_ownership", new_callable=AsyncMock)
@patch("app.api.graph.GraphRepository")
def test_get_graph_success(
    mock_repo_cls: AsyncMock,
    mock_ownership: AsyncMock,
    client: TestClient,
    sample_graph_result: GraphResult,
) -> None:
    mock_repo_inst = AsyncMock()
    mock_repo_inst.get_graph.return_value = sample_graph_result
    mock_repo_cls.return_value = mock_repo_inst

    response = client.get(
        "/api/investigations/inv-100/graph",
        params={"entity_type": "User"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["investigation_id"] == "inv-100"
    assert len(data["data"]["nodes"]) == 1
    assert data["data"]["nodes"][0]["entity_id"] == "user:alice"
    mock_ownership.assert_awaited_once()


@patch("app.api.graph._check_investigation_ownership", new_callable=AsyncMock)
@patch("app.api.graph.GraphRepository")
def test_pivot_graph_success(
    mock_repo_cls: AsyncMock,
    mock_ownership: AsyncMock,
    client: TestClient,
    sample_graph_result: GraphResult,
) -> None:
    mock_repo_inst = AsyncMock()
    mock_repo_inst.pivot.return_value = sample_graph_result
    mock_repo_cls.return_value = mock_repo_inst

    response = client.get(
        "/api/investigations/inv-100/graph/pivot",
        params={"entity_id": "user:alice", "hops": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["investigation_id"] == "inv-100"
    mock_repo_inst.pivot.assert_awaited_once_with(
        entity_id="user:alice",
        investigation_id="inv-100",
        hops=2,
    )


@patch("app.api.graph._check_investigation_ownership", new_callable=AsyncMock)
@patch("app.api.graph.GraphRepository")
def test_get_entity_detail_success(
    mock_repo_cls: AsyncMock,
    mock_ownership: AsyncMock,
    client: TestClient,
    sample_entity_detail: EntityDetail,
) -> None:
    mock_repo_inst = AsyncMock()
    mock_repo_inst.get_entity.return_value = sample_entity_detail
    mock_repo_cls.return_value = mock_repo_inst

    response = client.get("/api/investigations/inv-100/entities/user:alice")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["entity"]["entity_id"] == "user:alice"
    mock_repo_inst.get_entity.assert_awaited_once_with(
        entity_id="user:alice",
        investigation_id="inv-100",
    )


@patch("app.api.graph._check_investigation_ownership", new_callable=AsyncMock)
@patch("app.api.graph.GraphRepository")
def test_get_entity_detail_not_found(
    mock_repo_cls: AsyncMock,
    mock_ownership: AsyncMock,
    client: TestClient,
) -> None:
    mock_repo_inst = AsyncMock()
    mock_repo_inst.get_entity.side_effect = KeyError("Entity not found")
    mock_repo_cls.return_value = mock_repo_inst

    response = client.get("/api/investigations/inv-100/entities/nonexistent")

    assert response.status_code == 404
    data = response.json()
    assert data["status"] == "error"
    assert data["code"] == "ENTITY_NOT_FOUND"


@patch("app.api.graph._check_investigation_ownership", new_callable=AsyncMock)
@patch("app.api.graph.GraphRepository")
def test_graph_unavailable_503(
    mock_repo_cls: AsyncMock,
    mock_ownership: AsyncMock,
    client: TestClient,
) -> None:
    mock_repo_inst = AsyncMock()
    mock_repo_inst.get_graph.side_effect = GraphUnavailableError("Neo4j unreachable")
    mock_repo_cls.return_value = mock_repo_inst

    response = client.get("/api/investigations/inv-100/graph")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["code"] == "GRAPH_UNAVAILABLE"


@patch(
    "app.api.graph._check_investigation_ownership",
    side_effect=ForbiddenError("You do not have permission to access this investigation."),
)
def test_graph_forbidden_non_owner(
    mock_ownership: AsyncMock,
    client: TestClient,
) -> None:
    response = client.get("/api/investigations/inv-100/graph")

    assert response.status_code == 403
    data = response.json()
    assert data["status"] == "error"
    assert data["code"] == "FORBIDDEN"
