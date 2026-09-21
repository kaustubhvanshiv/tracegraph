import copy
import pytest
from hypothesis import given, settings, strategies as st

from app.adapters import (
    AuthAdapter,
    EDRAdapter,
    NetworkAdapter,
    PublicDatasetAdapter,
    SIEMAdapter,
    SysmonAdapter,
    register_default_adapters,
)
from app.schemas.parser import ParsedEvent, ParseError
from app.services.parser_registry import AdapterRegistry, default_registry


# ---------------------------------------------------------------------------
# Unit Tests for SIEMAdapter
# ---------------------------------------------------------------------------

def test_siem_adapter_success():
    adapter = SIEMAdapter()
    raw = {
        "event_id": "siem-001",
        "@timestamp": "2026-09-20T10:00:00Z",
        "event_type": "authentication",
        "action": "login",
        "user": "alice",
        "src_host": "workstation-a",
        "custom_vendor_field": "unmapped_value",
    }
    result = adapter.parse(raw)
    assert isinstance(result, ParsedEvent)
    assert result.event_id == "siem-001"
    assert result.source_type == "siem"
    assert result.timestamp_raw == "2026-09-20T10:00:00Z"
    assert result.user == "alice"
    assert result.source_host == "workstation-a"
    assert result.extra_fields == {"custom_vendor_field": "unmapped_value"}


def test_siem_adapter_missing_required_fields():
    adapter = SIEMAdapter()

    # Missing event_id
    raw1 = {"@timestamp": "2026-09-20T10:00:00Z", "user": "bob"}
    err1 = adapter.parse(raw1)
    assert isinstance(err1, ParseError)
    assert err1.field_name == "event_id"

    # Missing timestamp
    raw2 = {"event_id": "siem-002", "user": "bob"}
    err2 = adapter.parse(raw2)
    assert isinstance(err2, ParseError)
    assert err2.field_name == "timestamp"
    assert err2.event_id == "siem-002"


# ---------------------------------------------------------------------------
# Unit Tests for EDRAdapter
# ---------------------------------------------------------------------------

def test_edr_adapter_success():
    adapter = EDRAdapter()
    raw = {
        "alert_id": "edr-001",
        "event_timestamp": "2026-09-20T10:05:00Z",
        "event_category": "process_creation",
        "action_taken": "execute",
        "account_name": "SYSTEM",
        "endpoint_name": "srv-prod-01",
        "process_path": "C:\\Windows\\System32\\cmd.exe",
        "threat_level": "high",
        "edr_rule_id": 9012,
    }
    result = adapter.parse(raw)
    assert isinstance(result, ParsedEvent)
    assert result.event_id == "edr-001"
    assert result.source_type == "edr"
    assert result.user == "SYSTEM"
    assert result.source_host == "srv-prod-01"
    assert result.process == "C:\\Windows\\System32\\cmd.exe"
    assert result.severity == "high"
    assert result.extra_fields == {"edr_rule_id": 9012}


# ---------------------------------------------------------------------------
# Unit Tests for SysmonAdapter
# ---------------------------------------------------------------------------

def test_sysmon_adapter_success():
    adapter = SysmonAdapter()
    raw = {
        "EventID": 1,
        "UtcTime": "2026-09-20 10:10:00.000",
        "EventDescription": "Process Create",
        "Action": "execute",
        "User": "NT AUTHORITY\\SYSTEM",
        "Computer": "DC01.corp.domain",
        "Image": "C:\\Windows\\System32\\powershell.exe",
        "ProcessId": 4096,
    }
    result = adapter.parse(raw)
    assert isinstance(result, ParsedEvent)
    assert result.event_id == "1"
    assert result.source_type == "sysmon"
    assert result.user == "NT AUTHORITY\\SYSTEM"
    assert result.source_host == "DC01.corp.domain"
    assert result.process == "C:\\Windows\\System32\\powershell.exe"
    assert result.extra_fields == {"ProcessId": 4096}


# ---------------------------------------------------------------------------
# Unit Tests for AuthAdapter
# ---------------------------------------------------------------------------

def test_auth_adapter_success():
    adapter = AuthAdapter()
    raw = {
        "auth_id": "auth-555",
        "event_time": "2026-09-20T10:15:00Z",
        "auth_event": "login",
        "auth_action": "auth_success",
        "user_id": "admin",
        "hostname": "bastion01",
        "target_host": "db01",
        "client_ip": "192.168.1.100",
        "server_ip": "10.0.0.5",
        "mfa_used": True,
    }
    result = adapter.parse(raw)
    assert isinstance(result, ParsedEvent)
    assert result.event_id == "auth-555"
    assert result.source_type == "auth"
    assert result.user == "admin"
    assert result.source_host == "bastion01"
    assert result.destination_host == "db01"
    assert result.source_ip == "192.168.1.100"
    assert result.destination_ip == "10.0.0.5"
    assert result.extra_fields == {"mfa_used": True}


