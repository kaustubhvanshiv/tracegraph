"""Native evidence packets preserve unknown labels and source identity."""
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
from research.ml.node_benchmark.background_review import canonical, candidate_pool, rank_candidates
from research.ml.node_benchmark.build_graphs import GraphStore, text_hash
from research.ml.node_benchmark.audit_protocol import file_hash
from research.ml.node_benchmark.review_packets import (
    NativeDefinitions, actor_chain, build, read_frozen_pool, verified_witness, write_viewer,
)
from research.ml.tests.test_recover_metadata import SCHEMA, HOST, OTHER_HOST, TARGET, ACTOR, OTHER, raw


class ReviewPacketTests(unittest.TestCase):
    def native_event(self):
        return dict(type='RECORD_EVENT', hostId=bytes.fromhex(HOST), datum=dict(
            uuid=bytes.fromhex(OTHER), subject=bytes.fromhex(ACTOR),
            predicateObject=bytes.fromhex(TARGET), timestampNanos=12))

    def candidate(self):
        event = self.native_event()
        return dict(host_uuid=HOST, node_uuid=TARGET, witness_event_uuid=OTHER, witness_role='predicateObject',
            witness_raw_sha256=hashlib.sha256(canonical(clean(event))).hexdigest(),
            witness_source_file='source.gz', witness_record_index_1based=3, first_event_nanos=12)

    def database(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.execute('CREATE TABLE entities(uuid TEXT,kind TEXT,payload TEXT,filename TEXT,record_index INTEGER,host TEXT)')
        return db

    def test_witness_requires_host_uuid_native_role_time_and_fingerprint(self):
        event, candidate = self.native_event(), self.candidate()
        self.assertEqual(verified_witness(event, candidate, dict(start_nanos=10, end_nanos=20))['raw_record'], clean(event))
        for changed in (dict(hostId=bytes.fromhex(OTHER_HOST)), dict(type='RECORD_SUBJECT'),
                        dict(datum=dict(event['datum'], timestampNanos=20)),
                        dict(datum=dict(event['datum'], predicateObject=bytes.fromhex(ACTOR)))):
            with self.subTest(change=changed), self.assertRaisesRegex(ValueError, 'Native witness'):
                verified_witness(dict(event, **changed), candidate, dict(start_nanos=10, end_nanos=20))
        candidate['witness_raw_sha256'] = '0' * 64
        with self.assertRaises(ValueError): verified_witness(event, candidate, dict(start_nanos=10, end_nanos=20))

    def test_conflicting_full_payloads_stay_conflicting_and_host_scoped(self):
        definitions = NativeDefinitions(self.database())
        definitions.add_object(dict(type='RECORD_FILE_OBJECT', hostId=bytes.fromhex(OTHER_HOST),
                                    datum=dict(uuid=bytes.fromhex(TARGET), type='FILE_OBJECT_FILE')), 'x.gz', 1)
        self.assertEqual(definitions.get(HOST, TARGET)['status'], 'not_found_in_review_sources')
        first = dict(type='RECORD_FILE_OBJECT', hostId=bytes.fromhex(HOST),
                     datum=dict(uuid=bytes.fromhex(OTHER), type='FILE_OBJECT_FILE', permissions='a'))
        definitions.add_object(first, 'x.gz', 2)
        definitions.add_object(first, 'x.gz', 3)
        definitions.add_object(dict(first, datum=dict(first['datum'], permissions='b')), 'x.gz', 4)
        result = definitions.get(HOST, OTHER)
        self.assertEqual(result['status'], 'conflicting_payloads_in_review_sources')
        self.assertEqual(sorted(v['occurrences'] for v in result['variants']), [1, 2])

    def test_actor_chain_discloses_future_missing_cycle_and_offline_availability(self):
        db = self.database()
        def subject(uid, parent=None, start=8):
            payload = dict(uuid=uid, type='SUBJECT_PROCESS', startTimestampNanos=start, parentSubject=parent)
            db.execute('INSERT INTO entities VALUES (?,?,?,?,?,?)', (uid, 'RECORD_SUBJECT', json.dumps(payload), 'x.gz', 1, HOST))
        subject(ACTOR, start=15)
        context = actor_chain(NativeDefinitions(db), HOST, ACTOR, 12)
        self.assertEqual(context['status'], 'future_start_in_chain')
        self.assertFalse(context['nodes'][0]['definition']['arrival_time_availability_proven'])
        self.assertEqual(actor_chain(NativeDefinitions(db), OTHER_HOST, ACTOR, 12)['status'], 'unresolved_or_conflicting')
        subject(TARGET, parent=TARGET)
        self.assertEqual(actor_chain(NativeDefinitions(db), HOST, TARGET, 12)['status'], 'cycle')
        subject(OTHER, start=None)
        self.assertEqual(actor_chain(NativeDefinitions(db), HOST, OTHER, 12)['status'], 'missing_start_in_chain')

    def fixture(self, base):
        source, pool, ref = [base / name for name in ('source', 'pool', 'ref')]
        for path in (source, pool, ref): path.mkdir()
        schema = copy.deepcopy(SCHEMA)
        schema['fields'][0]['type'][0]['fields'].append(dict(name='startTimestampNanos', type='long'))
        schema['fields'][0]['type'][2]['fields'].append(dict(name='timestampNanos', type='long'))
        records = [raw('RECORD_FILE_OBJECT'),
            dict(type='RECORD_SUBJECT', hostId=bytes.fromhex(HOST), datum=('Subject', dict(
                uuid=bytes.fromhex(ACTOR), type='SUBJECT_PROCESS', startTimestampNanos=8))),
            dict(self.native_event(), datum=('Event', self.native_event()['datum']))]
        path = source / 'source.gz'
        with gzip.open(path, 'wb') as stream: writer(stream, schema, records)
        with gzip.open(path, 'rb') as stream: decoded = list(reader(stream))
        db = sqlite3.connect(ref / 'references.sqlite')
        db.execute('CREATE TABLE entities(uuid TEXT,kind TEXT,payload TEXT,filename TEXT,record_index INTEGER,host TEXT)')
        db.execute('INSERT INTO entities VALUES (?,?,?,?,?,?)', (ACTOR, 'RECORD_SUBJECT', json.dumps(clean(decoded[1]['datum'])), path.name, 2, HOST))
        db.commit(); db.close()
        item = dict(filename=path.name, records=3, complete_scan=True, compressed_bytes=path.stat().st_size,
            modified_time_ns=path.stat().st_mtime_ns, record_type_counts=dict(RECORD_FILE_OBJECT=1, RECORD_SUBJECT=1, RECORD_EVENT=1))
        (ref / 'reference_report.json').write_text(json.dumps(dict(all_files_fully_scanned=True, files=[item])), encoding='utf-8')
        window = dict(host_uuid=HOST, start_nanos=10, end_nanos=20)
        candidate_events = {OTHER: dict(timestamp_nanos=12, source_file=path.name, record_index=3,
            raw_sha256=hashlib.sha256(canonical(clean(decoded[2]))).hexdigest(), references=[(ACTOR, 'subject'), (TARGET, 'predicateObject')])}
        rows = candidate_pool(candidate_events, window)
        (pool / 'universe.jsonl').write_bytes(b''.join(canonical([HOST, uid, 19]) + b'\n' for uid in sorted(rows)))
        selected = rank_candidates(rows, window, 42, 500)
        (pool / 'review_candidates.jsonl').write_bytes(b''.join(canonical(row) + b'\n' for row in selected))
        plan = base / 'plan.json'
        plan.write_text(json.dumps(dict(seed=42, limit=500, candidate_label=None)), encoding='utf-8')
        manifest = dict(status='complete_unknown_label_review_pool', reference_membership_used=False,
            candidate_labels_assigned=False, frozen_before_reference_join=True, plan_sha256_utf8_lf=text_hash(plan),
            universe_sha256=file_hash(pool / 'universe.jsonl'), candidate_file_sha256=file_hash(pool / 'review_candidates.jsonl'),
            window=window, pool_node_count=2, candidate_count=2, seed=42, limit=500, scans=[item],
            source_reference_report_sha256_utf8_lf=text_hash(ref / 'reference_report.json'))
        (pool / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        graphpath = base / 'graph.sqlite'
        db = sqlite3.connect(graphpath)
        store = GraphStore(db)
        store.node(HOST, TARGET, 'case-a', 1)
        db.commit(); db.close()
        group = base / 'group.json'
        group.write_text(json.dumps(dict(status='accepted_conservative_single_holdout', graph_sha256=file_hash(graphpath), assignments={'case-a': 'joint'})), encoding='utf-8')
        annotations = base / 'annotations.json'
        annotations.write_text('{"events": []}\n', encoding='utf-8')
        return source, pool, plan, ref, graphpath, group, annotations

    def test_end_to_end_packets_are_deterministic_unknown_and_traceable(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            args = self.fixture(base)
            first = build(*args, base / 'first')
            second = build(*args, base / 'second')
            self.assertEqual(first['packet_file_sha256'], second['packet_file_sha256'])
            self.assertEqual(first['verified_candidate_witnesses'], 2)
            self.assertEqual(first['distinct_witness_events'], 1)
            self.assertEqual(first['candidates_overlapping_pilot'], 1)
            self.assertEqual(first['scans'][0]['records'], 3)
            self.assertEqual(first['new_verified_benign_labels'], 0)
            self.assertFalse(first['ready_for_training'])
            packets = [json.loads(line) for line in (base / 'first/packets.jsonl').read_text().splitlines()]
            self.assertTrue(all(p['label'] is None and p['candidate']['label'] is None for p in packets))
            self.assertEqual(first['node_definition_status_counts'], {'one_payload_in_review_sources': 2})
            self.assertEqual(first['witness_actor_chain_status_counts'], {'native_starts_at_or_before_witness': 2})
            with self.assertRaisesRegex(ValueError, 'fresh'): build(*args, base / 'first')

    def test_changed_frozen_labels_or_order_are_rejected_even_with_new_file_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            _, pool, plan, *_ = self.fixture(base)
            path = pool / 'review_candidates.jsonl'
            original = path.read_bytes()
            rows = [json.loads(line) for line in original.splitlines()]
            for altered in (list(reversed(rows)), [dict(rows[0], label=0), rows[1]]):
                path.write_bytes(b''.join(canonical(row) + b'\n' for row in altered))
                manifest = json.loads((pool / 'manifest.json').read_text())
                manifest['candidate_file_sha256'] = file_hash(path)
                (pool / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'Candidate labels, identity, ordering'):
                    read_frozen_pool(pool, plan)

    def test_viewer_renders_source_markup_as_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'review.html'
            packet = dict(candidate=dict(node_uuid='<script>bad()</script>'), pilot_overlap=[],
                node_definition=dict(status='unknown'), evidence='<img src=x onerror=bad()>')
            write_viewer(path, [packet])
            output = path.read_text(encoding='utf-8')
            self.assertNotIn('<script>', output)
            self.assertNotIn('<img', output)
            self.assertIn('&lt;script&gt;', output)
            self.assertIn("default-src 'none'", output)


if __name__ == '__main__':
    unittest.main()
