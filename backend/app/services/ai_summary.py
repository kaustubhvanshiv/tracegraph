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
    """Default provider that formats structured summary from context without external API call."""

    async def generate(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
    ) -> dict[str, Any]:
        sampled_events = user_payload.get("sampled_events", [])
        entities = user_payload.get("entities", [])
        relationships = user_payload.get("relationships", [])

        event_ids = [e.get("event_id") for e in sampled_events if e.get("event_id")]
        entity_keys = [e.get("canonical_key") for e in entities if e.get("canonical_key")]
        rel_ids = [r.get("relationship_id") for r in relationships if r.get("relationship_id")]

        overview = (
            f"Investigation {user_payload.get('investigation_id', '')} comprises "
            f"{user_payload.get('total_events', 0)} total events across {len(entities)} entities "
            f"and {len(relationships)} correlated relationships."
        )

        sequence = [
            f"Event {e.get('event_id')} ({e.get('event_type')} / {e.get('action')}) "
            f"on {e.get('source_host') or 'unknown'} at {e.get('timestamp')}"
            for e in sampled_events[:5]
        ]

        return {
            "overview": overview,
            "chronological_sequence": sequence,
            "key_entities": entity_keys[:5],
            "key_relationships": rel_ids[:5],
            "evidence_refs": event_ids[:10],
            "uncertainty": "Summary bounded by sampled events; un-sampled low-severity events may contain additional background noise.",
            "next_questions": [
                "Are there additional hosts communicating with these entities?",
                "Has lateral movement occurred across neighboring subnets?",
            ],
        }


# ---------------------------------------------------------------------------
# AISummaryService
# ---------------------------------------------------------------------------


class AISummaryService:
    """Service to generate grounded AI summaries with caching and error isolation."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider: LLMProvider = provider or DefaultLLMProvider()
        # In-memory summary cache: (investigation_id, context_hash) -> SummaryResult
        self._cache: dict[tuple[str, str], SummaryResult] = {}

    def _compute_hash(self, context: InvestigationContext) -> str:
        """Compute stable SHA256 hash of context data."""
        data_bytes = context.model_dump_json().encode("utf-8")
        return hashlib.sha256(data_bytes).hexdigest()

    async def generate_summary(
        self,
        context: InvestigationContext,
        force_refresh: bool = False,
    ) -> SummaryResult:
        """Generate or retrieve cached summary for the given context.

        Parameters
        ----------
        context:
            InvestigationContext built by AIContextBuilder.
        force_refresh:
            If True, bypass cache and re-generate.

        Returns
        -------
        SummaryResult:
            Grounded summary output. On failure, returns SummaryResult(error_flag=True)
            and never raises an exception.
        """
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

        # Fallback: return most recent summary for this investigation_id
        for (inv_id, _), summary in reversed(list(self._cache.items())):
            if inv_id == investigation_id:
                return summary

        return None
