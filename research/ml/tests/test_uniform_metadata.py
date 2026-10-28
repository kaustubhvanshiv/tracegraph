"""Prove native recovery selects listed and unlisted identities identically."""
from contextlib import closing
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
from research.ml.node_benchmark.audit_protocol import audit, text_hash, validate_uniform_scope, universe_identity_hash
from research.ml.node_benchmark.uniform_metadata import (
    apply_types, create_spool, file_hash, freeze_universe, recover, scan_objects, store_batch,
)
from research.ml.tests.test_recover_metadata import SCHEMA, HOST, OTHER_HOST, TARGET, OTHER, ACTOR, raw


class UniformMetadataTests(unittest.TestCase):
    def make_graph(self, db):
        graph = GraphStore(db)
        a = graph.node(HOST,TARGET,'case',1)
        b = graph.node(HOST,OTHER,'case',1)
        db.execute("INSERT INTO published_nodes VALUES (?,?,?,?,?)",('case',TARGET,'RECORD_FILE_OBJECT','nodes.csv',1))
        graph.match_references()
        return graph,a,b

    def test_frozen_universe_ignores_membership_and_metadata(self):
        with closing(sqlite3.connect(':memory:')) as db:
            graph,a,b = self.make_graph(db)
            first = freeze_universe(db)
            graph.apply_metadata(b,'RECORD_FILE_OBJECT',{'type':'FILE_OBJECT_FILE'},'fixture')
            db.execute('DELETE FROM published_nodes')
            db.execute("INSERT INTO published_nodes VALUES (?,?,?,?,?)",('case',OTHER,'RECORD_FILE_OBJECT','different.csv',8))
            self.assertEqual(freeze_universe(db),first)
            self.assertEqual(set(first[0]),{(HOST,TARGET),(HOST,OTHER)})

    def test_single_and_multi_record_scans_recover_unlisted_and_check_full_positions(self):
        records = [raw('RECORD_FILE_OBJECT',OTHER),raw('RECORD_FILE_OBJECT',TARGET),
                   raw('RECORD_FILE_OBJECT',TARGET,OTHER_HOST)]
        for interval in (1,1_000_000):
            with self.subTest(interval=interval), tempfile.TemporaryDirectory() as folder, closing(sqlite3.connect(':memory:')) as db:
                graph,a,b = self.make_graph(db)
                targets,_,_ = freeze_universe(db)
                create_spool(db)
                path = Path(folder)/'source.gz'
                with gzip.open(path,'wb') as stream:
                    writer(stream,SCHEMA,records,sync_interval=interval)
                result = scan_objects(path,targets,db,3)
                self.assertEqual(result['matching_object_definitions'],2)
                evidence = db.execute('SELECT node_id,record_index,raw_sha256 FROM uniform_object_definitions ORDER BY record_index').fetchall()
                self.assertEqual([e[0] for e in evidence],[b,a])
                with gzip.open(path,'rb') as stream:
                    decoded = list(reader(stream))
                for node_id,index,fingerprint in evidence:
                    expected = hashlib.sha256(json.dumps(clean(decoded[index-1]),sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    self.assertEqual(fingerprint,expected)
                result = apply_types(db)
                self.assertEqual(result['newly_resolved_nodes'],2)
                labels = dict(db.execute('SELECT node_id,published_reference_label FROM node_reference_labels'))
                self.assertEqual(labels[a],1)
                self.assertIsNone(labels[b])

    def test_type_conflicts_apply_to_listed_and_unlisted_nodes(self):
        with closing(sqlite3.connect(':memory:')) as db:
            _,a,b = self.make_graph(db)
            create_spool(db)
            for node_id in (a,b):
                store_batch(db,[(node_id,'RECORD_FILE_OBJECT','FILE_OBJECT_FILE','a.gz',1,'x'),
                    (node_id,'RECORD_FILE_OBJECT','FILE_OBJECT_DIRECTORY','b.gz',2,'y')])
            result = apply_types(db)
            self.assertEqual(result['conflicting_object_nodes'],2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM nodes WHERE metadata_status='conflicting'").fetchone()[0],2)
            self.assertTrue(all(label is None for (label,) in db.execute('SELECT published_reference_label FROM node_reference_labels')))

    def test_truncated_or_incomplete_stream_never_counts_as_complete(self):
        with tempfile.TemporaryDirectory() as folder, closing(sqlite3.connect(':memory:')) as db:
            self.make_graph(db); targets,_,_ = freeze_universe(db); create_spool(db)
            path = Path(folder)/'source.gz'
            with gzip.open(path,'wb') as stream:
                writer(stream,SCHEMA,[raw('RECORD_FILE_OBJECT')],sync_interval=1)
            with self.assertRaisesRegex(ValueError,'record total'):
                scan_objects(path,targets,db,2)
            path.write_bytes(path.read_bytes()[:-5])
            with self.assertRaises((EOFError,OSError)):
                scan_objects(path,targets,db,1)

    def test_incorrect_universe_or_annotation_flag_cannot_clear_protocol_scope_gate(self):
        with closing(sqlite3.connect(':memory:')) as db:
            self.make_graph(db)
            digest,count = universe_identity_hash(db)
            valid = dict(status='complete_uniform_metadata_not_training_ready',
                scope='all_frozen_graph_nodes_without_reference_join',label_selection_used=False,
                universe_frozen_before_reference_join=True,universe_sha256=digest,universe_count=count,
                target_count=count,new_scans=[dict(complete_stream_read=True)],
                reused_complete_pilot_scans=[dict(complete_scan=True)])
            validate_uniform_scope(valid,db)
            for key,value in [('universe_sha256','wrong'),('label_selection_used',True),('universe_count',count-1),
                              ('status','complete_metadata_review_not_training_ready')]:
                with self.subTest(field=key), self.assertRaisesRegex(ValueError,'exact frozen graph universe'):
                    validate_uniform_scope({**valid,key:value},db)

    def test_end_to_end_starts_from_original_and_resolves_both_membership_classes(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder);source = base/'raw';source.mkdir();ref = base/'reference';ref.mkdir()
            items = []
            for name,records in [('ta1-fivedirections-1-e5-official-1.bin.gz',[raw('RECORD_FILE_OBJECT',ACTOR)]),
                                 ('ta1-fivedirections-1-e5-official-1.bin.1.gz',[raw('RECORD_FILE_OBJECT',TARGET),raw('RECORD_FILE_OBJECT',OTHER)])]:
                path = source/name
                with gzip.open(path,'wb') as stream:
                    writer(stream,SCHEMA,records,sync_interval=1)
                items.append(dict(filename=name,records=len(records),complete_scan=True,
                    compressed_bytes=path.stat().st_size,modified_time_ns=path.stat().st_mtime_ns,
                    record_type_counts={'RECORD_FILE_OBJECT':len(records)}))
            with closing(sqlite3.connect(ref/'references.sqlite')) as db:
                db.execute('CREATE TABLE entities(host TEXT,uuid TEXT,kind TEXT,filename TEXT)');db.commit()
            (ref/'reference_report.json').write_text(json.dumps(dict(all_files_fully_scanned=True,files=items)),encoding='utf-8')
            graph = base/'original.sqlite'
            with closing(sqlite3.connect(graph)) as db:
                self.make_graph(db);db.commit()
            before = file_hash(graph)
            pilot = base/'pilot.json'
            pilot.write_text(json.dumps(dict(status='complete_pilot_not_training_ready',database_sha256=before,scans=[items[0]])),encoding='utf-8')
            result = recover(source,graph,pilot,ref,base/'out',max_gib=0.02)
            self.assertEqual(file_hash(graph),before)
            self.assertEqual(result['newly_resolved_nodes'],2)
            self.assertEqual(result['universe_count'],2)
            self.assertFalse(result['label_selection_used'])
            self.assertEqual(result['status'],'complete_uniform_metadata_not_training_ready')
            self.assertEqual(result['reference_status_counts'],{'typed_uuid_match':1})
            self.assertEqual(result['zero_node_labels'],0)
            self.assertEqual(hashlib.sha256((base/'out/universe.jsonl').read_bytes()).hexdigest(),result['universe_sha256'])
            annotations = base/'annotations.json'
            annotations.write_text('{"events": []}\n',encoding='utf-8')
            gate = base/'event_gate.json'
            gate.write_text(json.dumps(dict(annotations_sha256=text_hash(annotations),status='blocked_for_training',
                eligible_label_counts={'1':3},eligible_label_group_counts={'0':0,'1':2})),encoding='utf-8')
            policy = Path(__file__).resolve().parents[3]/'data/ml/datasets/darpa/node_benchmark/preparation_protocol_v1_20261028.json'
            assessment = audit(policy,graph,base/'out/graph.sqlite',base/'out/manifest.json',gate,annotations)
            codes = {r['code'] for r in assessment['blocking_conditions']}
            self.assertNotIn('annotation_directed_metadata',codes)
            self.assertIn('binary_node_ground_truth_missing',codes)
            self.assertEqual(assessment['metadata_change_scope'],{'listed_nodes_changed':1,'unlisted_nodes_changed':1})
            self.assertFalse(assessment['partitions_created'])


if __name__ == '__main__':
    unittest.main()
