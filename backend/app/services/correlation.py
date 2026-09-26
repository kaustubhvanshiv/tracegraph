"""Temporal correlation engine.

Evaluates candidate pairs against seven named signals:
  shared_user, shared_host, shared_ip, host_continuity,
  temporal_proximity, compatible_action_sequence, process_file_context

combined_score = sum(fired weights) / sum(ALL weights)

# combined_score is a weighted-sum relevance indicator.
# It is NOT an attack probability score.

Signal weights are loaded from config, not hardcoded.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
"""

from __future__ import annotations

import hashlib
from typing import Sequence

from app.core.config import settings
from app.schemas.relationship import (
    CandidatePair,
    CorrelatedRelationship,
    RelationshipType,
)
from app.schemas.security_event import SecurityEvent

# ---------------------------------------------------------------------------
# Compatible action-sequence table
# Maps (action_a, action_b) pairs that represent a plausible attack/activity
# progression, along with the most specific RelationshipType they imply.
# All action strings are compared in lower-case after stripping whitespace.
# ---------------------------------------------------------------------------
_ACTION_SEQUENCES: dict[tuple[str, str], RelationshipType] = {
    ("login", "auth"):        RelationshipType.LOGGED_INTO,
    ("login", "execute"):     RelationshipType.LOGGED_INTO,
    ("login", "access"):      RelationshipType.LOGGED_INTO,
    ("auth", "execute"):      RelationshipType.AUTHENTICATED_TO,
    ("auth", "access"):       RelationshipType.AUTHENTICATED_TO,
    ("auth", "connect"):      RelationshipType.AUTHENTICATED_TO,
    ("execute", "access"):    RelationshipType.EXECUTED,
    ("execute", "connect"):   RelationshipType.EXECUTED,
    ("connect", "access"):    RelationshipType.CONNECTED_TO,
    ("connect", "execute"):   RelationshipType.CONNECTED_TO,
    ("access", "execute"):    RelationshipType.ACCESSED,
    ("access", "connect"):    RelationshipType.ACCESSED,
}


def _norm_action(action: str) -> str:
    """Return a lower-cased, stripped action string for sequence matching."""
    return action.strip().lower()


def _compatible_action_sequence(
    action_a: str, action_b: str
) -> RelationshipType | None:
    """Return the implied RelationshipType if the action pair is known, else None."""
    key = (_norm_action(action_a), _norm_action(action_b))
    return _ACTION_SEQUENCES.get(key)


def _shared_host(a: SecurityEvent, b: SecurityEvent) -> str | None:
    """Return the shared hostname if any host field matches, else None."""
    hosts_a: set[str] = set()
    hosts_b: set[str] = set()
    for val in (a.source_host, a.destination_host):
        if val:
            hosts_a.add(val.lower())
    for val in (b.source_host, b.destination_host):
        if val:
            hosts_b.add(val.lower())
    common = hosts_a & hosts_b
    return next(iter(common)) if common else None


def _shared_ip(a: SecurityEvent, b: SecurityEvent) -> str | None:
    """Return the shared IP if any IP field matches, else None."""
    ips_a: set[str] = set()
    ips_b: set[str] = set()
    for val in (a.source_ip, a.destination_ip):
        if val:
            ips_a.add(val)
    for val in (b.source_ip, b.destination_ip):
        if val:
            ips_b.add(val)
    common = ips_a & ips_b
    return next(iter(common)) if common else None


def _host_continuity(a: SecurityEvent, b: SecurityEvent) -> str | None:
    """Return the hop hostname if event_a's destination equals event_b's source."""
    if a.destination_host and b.source_host:
        if a.destination_host.lower() == b.source_host.lower():
            return a.destination_host.lower()
    return None


def _shared_process_or_file(a: SecurityEvent, b: SecurityEvent) -> str | None:
    """Return the shared process/file identifier if any match, else None."""
    if a.process and b.process and a.process == b.process:
        return a.process
    if a.file and b.file and a.file == b.file:
        return a.file
    return None


