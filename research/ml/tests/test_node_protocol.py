"""Check that protocol review preserves partial labels and cannot export splits."""
from contextlib import closing
import copy
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from research.ml.node_benchmark.audit_protocol import audit, blockers, file_hash, profile, text_hash, validate_policy
from research.ml.node_benchmark.build_graphs import GraphStore

ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT/'data/ml/datasets/darpa/node_benchmark/preparation_protocol_v1_20261028.json'


class NodeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.original, self.review = self.base/'original.sqlite', self.base/'review.sqlite'
        with closing(sqlite3.connect(self.original)) as db:
            graph = GraphStore(db)
            db.executemany("INSERT INTO cases VALUES (?,?,?,?)", [('a','host-a',10,20),('b','host-b',30,40)])
            listed = graph.node('host-a','listed','a',1)
            unlisted = graph.node('host-a','unlisted','a',1)
            graph.node('host-b','other','b',1)
            graph.apply_metadata(unlisted,'RECORD_FILE_OBJECT',{'type':'FILE_OBJECT_FILE'},'fixture')
            db.execute("INSERT INTO published_nodes VALUES ('a','listed','RECORD_FILE_OBJECT','nodes.csv',1)")
            graph.match_references()
            db.commit()
        shutil.copyfile(self.original,self.review)
        with closing(sqlite3.connect(self.review)) as db:
            graph = GraphStore(db,initialize=False)
            graph.apply_metadata(listed,'RECORD_FILE_OBJECT',{'type':'FILE_OBJECT_FILE'},'recovered')
            db.execute('DELETE FROM reference_matches')
            graph.match_references()
            db.commit()
        self.recovery = self.base/'recovery.json'
        self.recovery.write_text(json.dumps(dict(status='complete_metadata_review_not_training_ready',
            input_graph_sha256=file_hash(self.original),database_sha256=file_hash(self.review),target_count=1)),encoding='utf-8')
        self.annotations = self.base/'annotations.json'
        self.annotations.write_text('{"events": []}\n',encoding='utf-8')
        self.gate = self.base/'gate.json'
        self.gate.write_text(json.dumps(dict(annotations_sha256=text_hash(self.annotations),status='blocked_for_training',
            eligible_label_counts={'1':3},eligible_label_group_counts={'0':0,'1':2})),encoding='utf-8')

    def run_audit(self):
        return audit(POLICY,self.original,self.review,self.recovery,self.gate,self.annotations)

    def test_real_file_audit_preserves_graphs_and_all_unlisted_labels(self):
        before = [file_hash(p) for p in (self.original,self.review)]
        result = self.run_audit()
        self.assertEqual([file_hash(p) for p in (self.original,self.review)],before)
        self.assertEqual(result['inventory']['reference_label_counts'],[[None,2],[1,1]])
        self.assertEqual(result['metadata_change_scope'],{'listed_nodes_changed':1,'unlisted_nodes_changed':0})
        self.assertEqual(len(result['blocking_conditions']),6)
        self.assertTrue(result['review_completed'])
        for flag in ('background_candidates_created','feature_vectors_created','partitions_created',
                     'models_selected_or_trained','training_authorized_by_this_audit'):
            self.assertIs(result[flag],False)

    def test_unknowns_and_group_safety_rules_cannot_be_silently_weakened(self):
        original = json.loads(POLICY.read_text(encoding='utf-8'))
        for section,key,value in [('label_contract','unlisted_is_benign',True),
                ('sampling','background_candidate_label',0),('split','random_row_splitting',True),
                ('execution','select_or_train_models',True),
                ('metadata','join_key',['native_entity_uuid']),('split','history_horizon_nanos',0)]:
            with self.subTest(rule=key):
                changed = copy.deepcopy(original)
                changed[section][key] = value
                with self.assertRaises(ValueError):
                    validate_policy(changed)

    def test_graph_fingerprint_mismatch_is_rejected(self):
        report = json.loads(self.recovery.read_text(encoding='utf-8'))
        report['database_sha256'] = '0'*64
        self.recovery.write_text(json.dumps(report),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'fingerprints'):
            self.run_audit()

    def test_changed_event_annotations_require_a_new_event_gate(self):
        self.annotations.write_text('{"events": [], "changed": true}\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Event labels changed'):
            self.run_audit()

    def test_shared_uuid_across_hosts_is_not_proof_of_group_independence(self):
        with closing(sqlite3.connect(self.review)) as db:
            graph = GraphStore(db,initialize=False)
            graph.node('host-b','listed','b',1)
            inventory = profile(db)
        self.assertEqual(inventory['exact_uuid_shared_across_cases'],1)
        self.assertEqual(inventory['case_group_upper_bound_before_campaign_review'],2)
        reasons = blockers(json.loads(POLICY.read_text()),inventory,{},dict(target_count=1))
        self.assertIn('campaign_group_review_missing',{r['code'] for r in reasons})
        self.assertIn('insufficient_whole_groups',{r['code'] for r in reasons})

    def test_known_reference_membership_does_not_supply_binary_node_ground_truth(self):
        result = self.run_audit()
        self.assertEqual(result['original_event_track_unchanged']['eligible_label_counts'],{'1':3})
        self.assertIn('binary_node_ground_truth_missing',{r['code'] for r in result['blocking_conditions']})

    def test_cli_returns_nonready_and_writes_only_a_diagnostic_report(self):
        output = self.base/'audit.json'
        completed = subprocess.run([sys.executable,'-m','research.ml.node_benchmark.audit_protocol',
            '--protocol',str(POLICY),'--original-graph',str(self.original),'--review-graph',str(self.review),
            '--recovery-report',str(self.recovery),'--event-gate',str(self.gate),
            '--annotations',str(self.annotations),'--output',str(output)],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(completed.returncode,2,completed.stderr)
        self.assertFalse(json.loads(output.read_text())['partitions_created'])
        self.assertFalse((self.base/'splits').exists())
        self.assertFalse((self.base/'features').exists())

    def test_frozen_history_requires_a_pinned_past_only_spec_for_every_window(self):
        policy = json.loads(POLICY.read_text(encoding='utf-8'))
        policy['split']['history_horizon_nanos'] = 10
        policy_path = self.base/'policy.json'
        policy_path.write_text(json.dumps(policy),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'sibling input-spec'):
            audit(policy_path,self.original,self.review,self.recovery,self.gate,self.annotations)
        spec = json.loads((POLICY.parent/'node_input_spec_20261029.json').read_text())
        spec['history_horizon_nanos'] = spec['purge_gap_minimum_nanos'] = 10
        spec_path = self.base/'spec.json'
        spec_path.write_text(json.dumps(spec),encoding='utf-8')
        policy['split']['input_spec_file'] = spec_path.name
        policy['split']['input_spec_sha256_utf8_lf'] = text_hash(spec_path)
        policy_path.write_text(json.dumps(policy),encoding='utf-8')
        result = audit(policy_path,self.original,self.review,self.recovery,self.gate,self.annotations)
        self.assertNotIn('history_horizon_not_frozen',{r['code'] for r in result['blocking_conditions']})
        self.assertEqual(len(result['input_history_review']['intervals']),2)
        self.assertFalse(result['training_authorized_by_this_audit'])
        spec['future_events_allowed'] = True
        spec_path.write_text(json.dumps(spec),encoding='utf-8')
        policy['split']['input_spec_sha256_utf8_lf'] = text_hash(spec_path)
        policy_path.write_text(json.dumps(policy),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'past-only'):
            audit(policy_path,self.original,self.review,self.recovery,self.gate,self.annotations)


if __name__ == '__main__':
    unittest.main()
