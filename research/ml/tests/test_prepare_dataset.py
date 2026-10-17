import unittest
import gzip
import json
import hashlib
from pathlib import Path
import tempfile
from fastavro import writer

from research.ml.data_prep.prepare_dataset import CDMReviewAdapter, make_splits, reviewed_label, prepare
from app.schemas.parser import ParseError
from research.ml.data_prep.resolve_references import audit


class ReferencePreparationTests(unittest.TestCase):
    def test_external_metadata_improves_fields_without_assigning_labels(self):
        schema = {"type": "record", "name": "CDM", "fields": [
            {"name": "type", "type": "string"}, {"name": "hostId", "type": "string"},
            {"name": "datum", "type": {"type": "record", "name": "Data", "fields": [
                {"name": "uuid", "type": "string"}, {"name": "type", "type": "string"},
                {"name": "timestampNanos", "type": "long", "default": 20},
                {"name": "startTimestampNanos", "type": "long", "default": 10},
                *[{"name": key, "type": ["null", "string"], "default": None}
                  for key in ("hostName", "username", "cmdLine", "localPrincipal", "subject")]]}}]}
        for definition_host, start, should_resolve in (("h", 10, True), ("other", 10, False), ("h", 30, False)):
            with self.subTest(definition_host=definition_host, start=start), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "raw"
                source.mkdir()
                with gzip.open(source / "metadata.gz", "wb") as stream:
                    writer(stream, schema, [{"type": kind, "hostId": definition_host, "datum": datum}
                        for kind, datum in (
                            ("RECORD_HOST", {"uuid": "h", "type": "HOST_DESKTOP", "hostName": "host-one"}),
                            ("RECORD_PRINCIPAL", {"uuid": "u", "type": "PRINCIPAL_LOCAL", "username": "alice"}),
                            ("RECORD_SUBJECT", {"uuid": "p", "type": "SUBJECT_PROCESS", "cmdLine": "firefox.exe",
                                                "localPrincipal": "u", "startTimestampNanos": start}))])
                with gzip.open(source / "events.gz", "wb") as stream:
                    writer(stream, schema, [{"type": "RECORD_EVENT", "hostId": "h", "datum": {
                        "uuid": "e", "type": "EVENT_OPEN", "subject": "p", "timestampNanos": 20}}])
                annotations = root / "annotations.json"
                annotations.write_text(json.dumps({"events": [{"event_uuid": "e", "host_uuid": "h",
                    "subject_uuid": "p", "timestamp_nanos": 20, "cdm_event_type": "EVENT_OPEN",
                    "source_file": "events.gz", "label": None}]}), encoding="utf-8")
                reference = root / "reference"
                audit(source, annotations, reference, file_pattern="metadata.gz")
                result = prepare(source, annotations, root / "prepared", 0, reference_audit=reference)
                self.assertEqual(result["resolved_process_count"], int(should_resolve))
                self.assertEqual(result["normalized_field_counts"]["user"], int(should_resolve))
                self.assertEqual(result["normalized_field_counts"]["source_host"], int(definition_host == "h"))
                self.assertEqual(result["label_counts"], {"None": 1})
                self.assertEqual(result["status"], "blocked_for_training")
                self.assertEqual(result["reference_audit"]["definitions_imported"], 3)
                self.assertEqual(result["reference_audit"]["report_sha256"], hashlib.sha256(
                    (reference / "reference_report.json").read_text(encoding="utf-8").encode("utf-8")).hexdigest())


