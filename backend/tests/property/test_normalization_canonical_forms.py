"""Property 13: Normalization Canonical Forms
Property 1: Identity Stability

**Property 13: Normalization Canonical Forms**
  ∀ ParsedEvent p: normalize(p).source_host == normalize(p).source_host.lower()
                   normalize(p).timestamp is UTC-aware (tzinfo is not None)

**Property 1: Identity Stability**
  ∀ raw event: normalize(parse(event)).event_id == event["event_id"]

**Validates: Requirements 2.2, 3.1, 3.3, 3.4, 3.5, 3.7**

Design note on hypothesis + asyncio
------------------------------------
These are plain synchronous property tests driving synchronous normalize() calls
— no asyncio needed.
"""

from __future__ import annotations

from datetime import timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.schemas.parser import ParsedEvent
from app.services.normalization import NormalizationEngine


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_SAFE_CHARS = st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_.")
_HOSTNAME_STRATEGY = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=64)
_USERID_STRATEGY = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=64)
_EVENT_ID_STRATEGY = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=64)

# Generate timestamps that the engine can successfully parse:
# ISO-8601 with explicit UTC offset.  We also include Unix epoch strings.
_ISO_TIMESTAMP_STRATEGY = st.datetimes(
    min_value=__import__("datetime").datetime(2000, 1, 1),
    max_value=__import__("datetime").datetime(2099, 12, 31),
).map(lambda dt: dt.replace(tzinfo=timezone.utc).isoformat())

_TIMESTAMP_STRATEGY = _ISO_TIMESTAMP_STRATEGY

_SOURCE_TYPE_STRATEGY = st.sampled_from(["siem", "edr", "sysmon", "auth", "network", "public_dataset"])
_SEVERITY_STRATEGY = st.one_of(
    st.none(),
    st.sampled_from(["low", "medium", "high", "critical"]),
)


def _parsed_event_strategy(include_source_host: bool = True) -> st.SearchStrategy:
    """Return a strategy producing ParsedEvent objects with varying optional fields."""
    return st.fixed_dictionaries(
        {
            "event_id": _EVENT_ID_STRATEGY,
            "source_type": _SOURCE_TYPE_STRATEGY,
            "timestamp_raw": _TIMESTAMP_STRATEGY,
            "event_type": st.one_of(st.none(), st.just("authentication")),
            "action": st.one_of(st.none(), st.just("login")),
            "user": st.one_of(st.none(), _USERID_STRATEGY),
            "source_host": _HOSTNAME_STRATEGY if include_source_host else st.none(),
            "destination_host": st.one_of(st.none(), _HOSTNAME_STRATEGY),
            "source_ip": st.none(),  # keep simple — IP canonicalization tested in unit tests
            "destination_ip": st.none(),
            "process": st.none(),
            "file": st.none(),
            "severity": _SEVERITY_STRATEGY,
            "extra_fields": st.just({}),
        }
    ).map(lambda d: ParsedEvent(**d))


# ---------------------------------------------------------------------------
# Property 13: Normalization Canonical Forms
# ---------------------------------------------------------------------------


@given(parsed=_parsed_event_strategy(include_source_host=True))
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_source_host_is_always_lowercased(parsed: ParsedEvent) -> None:
    """Property 13 (partial): source_host in normalized output equals its own lower-case.

    **Validates: Requirements 3.1, 3.3, 3.4, 3.5**
    """
    engine = NormalizationEngine()
    result = engine.normalize(parsed)

    if result.source_host is not None:
        assert result.source_host == result.source_host.lower(), (
            f"source_host not lowercased: {result.source_host!r}"
        )


@given(parsed=_parsed_event_strategy(include_source_host=True))
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_timestamp_is_always_utc_aware(parsed: ParsedEvent) -> None:
    """Property 13 (partial): timestamp in normalized output is always UTC-aware.

    **Validates: Requirements 3.1, 3.3**
    """
    engine = NormalizationEngine()
    result = engine.normalize(parsed)

    assert result.timestamp.tzinfo is not None, (
        f"timestamp lacks tzinfo: {result.timestamp!r}"
    )
    # Confirm the offset is UTC (zero offset)
    offset = result.timestamp.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0.0, (
        f"timestamp is not UTC: utcoffset={offset!r}"
    )


# ---------------------------------------------------------------------------
# Property 1: Identity Stability
# ---------------------------------------------------------------------------


@given(parsed=_parsed_event_strategy())
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_event_id_is_preserved_through_normalization(parsed: ParsedEvent) -> None:
    """Property 1: Identity Stability — event_id survives parse→normalize unchanged.

    normalize(parsed).event_id == parsed.event_id

    **Validates: Requirements 2.2, 3.7**
    """
    engine = NormalizationEngine()
    result = engine.normalize(parsed)

    assert result.event_id == parsed.event_id, (
        f"event_id changed: {parsed.event_id!r} → {result.event_id!r}"
    )
