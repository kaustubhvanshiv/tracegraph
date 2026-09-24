from datetime import datetime, timezone
import pytest
from hypothesis import given, settings, strategies as st

from app.schemas.entity import Entity, EntityType, generate_entity_id
from app.schemas.relationship import RawRelationship, RelationshipType
from app.schemas.security_event import SecurityEvent
from app.services.entity_extractor import EntityExtractor
from app.services.relationship_extractor import RelationshipExtractor


# ---------------------------------------------------------------------------
# Unit Tests for Each Relationship Type
# ---------------------------------------------------------------------------

def test_extract_logged_into():
    extractor = RelationshipExtractor()
    entity_extractor = EntityExtractor()

    event = SecurityEvent(
        event_id="evt-001",
        source_type="sysmon",
        timestamp="2026-09-24T12:00:00Z",
        event_type="authentication",
        action="login",
        user="alice",
        source_host="workstation1",
    )

    entities = entity_extractor.extract([event], investigation_id="inv-101")
    rels = extractor.extract([event], entities, investigation_id="inv-101")

    assert len(rels) == 1
    rel = rels[0]
    assert rel.relationship_type == RelationshipType.LOGGED_INTO
    assert rel.event_ids == ["evt-001"]
    assert rel.investigation_id == "inv-101"
    assert rel.source == "sysmon"

    user_id = generate_entity_id(EntityType.USER, "alice")
    host_id = generate_entity_id(EntityType.HOST, "workstation1")
    assert rel.source_entity_id == user_id
    assert rel.target_entity_id == host_id


def test_extract_authenticated_to():
    extractor = RelationshipExtractor()
    entity_extractor = EntityExtractor()

    event = SecurityEvent(
        event_id="evt-002",
        source_type="auth",
        timestamp="2026-09-24T12:05:00Z",
        event_type="server_authentication",
        action="auth",
        user="bob",
        destination_host="dc01.corp",
        raw_data={"server_role": "domain_controller"},
    )

    entities = entity_extractor.extract([event], investigation_id="inv-101")
    rels = extractor.extract([event], entities, investigation_id="inv-101")

    assert len(rels) == 1
    rel = rels[0]
    assert rel.relationship_type == RelationshipType.AUTHENTICATED_TO
    assert rel.event_ids == ["evt-002"]

    user_id = generate_entity_id(EntityType.USER, "bob")
    assert rel.source_entity_id == user_id


def test_extract_executed():
    extractor = RelationshipExtractor()
    entity_extractor = EntityExtractor()

    event = SecurityEvent(
        event_id="evt-003",
        source_type="edr",
        timestamp="2026-09-24T12:10:00Z",
        event_type="process_creation",
        action="execute",
        source_host="srv-prod-01",
        process="cmd.exe",
    )

    entities = entity_extractor.extract([event], investigation_id="inv-101")
    rels = extractor.extract([event], entities, investigation_id="inv-101")

    assert len(rels) == 1
    rel = rels[0]
    assert rel.relationship_type == RelationshipType.EXECUTED
    proc_id = generate_entity_id(EntityType.PROCESS, "srv-prod-01::cmd.exe")
    host_id = generate_entity_id(EntityType.HOST, "srv-prod-01")
    assert rel.source_entity_id == proc_id
    assert rel.target_entity_id == host_id


def test_extract_connected_to():
    extractor = RelationshipExtractor()
    entity_extractor = EntityExtractor()

    event = SecurityEvent(
        event_id="evt-004",
        source_type="network",
        timestamp="2026-09-24T12:15:00Z",
        event_type="network_flow",
        action="connect",
        source_ip="192.168.1.50",
        destination_ip="10.0.0.1",
    )

    entities = entity_extractor.extract([event], investigation_id="inv-101")
    rels = extractor.extract([event], entities, investigation_id="inv-101")

    assert len(rels) == 1
    rel = rels[0]
    assert rel.relationship_type == RelationshipType.CONNECTED_TO
    src_ip_id = generate_entity_id(EntityType.IP, "192.168.1.50")
    dst_ip_id = generate_entity_id(EntityType.IP, "10.0.0.1")
    assert rel.source_entity_id == src_ip_id
    assert rel.target_entity_id == dst_ip_id


