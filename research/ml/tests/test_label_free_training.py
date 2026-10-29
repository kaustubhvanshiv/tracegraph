"""Check reconstruction training, frozen inputs and separation of the holdout."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from research.ml.label_free.evaluate import evaluate
from research.ml.label_free.model import ActivityAutoencoder, baseline_metrics, state_digest
from research.ml.label_free.prepare import prepare
from research.ml.label_free.train import train
from research.ml.label_free.training_data import partition, snapshot, validate_config
from research.ml.label_free.verify import verify
from research.ml.node_benchmark.audit_protocol import file_hash, text_hash
from research.ml.tests import test_label_free as prep_fixtures

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT/'research/ml/label_free/training_config.json'


class LabelFreeTrainingTests(unittest.TestCase):
    def fixture(self, base):
        args = prep_fixtures.LabelFreeTests().fixture(base)
        directory = base/'prepared'
        prepare(*args,directory)
        verify(directory,args[1],directory/'verification.json')
        config = json.loads(CONFIG.read_text())
        config.update(input_dim=8,hidden_dim=4,latent_dim=2,max_epochs=4,smoke_epochs=2,patience=2,
            dataset_manifest_sha256_utf8_lf=text_hash(directory/'manifest.json'),
            dataset_verification_sha256_utf8_lf=text_hash(directory/'verification.json'))
        config_path = base/'training.json'
        config_path.write_text(json.dumps(config),encoding='utf-8')
        return directory,config_path

    def test_model_shape_parameter_count_and_finite_gradients(self):
        torch.manual_seed(42)
        model = ActivityAutoencoder()
        values = torch.randn(3,62)
        output = model(values)
        self.assertEqual(tuple(output.shape),(3,62))
        self.assertEqual(sum(p.numel() for p in model.parameters()),2210)
        (output-values).square().mean().backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))

    def test_invalid_or_supervised_config_is_rejected(self):
        original = json.loads(CONFIG.read_text())
        for key,value in [('security_labels_used',True),('holdout_used_for_training_or_readiness',True),
                ('learning_rate',float('nan')),('batch_size',0),('device','cuda'),('latent_dim',62)]:
            config = copy.deepcopy(original);config[key] = value
            with self.subTest(setting=key),self.assertRaises(ValueError):validate_config(config)

    def test_smoke_training_never_opens_holdout_and_reloads_selected_weights(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,config=self.fixture(base)
            original_open = Path.open
            def guarded(path,*args,**kwargs):
                if path.name=='holdout.jsonl':
                    raise AssertionError('Training attempted to open holdout vectors')
                return original_open(path,*args,**kwargs)
            with patch.object(Path,'open',guarded):
                report=train(directory,config,base/'smoke','smoke')
            self.assertEqual(report['status'],'smoke_passed_training_ready')
            self.assertTrue(report['optimizer_changed_weights'])
            self.assertTrue(report['checkpoint_reload_verified'])
            self.assertFalse(report['holdout_vectors_read'])
            self.assertIsNone(report['holdout_metrics'])
            self.assertFalse(report['full_training_completed'])
            history=[json.loads(line) for line in (base/'smoke/history.jsonl').read_text().splitlines()]
            expected=min(history,key=lambda item:item['development']['mse'])
            self.assertEqual(report['best_epoch'],expected['epoch'])
            self.assertAlmostEqual(report['selected_checkpoint_metrics']['development']['mse'],expected['development']['mse'])

    def test_same_cpu_seed_reproduces_history_and_weights(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,config=self.fixture(base)
            first=train(directory,config,base/'a','smoke')
            second=train(directory,config,base/'b','smoke')
            self.assertEqual(first['checkpoint_state_sha256'],second['checkpoint_state_sha256'])
            self.assertEqual((base/'a/history.jsonl').read_bytes(),(base/'b/history.jsonl').read_bytes())

    def test_mean_baseline_uses_training_mean_and_metrics_stay_finite(self):
        values=torch.tensor([[1.,2.],[3.,4.]])
        baseline=values.mean(dim=0)
        self.assertEqual(baseline_metrics(baseline,values),dict(mse=1.,mae=1.))
        with self.assertRaisesRegex(ValueError,'Nonfinite'):
            baseline_metrics(torch.zeros(2),torch.tensor([[1e30,1e30]]))

    def test_changed_partition_or_preprocessing_artifact_stops_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,config_path=self.fixture(base)
            config=json.loads(config_path.read_text());metadata=snapshot(directory,config)
            with (directory/'train.jsonl').open('ab') as stream:stream.write(b'\n')
            with self.assertRaisesRegex(ValueError,'fingerprint changed'):
                partition(directory,metadata,'train')
            with (directory/'scaler.json').open('ab') as stream:stream.write(b'\n')
            with self.assertRaisesRegex(ValueError,'preprocessing artifact changed'):
                snapshot(directory,config)

    def test_smoke_checkpoint_cannot_unlock_holdout_evaluation(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,config=self.fixture(base)
            train(directory,config,base/'smoke','smoke')
            with self.assertRaisesRegex(ValueError,'completed full run'):
                evaluate(directory,base/'smoke',base/'forbidden.json')
            self.assertFalse((base/'forbidden.json').exists())

    def test_loader_rejects_nonfinite_vectors_and_labels_even_with_updated_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,config_path=self.fixture(base)
            metadata=snapshot(directory,json.loads(config_path.read_text()))
            path=directory/'train.jsonl'
            original=[json.loads(line) for line in path.read_text().splitlines()]
            for change in ('label','nonfinite'):
                rows=copy.deepcopy(original)
                if change=='label':rows[0]['security_label']=0
                else:rows[0]['features'][0]=float('nan')
                path.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
                metadata['manifest']['partition_file_sha256']['train']=file_hash(path)
                with self.subTest(change=change),self.assertRaisesRegex(ValueError,'Invalid vectors'):
                    partition(directory,metadata,'train')

    def test_full_run_evaluator_preserves_weights_and_reports_only_reconstruction(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,config=self.fixture(base)
            training=train(directory,config,base/'full','full')
            before=file_hash(base/'full/best.pt')
            result=evaluate(directory,base/'full',base/'evaluation.json')
            self.assertEqual(before,file_hash(base/'full/best.pt'))
            self.assertEqual(result['status'],'final_label_free_reconstruction_evaluated')
            self.assertEqual(result['holdout_samples'],1)
            self.assertFalse(result['attack_detection_metrics_available'])
            self.assertFalse(result['weights_updated'])
            self.assertFalse(result['holdout_used_for_checkpoint_selection'])
            self.assertEqual(result['checkpoint_sha256'],training['checkpoint_sha256'])

    def test_changed_checkpoint_or_configuration_is_rejected_by_final_evaluator(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,config=self.fixture(base)
            train(directory,config,base/'full','full')
            weight_file=base/'full/best.pt';original=weight_file.read_bytes()
            weight_file.write_bytes(original+b'changed')
            with self.assertRaisesRegex(ValueError,'checkpoint fingerprint'):
                evaluate(directory,base/'full',base/'bad-weight.json')
            weight_file.write_bytes(original)
            with (base/'full/config.json').open('ab') as stream:stream.write(b'\n')
            with self.assertRaisesRegex(ValueError,'configuration changed'):
                evaluate(directory,base/'full',base/'bad-config.json')

    def test_failed_smoke_has_a_failed_report_and_is_not_training_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);directory,config=self.fixture(base)
            with patch('research.ml.label_free.train.reconstruction_metrics',side_effect=ValueError('nonfinite fixture')):
                with self.assertRaises(ValueError):train(directory,config,base/'failed','smoke')
            report=json.loads((base/'failed/run.json').read_text())
            self.assertEqual(report['status'],'incomplete_failed')
            self.assertFalse(report['full_training_completed'])


if __name__=='__main__':
    unittest.main()
