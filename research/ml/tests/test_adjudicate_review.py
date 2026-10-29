"""Evidence-sufficiency decisions cannot turn unknown candidates into labels."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from research.ml.node_benchmark.adjudicate_review import adjudicate
from research.ml.node_benchmark.audit_protocol import file_hash, text_hash
from research.ml.node_benchmark.input_contract import history_bounds, validate_input_contract
from research.ml.node_benchmark.review_packets import build
from research.ml.tests import test_review_packets as packet_fixtures
from research.ml.tests.test_recover_metadata import HOST

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'data/ml/datasets/darpa/node_benchmark'


class EvidenceDecisionTests(unittest.TestCase):
    def spec(self):
        spec = json.loads((DATA / 'node_input_spec_20261029.json').read_text())
        spec['history_horizon_nanos'] = spec['purge_gap_minimum_nanos'] = 10
        return spec

    def fixture(self, base):
        args = packet_fixtures.ReviewPacketTests().fixture(base)
        packet_report = build(*args, base / 'packets')
        spec = base / 'spec.json'; spec.write_text(json.dumps(self.spec()), encoding='utf-8')
        policy = json.loads((DATA / 'preparation_protocol_v2_history_20261029.json').read_text())
        policy['split']['history_horizon_nanos'] = 10
        policy['split']['input_spec_sha256_utf8_lf'] = text_hash(spec)
        policy_path = base / 'policy.json'; policy_path.write_text(json.dumps(policy), encoding='utf-8')
        findings = dict(review_id='software-fixture', reviewer='fixture reviewer, not ground truth',
            classification_decision='retain_unknown_all_candidates', binary_intent_evidence_rows=[],
            source_absence_proves_no_attack=False, all_candidate_actions_certified_benign=False,
            training_authorized=False, packet_file_sha256=packet_report['packet_file_sha256'],
            reviewed_window=dict(host_uuid=HOST, start_nanos=10, end_nanos=20),
            source_files=[dict(path=str(args[-1]), hash_format='binary', sha256=file_hash(args[-1]))],
            findings=[dict(id='fixture_insufficient_evidence')])
        findings_path = base / 'findings.json'; findings_path.write_text(json.dumps(findings), encoding='utf-8')
        return base / 'packets/manifest.json', findings_path, policy_path, spec

    def test_past_only_integer_interval_fits_exactly_without_one_nanosecond_lookback(self):
        spec = self.spec()
        interval = history_bounds(dict(start_nanos=10, end_nanos=20), spec)
        self.assertEqual((interval['start_inclusive_nanos'], interval['end_exclusive_nanos'], interval['anchor_nanos']), (10, 20, 19))
        self.assertFalse(interval['continuous_coverage_proven'])
        with self.assertRaisesRegex(ValueError, 'cannot accommodate'):
            history_bounds(dict(start_nanos=11, end_nanos=20), spec)

    def test_future_input_or_short_purge_gap_is_rejected(self):
        for key, value in [('future_events_allowed', True), ('purge_gap_minimum_nanos', 9),
                           ('unknown_labels_used_for_supervised_training', True),
                           ('offline_metadata_proves_arrival_time_availability', True),
                           ('history_horizon_nanos', True)]:
            spec = self.spec(); spec[key] = value
            with self.subTest(rule=key), self.assertRaises(ValueError):
                history_bounds(dict(start_nanos=10, end_nanos=20), spec)

    def test_completed_source_review_remains_unknown_and_deterministic(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); args = self.fixture(base)
            first = adjudicate(*args, base / 'first'); second = adjudicate(*args, base / 'second')
            self.assertEqual(first['decision_file_sha256'], second['decision_file_sha256'])
            self.assertEqual(first['source_sufficiency_decisions'], 2)
            self.assertEqual((first['unknown_labels'], first['verified_binary_labels'], first['supervised_eligible']), (2, 0, 0))
            self.assertFalse(first['preparation_complete'])
            self.assertFalse(first['models_selected_or_trained'])
            decisions = [json.loads(line) for line in (base / 'first/review_decisions.jsonl').read_text().splitlines()]
            self.assertTrue(all(d['label'] is None and d['supervised_eligible'] is False for d in decisions))
            policy = json.loads(args[2].read_text())
            contract = validate_input_contract(policy, args[3], [dict(host_uuid=HOST, start_nanos=10, end_nanos=20)])
            self.assertFalse(contract['graph_inputs_created'])

    def test_benign_certification_or_binary_evidence_cannot_be_imported(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); args = self.fixture(base)
            original = json.loads(args[1].read_text())
            for key, value in [('all_candidate_actions_certified_benign', True),
                               ('binary_intent_evidence_rows', [dict(label=0)]), ('training_authorized', True)]:
                changed = copy.deepcopy(original); changed[key] = value
                args[1].write_text(json.dumps(changed), encoding='utf-8')
                with self.subTest(rule=key), self.assertRaisesRegex(ValueError, 'never manufacture'):
                    adjudicate(*args, base / 'unsafe')

    def test_changed_support_source_or_input_contract_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); args = self.fixture(base)
            findings = json.loads(args[1].read_text()); findings['source_files'][0]['sha256'] = '0' * 64
            args[1].write_text(json.dumps(findings), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'support source changed'):
                adjudicate(*args, base / 'source-changed')
            policy = json.loads(args[2].read_text()); policy['split']['input_spec_sha256_utf8_lf'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'policy differ'):
                validate_input_contract(policy, args[3], [])


if __name__ == '__main__':
    unittest.main()