# ---------------------------------------------------------------------------
# Unit Tests for NetworkAdapter
# ---------------------------------------------------------------------------

def test_network_adapter_success():
    adapter = NetworkAdapter()
    raw = {
        "flow_id": "flow-999",
        "start_time": "2026-09-20T10:20:00Z",
        "protocol": "TCP",
        "connection_state": "connect",
        "src_ip": "10.0.1.50",
        "dst_ip": "185.220.101.5",
        "src_host": "user-pc",
        "dst_host": "external-c2",
        "bytes_sent": 1048576,
    }
    result = adapter.parse(raw)
    assert isinstance(result, ParsedEvent)
    assert result.event_id == "flow-999"
    assert result.source_type == "network"
    assert result.event_type == "TCP"
    assert result.action == "connect"
    assert result.source_ip == "10.0.1.50"
    assert result.destination_ip == "185.220.101.5"
    assert result.extra_fields == {"bytes_sent": 1048576}


# ---------------------------------------------------------------------------
# Unit Tests for PublicDatasetAdapter
# ---------------------------------------------------------------------------

def test_public_dataset_adapter_success():
    adapter = PublicDatasetAdapter()
    raw = {
        "event_id": "mordor-1234",
        "timestamp": "2026-09-20T10:25:00Z",
        "event_type": "process_creation",
        "action": "execute",
        "user": "victim_user",
        "source_host": "target-workstation",
        "process": "cmd.exe",
        "dataset_name": "mordor_apt29",
    }
    result = adapter.parse(raw)
    assert isinstance(result, ParsedEvent)
    assert result.event_id == "mordor-1234"
    assert result.source_type == "public_dataset"
    assert result.user == "victim_user"
    assert result.extra_fields == {"dataset_name": "mordor_apt29"}


# ---------------------------------------------------------------------------
# AdapterRegistry Tests
# ---------------------------------------------------------------------------

def test_adapter_registry_registration_and_dispatch():
    registry = AdapterRegistry()
    register_default_adapters(registry)

    assert set(registry.list_source_types()) == {"siem", "edr", "sysmon", "auth", "network", "public_dataset"}

    raw = {"event_id": "evt-reg-1", "timestamp": "2026-09-20T11:00:00Z", "action": "login"}
    res = registry.dispatch("siem", raw)
    assert isinstance(res, ParsedEvent)
    assert res.source_type == "siem"

    # Unregistered source_type returns ParseError
    unreg_res = registry.dispatch("unknown_source", raw)
    assert isinstance(unreg_res, ParseError)
    assert unreg_res.field_name == "source_type"


# ---------------------------------------------------------------------------
# Property 16: Parser Non-Mutation
# Validates: Requirements 2.1, 2.4
# ---------------------------------------------------------------------------

@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(st.text(), st.integers(), st.booleans(), st.none()),
        max_size=15,
    )
)
@settings(max_examples=50)
def test_property_parser_non_mutation(raw_dict: dict):
    """
    Property 16: Parser Non-Mutation
    Use hypothesis to generate arbitrary raw event dicts.
    Assert every key is present in either recognized fields or extra_fields after parsing.
    Assert input dict is NOT mutated.
    """
    adapters = [
        SIEMAdapter(),
        EDRAdapter(),
        SysmonAdapter(),
        AuthAdapter(),
        NetworkAdapter(),
        PublicDatasetAdapter(),
    ]

    for adapter in adapters:
        original_copy = copy.deepcopy(raw_dict)
        res = adapter.parse(raw_dict)

        # 1. Input dict MUST NOT be mutated
        assert raw_dict == original_copy

        if isinstance(res, ParsedEvent):
            # 2. Every key in raw_dict MUST be accounted for in either a recognized attribute or extra_fields
            parsed_dump = res.model_dump()
            extra = res.extra_fields

            for k, v in raw_dict.items():
                is_in_extra = k in extra
                is_recognized_attr = k in parsed_dump and parsed_dump[k] is not None
                assert is_in_extra or is_recognized_attr or k in {
                    "event_id", "@id", "id", "uuid", "alert_id", "EventID", "RecordID", "auth_id", "flow_id",
                    "@timestamp", "timestamp", "time", "EventTime", "event_timestamp", "UtcTime", "TimeCreated", "auth_time", "event_time", "start_time"
                }
