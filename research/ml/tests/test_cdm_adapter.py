import json
import sqlite3
import unittest

from research.ml.data_prep.prepare_dataset import CDMReviewAdapter
from research.ml.data_prep.cdm_adapter import EntityResolver, executable


class CDMAdapterTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE entities(host TEXT,uuid TEXT,kind TEXT,payload TEXT,conflict INTEGER DEFAULT 0,PRIMARY KEY(host,uuid))")
        self.adapter = CDMReviewAdapter(EntityResolver(self.db))

    def add(self, uid, kind, datum, host="h", conflict=0):
        self.db.execute("INSERT INTO entities VALUES (?,?,?,?,?)", (host, uid, kind, json.dumps(datum), conflict))

    def event(self, action="EVENT_OPEN", target="o", actor="t", timestamp=100):
        return {"type": "RECORD_EVENT", "hostId": "h", "datum": {"uuid": "e", "type": action,
                "timestampNanos": timestamp, "predicateObject": target, "subject": actor,
                "predicateObjectPath": r"C:\example\artifact"}}

    def test_only_typed_file_open_maps_to_file_access(self):
        self.add("o", "RECORD_FILE_OBJECT", {})
        parsed = self.adapter.parse(self.event())
        self.assertEqual((parsed.event_type, parsed.action), ("file", "access"))
        self.assertEqual(parsed.file, r"C:\example\artifact")
        self.assertEqual(parsed.extra_fields["cdm"]["datum"]["type"], "EVENT_OPEN")
        self.assertEqual(self.adapter.parse(self.event("EVENT_CLOSE")).action, "close")

    def test_registry_and_memory_open_never_become_file_access(self):
        for uid, kind, category in (("r", "RECORD_REGISTRY_KEY_OBJECT", "registry"), ("m", "RECORD_MEMORY_OBJECT", "memory")):
            self.add(uid, kind, {})
            parsed = self.adapter.parse(self.event(target=uid))
            self.assertEqual((parsed.event_type, parsed.action, parsed.file), (category, "open", None))

    def test_future_or_missing_process_start_does_not_supply_image(self):
        self.add("t", "RECORD_SUBJECT", {"type": "SUBJECT_THREAD", "cid": 123, "parentSubject": "p", "startTimestampNanos": 10})
        self.add("p", "RECORD_SUBJECT", {"type": "SUBJECT_PROCESS", "cid": 456, "startTimestampNanos": 101, "cmdLine": '"C:\\Program Files\\firefox.exe" -x'})
        parsed = self.adapter.parse(self.event())
        self.assertIsNone(parsed.process)
        self.assertFalse(parsed.extra_fields["subject_resolution"]["process_resolved"])
        valid = self.adapter.parse(self.event(timestamp=200))
        self.assertEqual(valid.process, r"C:\Program Files\firefox.exe")
        self.assertEqual(valid.extra_fields["subject_resolution"]["chain"][-1]["cid"], 456)

    def test_host_and_principal_fields_require_same_host_definitions(self):
        self.add("t", "RECORD_SUBJECT", {"type": "SUBJECT_PROCESS", "startTimestampNanos": 1, "localPrincipal": "u", "cmdLine": "firefox.exe"})
        self.add("u", "RECORD_PRINCIPAL", {"username": "alice"})
        self.add("h", "RECORD_HOST", {"hostName": "lab-host"})
        self.add("o", "RECORD_FILE_OBJECT", {}, host="other")
        parsed = self.adapter.parse(self.event())
        self.assertEqual((parsed.user, parsed.source_host), ("alice", "lab-host"))
        self.assertIsNone(parsed.file)

    def test_conflicting_object_definition_is_not_used(self):
        self.add("o", "RECORD_FILE_OBJECT", {}, conflict=1)
        parsed = self.adapter.parse(self.event())
        self.assertIsNone(parsed.file)
        self.assertEqual(parsed.event_type, "cdm_event")

    def test_network_orientation_and_invalid_addresses(self):
        self.add("h", "RECORD_HOST", {"hostName": "local-host"})
        self.add("o", "RECORD_NET_FLOW_OBJECT", {"localAddress": "10.0.0.1", "remoteAddress": "10.0.0.2"})
        outgoing = self.adapter.parse(self.event("EVENT_CONNECT"))
        incoming = self.adapter.parse(self.event("EVENT_ACCEPT"))
        self.assertEqual((outgoing.source_ip, outgoing.destination_ip, outgoing.action), ("10.0.0.1", "10.0.0.2", "connect"))
        self.assertEqual((incoming.source_ip, incoming.destination_ip, incoming.action), ("10.0.0.2", "10.0.0.1", "accept"))
        self.assertEqual(outgoing.source_host, "local-host")
        self.assertEqual(incoming.destination_host, "local-host")
        self.assertIsNone(incoming.source_host)
        self.add("bad", "RECORD_NET_FLOW_OBJECT", {"localAddress": "not-an-ip"})
        self.assertIsNone(self.adapter.parse(self.event("EVENT_CONNECT", target="bad")).source_ip)

    def test_login_logout_thread_and_execute_are_distinct(self):
        for action, category, mapped in (("EVENT_LOGIN", "authentication", "login"),
                                          ("EVENT_LOGOUT", "authentication", "logout"),
                                          ("EVENT_CREATE_THREAD", "thread", "create_thread")):
            parsed = self.adapter.parse(self.event(action))
            self.assertEqual((parsed.event_type, parsed.action), (category, mapped))
        self.add("t", "RECORD_SUBJECT", {"type": "SUBJECT_PROCESS", "startTimestampNanos": 1, "cmdLine": "parent.exe"})
        self.add("o", "RECORD_FILE_OBJECT", {})
        executed = self.adapter.parse(self.event("EVENT_EXECUTE"))
        self.assertEqual(executed.process, r"C:\example\artifact")
        self.assertNotEqual(executed.process, "parent.exe")

    def test_ambiguous_or_malformed_command_is_not_guessed(self):
        self.assertIsNone(executable(r"C:\Program Files\firefox.exe -x"))
        self.assertIsNone(executable('"unclosed'))


if __name__ == "__main__":
    unittest.main()
