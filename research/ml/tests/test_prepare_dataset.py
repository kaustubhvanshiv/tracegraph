import unittest
import gzip
import json
from pathlib import Path
import tempfile
from fastavro import writer

from research.ml.data_prep.prepare_dataset import CDMReviewAdapter, make_splits, reviewed_label, prepare
from app.schemas.parser import ParseError


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
