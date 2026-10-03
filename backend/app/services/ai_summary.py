"""AI summary service.

Generates evidence-grounded narrative summaries using an LLM provider
abstracted behind the LLMProvider protocol.

Anti-hallucination: system prompt prohibits inventing events, entities, or
maliciousness claims not present in context. Post-generation validation
checks all evidence_refs exist in context.

On LLM failure: returns SummaryResult(error_flag=True) — never raises to caller.

Caches by (investigation_id, context_hash); supports force_refresh=True.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 15.8
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Protocol

from app.schemas.summary import InvestigationContext, SummaryResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLMProvider Protocol
# ---------------------------------------------------------------------------


class LLMProvider(Protocol):
    """Protocol enabling substitution of LLM backends (OpenAI, Gemini, Mock, etc.)."""

    async def generate(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate response from LLM given prompt and structured payload."""
        ...


# ---------------------------------------------------------------------------
# Default Mock Provider
# ---------------------------------------------------------------------------


class DefaultLLMProvider:
    """Default mock LLM provider for development and testing."""

    async def generate(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
    ) -> dict[str, Any]:
        sampled_events = user_payload.get("sampled_events") or []
        evidence_refs = [
            e["event_id"] if isinstance(e, dict) else getattr(e, "event_id", "")
            for e in sampled_events
        ]
        evidence_refs = [ref for ref in evidence_refs if ref]

        return {
            "overview": (
                f"Investigation {user_payload.get('investigation_id')} summary: "
                f"analyzed {user_payload.get('total_events', len(sampled_events))} events."
            ),
            "chronological_sequence": [
                f"Event {ref} processed" for ref in evidence_refs[:5]
            ],
            "key_entities": [
                e.get("canonical_key") if isinstance(e, dict) else getattr(e, "canonical_key", "")
                for e in user_payload.get("entities") or []
            ],
            "key_relationships": [],
            "evidence_refs": evidence_refs[:10],
            "uncertainty": "Mock provider summary: analysis based on limited sampled events.",
            "next_questions": ["Verify root cause host", "Inspect secondary credentials"],
            "error_flag": False,
        }


# ---------------------------------------------------------------------------
# AISummaryService
# ---------------------------------------------------------------------------


class AISummaryService:
    """Service to generate evidence-grounded AI narrative summaries."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._provider = provider or llm_provider or DefaultLLMProvider()
        self._cache: dict[tuple[str, str], SummaryResult] = {}

    def _compute_hash(self, context: InvestigationContext) -> str:
        parts = [context.investigation_id]
        for e in sorted(context.entities, key=lambda x: x.entity_id):
            parts.append(f"E:{e.entity_id}")
        for r in sorted(context.relationships, key=lambda x: x.relationship_id):
            parts.append(f"R:{r.relationship_id}")
        for e in sorted(context.sampled_events, key=lambda x: x.event_id):
            parts.append(f"V:{e.event_id}")
        context_str = "|".join(parts)
        return hashlib.sha256(context_str.encode()).hexdigest()[:16]

    async def generate_summary(
        self,
        context: InvestigationContext,
        force_refresh: bool = False,
    ) -> SummaryResult:
        """Generate or retrieve cached summary for the given context."""
        ctx_hash = self._compute_hash(context)
        cache_key = (context.investigation_id, ctx_hash)

        if not force_refresh and cache_key in self._cache:
            logger.debug("Summary cache hit for investigation %s", context.investigation_id)
            return self._cache[cache_key]

        system_prompt = (
            "You are an expert cybersecurity analyst assistant. "
            "Generate an evidence-grounded summary of the provided investigation context. "
            "STRICT RULES:\n"
            "1. Do NOT invent events, entities, or maliciousness claims not present in context.\n"
            "2. All cited evidence_refs MUST be valid event_ids present in the context.\n"
            "3. You MUST provide a non-empty uncertainty statement describing limits of the data."
        )

        try:
            raw_res = await self._provider.generate(system_prompt, context.model_dump())

            # Gather all valid event_ids in context for grounding validation
            valid_event_ids: set[str] = {e.event_id for e in context.sampled_events}
            for rel in context.relationships:
                valid_event_ids.update(rel.event_ids)

            cited_refs: list[str] = list(raw_res.get("evidence_refs") or [])
            invalid_refs = [ref for ref in cited_refs if ref not in valid_event_ids]

            if invalid_refs:
                logger.warning(
                    "AI summary hallucinated evidence refs: %s", invalid_refs
                )
                return SummaryResult(
                    error_flag=True,
                    error_message=f"Summary post-validation failed: hallucinated evidence_refs {invalid_refs}",
                    uncertainty="Summary generation failed due to hallucinated evidence references.",
                )

            uncertainty = str(
                raw_res.get("uncertainty")
                or "No specific uncertainty noted based on available context."
            ).strip()

            if not uncertainty:
                uncertainty = "No specific uncertainty noted based on available context."

            result = SummaryResult(
                overview=str(raw_res.get("overview") or ""),
                chronological_sequence=list(raw_res.get("chronological_sequence") or []),
                key_entities=list(raw_res.get("key_entities") or []),
                key_relationships=list(raw_res.get("key_relationships") or []),
                evidence_refs=cited_refs,
                uncertainty=uncertainty,
                next_questions=list(raw_res.get("next_questions") or []),
                error_flag=False,
            )

            # Store in cache
            self._cache[cache_key] = result
            return result

        except Exception as exc:
            logger.error("AI summary generation failed: %s", exc)
            return SummaryResult(
                error_flag=True,
                error_message=f"AI summary service error: {exc}",
                uncertainty="Summary generation failed due to service error.",
            )

    def get_cached_summary(
        self,
        investigation_id: str,
        context: InvestigationContext | None = None,
    ) -> SummaryResult | None:
        """Retrieve a cached summary for investigation_id if available."""
        if context is not None:
            cache_key = (investigation_id, self._compute_hash(context))
            return self._cache.get(cache_key)

        for (inv_id, _), summary in reversed(list(self._cache.items())):
            if inv_id == investigation_id:
                return summary

        return None


# Module-level singleton
_ai_summary_service = AISummaryService()


def get_ai_summary_service() -> AISummaryService:
    """Get the AI summary service instance."""
    return _ai_summary_service