def _derive_relationship_id(
    event_a_id: str, event_b_id: str, investigation_id: str
) -> str:
    """Generate a deterministic relationship_id from the pair and investigation."""
    raw = f"{event_a_id}|{event_b_id}|{investigation_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _infer_relationship_type(
    a: SecurityEvent,
    b: SecurityEvent,
    compatible_rel: RelationshipType | None,
    fired: set[str],
) -> RelationshipType:
    """Infer the most specific RelationshipType from available signals.

    Priority:
      1. Compatible action sequence → use the action-implied type.
      2. Shared IP with no host/user context → CONNECTED_TO.
      3. Shared user with no IP/host context → LOGGED_INTO.
      4. Fallback → CONNECTED_TO.
    """
    if compatible_rel is not None:
        return compatible_rel
    if "shared_ip" in fired and "shared_user" not in fired:
        return RelationshipType.CONNECTED_TO
    if "shared_user" in fired:
        return RelationshipType.LOGGED_INTO
    return RelationshipType.CONNECTED_TO


def _derive_source_entity_id(event: SecurityEvent) -> str:
    """Derive a stable source entity ID from the event (best-effort)."""
    # Use the same hashing approach as EntityExtractor: sha256 of type:key.
    if event.user:
        raw = f"User:{event.user}"
    elif event.source_host:
        raw = f"Host:{event.source_host.lower()}"
    elif event.source_ip:
        raw = f"IP:{event.source_ip}"
    else:
        raw = f"Event:{event.event_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _derive_target_entity_id(event: SecurityEvent) -> str:
    """Derive a stable target entity ID from the event (best-effort)."""
    if event.destination_host:
        raw = f"Host:{event.destination_host.lower()}"
    elif event.destination_ip:
        raw = f"IP:{event.destination_ip}"
    elif event.user:
        raw = f"User:{event.user}"
    else:
        raw = f"Event:{event.event_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _build_explanation(
    fired: set[str],
    evidence: dict[str, str],
    combined_score: float,
) -> str:
    """Build a human-readable explanation string."""
    parts: list[str] = []
    for signal in sorted(fired):  # deterministic ordering
        detail = evidence.get(signal, "")
        if detail:
            parts.append(f"{signal} ({detail})")
        else:
            parts.append(signal)
    signals_text = ", ".join(parts) if parts else "none"
    return f"Signals fired: {signals_text}. Score: {combined_score:.4f}."


