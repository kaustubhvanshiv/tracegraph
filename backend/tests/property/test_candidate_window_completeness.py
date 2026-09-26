"""Property 14: Candidate Window Completeness

**Property 14: Candidate Window Completeness**
  ∀ sorted event lists E and window W:
    - Every pair (a, b) with |a.timestamp - b.timestamp| ≤ W appears in the result.
    - No pair (a, b) with |a.timestamp - b.timestamp| > W appears in the result.

**Validates: Requirements 6.1, 6.2**

Test approach
-------------
Hypothesis generates lists of SecurityEvents with monotonically increasing
timestamps (pre-sorted) and a positive window value.  We then verify both
the completeness guarantee and the no-false-positive guarantee by brute-force
checking all pairs against the window.

Note on hypothesis + asyncio
-----------------------------
These tests are plain synchronous — CandidateRetrieval.retrieve() is synchronous.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.schemas.security_event import SecurityEvent
from app.services.candidate_retrieval import CandidateRetrieval


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_BASE_TS = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# Generate a list of monotonically increasing offsets in seconds [0, 3600]
_offset_list_strategy = st.lists(
    st.integers(min_value=0, max_value=3600),
    min_size=1,
    max_size=20,
).map(sorted)  # ensure ascending order

_window_strategy = st.integers(min_value=1, max_value=60)  # 1–60 minutes


def _build_events(offsets: list[int]) -> list[SecurityEvent]:
    """Build SecurityEvents with distinct IDs and timestamps at given second offsets."""
    return [
        SecurityEvent(
            event_id=f"evt-{i}",
            source_type="siem",
            timestamp=_BASE_TS + timedelta(seconds=off),
            event_type="authentication",
            action="login",
        )
        for i, off in enumerate(offsets)
    ]


def _brute_force_pairs(
    events: list[SecurityEvent], window_minutes: int
) -> set[tuple[str, str]]:
    """Return all (a_id, b_id) pairs where |a.ts - b.ts| ≤ window and i < j."""
    window = timedelta(minutes=window_minutes)
    result: set[tuple[str, str]] = set()
    for i in range(len(events)):
        for j in range(i + 1, len(events)):
            delta = events[j].timestamp - events[i].timestamp
            if delta <= window:
                result.add((events[i].event_id, events[j].event_id))
    return result


# ---------------------------------------------------------------------------
# Property 14
# ---------------------------------------------------------------------------


@given(
    offsets=_offset_list_strategy,
    window_minutes=_window_strategy,
)
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_candidate_window_completeness(
    offsets: list[int],
    window_minutes: int,
) -> None:
    """Property 14: Candidate Window Completeness.

    Every pair within the window is returned and no pair outside is included.

    **Validates: Requirements 6.1, 6.2**
    """
    events = _build_events(offsets)

    # Deduplicate events that have the same event_id (same offset → same timestamp
    # is fine, but same event_id would be a self-pair — we generated unique IDs).
    retrieval = CandidateRetrieval()
    result_pairs = retrieval.retrieve(
        events, window_minutes=window_minutes, investigation_id="inv-prop14"
    )

    # Map result to a set of (a_id, b_id) tuples
    result_set = {(p.event_a.event_id, p.event_b.event_id) for p in result_pairs}

    # Compute expected pairs by brute force
    expected_set = _brute_force_pairs(events, window_minutes)

    # Property 14a: Every expected pair is in the result (completeness)
    missing = expected_set - result_set
    assert not missing, (
        f"Missing pairs: {missing}. "
        f"window_minutes={window_minutes}, events={[(e.event_id, e.timestamp) for e in events]}"
    )

    # Property 14b: No pair outside the window is in the result (no false positives)
    extra = result_set - expected_set
    assert not extra, (
        f"Unexpected pairs: {extra}. "
        f"window_minutes={window_minutes}"
    )
