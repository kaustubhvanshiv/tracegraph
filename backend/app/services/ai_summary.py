"""AI summary service.

Generates evidence-grounded narrative summaries using an LLM provider
abstracted behind the LLMProvider protocol.

Anti-hallucination: system prompt prohibits inventing events, entities, or
maliciousness claims not present in context.  Post-generation validation
checks all evidence_refs exist in context.

On LLM failure: returns SummaryResult(error_flag=True) — never raises.

Caches by (investigation_id, context_hash); supports force_refresh=True.

Full implementation is covered by task 20.1.
"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings
from app.schemas.summary import InvestigationContext, SummaryResult

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Protocol for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate a completion from the LLM."""
        pass


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for development/testing.

    Returns a structured summary based on the context without calling a real LLM.
    """

    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Generate a mock summary from the prompt."""
        # Parse the context from the prompt (it's JSON embedded in the prompt)
        import re

        context_match = re.search(r"Context:\s*(\{.*\})", prompt, re.DOTALL)
        if not context_match:
            return json.dumps(
                {
                    "overview": "Unable to parse context",
                    "chronological_sequence": [],
                    "key_entities": [],
                    "key_relationships": [],
                    "evidence_refs": [],
                    "uncertainty": "Could not parse investigation context from prompt.",
                    "next_questions": [],
                    "error_flag": True,
                    "error_message": "Context parsing failed",
                }
            )

        try:
            context_data = json.loads(context_match.group(1))
        except json.JSONDecodeError:
            return json.dumps(
                {
                    "overview": "Invalid context JSON",
                    "chronological_sequence": [],
                    "key_entities": [],
                    "key_relationships": [],
                    "evidence_refs": [],
                    "uncertainty": "Failed to parse context JSON.",
                    "next_questions": [],
                    "error_flag": True,
                    "error_message": "Context JSON decode error",
                }
            )

        # Build a grounded summary from the context
        entities = context_data.get("entities", [])
        relationships = context_data.get("relationships", [])
        events = context_data.get("sampled_events", [])

        # Extract key entities (top 5 by connection count)
        entity_names = [e.get("canonical_key", e.get("entity_id", "")) for e in entities]
        key_entities = entity_names[:5]

        # Extract key relationships
        rel_descriptions = [
            f"{r.get('source_entity_id', '')} --{r.get('relationship_type', '')}--> {r.get('target_entity_id', '')}"
            for r in relationships
        ]
        key_relationships = rel_descriptions[:5]

        # Evidence refs from sampled events
        evidence_refs = [e.get("event_id", "") for e in events if e.get("event_id")]

        # Chronological sequence from events
        sorted_events = sorted(
            events, key=lambda x: x.get("timestamp", "")
        )
        chronological_sequence = [
            f"{e.get('timestamp', '')}: {e.get('event_type', '')} - {e.get('action', '')}"
            for e in sorted_events[:10]
        ]

        # Overview
        total_events = context_data.get("total_events", len(events))
        overview = (
            f"Investigation contains {total_events} total events across "
            f"{len(entities)} entities and {len(relationships)} correlated relationships. "
            f"Top entities: {', '.join(key_entities[:3])}. "
        )
        if relationships:
            rel_types = set(r.get("relationship_type", "") for r in relationships)
            overview += f"Relationship types observed: {', '.join(rel_types)}. "

        # Uncertainty
        uncertainty = (
            "This summary is generated from a sampled subset of events and may not "
            "capture all investigation details. Correlation scores indicate relevance "
            "strength, not attack probability."
        )

        return json.dumps(
            {
                "overview": overview,
                "chronological_sequence": chronological_sequence,
                "key_entities": key_entities,
                "key_relationships": key_relationships,
                "evidence_refs": evidence_refs,
                "uncertainty": uncertainty,
                "next_questions": [
                    "What is the root cause of the initial event?",
                    "Are there any lateral movement indicators?",
                    "What remediation actions have been taken?",
                ],
                "error_flag": False,
                "error_message": None,
            }
        )


