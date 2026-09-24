"""
Candidate Retrieval Service.

Identifies pairs of SecurityEvents that are candidates for temporal correlation
using an efficient sliding-window algorithm.

Algorithm overview
------------------
Events MUST be sorted by timestamp ascending before calling ``retrieve``.
For each event at index i, the inner loop walks forward (j = i+1, i+2, ...)
and breaks as soon as the time delta exceeds the window — since the list is
sorted, no further j can ever fall back within the window.  This makes the
inner loop O(W) where W is the number of events inside the window, giving
near-linear performance on typical security event streams.

Deduplication
-------------
Because the outer loop always has i < j, (a, b) and (b, a) are inherently
deduplicated by construction — there is no second pass or set membership test.

Investigation scoping
---------------------
``retrieve`` accepts an explicit ``investigation_id`` parameter.  Only events
whose effective investigation ID matches are paired.  The effective ID for an
event is resolved as:

  1. The ``investigation_id`` keyword argument to ``retrieve`` (preferred when
     all events belong to the same investigation).
  2. The ``investigation_id`` attribute on the ``SecurityEvent`` object itself
     (present when events are attached to a specific investigation at ingestion).
  3. An empty string — the event is considered un-scoped and will only pair
     with other un-scoped events.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

from __future__ import annotations

from datetime import timedelta
from typing import Sequence

from app.schemas.relationship import CandidatePair
from app.schemas.security_event import SecurityEvent


class CandidateRetrieval:
    """Identify temporally proximate event pairs for downstream correlation."""

    def retrieve(
        self,
        events: Sequence[SecurityEvent],
        window_minutes: int = 10,
        *,
        investigation_id: str | None = None,
    ) -> list[CandidatePair]:
        """Return all candidate pairs within the configured time window.

        Preconditions:
          - ``events`` is sorted by ``timestamp`` **ascending**.  Callers that
            do not sort will receive silently incomplete results; the contract
            is documented rather than enforced at runtime to avoid the O(n log n)
            overhead inside a hot pipeline stage.
          - ``window_minutes`` must be a positive integer (> 0).

        Postconditions:
          - Every pair ``(a, b)`` where ``|a.timestamp - b.timestamp|
            <= window_minutes * 60 seconds`` is present in the result.
          - ``(a, b)`` and ``(b, a)`` are deduplicated; only the pair where
            ``a`` precedes ``b`` in the input list is emitted.
          - No pair contains two events with the same ``event_id``.
          - Both events in every returned pair share the same ``investigation_id``.
          - Returns an empty list when fewer than two events fall within any
            common window or investigation scope.

        Args:
            events: Events sorted by timestamp ascending.
            window_minutes: Maximum time delta in minutes; defaults to 10.
            investigation_id: When supplied, overrides per-event investigation
                lookup and scopes ALL events to this investigation.

        Returns:
            List of ``CandidatePair`` objects ready for the correlation engine.
        """
        if window_minutes <= 0:
            raise ValueError(f"window_minutes must be > 0, got {window_minutes!r}")

        if not events:
            return []

        window_delta = timedelta(minutes=window_minutes)
        candidates: list[CandidatePair] = []
        n = len(events)

        for i in range(n):
            event_i = events[i]
            inv_i = _effective_investigation_id(event_i, investigation_id)

            for j in range(i + 1, n):
                event_j = events[j]

                # O(n) early exit: events are sorted, so once delta > window no
                # further j can be within the window.
                delta = event_j.timestamp - event_i.timestamp
                if delta > window_delta:
                    break

                # Skip self-pairs (same event_id seen twice — e.g., duplicates).
                if event_i.event_id == event_j.event_id:
                    continue

                # Filter to the same investigation scope.
                inv_j = _effective_investigation_id(event_j, investigation_id)
                if inv_i != inv_j:
                    continue

                candidates.append(
                    CandidatePair(
                        event_a=event_i,
                        event_b=event_j,
                        investigation_id=inv_i,
                        delta_seconds=delta.total_seconds(),
                    )
                )

        return candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _effective_investigation_id(event: SecurityEvent, override: str | None) -> str:
    """Resolve the investigation ID for *event*.

    Priority:
      1. The explicit ``override`` argument (same for all events in the batch).
      2. ``event.investigation_id`` attribute (may be present on enriched events).
      3. Empty string (un-scoped; only pairs with other un-scoped events).
    """
    if override is not None:
        return override
    return getattr(event, "investigation_id", "") or ""
