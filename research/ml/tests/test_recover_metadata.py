"""Check native UUID recovery against ordinary Avro decoding and graph labels."""
from contextlib import closing
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastavro import reader, writer

from research.ml.data_prep.resolve_references import clean
from research.ml.node_benchmark.build_graphs import GraphStore
from research.ml.node_benchmark.recover_metadata import (
    apply_definitions, definition_prefixes, file_hash, recover, scan_archive,
)


HOST, OTHER_HOST, TARGET, ACTOR, OTHER = [f"{i:032x}" for i in range(1, 6)]
SCHEMA = {"type": "record", "name": "NativeFixture", "fields": [
    {"name": "datum", "type": [
        {"type": "record", "name": "Subject", "fields": [
            {"name": "uuid", "type": {"type": "fixed", "name": "UUID", "size": 16}},
            {"name": "type", "type": "string"}]},
        {"type": "record", "name": "FileObject", "fields": [
            {"name": "uuid", "type": "UUID"}, {"name": "type", "type": "string"}]},
        {"type": "record", "name": "Event", "fields": [
            {"name": "uuid", "type": "UUID"}, {"name": "subject", "type": "UUID"},
            {"name": "predicateObject", "type": "UUID"}]}]},
    {"name": "type", "type": "string"}, {"name": "hostId", "type": "UUID"}]}


def raw(kind, uid=TARGET, host=HOST, subtype="FILE_OBJECT_FILE"):
    datum = {"uuid": bytes.fromhex(uid), "type": subtype}
    return {"datum": ("FileObject", datum), "type": kind, "hostId": bytes.fromhex(host)}