class PreparationTests(unittest.TestCase):
    def test_streaming_run_preserves_unknown_and_refuses_splits(self):
        schema = {"type": "record", "name": "CDM", "fields": [
            {"name": "type", "type": "string"}, {"name": "hostId", "type": "string"},
            {"name": "datum", "type": {"type": "record", "name": "Event", "fields": [
                {"name": "uuid", "type": "string"}, {"name": "type", "type": "string"},
                {"name": "timestampNanos", "type": "long"}]}}]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "raw"
            source.mkdir()
            raw = {"type": "RECORD_EVENT", "hostId": "h", "datum": {"uuid": "e", "type": "EVENT_OPEN", "timestampNanos": 1}}
            with gzip.open(source / "sample.gz", "wb") as stream:
                writer(stream, schema, [raw, raw])
            annotations = root / "annotations.json"
            annotations.write_text(json.dumps({"events": [{"event_uuid": "e", "host_uuid": "h", "timestamp_nanos": 1,
                "cdm_event_type": "EVENT_OPEN", "source_file": "sample.gz", "label": None}]}))
            manifest = prepare(source, annotations, root / "out", 2)
            self.assertEqual(manifest["sample_count"], 1)
            self.assertEqual(manifest["label_counts"], {"None": 1})
            self.assertTrue(manifest["files"][0]["complete_scan"])
            self.assertFalse((root / "out" / "splits").exists())
            with self.assertRaises(ValueError):
                prepare(source, annotations, root / "out", 2)

    def test_unknowns_cannot_create_splits(self):
        splits, reasons = make_splits([{"event_uuid": "a", "label": None}])
        self.assertIsNone(splits)
        self.assertTrue(reasons)

    def test_same_incident_cannot_be_split_by_different_group_ids(self):
        rows = [{"event_uuid": f"{g}-{label}", "group_id": str(g), "incident_id": "same-attack",
                 "timestamp_nanos": g * 100 + label, "label": label}
                for g in range(3) for label in (0, 1)]
        splits, reasons = make_splits(rows)
        self.assertIsNone(splits)
        self.assertIn("positive incident", reasons[0])

    def test_verified_fixture_exports_only_split_ids_to_requested_directory(self):
        schema = {"type": "record", "name": "CDM", "fields": [
            {"name": "type", "type": "string"}, {"name": "hostId", "type": "string"},
            {"name": "datum", "type": {"type": "record", "name": "Event", "fields": [
                {"name": "uuid", "type": "string"}, {"name": "type", "type": "string"},
                {"name": "timestampNanos", "type": "long"}]}}]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "raw"
            source.mkdir()
            rows, annotations = [], []
            for group in range(3):
                for label in (0, 1):
                    uid, timestamp = f"{group}-{label}", group * 100 + label
                    rows.append({"type": "RECORD_EVENT", "hostId": "h", "datum": {
                        "uuid": uid, "type": "EVENT_OPEN", "timestampNanos": timestamp}})
                    annotations.append({"event_uuid": uid, "host_uuid": "h", "timestamp_nanos": timestamp,
                        "cdm_event_type": "EVENT_OPEN", "source_file": "sample.gz", "label": label,
                        "group_id": str(group), "incident_id": str(group), "review_status": "verified", "evidence": "synthetic test fixture only"})
            with gzip.open(source / "sample.gz", "wb") as stream:
                writer(stream, schema, rows)
            annotation_path = root / "annotations.json"
            annotation_path.write_text(json.dumps({"events": annotations}))
            destination = root / "data" / "ml" / "splits"
            manifest = prepare(source, annotation_path, root / "run", 0, split_output=destination)
            self.assertEqual(manifest["status"], "split_ready")
            self.assertEqual({p.name for p in destination.iterdir()}, {"train.json", "validation.json", "test.json"})
            ids = [uid for p in destination.iterdir() for uid in json.loads(p.read_text())]
            self.assertEqual(set(ids), {row["datum"]["uuid"] for row in rows})
            self.assertEqual(len(ids), 6)
            with self.assertRaises(ValueError):
                prepare(source, annotation_path, root / "new-run", 0, split_output=destination)

    def test_groups_remain_whole_and_chronological(self):
        rows = [{"event_uuid": f"{g}-{label}", "group_id": str(g),
                 "timestamp_nanos": g * 100 + label, "label": label}
                for g in range(5) for label in (0, 1)]
        splits, reasons = make_splits(list(reversed(rows)))
        self.assertEqual(reasons, [])
        self.assertEqual([len(splits[n]) for n in ("train", "validation", "test")], [6, 2, 2])
        groups = [{r["group_id"] for r in splits[n]} for n in ("train", "validation", "test")]
        self.assertFalse(groups[0] & groups[1] | groups[1] & groups[2] | groups[0] & groups[2])
        self.assertIsNone(make_splits(rows, context_nanos=100)[0])

    def test_interleaved_groups_are_rejected(self):
        rows = [{"event_uuid": f"{g}-{label}", "group_id": str(g),
                 "timestamp_nanos": g + label * 100, "label": label}
                for g in range(3) for label in (0, 1)]
        self.assertIsNone(make_splits(rows)[0])

    def test_label_requires_evidence_and_exact_match(self):
        raw = {"hostId": b"h", "datum": {"uuid": b"e", "timestampNanos": 1, "type": "EVENT_OPEN"}}
        annotation = {"event_uuid": "65", "host_uuid": "68", "timestamp_nanos": 1,
                      "cdm_event_type": "EVENT_OPEN", "label": 1}
        with self.assertRaises(ValueError):
            reviewed_label(annotation, raw)
        annotation.update(review_status="verified", evidence="source", group_id="g")
        with self.assertRaises(ValueError):
            reviewed_label(annotation, raw)
        annotation["incident_id"] = "incident"
        self.assertEqual(reviewed_label(annotation, raw), 1)
        annotation["timestamp_nanos"] = 2
        with self.assertRaises(ValueError):
            reviewed_label(annotation, raw)

    def test_adapter_does_not_invent_file_or_process(self):
        raw = {"type": "RECORD_EVENT", "datum": {"uuid": b"e", "timestampNanos": 1,
               "type": "EVENT_OPEN", "predicateObjectPath": "registry-or-file"}}
        parsed = CDMReviewAdapter().parse(raw)
        self.assertEqual(parsed.action, "EVENT_OPEN")
        self.assertIsNone(parsed.file)
        self.assertIsNone(parsed.process)
        self.assertEqual(parsed.extra_fields["cdm"]["datum"]["timestampNanos"], 1)
        self.assertIsInstance(CDMReviewAdapter().parse({}), ParseError)


if __name__ == "__main__":
    unittest.main()
