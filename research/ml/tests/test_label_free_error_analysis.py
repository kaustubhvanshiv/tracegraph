"""Post-evaluation diagnostics must preserve model, labels and source evidence."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from research.ml.label_free.error_analysis import analyze,profile_groups,quantile,summarize,witness_evidence
from research.ml.label_free.evaluate import evaluate
from research.ml.label_free.train import train
from research.ml.node_benchmark.audit_protocol import file_hash
from research.ml.tests import test_label_free_training as fixtures


class ErrorAnalysisTests(unittest.TestCase):
    def completed_fixture(self,base):
        directory,config=fixtures.LabelFreeTrainingTests().fixture(base)
        run=base/'full';train(directory,config,run,'full')
        evaluation=base/'final.json';evaluate(directory,run,evaluation)
        return directory,run,evaluation

    def test_linear_quantiles_are_descriptive_and_handle_singletons(self):
        self.assertEqual(quantile([4,1,3,2],.5),2.5)
        self.assertAlmostEqual(quantile([1,2,3,4],.95),3.85)
        self.assertEqual(quantile([7],.99),7)
        with self.assertRaises(ValueError):quantile([], .5)
        with self.assertRaises(ValueError):quantile([float('nan')],.5)

    def test_residual_decomposition_and_error_concentration_are_exact(self):
        result,mse,mae=summarize([[9,0],[1,0]],[[3,0],[1,0]],['a','b'])
        self.assertEqual(mse,[4.5,.5]);self.assertEqual(mae,[1.5,.5])
        self.assertEqual(result['sample_mse']['mean'],2.5)
        self.assertEqual(result['features'][0]['feature'],'a')
        self.assertEqual(result['features'][0]['squared_error_share'],1)
        self.assertEqual(result['largest_sample_error_shares']['1'],.9)
        zeros,_,_=summarize([[0,0]],[[0,0]],['a','b'])
        self.assertEqual(zeros['largest_sample_error_shares']['1'],0)
        with self.assertRaises(ValueError):summarize([[1,-1]],[[1,1]],['a','b'])
        with self.assertRaises(ValueError):summarize([[1]],[[1]],['a','b'])

    def test_exact_raw_profile_groups_do_not_assign_security_classes(self):
        from research.ml.label_free.error_analysis import profile_key
        rows=[dict(raw_features=[1,2]),dict(raw_features=[3,4])]
        groups=profile_groups(rows,[.1,.9],{profile_key(rows[0])})
        self.assertEqual(groups['exact_raw_profile_seen_in_training'],dict(rows=1,mean_mse=.1,median_mse=.1))
        self.assertEqual(groups['exact_raw_profile_unseen_in_training']['rows'],1)
        self.assertNotIn('security_label',groups)

    def test_review_witness_requires_native_actor_time_window_and_source_match(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,_,_=self.completed_fixture(base)
            row=json.loads((directory/'holdout.jsonl').read_text())
            windows=json.loads((directory/'manifest.json').read_text())['windows']
            with closing(sqlite3.connect((directory/'events.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
                evidence=witness_evidence(db,row['trace'],windows)
                self.assertEqual(len(evidence['raw_record_sha256']),64)
                trace=dict(row['trace'],subject_uuid='wrong-native-actor')
                with self.assertRaisesRegex(ValueError,'native Event index'):
                    witness_evidence(db,trace,windows)

    def test_completed_analysis_preserves_weights_and_records_only_unknown_review_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,run,evaluation=self.completed_fixture(base)
            checkpoint_sha=file_hash(run/'best.pt');index_sha=file_hash(directory/'events.sqlite')
            with patch('torch.optim.Adam',side_effect=AssertionError('Analysis must not instantiate an optimizer')):
                report=analyze(directory,run,evaluation,base/'analysis')
            self.assertEqual(report['status'],'frozen_post_evaluation_error_analysis_complete')
            self.assertEqual(report['partition_rows'],dict(train=2,development=1,holdout=1))
            self.assertEqual(report['review_queue_rows'],4)
            self.assertFalse(report['weights_updated'])
            self.assertFalse(report['preprocessing_refit'])
            self.assertIsNone(report['security_threshold'])
            self.assertEqual(file_hash(run/'best.pt'),checkpoint_sha)
            self.assertEqual(file_hash(directory/'events.sqlite'),index_sha)
            queue=[json.loads(line) for line in (base/'analysis/review_queue.jsonl').read_text().splitlines()]
            self.assertTrue(all(row['security_label'] is None and row['security_threshold'] is None for row in queue))
            self.assertTrue(all(row['witness']['record_index_1based']>0 for row in queue))

    def test_changed_final_metrics_or_run_binding_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,run,evaluation=self.completed_fixture(base)
            original=json.loads(evaluation.read_text())
            changed=dict(original,frozen_run_sha256_utf8_lf='0'*64)
            evaluation.write_text(json.dumps(changed),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'completed final evaluation'):
                analyze(directory,run,evaluation,base/'wrong-binding')
            original['reconstruction_metrics']['mse']+=1
            evaluation.write_text(json.dumps(original),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'frozen aggregate metrics'):
                analyze(directory,run,evaluation,base/'wrong-metric')
            self.assertFalse((base/'wrong-metric').exists())


if __name__=='__main__':
    unittest.main()
