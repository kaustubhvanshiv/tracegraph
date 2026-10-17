import json
import gzip
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastavro import writer
from research.ml.data_prep.resolve_references import audit, lookup, resolve_chain


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE entities(uuid TEXT,kind TEXT,payload TEXT,filename TEXT,record_index INTEGER,host TEXT)")

    def add(self, uid, payload):
        self.db.execute("INSERT INTO entities VALUES (?,?,?,?,?,?)", (uid, "RECORD_SUBJECT", json.dumps(payload), "sample.gz", 1, "h"))

    def test_thread_resolves_process_and_checks_event_time(self):
        self.add("t", {"type": "SUBJECT_THREAD", "parentSubject": "p", "cid": 7})
        self.add("p", {"type": "SUBJECT_PROCESS", "cid": 9, "startTimestampNanos": 20,
                       "cmdLine": 'firefox.exe --private-secret', "localPrincipal": "u"})
        chain = resolve_chain(self.db, "t", 10)
        self.assertEqual(chain[-1]["cid"], 9)
        self.assertFalse(chain[-1]["started_at_or_before_event"])
        self.assertTrue(chain[-1]["firefox_command_line"])
        self.assertEqual(chain[-1]["principal_resolution"]["status"], "missing")
        self.assertNotIn("private-secret", json.dumps(chain))

    def test_conflicting_definitions_are_not_resolved(self):
        self.add("p", {"type": "SUBJECT_PROCESS", "cid": 1})
        self.add("p", {"type": "SUBJECT_PROCESS", "cid": 2})
        self.assertEqual(lookup(self.db, "p")["status"], "conflicting_definitions")

    def test_missing_and_cyclic_parents_terminate(self):
        self.assertEqual(resolve_chain(self.db, "absent", 0)[0]["status"], "missing")
        self.add("a", {"type": "SUBJECT_THREAD", "parentSubject": "b"})
        self.add("b", {"type": "SUBJECT_THREAD", "parentSubject": "a"})
        self.assertEqual(len(resolve_chain(self.db, "a", 0)), 2)

    def test_host_and_entity_kind_prevent_cross_host_resolution(self):
        self.add("p", {"type": "SUBJECT_PROCESS", "cid": 9})
        self.db.execute("INSERT INTO entities VALUES (?,?,?,?,?,?)", (
            "p", "RECORD_SUBJECT", json.dumps({"type": "SUBJECT_PROCESS", "cid": 10}), "other.gz", 1, "other-host"))
        self.assertEqual(lookup(self.db, "p")["status"], "conflicting_definitions")
        self.assertEqual(resolve_chain(self.db, "p", 0, "h")[0]["cid"], 9)
        self.assertEqual(lookup(self.db, "p", "other-host", "RECORD_PRINCIPAL")["status"], "missing")
        self.assertEqual(resolve_chain(self.db, "p", 0, "absent-host")[0]["status"], "missing")


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "raw"
        self.source.mkdir()
        self.annotations = self.root / "annotations.json"
        self.annotations.write_text(json.dumps({"events": [{"event_uuid": "e", "host_uuid": "h",
            "subject_uuid": "p", "timestamp_nanos": 20}]}), encoding="utf-8")
        self.schema = {"type": "record", "name": "CDM", "fields": [
            {"name": "type", "type": "string"}, {"name": "hostId", "type": "string"},
            {"name": "datum", "type": {"type": "record", "name": "Data", "fields": [
                {"name": "uuid", "type": "string"}, {"name": "type", "type": "string"},
                {"name": "timestampNanos", "type": "long", "default": 10}]}}]}
        self.write("one.gz")
        self.prior = self.root / "prior"
        audit(self.source, self.annotations, self.prior)

    def write(self, name):
        with gzip.open(self.source / name, "wb") as stream:
            writer(stream, self.schema, [{"type": "RECORD_SUBJECT", "hostId": "h",
                "datum": {"uuid": name, "type": "SUBJECT_PROCESS"}},
                {"type": "RECORD_EVENT", "hostId": "h", "datum": {"uuid": "e", "type": "EVENT_OPEN"}}])

    def test_reuse_matches_fresh_scan_without_duplicating_old_rows(self):
        self.write("two.gz")
        incremental = audit(self.source, self.annotations, self.root / "incremental", reuse_audit=self.prior)
        fresh = audit(self.source, self.annotations, self.root / "fresh")
        self.assertEqual(incremental["files"], fresh["files"])
        self.assertEqual(incremental["review_events"], fresh["review_events"])
        self.assertEqual(incremental["reused_file_count"], 1)
        self.assertEqual(incremental["newly_scanned_file_count"], 1)
        with closing(sqlite3.connect(self.root / "incremental" / "references.sqlite")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM entities").fetchone()[0], 2)

    def test_changed_source_is_rejected_before_output_creation(self):
        with (self.source / "one.gz").open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "Cached source changed"):
            audit(self.source, self.annotations, self.root / "out", reuse_audit=self.prior)
        self.assertFalse((self.root / "out").exists())

    def test_inconsistent_cache_and_prefix_reuse_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "full scan"):
            audit(self.source, self.annotations, self.root / "prefix", 1, reuse_audit=self.prior)
        with closing(sqlite3.connect(self.prior / "references.sqlite")) as db:
            db.execute("DELETE FROM entities")
            db.commit()
        with self.assertRaisesRegex(ValueError, "Cached index"):
            audit(self.source, self.annotations, self.root / "out", reuse_audit=self.prior)

    def test_file_filter_excludes_other_streams(self):
        self.write("other.gz")
        result = audit(self.source, self.annotations, self.root / "selected", file_pattern="one.gz")
        self.assertEqual([f["filename"] for f in result["files"]], ["one.gz"])


if __name__ == "__main__":
    unittest.main()
