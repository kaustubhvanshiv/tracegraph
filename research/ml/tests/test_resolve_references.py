import json
import sqlite3
import unittest

from research.ml.data_prep.resolve_references import lookup, resolve_chain


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


if __name__ == "__main__":
    unittest.main()
