"""Unknown-label background triage must be bounded, deterministic and native."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from fastavro import writer

from research.ml.node_benchmark.background_review import build, candidate_pool, rank_candidates
from research.ml.node_benchmark.build_graphs import text_hash
from research.ml.data_prep.inspect_fivedirections import utc_nanos
from research.ml.tests.test_recover_metadata import SCHEMA, HOST, OTHER_HOST, TARGET, OTHER, ACTOR


class BackgroundReviewTests(unittest.TestCase):
    def setUp(self):
        self.window=dict(host_uuid=HOST,start_nanos=10,end_nanos=20)

    def event(self,ts=12,entity=TARGET):
        return dict(timestamp_nanos=ts,references=[(ACTOR,'subject'),(entity,'predicateObject')],
            source_file='source.gz',record_index=3,raw_sha256='fixture')

    def test_pool_uses_observed_ids_and_keeps_every_candidate_unknown(self):
        pool=candidate_pool({'event-b':self.event(14),'event-a':self.event(12)},self.window)
        self.assertEqual(set(pool),{ACTOR,TARGET})
        for row in pool.values():
            self.assertIsNone(row['label'])
            self.assertEqual(row['anchor_nanos'],19)
            self.assertEqual(row['witness_event_uuid'],'event-a')
            self.assertEqual((row['first_event_nanos'],row['last_event_nanos']),(12,14))

    def test_seeded_draw_is_order_independent_and_does_not_consult_labels(self):
        pool=candidate_pool({'a':self.event(entity=TARGET),'b':self.event(entity=OTHER)},self.window)
        first=rank_candidates(pool,self.window,42,2)
        reordered=dict(reversed(list(pool.items())))
        for row in reordered.values(): row['ignored_annotation']='listed'
        second=rank_candidates(reordered,self.window,42,2)
        self.assertEqual([(r['node_uuid'],r['selection_sha256']) for r in first],[(r['node_uuid'],r['selection_sha256']) for r in second])
        with self.assertRaises(ValueError): rank_candidates(pool,self.window,42,0)

    def test_complete_build_filters_host_and_half_open_time_and_reproduces_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'source';source.mkdir();ref=base/'ref';ref.mkdir();support=base/'support';support.mkdir()
            schema=copy.deepcopy(SCHEMA)
            schema['fields'][0]['type'][2]['fields'].append(dict(name='timestampNanos',type='long'))
            def native(uid,host,ts,target=TARGET):
                return dict(datum=('Event',dict(uuid=bytes.fromhex(uid),subject=bytes.fromhex(ACTOR),
                    predicateObject=bytes.fromhex(target),timestampNanos=ts)),type='RECORD_EVENT',hostId=bytes.fromhex(host))
            records=[native('0'*31+'6',HOST,12),native('0'*31+'7',OTHER_HOST,13),native('0'*31+'8',HOST,20),
                native('0'*31+'9',HOST,14,OTHER),native('0'*31+'9',HOST,15,OTHER)]
            path=source/'ta1-fivedirections-1-e5-official-1.bin.gz'
            with gzip.open(path,'wb') as stream: writer(stream,schema,records)
            (ref/'references.sqlite').write_bytes(b'fixture')
            item=dict(filename=path.name,records=5,complete_scan=True,compressed_bytes=path.stat().st_size,
                modified_time_ns=path.stat().st_mtime_ns,record_type_counts={'RECORD_EVENT':5},
                min_event_utc=utc_nanos(12),max_event_utc=utc_nanos(20))
            (ref/'reference_report.json').write_text(json.dumps(dict(all_files_fully_scanned=True,files=[item])),encoding='utf-8')
            payload=b'unchanged source fixture'
            with zipfile.ZipFile(support/'source.zip','w') as archive: archive.writestr('report.pdf',payload)
            (support/'ops.md').write_text('Operational fixture\n',encoding='utf-8')
            plan=dict(plan_id='fixture',source_reference_report_sha256_utf8_lf=text_hash(ref/'reference_report.json'),seed=42,limit=500,
                window=dict(window_id='a',host_uuid=HOST,file_prefix='ta1-fivedirections-1-',start_utc=utc_nanos(10),end_utc=utc_nanos(20)),
                candidate_label=None,sample_role='unknown_label_review_candidate_only',clock_review='fixture',coverage_contract='fixture',
                act_report=dict(archive='source.zip',member='report.pdf',sha256=hashlib.sha256(payload).hexdigest()),
                operational_log=dict(filename='ops.md',sha256_utf8_lf=text_hash(support/'ops.md')))
            planfile=base/'plan.json';planfile.write_text(json.dumps(plan),encoding='utf-8')
            first=build(source,planfile,ref,support,base/'first')
            second=build(source,planfile,ref,support,base/'second')
            self.assertEqual(first['raw_event_records_in_window'],3)
            self.assertEqual(first['unique_nonconflicting_events'],1)
            self.assertEqual(first['conflicting_event_uuids'],['0'*31+'9'])
            self.assertEqual(first['candidate_count'],2)
            self.assertEqual(first['unknown_candidate_labels'],2)
            self.assertEqual(first['verified_benign_labels'],0)
            self.assertEqual(first['candidate_file_sha256'],second['candidate_file_sha256'])
            self.assertEqual(first['universe_sha256'],second['universe_sha256'])
            rows=[json.loads(line) for line in (base/'first/review_candidates.jsonl').read_text().splitlines()]
            self.assertTrue(all(r['label'] is None for r in rows))
            plan['candidate_label']=0;planfile.write_text(json.dumps(plan),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'unknown, not benign'):
                build(source,planfile,ref,support,base/'unsafe')


if __name__=='__main__':
    unittest.main()
