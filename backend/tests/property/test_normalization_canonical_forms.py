"""Property 13: Normalization Canonical Forms
Property 1: Identity Stability

**Property 13: Normalization Canonical Forms**
  ∀ ParsedEvent p: normalize(p).source_host == normalize(p).source_host.lower()
                   normalize(p).destination_host == normalize(p).destination_host.lower()
                   normalize(p).timestamp is UTC-aware (tzinfo is not None, utcoffset == 0)
                   normalize(p).user has no domain prefix (no \\ or @)
                   normalize(p).source_ip / destination_ip are dotted-decimal or compressed IPv6

**Property 1: Identity Stability**
  ∀ raw event: normalize(parse(event)).event_id == event["event_id"]

**Validates: Requirements 2.2, 3.1, 3.3, 3.4, 3.5, 3.7**

Design note on hypothesis + asyncio
------------------------------------
These are plain synchronous property tests driving synchronous normalize() calls
— no asyncio needed.
"""

from __future__ import annotations

import ipaddress
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
_EVENT_ID_STRATEGY = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=64)

# Generate timestamps that the engine can successfully parse:
# ISO-8601 with explicit UTC offset.
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

# Username strategies covering bare, DOMAIN\user, and user@domain forms
_BARE_USER_STRATEGY = st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=32)
_BACKSLASH_USER_STRATEGY = st.builds(
    lambda domain, user: f"{domain}\\{user}",
    domain=st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=16),
    user=st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=32),
)
_AT_USER_STRATEGY = st.builds(
    lambda user, domain: f"{user}@{domain}",
    user=st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=32),
    domain=st.text(alphabet=_SAFE_CHARS, min_size=1, max_size=32),
)
_USERNAME_STRATEGY = st.one_of(
    st.none(),
    _BARE_USER_STRATEGY,
    _BACKSLASH_USER_STRATEGY,
    _AT_USER_STRATEGY,
)

# IPv4 address strategy using hypothesis inet addresses
_IPV4_STRATEGY = st.builds(
    lambda a, b, c, d: f"{a}.{b}.{c}.{d}",
    a=st.integers(min_value=1, max_value=254),
    b=st.integers(min_value=0, max_value=255),
    c=st.integers(min_value=0, max_value=255),
    d=st.integers(min_value=1, max_value=254),
)
_IP_STRATEGY = st.one_of(st.none(), _IPV4_STRATEGY)


def _parsed_event_strategy(
    include_source_host: bool = True,
    include_destination_host: bool = True,
    include_user: bool = False,
    include_ip: bool = False,
) -> st.SearchStrategy:
    """Return a strategy producing ParsedEvent objects with varying optional fields."""
    return st.fixed_dictionaries(
        {
            "event_id": _EVENT_ID_STRATEGY,
            "source_type": _SOURCE_TYPE_STRATEGY,
            "timestamp_raw": _TIMESTAMP_STRATEGY,
            "event_type": st.one_of(st.none(), st.just("authentication")),
            "action": st.one_of(st.none(), st.just("login")),
            "user": _USERNAME_STRATEGY if include_user else st.none(),
            "source_host": _HOSTNAME_STRATEGY if include_source_host else st.none(),
            "destination_host": _HOSTNAME_STRATEGY if include_destination_host else st.one_of(st.none(), _HOSTNAME_STRATEGY),
            "source_ip": _IP_STRATEGY if include_ip else st.none(),
            "destination_ip": _IP_STRATEGY if include_ip else st.none(),
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
    """Property 13 (Req 3.3): source_host in normalized output equals its own lower-case.

    **Validates: Requirements 3.3**
    """
    engine = NormalizationEngine()
    result = engine.normalize(parsed)

    if result.source_host is not None:
        assert result.source_host == result.source_host.lower(), (
            f"source_host not lowercased: {result.source_host!r}"
        )


@given(
    parsed=_parsed_event_strategy(
        include_source_host=False,
        include_destination_host=True,
    )
)
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_destination_host_is_always_lowercased(parsed: ParsedEvent) -> None:
    """Property 13 (Req 3.3): destination_host in normalized output equals its own lower-case.

    **Validates: Requirements 3.3**
    """
    engine = NormalizationEngine()
    result = engine.normalize(parsed)

    if result.destination_host is not None:
        assert result.destination_host == result.destination_host.lower(), (
            f"destination_host not lowercased: {result.destination_host!r}"
        )


@given(parsed=_parsed_event_strategy(include_source_host=True))
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_timestamp_is_always_utc_aware(parsed: ParsedEvent) -> None:
    """Property 13 (Req 3.1): timestamp in normalized output is always UTC-aware.

    **Validates: Requirements 3.1**
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


@given(
    parsed=_parsed_event_strategy(include_user=True)
)
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_username_has_no_domain_prefix(parsed: ParsedEvent) -> None:
    """Property 13 (Req 3.4): normalized user has no domain prefix (no backslash or @-suffix).

    Covers DOMAIN\\user → user and user@domain → user forms.

    **Validates: Requirements 3.4**
    """
    engine = NormalizationEngine()
    result = engine.normalize(parsed)

    if result.user is not None:
        assert "\\" not in result.user, (
            f"normalized user still contains backslash: {result.user!r} "
            f"(parsed.user={parsed.user!r})"
        )
        assert "@" not in result.user, (
            f"normalized user still contains @: {result.user!r} "
            f"(parsed.user={parsed.user!r})"
        )


@given(
    parsed=_parsed_event_strategy(include_ip=True)
)
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_ip_fields_are_valid_canonical_notation(parsed: ParsedEvent) -> None:
    """Property 13 (Req 3.5): source_ip / destination_ip are dotted-decimal IPv4 or
    compressed IPv6 when the input is a valid IP address.

    **Validates: Requirements 3.5**
    """
    engine = NormalizationEngine()
    result = engine.normalize(parsed)

    for field_name, ip_value in [("source_ip", result.source_ip), ("destination_ip", result.destination_ip)]:
        if ip_value is None:
            continue
        # The value must be parseable as a valid IP address (dotted-decimal IPv4
        # or compressed IPv6) — this is the canonical form produced by ipaddress.ip_address()
        try:
            addr = ipaddress.ip_address(ip_value)
        except ValueError:
            raise AssertionError(
                f"{field_name} is not a valid canonical IP: {ip_value!r}"
            )
        # Verify round-trip: str(ip_address(x)) produces the canonical form
        assert ip_value == str(addr), (
            f"{field_name} is not in canonical form: {ip_value!r} != {str(addr)!r}"
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
