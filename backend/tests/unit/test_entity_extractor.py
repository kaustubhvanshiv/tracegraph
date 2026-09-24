"""Unit tests for EntityExtractor.

Covers:
  - All six entity types (User, Host, Server, IP, Process, File)
  - Alias merging on deduplication
  - entity_id deduplication across multiple events
  - Deterministic entity_id across calls with identical input
  - No entity created without at least one event_id reference
  - Server-vs-Host classification via server_role / event_type
  - Process canonical_key uses source_host::process_name (pid excluded)
  - File canonical_key uses source_host::file_path
  - Events with no extractable fields produce no entities
  - Investigation ID is propagated onto every entity

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.entity import EntityType, generate_entity_id
from app.schemas.security_event import SecurityEvent
from app.services.entity_extractor import EntityExtractor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INV = "inv-test-001"

_TS = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _event(
    event_id: str = "evt-1",
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
    severity: str | None = None,
    raw_data: dict | None = None,
) -> SecurityEvent:
    """Construct a minimal SecurityEvent for testing."""
    return SecurityEvent(
        event_id=event_id,
        source_type=source_type,
        timestamp=_TS,
        event_type=event_type,
        action=action,
        user=user,
        source_host=source_host,
        destination_host=destination_host,
        source_ip=source_ip,
        destination_ip=destination_ip,
        process=process,
        file=file,
        severity=severity,
        raw_data=raw_data,
    )


@pytest.fixture()
def extractor() -> EntityExtractor:
    return EntityExtractor()


# ---------------------------------------------------------------------------
# User entity tests
# ---------------------------------------------------------------------------


class TestUserEntity:
    def test_user_entity_extracted(self, extractor):
        events = [_event(event_id="e1", user="alice")]
        result = extractor.extract(events, _INV)
        users = [e for e in result if e.entity_type == EntityType.USER]
        assert len(users) == 1
        assert users[0].canonical_key == "alice"

    def test_user_entity_id_is_deterministic_hash(self, extractor):
        events = [_event(event_id="e1", user="alice")]
        result = extractor.extract(events, _INV)
        users = [e for e in result if e.entity_type == EntityType.USER]
        expected_id = generate_entity_id(EntityType.USER, "alice")
        assert users[0].entity_id == expected_id

    def test_user_carries_event_id(self, extractor):
        events = [_event(event_id="e1", user="alice")]
        result = extractor.extract(events, _INV)
        users = [e for e in result if e.entity_type == EntityType.USER]
        assert "e1" in users[0].event_ids

    def test_same_user_across_two_events_deduplicates(self, extractor):
        events = [
            _event(event_id="e1", user="bob"),
            _event(event_id="e2", user="bob"),
        ]
        result = extractor.extract(events, _INV)
        users = [e for e in result if e.entity_type == EntityType.USER]
        assert len(users) == 1
        assert set(users[0].event_ids) == {"e1", "e2"}

    def test_two_different_users_produce_two_entities(self, extractor):
        events = [
            _event(event_id="e1", user="alice"),
            _event(event_id="e2", user="bob"),
        ]
        result = extractor.extract(events, _INV)
        users = [e for e in result if e.entity_type == EntityType.USER]
        assert len(users) == 2
        keys = {u.canonical_key for u in users}
        assert keys == {"alice", "bob"}

    def test_user_investigation_id_set(self, extractor):
        events = [_event(event_id="e1", user="alice")]
        result = extractor.extract(events, _INV)
        users = [e for e in result if e.entity_type == EntityType.USER]
        assert users[0].investigation_id == _INV


# ---------------------------------------------------------------------------
# Host entity tests
# ---------------------------------------------------------------------------


class TestHostEntity:
    def test_source_host_produces_host_entity(self, extractor):
        events = [_event(event_id="e1", source_host="workstation-01")]
        result = extractor.extract(events, _INV)
        hosts = [e for e in result if e.entity_type == EntityType.HOST]
        assert len(hosts) == 1
        assert hosts[0].canonical_key == "workstation-01"

    def test_destination_host_always_produces_host(self, extractor):
        events = [_event(event_id="e1", destination_host="dc-01")]
        result = extractor.extract(events, _INV)
        hosts = [e for e in result if e.entity_type == EntityType.HOST]
        assert len(hosts) == 1
        assert hosts[0].canonical_key == "dc-01"

    def test_same_host_in_source_and_dest_deduplicates(self, extractor):
        events = [
            _event(event_id="e1", source_host="host-a"),
            _event(event_id="e2", destination_host="host-a"),
        ]
        result = extractor.extract(events, _INV)
        hosts = [e for e in result if e.entity_type == EntityType.HOST]
        assert len(hosts) == 1
        assert set(hosts[0].event_ids) == {"e1", "e2"}

    def test_source_host_without_server_role_is_host_not_server(self, extractor):
        events = [_event(event_id="e1", source_host="db-host", event_type="authentication")]
        result = extractor.extract(events, _INV)
        host_types = {e.entity_type for e in result}
        assert EntityType.HOST in host_types
        assert EntityType.SERVER not in host_types


# ---------------------------------------------------------------------------
# Server entity tests
# ---------------------------------------------------------------------------


class TestServerEntity:
    def test_server_role_in_raw_data_yields_server_entity(self, extractor):
        events = [
            _event(
                event_id="e1",
                source_host="db-server-01",
                raw_data={"server_role": "database"},
            )
        ]
        result = extractor.extract(events, _INV)
        servers = [e for e in result if e.entity_type == EntityType.SERVER]
        assert len(servers) == 1
        assert servers[0].canonical_key == "db-server-01"

    def test_event_type_containing_server_yields_server_entity(self, extractor):
        events = [_event(event_id="e1", source_host="web-01", event_type="server_access")]
        result = extractor.extract(events, _INV)
        servers = [e for e in result if e.entity_type == EntityType.SERVER]
        assert len(servers) == 1

    def test_server_and_host_have_different_entity_ids_for_same_hostname(self, extractor):
        """Same hostname classified as Server vs Host produces distinct entity_ids."""
        server_id = generate_entity_id(EntityType.SERVER, "host-a")
        host_id = generate_entity_id(EntityType.HOST, "host-a")
        assert server_id != host_id

    def test_empty_server_role_string_does_not_classify_as_server(self, extractor):
        events = [
            _event(
                event_id="e1",
                source_host="host-b",
                raw_data={"server_role": ""},
            )
        ]
        result = extractor.extract(events, _INV)
        servers = [e for e in result if e.entity_type == EntityType.SERVER]
        assert len(servers) == 0
        hosts = [e for e in result if e.entity_type == EntityType.HOST]
        assert len(hosts) == 1

    def test_no_raw_data_no_server_type(self, extractor):
        events = [_event(event_id="e1", source_host="file-server", event_type="file_access")]
        result = extractor.extract(events, _INV)
        # "file_access" does not contain "server", so should be HOST
        servers = [e for e in result if e.entity_type == EntityType.SERVER]
        assert len(servers) == 0


# ---------------------------------------------------------------------------
# IP entity tests
# ---------------------------------------------------------------------------


class TestIPEntity:
    def test_source_ip_produces_ip_entity(self, extractor):
        events = [_event(event_id="e1", source_ip="192.168.1.100")]
        result = extractor.extract(events, _INV)
        ips = [e for e in result if e.entity_type == EntityType.IP]
        assert len(ips) == 1
        assert ips[0].canonical_key == "192.168.1.100"

    def test_destination_ip_produces_ip_entity(self, extractor):
        events = [_event(event_id="e1", destination_ip="10.0.0.1")]
        result = extractor.extract(events, _INV)
        ips = [e for e in result if e.entity_type == EntityType.IP]
        assert len(ips) == 1
        assert ips[0].canonical_key == "10.0.0.1"

    def test_same_ip_in_source_and_dest_deduplicates(self, extractor):
        events = [
            _event(event_id="e1", source_ip="10.0.0.1"),
            _event(event_id="e2", destination_ip="10.0.0.1"),
        ]
        result = extractor.extract(events, _INV)
        ips = [e for e in result if e.entity_type == EntityType.IP]
        assert len(ips) == 1
        assert set(ips[0].event_ids) == {"e1", "e2"}

    def test_two_distinct_ips_produce_two_entities(self, extractor):
        events = [_event(event_id="e1", source_ip="1.1.1.1", destination_ip="2.2.2.2")]
        result = extractor.extract(events, _INV)
        ips = [e for e in result if e.entity_type == EntityType.IP]
        assert len(ips) == 2


# ---------------------------------------------------------------------------
# Process entity tests
# ---------------------------------------------------------------------------


class TestProcessEntity:
    def test_process_entity_uses_host_and_name_as_key(self, extractor):
        events = [_event(event_id="e1", source_host="host-a", process="cmd.exe")]
        result = extractor.extract(events, _INV)
        procs = [e for e in result if e.entity_type == EntityType.PROCESS]
        assert len(procs) == 1
        assert procs[0].canonical_key == "host-a::cmd.exe"

    def test_process_without_source_host_not_extracted(self, extractor):
        """Process requires source_host for a stable canonical key."""
        events = [_event(event_id="e1", process="cmd.exe")]
        result = extractor.extract(events, _INV)
        procs = [e for e in result if e.entity_type == EntityType.PROCESS]
        assert len(procs) == 0

    def test_same_process_different_host_produces_two_entities(self, extractor):
        events = [
            _event(event_id="e1", source_host="host-a", process="powershell.exe"),
            _event(event_id="e2", source_host="host-b", process="powershell.exe"),
        ]
        result = extractor.extract(events, _INV)
        procs = [e for e in result if e.entity_type == EntityType.PROCESS]
        assert len(procs) == 2

    def test_same_process_same_host_deduplicates_regardless_of_pid(self, extractor):
        """PID is NOT in the canonical key; same process on same host deduplicates."""
        events = [
            _event(
                event_id="e1",
                source_host="host-a",
                process="svchost.exe",
                raw_data={"pid": 1234},
            ),
            _event(
                event_id="e2",
                source_host="host-a",
                process="svchost.exe",
                raw_data={"pid": 5678},
            ),
        ]
        result = extractor.extract(events, _INV)
        procs = [e for e in result if e.entity_type == EntityType.PROCESS]
        assert len(procs) == 1
        assert set(procs[0].event_ids) == {"e1", "e2"}

    def test_process_alias_is_process_name(self, extractor):
        events = [_event(event_id="e1", source_host="host-a", process="notepad.exe")]
        result = extractor.extract(events, _INV)
        procs = [e for e in result if e.entity_type == EntityType.PROCESS]
        assert "notepad.exe" in procs[0].aliases


# ---------------------------------------------------------------------------
# File entity tests
# ---------------------------------------------------------------------------


class TestFileEntity:
    def test_file_entity_uses_host_and_path_as_key(self, extractor):
        events = [
            _event(
                event_id="e1",
                source_host="host-a",
                file="/etc/passwd",
            )
        ]
        result = extractor.extract(events, _INV)
        files = [e for e in result if e.entity_type == EntityType.FILE]
        assert len(files) == 1
        assert files[0].canonical_key == "host-a::/etc/passwd"

    def test_file_without_source_host_not_extracted(self, extractor):
        events = [_event(event_id="e1", file="/etc/passwd")]
        result = extractor.extract(events, _INV)
        files = [e for e in result if e.entity_type == EntityType.FILE]
        assert len(files) == 0

    def test_same_path_on_different_hosts_produces_two_file_entities(self, extractor):
        events = [
            _event(event_id="e1", source_host="host-a", file="/tmp/malware.exe"),
            _event(event_id="e2", source_host="host-b", file="/tmp/malware.exe"),
        ]
        result = extractor.extract(events, _INV)
        files = [e for e in result if e.entity_type == EntityType.FILE]
        assert len(files) == 2

    def test_same_file_same_host_deduplicates(self, extractor):
        events = [
            _event(event_id="e1", source_host="host-a", file="/var/log/auth.log"),
            _event(event_id="e2", source_host="host-a", file="/var/log/auth.log"),
        ]
        result = extractor.extract(events, _INV)
        files = [e for e in result if e.entity_type == EntityType.FILE]
        assert len(files) == 1
        assert set(files[0].event_ids) == {"e1", "e2"}


# ---------------------------------------------------------------------------
# Deduplication and alias merging
# ---------------------------------------------------------------------------


class TestDeduplicationAndAliases:
    def test_aliases_accumulate_across_events(self, extractor):
        """When the same entity appears under the same canonical key, aliases grow."""
        # Both events have the same user canonical key; no alias variation here
        # (alias = canonical_key when there's only one observed name).
        events = [
            _event(event_id="e1", user="carol"),
            _event(event_id="e2", user="carol"),
        ]
        result = extractor.extract(events, _INV)
        users = [e for e in result if e.entity_type == EntityType.USER]
        assert "carol" in users[0].aliases

    def test_entity_ids_are_all_unique(self, extractor):
        events = [
            _event(
                event_id="e1",
                user="alice",
                source_host="ws-01",
                source_ip="192.168.1.1",
                process="cmd.exe",
                file="/etc/hosts",
            )
        ]
        result = extractor.extract(events, _INV)
        ids = [e.entity_id for e in result]
        assert len(ids) == len(set(ids))

    def test_no_entity_created_without_event_id(self, extractor):
        events = [_event(event_id="e1", user="dave", source_host="host-z")]
        result = extractor.extract(events, _INV)
        for entity in result:
            assert len(entity.event_ids) >= 1, f"Entity {entity.entity_id} has no event_ids"

    def test_result_is_deterministic_for_same_input(self, extractor):
        events = [
            _event(event_id="e1", user="alice", source_host="host-a"),
            _event(event_id="e2", user="bob", source_ip="10.0.0.1"),
        ]
        result1 = extractor.extract(events, _INV)
        result2 = extractor.extract(events, _INV)
        ids1 = sorted(e.entity_id for e in result1)
        ids2 = sorted(e.entity_id for e in result2)
        assert ids1 == ids2


# ---------------------------------------------------------------------------
# Event with no extractable fields
# ---------------------------------------------------------------------------


class TestNoExtractableFields:
    def test_event_with_no_entity_fields_produces_no_entities(self, extractor):
        events = [_event(event_id="e1")]
        result = extractor.extract(events, _INV)
        assert result == []

    def test_empty_event_list_produces_empty_result(self, extractor):
        result = extractor.extract([], _INV)
        assert result == []


# ---------------------------------------------------------------------------
# Multi-type event (all fields populated)
# ---------------------------------------------------------------------------


class TestMultiTypeEvent:
    def test_fully_populated_event_extracts_all_six_types(self, extractor):
        events = [
            _event(
                event_id="e1",
                user="alice",
                source_host="host-a",
                destination_host="host-b",
                source_ip="1.2.3.4",
                destination_ip="5.6.7.8",
                process="bash",
                file="/tmp/script.sh",
                raw_data={"server_role": "web"},
            )
        ]
        result = extractor.extract(events, _INV)
        entity_types = {e.entity_type for e in result}

        # source_host has server_role → SERVER; destination_host → HOST
        expected = {
            EntityType.USER,
            EntityType.SERVER,
            EntityType.HOST,
            EntityType.IP,      # source_ip and destination_ip (two IP entities)
            EntityType.PROCESS,
            EntityType.FILE,
        }
        assert entity_types == expected

    def test_fully_populated_event_all_entities_carry_same_event_id(self, extractor):
        events = [
            _event(
                event_id="e-multi",
                user="bob",
                source_host="host-x",
                destination_host="host-y",
                source_ip="10.0.0.1",
                process="python.exe",
                file="C:/scripts/run.py",
            )
        ]
        result = extractor.extract(events, _INV)
        for entity in result:
            assert "e-multi" in entity.event_ids, (
                f"Entity {entity.entity_type}/{entity.canonical_key} missing event_id"
            )


# ---------------------------------------------------------------------------
# Investigation ID propagation
# ---------------------------------------------------------------------------


class TestInvestigationIdPropagation:
    def test_all_entities_carry_the_supplied_investigation_id(self, extractor):
        events = [
            _event(
                event_id="e1",
                user="alice",
                source_host="host-a",
                source_ip="1.1.1.1",
            )
        ]
        inv = "my-investigation-xyz"
        result = extractor.extract(events, inv)
        for entity in result:
            assert entity.investigation_id == inv
