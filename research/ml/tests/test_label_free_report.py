"""Reporting must preserve measured results and reject mixed evidence."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from research.ml.label_free.report import build_report

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT/'data/ml/datasets/darpa/label_free'
CONFIG = ROOT/'research/ml/label_free/training_config_cuda.json'


class ReportTests(unittest.TestCase):
    def test_published_evidence_reproduces_the_frozen_results_and_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'compiled'
            summary = build_report(REPORTS, CONFIG, output)
            self.assertEqual(summary['total_rows'], 1358)
            self.assertEqual(summary['architecture'], [62, 16, 4, 16, 62])
            self.assertEqual(summary['best_epoch'], 185)
            self.assertFalse(summary['attack_detection_metrics_available'])
            self.assertFalse(summary['original_supervised_task_complete'])
            self.assertIsNone(summary['security_threshold'])
            self.assertEqual(summary['results'][-1]['autoencoder']['mse'], 0.07237275689840317)
            self.assertIn('| holdout | 98 | 0.072372757 | 0.090199672 | 0.282537609 | 0.181020141 |',
                          (output/'results_table.md').read_text())

    def test_replaced_run_or_inconsistent_diagnostics_leave_no_report(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); reports = base/'inputs'; shutil.copytree(REPORTS, reports)
            run_path = reports/'gpu_training_report_20261029.json'; original = run_path.read_bytes()
            run = json.loads(original); run['best_epoch'] = 186
            run_path.write_text(json.dumps(run), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fingerprint mismatch'):
                build_report(reports, CONFIG, base/'mixed-run')
            self.assertFalse((base/'mixed-run').exists()); run_path.write_bytes(original)
            analysis_path = reports/'error_analysis_report_20261029.json'
            analysis = json.loads(analysis_path.read_text())
            analysis['partitions']['holdout']['aggregate_metrics']['mse'] = 0.5
            analysis_path.write_text(json.dumps(analysis), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Analysis metrics'):
                build_report(reports, CONFIG, base/'mixed-metrics')
            self.assertFalse((base/'mixed-metrics').exists())

    def test_unapproved_label_or_preprocessing_claim_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); reports = base/'inputs'; shutil.copytree(REPORTS, reports)
            path = reports/'error_analysis_report_20261029.json'; original = json.loads(path.read_text())
            for key in ('security_labels_assigned', 'preprocessing_refit', 'weights_updated'):
                changed = dict(original, **{key: True})
                path.write_text(json.dumps(changed), encoding='utf-8')
                with self.subTest(flag=key), self.assertRaisesRegex(ValueError, 'contract differs'):
                    build_report(reports, CONFIG, base/key)
                self.assertFalse((base/key).exists())


if __name__=='__main__':
    unittest.main()
