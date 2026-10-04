"""Property tests for AI Summary Service (Task 20.3 & Task 20.4).

Properties covered:
  - Property 12: Graceful AI Failure (Req 13.3)
  - Property 10: Summary Grounding (Req 13.1, 13.7)
"""

from __future__ import annotations

from typing import Any
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.schemas.entity import Entity, EntityType
from app.schemas.security_event import SecurityEvent
from app.schemas.summary import InvestigationContext, SummaryResult
from app.services.ai_summary import AISummaryService


class ExceptionThrowingLLMProvider:
    """Mock LLM provider that always raises an exception."""

    async def generate(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("LLM connection timed out or quota exceeded")


class GroundedMockLLMProvider:
    """Mock LLM provider returning cited evidence refs."""

    def __init__(self, cited_refs: list[str]) -> None:
        self._cited_refs = cited_refs

    async def generate(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "overview": "Test overview",
            "evidence_refs": self._cited_refs,
            "uncertainty": "Test uncertainty statement",
        }


# ---------------------------------------------------------------------------
# Property 12: Graceful AI Failure (Requirement 13.3)
# ---------------------------------------------------------------------------


@given(
    inv_id=st.text(min_size=1, max_size=20),
    total_evts=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=25)

@pytest.mark.asyncio
async def test_property_12_graceful_ai_failure(inv_id: str, total_evts: int) -> None:
    """Assert generate_summary NEVER raises an exception when LLM fails."""
    context = InvestigationContext(
        investigation_id=inv_id,
        total_events=total_evts,
        entities=[],
        relationships=[],
        sampled_events=[],
    )
    svc = AISummaryService(provider=ExceptionThrowingLLMProvider())

    # Must return SummaryResult with error_flag=True, never raise
    result = await svc.generate_summary(context, force_refresh=True)
    assert isinstance(result, SummaryResult)
    assert result.error_flag is True
    assert result.error_message is not None


# ---------------------------------------------------------------------------
# Property 10: Summary Grounding (Requirement 13.1, 13.7)
# ---------------------------------------------------------------------------


@given(
    event_ids=st.lists(st.text(min_size=3, max_size=10, alphabet="abcdef0123456789"), min_size=1, max_size=5, unique=True),
)
@settings(max_examples=25)

@pytest.mark.asyncio
async def test_property_10_summary_grounding(event_ids: list[str]) -> None:
    """Assert every evidence_ref in the output exists in context valid event IDs."""
    sampled_events = [
        SecurityEvent(
            event_id=eid,
            source_type="sysmon",
            timestamp="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
            event_type="logon",
            action="login",
        )
        for eid in event_ids
    ]
    context = InvestigationContext(
        investigation_id="inv-test",
        total_events=len(event_ids),
        entities=[],
        relationships=[],
        sampled_events=sampled_events,
    )

    # Return valid subset of event_ids
    valid_refs = event_ids[:2]
    svc = AISummaryService(provider=GroundedMockLLMProvider(valid_refs))

    result = await svc.generate_summary(context, force_refresh=True)
    assert result.error_flag is False

    valid_context_eids = {e.event_id for e in context.sampled_events}
    for ref in result.evidence_refs:
        assert ref in valid_context_eids
