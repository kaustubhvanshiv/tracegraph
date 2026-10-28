"""Verify review manifests cannot manufacture normal labels or independence."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from research.ml.node_benchmark.audit_protocol import validate_review_inputs
from research.ml.node_benchmark.background_review import candidate_pool,canonical,rank_candidates
from research.ml.node_benchmark.build_graphs import GraphStore
from research.ml.tests.test_recover_metadata import HOST,OTHER_HOST,TARGET,ACTOR


class ReviewInputTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        graph=GraphStore(self.db);graph.node(HOST,TARGET,'a',1)
        self.inventory=dict(cases=[dict(case_id='a',host_uuid=HOST,start_nanos=100,end_nanos=200),
            dict(case_id='b',host_uuid=OTHER_HOST,start_nanos=300,end_nanos=400)])
        self.window=dict(host_uuid=HOST,start_nanos=10,end_nanos=20)
        events={'e':dict(timestamp_nanos=12,references=[(ACTOR,'subject'),(TARGET,'predicateObject')],
            source_file='source.gz',record_index=3,raw_sha256='fixture')}
        pool=candidate_pool(events,self.window)
        identities=sorted([[r['host_uuid'],r['node_uuid'],r['anchor_nanos']] for r in pool.values()])
        (self.base/'universe.jsonl').write_bytes(b''.join(canonical(row)+b'\n' for row in identities))
        self.rows=rank_candidates(pool,self.window,42,500)
        self.background_path=self.base/'background.json';self.group_path=self.base/'group.json'
        self.background=dict(status='complete_unknown_label_review_pool',reference_membership_used=False,
            frozen_before_reference_join=True,verified_benign_labels=0,plan_sha256_utf8_lf='plan',
            source_reference_report_sha256_utf8_lf='source',seed=42,limit=500,scans=[dict(complete_scan=True)],
            support_sources=dict(act_pdf_sha256='pdf',operational_log_sha256_utf8_lf='ops'),window=self.window,
            universe_sha256=hashlib.sha256((self.base/'universe.jsonl').read_bytes()).hexdigest(),
            pool_node_count=2,candidate_count=2,unknown_candidate_labels=2)
        self.group=dict(status='accepted_conservative_single_holdout',assignments={'a':'holdout','b':'holdout'},
            independence_claim=False,common_actor_or_campaign_claim=False,graph_sha256='graph',
            sources=dict(act_report_sha256='pdf',operational_log_sha256_utf8_lf='ops'))
        policyfile=Path(__file__).resolve().parents[3]/'data/ml/datasets/darpa/node_benchmark/preparation_protocol_v2_20261028.json'
        self.policy=json.loads(policyfile.read_text())
        self.policy['sampling']['review_pool_plan_sha256_utf8_lf']='plan'
        self.save()

    def save(self):
        candidates=self.base/'review_candidates.jsonl'
        candidates.write_bytes(b''.join(canonical(row)+b'\n' for row in self.rows))
        self.background['candidate_file_sha256']=hashlib.sha256(candidates.read_bytes()).hexdigest()
        self.background_path.write_text(json.dumps(self.background),encoding='utf-8')
        self.group_path.write_text(json.dumps(self.group),encoding='utf-8')

    def check(self):
        return validate_review_inputs(self.policy,self.db,self.inventory,
            dict(reference_report_sha256_utf8_lf='source'),'graph',self.background_path,self.group_path)

    def test_conservative_group_and_seeded_unknown_pool_are_accepted_with_overlap_disclosed(self):
        result=self.check()
        self.assertEqual(self.inventory['evaluation_group_count'],1)
        self.assertEqual(result['background_review_pool']['candidate_identity_overlap_with_current_pilot'],1)
        self.assertFalse(result['background_review_pool']['accepted_training_background'])
        self.assertFalse(result['group_review']['independence_claim'])

    def test_fabricated_benign_candidate_is_rejected_even_with_updated_file_digest(self):
        self.rows[0]['label']=0;self.save()
        with self.assertRaisesRegex(ValueError,'unknown-label draw'):self.check()

    def test_changed_seeded_draw_is_rejected_even_with_updated_file_digest(self):
        self.rows.reverse();self.save()
        with self.assertRaisesRegex(ValueError,'unknown-label draw'):self.check()

    def test_uncovered_case_or_claimed_independence_cannot_clear_group_review(self):
        self.group['assignments']['b']='different';self.save()
        with self.assertRaisesRegex(ValueError,'conservatively cover'):self.check()
        self.group['assignments']['b']='holdout';self.group['independence_claim']=True;self.save()
        with self.assertRaisesRegex(ValueError,'conservatively cover'):self.check()


if __name__=='__main__':
    unittest.main()
