"""Property 4: Entity Uniqueness
Property 3: Entity Coverage

**Property 4: Entity Uniqueness**
  ∀ list[SecurityEvent]: no two entities in the extraction result share the same entity_id.

**Property 3: Entity Coverage**
  ∀ SecurityEvent e with at least one extractable field: at least one returned entity
  carries e.event_id.

**Validates: Requirements 4.1, 4.2, 4.4**

Test approach
-------------
These are plain synchronous property tests.  Hypothesis generates lists of
SecurityEvent-like dicts that are converted to SecurityEvent instances before
calling EntityExtractor.extract().  We constrain generated inputs to plausible
field values to avoid spending hypothesis budget on truly degenerate cases.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.schemas.entity import EntityType
from app.schemas.security_event import SecurityEvent
from app.services.entity_extractor import EntityExtractor


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_SAFE_CHARS = st.characters(
    whitelist_categories=("Lu", "Ll", "Nd"),
    whitelist_characters="-_.",
)
_SHORT_TEXT = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=32)
_TIMESTAMP = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_INV_ID = "inv-prop-test"


def _security_event_strategy() -> st.SearchStrategy:
    """Generate SecurityEvent dicts with a mix of populated optional fields."""
    return st.fixed_dictionaries(
        {
            "event_id": _SHORT_TEXT.map(lambda s: f"evt-{s}"),
            "source_type": st.sampled_from(["siem", "edr", "sysmon", "auth", "network"]),
            "timestamp": st.just(_TIMESTAMP),
            "event_type": st.sampled_from(["authentication", "process_creation", "file_access", "network_flow"]),
            "action": st.sampled_from(["login", "execute", "access", "connect"]),
            "user": st.one_of(st.none(), _SHORT_TEXT),
            "source_host": st.one_of(st.none(), _SHORT_TEXT.map(str.lower)),
            "destination_host": st.one_of(st.none(), _SHORT_TEXT.map(str.lower)),
            "source_ip": st.one_of(st.none(), st.just("10.0.0.1")),
            "destination_ip": st.one_of(st.none(), st.just("10.0.0.2")),
            "process": st.one_of(st.none(), st.just("cmd.exe")),
            "file": st.one_of(st.none(), st.just("/tmp/file.txt")),
            "severity": st.one_of(st.none(), st.sampled_from(["low", "medium", "high", "critical"])),
            "raw_data": st.just(None),
        }
    ).map(lambda d: SecurityEvent(**d))


def _has_extractable_field(event: SecurityEvent) -> bool:
    """Return True if the event has at least one field from which an entity can be extracted."""
    # Process requires source_host; File requires source_host
    if event.user:
        return True
    if event.source_host:
        return True
    if event.destination_host:
        return True
    if event.source_ip:
        return True
    if event.destination_ip:
        return True
    return False


# ---------------------------------------------------------------------------
# Property 4: Entity Uniqueness
# ---------------------------------------------------------------------------


@given(
    events=st.lists(_security_event_strategy(), min_size=1, max_size=15),
)
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_entity_uniqueness_no_duplicate_entity_ids(events: list[SecurityEvent]) -> None:
    """Property 4: Entity Uniqueness.

    No two entities returned by EntityExtractor.extract() share the same entity_id.

    **Validates: Requirements 4.1, 4.2**
    """
    extractor = EntityExtractor()
    entities = extractor.extract(events, _INV_ID)

    entity_ids = [e.entity_id for e in entities]
    # All entity_ids must be unique
    assert len(entity_ids) == len(set(entity_ids)), (
        f"Duplicate entity_ids found: {entity_ids}"
    )


# ---------------------------------------------------------------------------
# Property 3: Entity Coverage
# ---------------------------------------------------------------------------


@given(
    events=st.lists(_security_event_strategy(), min_size=1, max_size=15),
)
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_entity_coverage_every_extractable_event_has_an_entity(
    events: list[SecurityEvent],
) -> None:
    """Property 3: Entity Coverage.

    For every event that has at least one extractable field, at least one
    entity in the result carries that event's event_id.

    **Validates: Requirements 4.4**
    """
    extractor = EntityExtractor()
    entities = extractor.extract(events, _INV_ID)

    # Build a mapping of event_id → set of entity_ids that reference it
    event_id_to_entities: dict[str, list] = {}
    for entity in entities:
        for eid in entity.event_ids:
            event_id_to_entities.setdefault(eid, []).append(entity)

    for event in events:
        if _has_extractable_field(event):
            assert event.event_id in event_id_to_entities, (
                f"Event {event.event_id!r} has extractable fields but no entity references it. "
                f"user={event.user!r}, source_host={event.source_host!r}, "
                f"source_ip={event.source_ip!r}"
            )
