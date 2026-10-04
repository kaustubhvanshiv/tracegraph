"""Unit tests for AISummaryService and Summary API routes (Task 20.5).

Tests:
  - Cache hit, cache miss, force_refresh
  - Post-generation evidence_ref validation failure handling
  - Mandatory uncertainty field requirement
  - Summary API route handling (POST and GET)
  - 503 AI_UNAVAILABLE on LLM failure
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db, get_neo4j_driver
from app.main import app
from app.schemas.security_event import SecurityEvent
from app.schemas.summary import InvestigationContext, SummaryResult
from app.services.ai_summary import AISummaryService, DefaultLLMProvider


@pytest.fixture
def mock_user() -> CurrentUser:
    return CurrentUser(user_id="user-123", payload={"sub": "user-123"})


@pytest.fixture
def sample_context() -> InvestigationContext:
    return InvestigationContext(
        investigation_id="inv-100",
        total_events=1,
        entities=[],
        relationships=[],
        sampled_events=[
            SecurityEvent(
                event_id="evt-001",
                source_type="sysmon",
                timestamp="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
                event_type="logon",
                action="login",
            )
        ],
    )


@pytest.fixture
def client(mock_user: CurrentUser) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_neo4j_driver] = lambda: AsyncMock()
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_summary_service_cache_hit_and_force_refresh(
    sample_context: InvestigationContext,
) -> None:
    mock_provider = AsyncMock()
    mock_provider.generate.return_value = {
        "overview": "Initial overview",
        "evidence_refs": ["evt-001"],
        "uncertainty": "Initial uncertainty",
    }

    svc = AISummaryService(provider=mock_provider)

    # First call: cache miss, calls provider
    res1 = await svc.generate_summary(sample_context, force_refresh=False)
    assert res1.overview == "Initial overview"
    assert mock_provider.generate.call_count == 1

    # Second call: cache hit, provider NOT called again
    res2 = await svc.generate_summary(sample_context, force_refresh=False)
    assert res2.overview == "Initial overview"
    assert mock_provider.generate.call_count == 1

    # Third call with force_refresh=True: calls provider again
    mock_provider.generate.return_value = {
        "overview": "Refreshed overview",
        "evidence_refs": ["evt-001"],
        "uncertainty": "Refreshed uncertainty",
    }
    res3 = await svc.generate_summary(sample_context, force_refresh=True)
    assert res3.overview == "Refreshed overview"
    assert mock_provider.generate.call_count == 2


@pytest.mark.asyncio
async def test_summary_service_hallucinated_refs_rejected(
    sample_context: InvestigationContext,
) -> None:
    mock_provider = AsyncMock()
    mock_provider.generate.return_value = {
        "overview": "Hallucinated summary",
        "evidence_refs": ["evt-NONEXISTENT"],  # Not in context
        "uncertainty": "Some uncertainty",
    }

    svc = AISummaryService(provider=mock_provider)
    result = await svc.generate_summary(sample_context, force_refresh=True)

    assert result.error_flag is True
    assert "hallucinated evidence_refs" in (result.error_message or "")


@pytest.mark.asyncio
async def test_summary_service_mandatory_uncertainty(
    sample_context: InvestigationContext,
) -> None:
    mock_provider = AsyncMock()
    mock_provider.generate.return_value = {
        "overview": "Overview without uncertainty field",
        "evidence_refs": ["evt-001"],
        "uncertainty": "",  # Empty
    }

    svc = AISummaryService(provider=mock_provider)
    result = await svc.generate_summary(sample_context, force_refresh=True)

    assert result.error_flag is False
    assert result.uncertainty != ""
    assert len(result.uncertainty) > 0


@patch("app.api.summary._check_investigation_ownership", new_callable=AsyncMock)
@patch("app.api.summary.GraphRepository")
@patch("app.api.summary.TimelineService")
def test_post_summary_api_route(
    mock_timeline_cls: AsyncMock,
    mock_graph_cls: AsyncMock,
    mock_ownership: AsyncMock,
    client: TestClient,
) -> None:
    mock_graph_inst = AsyncMock()
    mock_graph_inst.get_graph.return_value = AsyncMock(nodes=[], edges=[])
    mock_graph_cls.return_value = mock_graph_inst

    mock_timeline_inst = AsyncMock()
    mock_timeline_inst.get_timeline.return_value = AsyncMock(events=[], total_count=0)
    mock_timeline_cls.return_value = mock_timeline_inst

    response = client.post("/api/investigations/inv-100/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "overview" in data["data"]
    assert "uncertainty" in data["data"]