def test_extract_accessed():
    extractor = RelationshipExtractor()
    entity_extractor = EntityExtractor()

    event = SecurityEvent(
        event_id="evt-005",
        source_type="sysmon",
        timestamp="2026-09-24T12:20:00Z",
        event_type="file_access",
        action="access",
        user="alice",
        source_host="workstation1",
        process="notepad.exe",
        file="C:\\secret.txt",
    )

    entities = entity_extractor.extract([event], investigation_id="inv-101")
    rels = extractor.extract([event], entities, investigation_id="inv-101")

    # Should create Process -> File and User -> File ACCESSED relationships
    assert len(rels) >= 1
    types = {r.relationship_type for r in rels}
    assert RelationshipType.ACCESSED in types
    for r in rels:
        assert r.relationship_type == RelationshipType.ACCESSED


def test_rejection_of_unsupported_action_condition():
    """Event matching entity fields but with non-matching action should produce no relationship."""
    extractor = RelationshipExtractor()
    entity_extractor = EntityExtractor()

    # Has process + source_host but action is 'connect' (not 'execute')
    event = SecurityEvent(
        event_id="evt-006",
        source_type="edr",
        timestamp="2026-09-24T12:25:00Z",
        event_type="network_connection",
        action="connect",
        source_host="workstation1",
        process="powershell.exe",
        source_ip="192.168.1.10",
        destination_ip="1.1.1.1",
    )

    entities = entity_extractor.extract([event], investigation_id="inv-101")
    rels = extractor.extract([event], entities, investigation_id="inv-101")

    # Should only create CONNECTED_TO for IP -> IP, NOT EXECUTED for process
    rel_types = [r.relationship_type for r in rels]
    assert RelationshipType.EXECUTED not in rel_types
    assert RelationshipType.CONNECTED_TO in rel_types


def test_multi_event_deduplication_and_evidence_accumulation():
    """Multiple events triggering the same relationship should accumulate event_ids."""
    extractor = RelationshipExtractor()
    entity_extractor = EntityExtractor()

    event1 = SecurityEvent(
        event_id="evt-100",
        source_type="sysmon",
        timestamp="2026-09-24T13:00:00Z",
        event_type="authentication",
        action="login",
        user="charlie",
        source_host="host-a",
    )
    event2 = SecurityEvent(
        event_id="evt-101",
        source_type="sysmon",
        timestamp="2026-09-24T13:05:00Z",
        event_type="authentication",
        action="login",
        user="charlie",
        source_host="host-a",
    )

    events = [event1, event2]
    entities = entity_extractor.extract(events, investigation_id="inv-200")
    rels = extractor.extract(events, entities, investigation_id="inv-200")

    assert len(rels) == 1
    rel = rels[0]
    assert rel.relationship_type == RelationshipType.LOGGED_INTO
    assert set(rel.event_ids) == {"evt-100", "evt-101"}
    assert rel.timestamp == event1.timestamp


# ---------------------------------------------------------------------------
# Property 5 Test: Relationship Evidence
# Validates: Requirement 5.2
# ---------------------------------------------------------------------------

@given(
    st.lists(
        st.fixed_dictionaries({
            "event_id": st.text(min_size=1, max_size=10).map(lambda s: f"evt-{s}"),
            "source_type": st.sampled_from(["sysmon", "edr", "auth", "network", "siem"]),
            "timestamp": st.just("2026-09-24T12:00:00Z"),
            "event_type": st.sampled_from(["authentication", "process_creation", "network_flow", "file_access"]),
            "action": st.sampled_from(["login", "auth", "execute", "connect", "access"]),
            "user": st.one_of(st.none(), st.just("user1")),
            "source_host": st.one_of(st.none(), st.just("host1")),
            "destination_host": st.one_of(st.none(), st.just("host2")),
            "source_ip": st.one_of(st.none(), st.just("10.0.0.1")),
            "destination_ip": st.one_of(st.none(), st.just("10.0.0.2")),
            "process": st.one_of(st.none(), st.just("cmd.exe")),
            "file": st.one_of(st.none(), st.just("C:\\test.txt")),
        }),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=30)
def test_property_relationship_evidence(raw_events):
    """Property 5: Relationship Evidence
    Assert every extracted relationship carries at least one event_id in event_ids.
    """
    events = [SecurityEvent(**re) for re in raw_events]
    entity_extractor = EntityExtractor()
    rel_extractor = RelationshipExtractor()

    entities = entity_extractor.extract(events, investigation_id="inv-prop5")
    rels = rel_extractor.extract(events, entities, investigation_id="inv-prop5")

    for rel in rels:
        assert isinstance(rel, RawRelationship)
        assert len(rel.event_ids) >= 1
        assert isinstance(rel.relationship_type, RelationshipType)
