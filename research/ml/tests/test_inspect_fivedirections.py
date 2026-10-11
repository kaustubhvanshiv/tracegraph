import gzip
from pathlib import Path
import tempfile
import unittest

from fastavro import writer

from research.ml.data_prep.inspect_fivedirections import inspect_dataset, inspect_file, utc_nanos


SCHEMA = {
    "type": "record", "name": "Datum", "fields": [
        {"name": "type", "type": "string"},
        {"name": "datum", "type": {"type": "record", "name": "Event", "fields": [
            {"name": "timestampNanos", "type": "long"},
            {"name": "type", "type": "string"},
            {"name": "subject", "type": ["null", "string"], "default": None},
            {"name": "properties", "type": {"type": "map", "values": "string"}},
        ]}},
    ],
}


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sample.bin.1.gz"
        rows = [
            {"type": "RECORD_EVENT", "datum": {
                "timestampNanos": t, "type": "EVENT_READ", "subject": s,
                "properties": props,
            }} for t, s, props in [(1_000_000_001, "p", {}), (999_999_999, None, {"label": "attack"})]
        ]
        with gzip.open(self.path, "wb") as stream:
            writer(stream, SCHEMA, rows)

    def test_cap_does_not_count_lookahead_or_infer_benign_labels(self):
        profile, _ = inspect_file(self.path, 1)
        self.assertEqual(profile["records_inspected"], 1)
        self.assertFalse(profile["complete_scan"])
        self.assertEqual(profile["candidate_label_key_counts"], {})
        self.assertEqual(profile["event_fields_populated"]["subject"], 1)

    def test_complete_scan_and_timestamp_precision(self):
        profile, _ = inspect_file(self.path, 0)
        self.assertTrue(profile["complete_scan"])
        self.assertEqual(profile["event_count"], 2)
        self.assertEqual(profile["event_timestamp_regressions"], 1)
        self.assertEqual(profile["candidate_label_key_counts"], {"label": 1})
        self.assertEqual(profile["event_time_min_utc"], "1970-01-01T00:00:00.999999999Z")
        self.assertEqual(utc_nanos(-1), "1969-12-31T23:59:59.999999999Z")

    def test_exact_cap_at_eof_is_complete(self):
        self.assertTrue(inspect_file(self.path, 2)[0]["complete_scan"])

    def test_corrupt_file_is_reported_and_prevents_complete_status(self):
        (self.path.parent / "broken.bin.2.gz").write_bytes(b"corrupt")
        report = inspect_dataset(self.path.parent, 10)
        self.assertEqual(len(report["errors"]), 1)
        self.assertEqual(report["records_inspected"], 2)
        self.assertFalse(report["all_files_fully_scanned"])

    def test_missing_source_and_negative_limit_rejected(self):
        with self.assertRaises(ValueError):
            inspect_dataset(self.path.parent / "missing")
        with self.assertRaises(ValueError):
            inspect_file(self.path, -1)


if __name__ == "__main__":
    unittest.main()
