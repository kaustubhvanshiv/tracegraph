import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fastavro import writer

from research.ml.data_prep.audit_attack_coverage import audit_file, time_nanos
from research.ml.tests.test_inspect_fivedirections import SCHEMA


class CoverageTests(unittest.TestCase):
    def test_cli_selects_one_file_and_rejects_changed_resume_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "raw"
            source.mkdir()
            row = {"type": "RECORD_EVENT", "datum": {
                "timestampNanos": 1_000_000_000, "type": "EVENT_OPEN", "subject": "p",
                "properties": {},
            }}
            for name in ["sample.bin.1.gz", "sample.bin.2.gz"]:
                with gzip.open(source / name, "wb") as stream:
                    writer(stream, SCHEMA, [row])
            candidates_path = root / "candidates.json"
            candidates_path.write_text(json.dumps({"incidents": []}), encoding="utf-8")
            output = root / "report.json"
            command = [sys.executable, "-m", "research.ml.data_prep.audit_attack_coverage",
                       "--source", str(source), "--candidates", str(candidates_path),
                       "--filename", "sample.bin.2.gz", "--output", str(output)]
            cwd = Path(__file__).resolve().parents[3]
            result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report["discovered_file_count"], 2)
            self.assertEqual(report["selected_file_count"], 1)
            self.assertTrue(report["all_files_fully_scanned"])
            self.assertEqual(Path(report["files"][0]["path"]).name, "sample.bin.2.gz")
            resumed = subprocess.run(command + ["--resume"], cwd=cwd, capture_output=True, text=True)
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn("Reusing complete audit", resumed.stdout)
            candidates_path.write_text(json.dumps({"incidents": [], "changed": True}), encoding="utf-8")
            rejected = subprocess.run(command + ["--resume"], cwd=cwd, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("identical incident/schema content", rejected.stderr)

    def test_indicator_match_is_not_an_attack_label(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.bin.121.gz"
            rows = [
                {"type": "RECORD_EVENT", "datum": {
                    "timestampNanos": t, "type": "EVENT_OPEN", "subject": "p",
                    "properties": {"FileName": "C:\\test\\DBGSTAT.DLL"},
                }} for t in [1_000_000_000, 3_000_000_000]
            ]
            with gzip.open(path, "wb") as stream:
                writer(stream, SCHEMA, rows)
            candidates = {"incidents": [{
                "incident_id": "incident1", "indicators": ["dbgstat.dll"],
                "candidate_start_utc": "1970-01-01T00:00:01Z",
                "candidate_end_utc": "1970-01-01T00:00:02Z",
            }]}
            report = audit_file(path, candidates, SCHEMA)
            self.assertTrue(report["complete_scan"])
            self.assertEqual(report["candidate_interval_event_counts"], {"incident1": 1})
            self.assertEqual(report["indicator_event_counts"], {"dbgstat.dll": 2})
            self.assertEqual(report["labels_assigned"], 0)
            self.assertTrue(all(r["label"] is None for r in report["review_event_references"]))
            self.assertTrue(report["downloaded_schema_matches"])
            self.assertNotIn("C:\\test\\DBGSTAT.DLL", str(report))

    def test_timezone_offset_is_converted_before_window_matching(self):
        self.assertEqual(time_nanos("2019-05-17T16:11:00-04:00"),
                         time_nanos("2019-05-17T20:11:00Z"))


if __name__ == "__main__":
    unittest.main()
