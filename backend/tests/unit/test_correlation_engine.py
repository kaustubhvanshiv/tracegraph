"""Unit tests for TemporalCorrelationEngine.

Covers:
  - Each of the seven correlation signals in isolation
  - Combined scoring formula: sum(fired) / sum(ALL weights) ∈ [0.0, 1.0]
  - Zero-signal pair filtering (no output produced)
  - temporal_proximity-only pair filtering (no output produced)
  - Configurable weights via settings patching
  - explanation field is non-empty
  - signal_names matches fired signals

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.schemas.relationship import CandidatePair, CorrelatedRelationship, RelationshipType
from app.schemas.security_event import SecurityEvent
from app.services.correlation import TemporalCorrelationEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_TS = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
_INV = "inv-test-corr"


def _ev(
    event_id: str,
    *,
    source_type: str = "siem",
    event_type: str = "authentication",
    action: str = "login",
    user: str | None = None,
    source_host: str | None = None,
    destination_host: str | None = None,
    source_ip: str | None = None,
    destination_ip: str | None = None,
    process: str | None = None,
    file: str | None = None,
    offset_seconds: float = 0.0,
) -> SecurityEvent:
    return SecurityEvent(
        event_id=event_id,
        source_type=source_type,
        timestamp=_BASE_TS + timedelta(seconds=offset_seconds),
        event_type=event_type,
        action=action,
        user=user,
        source_host=source_host,
        destination_host=destination_host,
        source_ip=source_ip,
        destination_ip=destination_ip,
        process=process,
        file=file,
    )


def _pair(a: SecurityEvent, b: SecurityEvent) -> CandidatePair:
    delta = (b.timestamp - a.timestamp).total_seconds()
    return CandidatePair(
        event_a=a,
        event_b=b,
        investigation_id=_INV,
        delta_seconds=abs(delta),
    )


@pytest.fixture()
def engine() -> TemporalCorrelationEngine:
    return TemporalCorrelationEngine()


# ---------------------------------------------------------------------------
# Signal: shared_user
# ---------------------------------------------------------------------------


class TestSharedUserSignal:
    def test_shared_user_fires_when_both_events_have_same_user(self, engine):
        a = _ev("e1", user="alice", source_host="host-a")
        b = _ev("e2", user="alice", source_host="host-b", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "shared_user" in results[0].signal_names

    def test_shared_user_does_not_fire_when_users_differ(self, engine):
        a = _ev("e1", user="alice", source_host="host-a")
        b = _ev("e2", user="bob", source_host="host-a", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        if results:
            assert "shared_user" not in results[0].signal_names

    def test_shared_user_does_not_fire_when_either_user_is_none(self, engine):
        a = _ev("e1", user=None, source_host="host-a")
        b = _ev("e2", user="alice", source_host="host-a", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        if results:
            assert "shared_user" not in results[0].signal_names


# ---------------------------------------------------------------------------
# Signal: shared_host
# ---------------------------------------------------------------------------


class TestSharedHostSignal:
    def test_shared_host_fires_on_matching_source_hosts(self, engine):
        a = _ev("e1", user="alice", source_host="host-a")
        b = _ev("e2", user="bob", source_host="host-a", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "shared_host" in results[0].signal_names

    def test_shared_host_fires_on_source_vs_destination_match(self, engine):
        a = _ev("e1", user="alice", destination_host="host-x")
        b = _ev("e2", user="alice", source_host="host-x", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "shared_host" in results[0].signal_names

    def test_shared_host_is_case_insensitive(self, engine):
        a = _ev("e1", user="alice", source_host="HOST-A")
        b = _ev("e2", user="alice", source_host="host-a", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "shared_host" in results[0].signal_names

    def test_shared_host_does_not_fire_when_hosts_differ(self, engine):
        a = _ev("e1", user="alice", source_host="host-a")
        b = _ev("e2", user="alice", source_host="host-b", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        if results:
            assert "shared_host" not in results[0].signal_names


# ---------------------------------------------------------------------------
# Signal: shared_ip
# ---------------------------------------------------------------------------


class TestSharedIPSignal:
    def test_shared_ip_fires_on_matching_ips(self, engine):
        a = _ev("e1", source_host="host-a", source_ip="192.168.1.1")
        b = _ev("e2", source_host="host-a", destination_ip="192.168.1.1", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "shared_ip" in results[0].signal_names

    def test_shared_ip_does_not_fire_when_ips_differ(self, engine):
        a = _ev("e1", source_host="host-a", source_ip="1.1.1.1")
        b = _ev("e2", source_host="host-a", source_ip="2.2.2.2", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        if results:
            assert "shared_ip" not in results[0].signal_names


# ---------------------------------------------------------------------------
# Signal: host_continuity
# ---------------------------------------------------------------------------


class TestHostContinuitySignal:
    def test_host_continuity_fires_when_destination_equals_source(self, engine):
        """event_a.destination_host == event_b.source_host → host_continuity fires."""
        a = _ev("e1", user="alice", destination_host="hop-host")
        b = _ev("e2", user="alice", source_host="hop-host", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "host_continuity" in results[0].signal_names

    def test_host_continuity_does_not_fire_in_reverse(self, engine):
        """source_a != destination_b → no host_continuity."""
        a = _ev("e1", user="alice", source_host="hop-host")
        b = _ev("e2", user="alice", destination_host="hop-host", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        if results:
            assert "host_continuity" not in results[0].signal_names

    def test_host_continuity_is_case_insensitive(self, engine):
        a = _ev("e1", user="alice", destination_host="HOP-HOST")
        b = _ev("e2", user="alice", source_host="hop-host", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "host_continuity" in results[0].signal_names


# ---------------------------------------------------------------------------
# Signal: temporal_proximity
# ---------------------------------------------------------------------------


class TestTemporalProximitySignal:
    def test_temporal_proximity_always_fires_for_valid_candidates(self, engine):
        """All candidates from CandidateRetrieval are within the window; proximity always fires."""
        a = _ev("e1", user="alice", source_host="host-a")
        b = _ev("e2", user="alice", source_host="host-b", offset_seconds=300)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "temporal_proximity" in results[0].signal_names

    def test_temporal_proximity_alone_is_rejected(self, engine):
        """A pair that triggers ONLY temporal_proximity must be filtered out."""
        # Events with no matching fields except proximity
        a = _ev("e1", event_type="authentication", action="login")
        b = _ev("e2", user="differentuser", source_host="host-z",
                destination_host="host-w", source_ip="1.2.3.4",
                destination_ip="5.6.7.8", event_type="network_flow",
                action="connect", offset_seconds=60)
        # The pair will have temporal_proximity but all other signals off
        # (different user, no shared host/ip/process/file, incompatible action)
        pair = _pair(a, b)
        results = engine.correlate([pair])
        # Check that if it was a temporal-proximity-only pair it got filtered
        for rel in results:
            non_temporal = [s for s in rel.signal_names if s != "temporal_proximity"]
            assert len(non_temporal) >= 1


# ---------------------------------------------------------------------------
# Signal: compatible_action_sequence
# ---------------------------------------------------------------------------


class TestCompatibleActionSequenceSignal:
    @pytest.mark.parametrize(
        "action_a, action_b",
        [
            ("login", "execute"),
            ("auth", "execute"),
            ("execute", "access"),
            ("connect", "access"),
        ],
    )
    def test_compatible_sequence_fires(self, engine, action_a, action_b):
        a = _ev("e1", action=action_a, source_host="host-a")
        b = _ev("e2", action=action_b, source_host="host-a", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "compatible_action_sequence" in results[0].signal_names

    def test_incompatible_action_sequence_does_not_fire(self, engine):
        """login → login is not a defined compatible sequence."""
        a = _ev("e1", action="login", user="alice")
        b = _ev("e2", action="login", user="alice", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        if results:
            assert "compatible_action_sequence" not in results[0].signal_names


# ---------------------------------------------------------------------------
# Signal: process_file_context
# ---------------------------------------------------------------------------


class TestProcessFileContextSignal:
    def test_shared_process_fires(self, engine):
        a = _ev("e1", source_host="host-a", process="cmd.exe", user="alice")
        b = _ev("e2", source_host="host-a", process="cmd.exe", user="alice", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "process_file_context" in results[0].signal_names

    def test_shared_file_fires(self, engine):
        a = _ev("e1", source_host="host-a", file="/etc/passwd", user="alice")
        b = _ev("e2", source_host="host-a", file="/etc/passwd", user="alice", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert "process_file_context" in results[0].signal_names

    def test_different_process_does_not_fire(self, engine):
        a = _ev("e1", source_host="host-a", process="cmd.exe", user="alice")
        b = _ev("e2", source_host="host-a", process="powershell.exe", user="alice", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        if results:
            assert "process_file_context" not in results[0].signal_names


# ---------------------------------------------------------------------------
# Combined scoring
# ---------------------------------------------------------------------------


class TestCombinedScoring:
    def test_combined_score_in_unit_interval(self, engine):
        a = _ev("e1", user="alice", source_host="host-a", source_ip="1.1.1.1")
        b = _ev("e2", user="alice", source_host="host-a", source_ip="1.1.1.1", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert 0.0 <= results[0].combined_score <= 1.0

    def test_more_signals_fired_means_higher_score(self, engine):
        """A pair with 3 contextual signals must score higher than a pair with 1."""
        # High-signal pair: shared_user + shared_host + compatible_action_sequence + temporal
        a_high = _ev("e1", user="alice", source_host="host-a", action="login")
        b_high = _ev("e2", user="alice", source_host="host-a", action="execute", offset_seconds=60)

        # Low-signal pair: only shared_host + temporal (no user, no compatible sequence)
        a_low = _ev("e3", source_host="host-a", action="login")
        b_low = _ev("e4", source_host="host-a", action="login", offset_seconds=60)

        high_results = engine.correlate([_pair(a_high, b_high)])
        low_results = engine.correlate([_pair(a_low, b_low)])

        assert len(high_results) == 1
        assert len(low_results) == 1
        assert high_results[0].combined_score > low_results[0].combined_score

    def test_combined_score_less_than_or_equal_to_one(self, engine):
        """Even all signals firing must produce score ≤ 1.0."""
        a = _ev(
            "e1",
            user="alice",
            source_host="host-a",
            destination_host="host-b",
            source_ip="1.1.1.1",
            process="cmd.exe",
            file="/etc/passwd",
            action="login",
        )
        b = _ev(
            "e2",
            user="alice",
            source_host="host-b",        # host_continuity: a.dst == b.src
            source_ip="1.1.1.1",
            process="cmd.exe",
            file="/etc/passwd",
            action="execute",            # compatible_action_sequence: login → execute
            offset_seconds=60,
        )
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert results[0].combined_score <= 1.0


# ---------------------------------------------------------------------------
# Zero-signal filtering
# ---------------------------------------------------------------------------


class TestZeroSignalFiltering:
    def test_empty_candidates_produce_empty_results(self, engine):
        results = engine.correlate([])
        assert results == []

    def test_no_context_signal_pair_filtered_out(self, engine):
        """A pair that produces NO context signals (only temporal) must be excluded."""
        # Craft a pair with completely disjoint fields to minimize signal firing.
        # Both events have only source_type and timestamps — no user/host/ip/process/file overlap.
        a = SecurityEvent(
            event_id="noise-a",
            source_type="siem",
            timestamp=_BASE_TS,
            event_type="unknown_type_xyz",
            action="unknown_action_xyz",
        )
        b = SecurityEvent(
            event_id="noise-b",
            source_type="edr",
            timestamp=_BASE_TS + timedelta(seconds=30),
            event_type="unknown_type_abc",
            action="unknown_action_abc",
        )
        pair = CandidatePair(
            event_a=a, event_b=b, investigation_id=_INV, delta_seconds=30
        )
        results = engine.correlate([pair])
        # temporal_proximity alone → filtered out
        assert results == []


# ---------------------------------------------------------------------------
# Configurable weights
# ---------------------------------------------------------------------------


class TestConfigurableWeights:
    def test_zero_weight_signal_does_not_contribute_to_score(self):
        """If shared_user weight is 0, firing shared_user does not increase score."""
        # Patch settings to give shared_user zero weight
        mock_weights = {
            "shared_user": 0.0,
            "shared_host": 1.0,
            "shared_ip": 1.0,
            "host_continuity": 1.0,
            "temporal_proximity": 1.0,
            "compatible_action_sequence": 1.0,
            "process_file_context": 1.0,
        }
        with patch("app.services.correlation.settings") as mock_settings:
            mock_settings.correlation_signal_weights = mock_weights
            engine = TemporalCorrelationEngine()
            total = sum(mock_weights.values())

            # Pair: shared_user + shared_host + temporal_proximity
            a = _ev("e1", user="alice", source_host="host-a")
            b = _ev("e2", user="alice", source_host="host-a", offset_seconds=60)
            results = engine.correlate([_pair(a, b)])

        assert len(results) == 1
        rel = results[0]
        # shared_user fired but has 0 weight; only shared_host + temporal contribute
        fired_score = (
            mock_weights["shared_host"] + mock_weights["temporal_proximity"]
        )
        expected = fired_score / total
        assert abs(rel.combined_score - expected) < 1e-9


# ---------------------------------------------------------------------------
# Explanation field
# ---------------------------------------------------------------------------


class TestExplanationField:
    def test_explanation_is_non_empty(self, engine):
        a = _ev("e1", user="alice", source_host="host-a")
        b = _ev("e2", user="alice", source_host="host-a", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert isinstance(results[0].explanation, str)
        assert len(results[0].explanation) > 0

    def test_explanation_mentions_fired_signals(self, engine):
        a = _ev("e1", user="alice", source_host="host-a")
        b = _ev("e2", user="alice", source_host="host-a", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        for signal in results[0].signal_names:
            assert signal in results[0].explanation


# ---------------------------------------------------------------------------
# signal_names accuracy
# ---------------------------------------------------------------------------


class TestSignalNamesAccuracy:
    def test_signal_names_matches_scored_signals(self, engine):
        a = _ev("e1", user="alice", source_host="host-a")
        b = _ev("e2", user="alice", source_host="host-a", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        rel = results[0]
        # signal_scores keys must be a subset of signal_names
        for signal in rel.signal_scores:
            assert signal in rel.signal_names

    def test_signal_names_are_sorted(self, engine):
        """signal_names must be in sorted order for determinism."""
        a = _ev("e1", user="alice", source_host="host-a", source_ip="1.1.1.1")
        b = _ev("e2", user="alice", source_host="host-a", source_ip="1.1.1.1", offset_seconds=60)
        results = engine.correlate([_pair(a, b)])
        assert len(results) == 1
        assert results[0].signal_names == sorted(results[0].signal_names)