class MetadataRecoveryTests(unittest.TestCase):
    def fixture(self, folder, records, interval, name="sample.gz"):
        path = Path(folder)/name
        with gzip.open(path, "wb") as stream:
            writer(stream, SCHEMA, records, sync_interval=interval)
        return path

    def test_single_and_multi_record_filters_equal_full_decode_with_exact_positions(self):
        records = [raw("RECORD_FILE_OBJECT", OTHER), raw("RECORD_FILE_OBJECT"),
            {"datum": ("Event", {"uuid": bytes.fromhex(OTHER), "subject": bytes.fromhex(ACTOR),
                                "predicateObject": bytes.fromhex(TARGET)}),
             "type": "RECORD_EVENT", "hostId": bytes.fromhex(HOST)},
            raw("RECORD_FILE_OBJECT", host=OTHER_HOST), raw("RECORD_FILE_OBJECT")]
        for interval in (1, 1_000_000):
            with self.subTest(sync_interval=interval), tempfile.TemporaryDirectory() as folder:
                path = self.fixture(folder, records, interval)
                result = scan_archive(path, [(HOST, TARGET)], len(records))
                self.assertEqual([h["record_index"] for h in result["definitions"]], [2, 5])
                with gzip.open(path, "rb") as stream:
                    decoded = list(reader(stream))
                for hit in result["definitions"]:
                    fingerprint = hashlib.sha256(json.dumps(clean(decoded[hit["record_index"]-1]),
                        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    self.assertEqual(hit["raw_sha256"], fingerprint)
                self.assertEqual(result["records"], len(records))
                self.assertTrue(result["complete_stream_read"])
                if interval == 1:
                    self.assertEqual(result["decoded_records"], 3)  # Includes rejected wrong-host definition.

    def test_unsupported_uuid_layout_fails_before_negative_results(self):
        bad = copy.deepcopy(SCHEMA)
        bad["fields"][0]["type"][0]["fields"][0]["type"]["size"] = 8
        with self.assertRaisesRegex(ValueError, "Unsupported native UUID"):
            definition_prefixes(bad, {bytes.fromhex(TARGET)})

    def test_incomplete_record_count_or_gzip_stream_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.fixture(folder, [raw("RECORD_FILE_OBJECT")], 1)
            with self.assertRaisesRegex(ValueError, "record count"):
                scan_archive(path, [(HOST, TARGET)], 2)
            path.write_bytes(path.read_bytes()[:-5])
            with self.assertRaises((EOFError, OSError)):
                scan_archive(path, [(HOST, TARGET)], 1)

    def test_recovery_changes_only_exact_native_types_and_keeps_other_labels_unknown(self):
        with closing(sqlite3.connect(":memory:")) as db:
            graph = GraphStore(db)
            targets = []
            for uid in (TARGET, OTHER, ACTOR):
                nid = graph.node(HOST, uid, "case", 1)
                db.execute("INSERT INTO published_nodes VALUES (?,?,?,?,?)", ("case", uid, "RECORD_FILE_OBJECT", "nodes.csv", 1))
                targets.append(dict(case_id="case", node_id=nid, host_uuid=HOST, uuid=uid,
                                    expected_kind="RECORD_FILE_OBJECT"))
            wrong_host = graph.node(OTHER_HOST, TARGET)
            native = lambda uid, kind, subtype, index: dict(host_uuid=HOST, uuid=uid, kind=kind,
                subtype=subtype, filename="sample.gz", record_index=index, raw_sha256="fixture",
                datum={"type": subtype})
            hits = [native(TARGET, "RECORD_FILE_OBJECT", "FILE_OBJECT_FILE", 1),
                    native(OTHER, "RECORD_MEMORY_OBJECT", None, 2)]
            result = apply_definitions(db, targets, hits)
            self.assertEqual([r["outcome"] for r in result], ["typed_uuid_match", "native_type_mismatch",
                             "no_native_definition_in_reviewed_local_sources"])
            labels = dict(db.execute("SELECT node_id,published_reference_label FROM node_reference_labels"))
            self.assertEqual(labels[targets[0]["node_id"]], 1)
            self.assertIsNone(labels[targets[1]["node_id"]])
            self.assertIsNone(labels[targets[2]["node_id"]])
            self.assertEqual(db.execute("SELECT metadata_status FROM nodes WHERE id=?", (wrong_host,)).fetchone()[0], "unresolved")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)
            self.assertNotIn(0, labels.values())

    def test_conflicting_native_type_definitions_are_preserved_and_withheld(self):
        with closing(sqlite3.connect(":memory:")) as db:
            graph = GraphStore(db)
            nid = graph.node(HOST, TARGET, "case", 1)
            db.execute("INSERT INTO published_nodes VALUES (?,?,?,?,?)", ("case", TARGET, "RECORD_FILE_OBJECT", "nodes.csv", 1))
            target = dict(case_id="case", node_id=nid, host_uuid=HOST, uuid=TARGET, expected_kind="RECORD_FILE_OBJECT")
            hits = [dict(host_uuid=HOST, uuid=TARGET, kind="RECORD_FILE_OBJECT", subtype=subtype,
                         filename="sample.gz", record_index=i, raw_sha256="fixture", datum={"type": subtype})
                    for i, subtype in enumerate(("FILE_OBJECT_FILE", "FILE_OBJECT_DIRECTORY"), 1)]
            result = apply_definitions(db, [target], hits)
            self.assertEqual(result[0]["outcome"], "conflicting_native_types")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM metadata_recovery_evidence").fetchone()[0], 2)
            self.assertIsNone(db.execute("SELECT published_reference_label FROM node_reference_labels").fetchone()[0])

    def test_end_to_end_recovery_preserves_input_and_adds_only_native_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base/"source"; source.mkdir()
            reference = base/"reference"; reference.mkdir()
            items = []
            for name, uid in [("ta1-fivedirections-1-e5-official-1.bin.gz", OTHER),
                              ("ta1-fivedirections-1-e5-official-1.bin.1.gz", TARGET)]:
                path = self.fixture(source, [raw("RECORD_FILE_OBJECT", uid)], 1, name)
                items.append(dict(filename=name, records=1, complete_scan=True,
                    compressed_bytes=path.stat().st_size, modified_time_ns=path.stat().st_mtime_ns,
                    record_type_counts={"RECORD_FILE_OBJECT": 1}))
            with closing(sqlite3.connect(reference/"references.sqlite")) as db:
                db.execute("CREATE TABLE entities(uuid TEXT,host TEXT,kind TEXT,filename TEXT)")
                db.commit()
            (reference/"reference_report.json").write_text(json.dumps({
                "all_files_fully_scanned": True, "files": items}), encoding="utf-8")
            graph_file = base/"graph.sqlite"
            with closing(sqlite3.connect(graph_file)) as db:
                graph = GraphStore(db)
                graph.node(HOST, TARGET, "case", 1)
                graph.node(HOST, OTHER, "case", 1)
                db.execute("INSERT INTO published_nodes VALUES (?,?,?,?,?)", ("case", TARGET,
                    "RECORD_FILE_OBJECT", "reference.csv", 1))
                graph.match_references()
                db.commit()
            original_hash = file_hash(graph_file)
            pilot_file = base/"pilot.json"
            pilot_file.write_text(json.dumps(dict(status="complete_pilot_not_training_ready",
                database_sha256=original_hash, scans=[items[0]])), encoding="utf-8")
            report = recover(source, graph_file, pilot_file, reference, base/"result")
            self.assertEqual(file_hash(graph_file), original_hash)
            self.assertEqual(report["outcome_counts"], {"typed_uuid_match": 1})
            self.assertEqual(report["new_records_streamed"], 1)
            self.assertFalse(report["ready_for_training"])
            with closing(sqlite3.connect(base/"result/graph.sqlite")) as db:
                labels = [r[0] for r in db.execute("SELECT published_reference_label FROM node_reference_labels")]
                self.assertEqual(labels, [1, None])
                self.assertEqual(db.execute("SELECT COUNT(*) FROM metadata_recovery_evidence").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