class AISummaryService:
    """Service for generating AI-powered investigation summaries."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        db=None,
    ) -> None:
        self._llm = llm_provider
        self._db = db
        self._cache: dict[tuple[str, str], SummaryResult] = {}

    async def generate_summary(
        self,
        context: InvestigationContext,
        force_refresh: bool = False,
    ) -> SummaryResult:
        """Generate a summary for the given investigation context.

        Args:
            context: Bounded investigation context from AIContextBuilder.
            force_refresh: If True, bypass cache and regenerate.

        Returns:
            SummaryResult with the generated summary or error information.
        """
        # Build cache key
        context_hash = self._compute_context_hash(context)
        cache_key = (context.investigation_id, context_hash)

        # Check cache
        if not force_refresh and cache_key in self._cache:
            logger.info("Cache hit for investigation %s", context.investigation_id)
            return self._cache[cache_key]

        # Serialize context for LLM
        context_json = self._serialize_context(context)

        # Build prompts
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(context_json)

        # Call LLM
        try:
            llm_output = await self._llm.generate(user_prompt, system_prompt)
            result = self._parse_llm_output(llm_output, context)
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM generation failed")
            result = SummaryResult(
                error_flag=True,
                error_message=f"LLM generation failed: {exc!s}",
                uncertainty="Summary generation failed due to LLM error.",
            )

        # Post-generation validation: verify all evidence_refs exist in context
        result = self._validate_evidence_refs(result, context)

        # Cache result
        self._cache[cache_key] = result

        return result

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the LLM."""
        return (
            "You are a security analyst assistant. Your task is to generate a "
            "concise, evidence-grounded narrative summary of a security investigation "
            "based on structured context data.\n\n"
            "CRITICAL RULES:\n"
            "1. NEVER invent events, entities, relationships, or maliciousness "
            "claims not present in the provided context.\n"
            "2. ONLY use information explicitly present in the context.\n"
            "3. Every claim must be traceable to an evidence_ref (event ID) in the context.\n"
            "4. The 'uncertainty' field is MANDATORY and must be non-empty.\n"
            "5. If you cannot determine something, state that explicitly in uncertainty.\n"
            "6. Correlation scores indicate relevance strength, NOT attack probability.\n"
            "7. Output MUST be valid JSON matching the SummaryResult schema.\n\n"
            "Output format (JSON only):\n"
            "{\n"
            '  "overview": "string",\n'
            '  "chronological_sequence": ["string"],\n'
            '  "key_entities": ["string"],\n'
            '  "key_relationships": ["string"],\n'
            '  "evidence_refs": ["string"],\n'
            '  "uncertainty": "string (mandatory, non-empty)",\n'
            '  "next_questions": ["string"],\n'
            '  "error_flag": boolean,\n'
            '  "error_message": "string or null"\n'
            "}"
        )

    def _build_user_prompt(self, context_json: str) -> str:
        """Build the user prompt with the investigation context."""
        return (
            "Generate a security investigation summary from the following context.\n\n"
            f"Context:\n{context_json}"
        )

    def _serialize_context(self, context: InvestigationContext) -> str:
        """Serialize InvestigationContext to JSON for the LLM."""
        # Convert to dict with only JSON-serializable fields
        data = {
            "investigation_id": context.investigation_id,
            "total_events": context.total_events,
            "entities": [
                {
                    "entity_id": e.entity_id,
                    "entity_type": e.entity_type.value,
                    "canonical_key": e.canonical_key,
                    "aliases": e.aliases,
                    "event_ids": e.event_ids,
                }
                for e in context.entities
            ],
            "relationships": [
                {
                    "relationship_id": r.relationship_id,
                    "source_entity_id": r.source_entity_id,
                    "target_entity_id": r.target_entity_id,
                    "relationship_type": r.relationship_type.value,
                    "event_ids": r.event_ids,
                    "signal_names": r.signal_names,
                    "combined_score": r.combined_score,
                }
                for r in context.relationships
            ],
            "sampled_events": [
                {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type,
                    "action": e.action,
                    "user": e.user,
                    "source_host": e.source_host,
                    "destination_host": e.destination_host,
                    "source_ip": e.source_ip,
                    "destination_ip": e.destination_ip,
                    "process": e.process,
                    "file": e.file,
                    "severity": e.severity,
                    "entity_ids": e.entity_ids,
                }
                for e in context.sampled_events
            ],
        }
        return json.dumps(data, default=str)

    def _parse_llm_output(
        self, llm_output: str, context: InvestigationContext
    ) -> SummaryResult:
        """Parse and validate LLM output into SummaryResult."""
        try:
            parsed = json.loads(llm_output)
        except json.JSONDecodeError as exc:
            logger.error("LLM output is not valid JSON: %s", exc)
            return SummaryResult(
                error_flag=True,
                error_message=f"LLM returned invalid JSON: {exc}",
                uncertainty="Failed to parse LLM response as JSON.",
            )

        # Ensure required fields
        required_fields = [
            "overview",
            "chronological_sequence",
            "key_entities",
            "key_relationships",
            "evidence_refs",
            "uncertainty",
            "next_questions",
            "error_flag",
            "error_message",
        ]
        for field in required_fields:
            if field not in parsed:
                parsed[field] = (
                    [] if field in ["chronological_sequence", "key_entities", "key_relationships", "evidence_refs", "next_questions"]
                    else "" if field in ["overview", "uncertainty"]
                    else False if field == "error_flag"
                    else None
                )

        # Ensure uncertainty is non-empty
        if not parsed.get("uncertainty"):
            parsed["uncertainty"] = "No specific uncertainty noted."

        return SummaryResult(**parsed)

    def _validate_evidence_refs(
        self, result: SummaryResult, context: InvestigationContext
    ) -> SummaryResult:
        """Validate that all evidence_refs exist in the context."""
        context_event_ids = {e.event_id for e in context.sampled_events}
        invalid_refs = [
            ref for ref in result.evidence_refs if ref not in context_event_ids
        ]

        if invalid_refs:
            logger.warning(
                "Invalid evidence_refs in summary for %s: %s",
                context.investigation_id,
                invalid_refs,
            )
            # Remove invalid refs and flag error
            result = SummaryResult(
                overview=result.overview,
                chronological_sequence=result.chronological_sequence,
                key_entities=result.key_entities,
                key_relationships=result.key_relationships,
                evidence_refs=[ref for ref in result.evidence_refs if ref in context_event_ids],
                uncertainty=result.uncertainty,
                next_questions=result.next_questions,
                error_flag=True,
                error_message=f"Invalid evidence references removed: {invalid_refs}",
            )

        return result

    def _compute_context_hash(self, context: InvestigationContext) -> str:
        """Compute a hash of the context for cache key."""
        parts = [context.investigation_id]
        for e in sorted(context.entities, key=lambda x: x.entity_id):
            parts.append(f"E:{e.entity_id}")
        for r in sorted(context.relationships, key=lambda x: x.relationship_id):
            parts.append(f"R:{r.relationship_id}")
        for e in sorted(context.sampled_events, key=lambda x: x.event_id):
            parts.append(f"V:{e.event_id}")
        context_str = "|".join(parts)
        return hashlib.sha256(context_str.encode()).hexdigest()[:16]


# Module-level singleton for backward compatibility
_llm_provider = MockLLMProvider()
_ai_summary_service = AISummaryService(_llm_provider)


def get_ai_summary_service() -> AISummaryService:
    """Get the AI summary service instance."""
    return _ai_summary_service


def get_llm_provider() -> LLMProvider:
    """Get the LLM provider instance."""
    return _llm_provider