class TemporalCorrelationEngine:
    """Evaluate candidate event pairs against named signals and produce correlated
    relationships.

    # combined_score is a weighted-sum relevance indicator.
    # It is NOT an attack probability score.
    """

    def __init__(self) -> None:
        # Load weights from config at construction time so they can be overridden
        # in tests by patching settings before instantiation.
        self._weights: dict[str, float] = dict(
            settings.correlation_signal_weights
        )
        self._total_weight: float = sum(self._weights.values())

    def correlate(
        self, candidates: Sequence[CandidatePair]
    ) -> list[CorrelatedRelationship]:
        """Evaluate each candidate pair and return correlated relationships.

        Preconditions:
          - ``candidates`` is a list of ``CandidatePair`` with both events populated.

        Postconditions:
          - Each result carries: signal_names, signal_scores, combined_score ∈ [0, 1],
            and a human-readable explanation.
          - combined_score is NOT an attack probability score.
          - Pairs with zero triggered signals produce no output.
          - Pairs where temporal_proximity is the ONLY triggered signal produce no output
            (temporal proximity alone is insufficient for meaningful correlation).

        Args:
            candidates: Pairs from the CandidateRetrieval stage.

        Returns:
            List of CorrelatedRelationship objects.
        """
        results: list[CorrelatedRelationship] = []

        for pair in candidates:
            rel = self._evaluate_pair(pair)
            if rel is not None:
                results.append(rel)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate_pair(self, pair: CandidatePair) -> CorrelatedRelationship | None:
        """Evaluate a single candidate pair; return None if it should be filtered."""
        a = pair.event_a
        b = pair.event_b

        fired: set[str] = set()
        signal_scores: dict[str, float] = {}
        # Evidence descriptions for the explanation string
        evidence: dict[str, str] = {}

        # --- 1. shared_user ---
        if a.user and b.user and a.user == b.user:
            fired.add("shared_user")
            signal_scores["shared_user"] = self._weights.get("shared_user", 0.0)
            evidence["shared_user"] = f"user={a.user}"

        # --- 2. shared_host ---
        host_match = _shared_host(a, b)
        if host_match:
            fired.add("shared_host")
            signal_scores["shared_host"] = self._weights.get("shared_host", 0.0)
            evidence["shared_host"] = f"host={host_match}"

        # --- 3. shared_ip ---
        ip_match = _shared_ip(a, b)
        if ip_match:
            fired.add("shared_ip")
            signal_scores["shared_ip"] = self._weights.get("shared_ip", 0.0)
            evidence["shared_ip"] = f"ip={ip_match}"

        # --- 4. host_continuity ---
        hop = _host_continuity(a, b)
        if hop:
            fired.add("host_continuity")
            signal_scores["host_continuity"] = self._weights.get("host_continuity", 0.0)
            evidence["host_continuity"] = f"hop={hop}"

        # --- 5. temporal_proximity ---
        # All candidates from CandidateRetrieval are already within the window, so
        # this signal always fires for valid candidates.
        fired.add("temporal_proximity")
        signal_scores["temporal_proximity"] = self._weights.get("temporal_proximity", 0.0)
        evidence["temporal_proximity"] = f"delta={pair.delta_seconds:.1f}s"

        # --- 6. compatible_action_sequence ---
        compatible_rel = _compatible_action_sequence(a.action, b.action)
        if compatible_rel is not None:
            fired.add("compatible_action_sequence")
            signal_scores["compatible_action_sequence"] = self._weights.get(
                "compatible_action_sequence", 0.0
            )
            evidence["compatible_action_sequence"] = (
                f"{_norm_action(a.action)}→{_norm_action(b.action)}"
            )

        # --- 7. process_file_context ---
        pf_match = _shared_process_or_file(a, b)
        if pf_match:
            fired.add("process_file_context")
            signal_scores["process_file_context"] = self._weights.get(
                "process_file_context", 0.0
            )
            evidence["process_file_context"] = f"context={pf_match}"

        # --- Filtering ---
        if not fired:
            return None

        context_signals = fired - {"temporal_proximity"}
        if not context_signals:
            # temporal_proximity alone is insufficient; reject this pair.
            return None

        # --- Score ---
        # combined_score is a weighted-sum relevance indicator — NOT an attack probability.
        combined_score = sum(signal_scores.values()) / self._total_weight

        # Clamp to [0, 1] for robustness against floating-point edge cases.
        combined_score = max(0.0, min(1.0, combined_score))

        # --- Explanation ---
        explanation = _build_explanation(fired, evidence, combined_score)

        # --- Relationship metadata ---
        relationship_id = _derive_relationship_id(
            a.event_id, b.event_id, pair.investigation_id
        )
        relationship_type = _infer_relationship_type(a, b, compatible_rel, fired)
        source_entity_id = _derive_source_entity_id(a)
        target_entity_id = _derive_target_entity_id(b)

        return CorrelatedRelationship(
            relationship_id=relationship_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            investigation_id=pair.investigation_id,
            timestamp=a.timestamp,
            event_ids=[a.event_id, b.event_id],
            source=a.source_type,
            signal_names=sorted(fired),
            signal_scores=signal_scores,
            combined_score=combined_score,
            explanation=explanation,
        )
