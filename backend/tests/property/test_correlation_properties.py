"""Property 6: Correlation Score Bounds
Property 7: Correlation Signal Presence

**Property 6: Correlation Score Bounds**
  ∀ CandidatePair lists: every CorrelatedRelationship has 0.0 ≤ combined_score ≤ 1.0.

**Property 7: Correlation Signal Presence**
  ∀ CorrelatedRelationship: len(signal_names) ≥ 1 and no result is produced for
  zero-signal pairs.

**Validates: Requirements 7.2, 7.3, 7.4, 7.8**

Test approach
-------------
Hypothesis generates lists of CandidatePair objects with varying SecurityEvent
fields.  We build the pairs directly (skipping parse/normalization/retrieval)
and assert the postconditions on the engine output.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.schemas.relationship import CandidatePair
from app.schemas.security_event import SecurityEvent
from app.services.correlation import TemporalCorrelationEngine


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_BASE_TS = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

_SAFE_CHARS = st.characters(
    whitelist_categories=("Lu", "Ll", "Nd"),
    whitelist_characters="-_.",
)
_SHORT_TEXT = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=32)


def _event_strategy(event_id_prefix: str) -> st.SearchStrategy[SecurityEvent]:
    """Generate a SecurityEvent with various optional fields populated."""
    return st.fixed_dictionaries(
        {
            "event_id": _SHORT_TEXT.map(lambda s: f"{event_id_prefix}-{s}"),
            "source_type": st.sampled_from(["siem", "edr", "sysmon", "auth", "network"]),
            "timestamp": st.just(_BASE_TS),
            "event_type": st.sampled_from(["authentication", "process_creation", "network_flow"]),
            "action": st.sampled_from(["login", "auth", "execute", "connect", "access"]),
            "user": st.one_of(st.none(), st.just("alice"), st.just("bob")),
            "source_host": st.one_of(st.none(), st.just("host-a"), st.just("host-b")),
            "destination_host": st.one_of(st.none(), st.just("host-c"), st.just("host-a")),
            "source_ip": st.one_of(st.none(), st.just("192.168.1.1")),
            "destination_ip": st.one_of(st.none(), st.just("10.0.0.1")),
            "process": st.one_of(st.none(), st.just("cmd.exe")),
            "file": st.one_of(st.none(), st.just("/tmp/file.txt")),
            "severity": st.one_of(st.none(), st.sampled_from(["low", "medium", "high"])),
            "raw_data": st.just(None),
        }
    ).map(lambda d: SecurityEvent(**d))


def _candidate_pair_strategy() -> st.SearchStrategy[CandidatePair]:
    """Generate a CandidatePair ensuring distinct event_ids."""
    return st.tuples(
        _event_strategy("A"),
        _event_strategy("B"),
    ).filter(
        lambda pair: pair[0].event_id != pair[1].event_id
    ).map(
        lambda pair: CandidatePair(
            event_a=pair[0],
            event_b=pair[1],
            investigation_id="inv-prop",
            delta_seconds=abs((pair[1].timestamp - pair[0].timestamp).total_seconds()),
        )
    )


# ---------------------------------------------------------------------------
# Property 6: Correlation Score Bounds
# ---------------------------------------------------------------------------


@given(
    candidates=st.lists(_candidate_pair_strategy(), min_size=1, max_size=10),
)
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_combined_score_bounds(candidates: list[CandidatePair]) -> None:
    """Property 6: Correlation Score Bounds.

    Every CorrelatedRelationship must have 0.0 ≤ combined_score ≤ 1.0.

    **Validates: Requirements 7.2, 7.8**
    """
    engine = TemporalCorrelationEngine()
    results = engine.correlate(candidates)

    for rel in results:
        assert 0.0 <= rel.combined_score <= 1.0, (
            f"combined_score={rel.combined_score!r} out of bounds [0, 1] "
            f"for relationship {rel.relationship_id!r}"
        )


# ---------------------------------------------------------------------------
# Property 7: Correlation Signal Presence
# ---------------------------------------------------------------------------


@given(
    candidates=st.lists(_candidate_pair_strategy(), min_size=1, max_size=10),
)
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_every_result_has_at_least_one_signal(candidates: list[CandidatePair]) -> None:
    """Property 7: Correlation Signal Presence.

    Every returned CorrelatedRelationship must have ≥ 1 entry in signal_names.
    No result is produced for zero-signal pairs.

    **Validates: Requirements 7.3, 7.4**
    """
    engine = TemporalCorrelationEngine()
    results = engine.correlate(candidates)

    for rel in results:
        assert len(rel.signal_names) >= 1, (
            f"CorrelatedRelationship {rel.relationship_id!r} has no signal_names"
        )
        # temporal_proximity alone is not sufficient — at least one other signal must fire
        # (this is guaranteed by the engine, but we verify it)
        non_temporal = [s for s in rel.signal_names if s != "temporal_proximity"]
        assert len(non_temporal) >= 1, (
            f"Relationship {rel.relationship_id!r} only has temporal_proximity — "
            f"should have been filtered out. signal_names={rel.signal_names}"
        )
