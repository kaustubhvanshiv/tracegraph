import gzip
import json
from pathlib import Path
import tempfile
import unittest

from fastavro import writer

from research.ml.data_prep.audit_label_evidence import audit, compiled_activities


class LabelEvidenceTests(unittest.TestCase):
    def test_host_time_and_candidate_cap_never_assign_negative_labels(self):
        schema = {"type": "record", "name": "CDM", "fields": [
            {"name": "type", "type": "string"}, {"name": "hostId", "type": "string"},
            {"name": "datum", "type": {"type": "record", "name": "Payload", "fields": [
                {"name": "uuid", "type": "string"}, {"name": "type", "type": "string"},
                {"name": "timestampNanos", "type": "long", "default": 0},
                {"name": "startTimestampNanos", "type": "long", "default": 0},
                {"name": "subject", "type": ["null", "string"], "default": None},
                {"name": "cmdLine", "type": ["null", "string"], "default": None}]}}]}

        def event(uid, second, subject="p", host="h"):
            return {"type": "RECORD_EVENT", "hostId": host, "datum": {
                "uuid": uid, "type": "EVENT_FORK", "timestampNanos": second * 10**9, "subject": subject}}

        def subject(uid, second):
            return {"type": "RECORD_SUBJECT", "hostId": "h", "datum": {
                "uuid": uid, "type": "SUBJECT_PROCESS", "startTimestampNanos": second * 10**9,
                "cmdLine": "BCDEDIT /set nointegritychecks ON"}}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "raw"
            source.mkdir()
            with gzip.open(source / "sample.bin.gz", "wb") as stream:
                writer(stream, schema, [event("early", 12), subject("p", 11), event("candidate", 13),
                    subject("q", 14), event("capped", 15, "q"), event("other-host", 12, host="other"), event("outside", 21)])
            config = root / "activities.json"
            config.write_text(json.dumps({"activities": [{"activity_id": "admin-command", "candidate_class": 0,
                "host_uuid": "h", "start_utc": "1970-01-01T00:00:10Z", "end_utc": "1970-01-01T00:00:20Z",
                "search_regex": "bcdedit", "subject_only": True, "evidence": {"source": "synthetic fixture"}}]}))
            report = audit(source, config, root / "out", candidate_cap=1)
            matches = report["activity_matches"]["admin-command"]
            self.assertEqual(matches["window_event_count"], 3)
            self.assertEqual(matches["subject_match_count"], 2)
            self.assertEqual(matches["known_subject_event_count"], 2)
            self.assertEqual(len(matches["subject_candidates"]), 1)
            self.assertEqual([r["event_uuid"] for r in matches["event_candidates"]], ["candidate"])
            self.assertIsNone(matches["event_candidates"][0]["label"])
            self.assertEqual(report["labels_assigned"], 0)
            self.assertTrue(report["all_files_fully_scanned"])
            self.assertEqual(report["files"][0]["records"], 7)
            self.assertIn("preceding definitions", report["candidate_caveat"])
            with self.assertRaises(ValueError):
                audit(source, config, root / "out")

    def test_duplicate_activities_and_invalid_time_windows_are_rejected(self):
        activity = {"activity_id": "one", "host_uuid": "h", "start_utc": "1970-01-01T00:00:10Z",
                    "end_utc": "1970-01-01T00:00:20Z", "search_regex": "bcdedit", "evidence": "fixture"}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            compiled_activities({"activities": [activity, activity]})
        with self.assertRaisesRegex(ValueError, "increasing"):
            compiled_activities({"activities": [{**activity, "end_utc": activity["start_utc"]}]})


if __name__ == "__main__":
    unittest.main()
