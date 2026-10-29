"""Frozen offline scoring must preserve preprocessing, provenance and unknown intent."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from research.ml.label_free.evaluate import evaluate
from research.ml.label_free.inference import (
    FILES, export_bundle, load_bundle, normalize_row, read_json, replay_input, score, write_json,
)
from research.ml.label_free.train import train
from research.ml.node_benchmark.audit_protocol import file_hash
from research.ml.tests import test_label_free_training as fixtures


class OfflineInferenceTests(unittest.TestCase):
    def fixture(self, base):
        data, config = fixtures.LabelFreeTrainingTests().fixture(base)
        run = base/'full'; train(data, config, run, 'full')
        evaluation = base/'evaluation.json'; evaluate(data, run, evaluation)
        bundle = base/'bundle'
        export_bundle(data, run, evaluation, base/'plan.json', bundle)
        digest = file_hash(bundle/'bundle.json'); inputs = base/'input.jsonl'
        replay_input(data, bundle, 'holdout', inputs, digest)
        return data, run, bundle, digest, inputs

    def test_bundle_scores_without_training_folders_and_without_optimizer(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); data, run, bundle, digest, inputs = self.fixture(base)
            source_checkpoint = file_hash(run/'best.pt')
            data.rename(base/'unavailable-data'); run.rename(base/'unavailable-run')
            with patch('torch.optim.Adam', side_effect=AssertionError('Offline scoring must never train')):
                report = score(bundle, inputs, base/'scored', 'cpu', digest, batch_size=1)
            self.assertEqual(report['rows'], 1)
            self.assertEqual(report['model_parameter_device'], 'cpu')
            self.assertFalse(report['weights_updated']); self.assertFalse(report['preprocessing_refit'])
            self.assertFalse(report['security_labels_assigned']); self.assertIsNone(report['security_threshold'])
            self.assertFalse(report['native_source_evidence_reverified'])
            self.assertEqual(source_checkpoint, file_hash(bundle/'best.pt'))
            output = json.loads((base/'scored/scores.jsonl').read_text())
            self.assertIsNone(output['security_label']); self.assertIsNone(output['security_threshold'])
            _, model, baseline, _, names, scaler, plan, _ = load_bundle(bundle, 'cpu', digest)
            values = torch.tensor([normalize_row(json.loads(inputs.read_text()), names, scaler, plan)])
            with torch.inference_mode():
                self.assertAlmostEqual(output['reconstruction_mse'], ((model(values)-values)**2).mean().item())
                self.assertAlmostEqual(output['training_mean_baseline_mse'], ((baseline-values)**2).mean().item())

    def test_changed_artifacts_and_wrong_bundle_digest_rejected_before_weight_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, bundle, digest, _ = self.fixture(Path(folder))
            with patch('torch.load', side_effect=AssertionError('Reject fingerprint changes before torch.load')):
                with self.assertRaisesRegex(ValueError, 'trusted digest'):
                    load_bundle(bundle, 'cpu', '0'*64)
                for name in FILES:
                    original = (bundle/name).read_bytes(); (bundle/name).write_bytes(original+b' ')
                    with self.subTest(artifact=name), self.assertRaisesRegex(ValueError, 'artifact changed'):
                        load_bundle(bundle, 'cpu', digest)
                    (bundle/name).write_bytes(original)

    def test_changed_code_or_checkpoint_binding_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, bundle, _, _ = self.fixture(Path(folder))
            original = read_json(bundle/'bundle.json')
            changed = copy.deepcopy(original); changed['code_sha256_utf8_lf']['model.py'] = '0'*64
            write_json(bundle/'bundle.json', changed)
            with self.assertRaisesRegex(ValueError, 'Scoring source'):
                load_bundle(bundle, 'cpu', file_hash(bundle/'bundle.json'))
            run = read_json(bundle/'run.json'); run['checkpoint_sha256'] = '0'*64
            write_json(bundle/'run.json', run)
            changed = copy.deepcopy(original); changed['files_sha256']['run.json'] = file_hash(bundle/'run.json')
            write_json(bundle/'bundle.json', changed)
            with self.assertRaisesRegex(ValueError, 'provenance'):
                load_bundle(bundle, 'cpu', file_hash(bundle/'bundle.json'))

    def test_named_raw_features_restore_order_and_reject_unsafe_or_inconsistent_values(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, bundle, digest, inputs = self.fixture(Path(folder))
            _, _, _, _, names, scaler, plan, _ = load_bundle(bundle, 'cpu', digest)
            original = json.loads(inputs.read_text()); expected = normalize_row(original, names, scaler, plan)
            reordered = copy.deepcopy(original)
            reordered['raw_features'] = dict(reversed(list(original['raw_features'].items())))
            self.assertEqual(normalize_row(reordered, names, scaler, plan), expected)
            second_only = copy.deepcopy(original)
            second_only['raw_features']['second_predicate_event_count'] = 1
            self.assertEqual(len(normalize_row(second_only, names, scaler, plan)), len(names))
            changes = [dict(security_label=0), dict(host_uuid='wrong'), dict(window_nanos=11),
                       dict(sample_id=''), dict(features=[1]), dict(window_nanos=True)]
            for changeset in changes:
                with self.subTest(change=changeset), self.assertRaises(ValueError):
                    normalize_row(dict(original, **changeset), names, scaler, plan)
            raw_changes = [('event_count', -1), ('event_count', float('nan')), ('event_count', True),
                ('event_count', .5), ('event_count', 2**60), ('event_count', 5),
                ('predicate_reference_count', 5), ('active_span_seconds', plan['window_nanos']/1e9)]
            for name, value in raw_changes:
                changed = copy.deepcopy(original); changed['raw_features'][name] = value
                with self.subTest(feature=name, value=value), self.assertRaises(ValueError):
                    normalize_row(changed, names, scaler, plan)
            for missing in (True, False):
                changed = copy.deepcopy(original)
                if missing: changed['raw_features'].pop(names[0])
                else: changed['raw_features']['new_feature'] = 0
                with self.assertRaises(ValueError): normalize_row(changed, names, scaler, plan)

    def test_duplicate_empty_or_invalid_inputs_leave_no_success_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); _, _, bundle, digest, inputs = self.fixture(base)
            original = inputs.read_bytes()
            for index, invalid in enumerate((b'', original+original, b'{"sample_id":"bad"}\n')):
                inputs.write_bytes(invalid); output = base/str(index)
                with self.assertRaises((ValueError, KeyError)):
                    score(bundle, inputs, output, 'cpu', digest)
                self.assertFalse(output.exists())

    def test_replay_normalization_is_exact_and_partition_fingerprint_is_required(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); data, _, bundle, digest, _ = self.fixture(base)
            _, _, _, _, names, scaler, plan, _ = load_bundle(bundle, 'cpu', digest)
            replay_input(data, bundle, 'train', base/'train-input.jsonl', digest)
            raw_rows = [json.loads(line) for line in (data/'train.jsonl').read_text().splitlines()]
            rows = [json.loads(line) for line in (base/'train-input.jsonl').read_text().splitlines()]
            self.assertEqual([normalize_row(row, names, scaler, plan) for row in rows],
                             [row['features'] for row in raw_rows])
            (data/'train.jsonl').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'frozen preparation'):
                replay_input(data, bundle, 'train', base/'bad.jsonl', digest)
            self.assertFalse((base/'bad.jsonl').exists())

    def test_cuda_missing_fails_explicitly_and_runtime_release_is_pinned(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, bundle, digest, _ = self.fixture(Path(folder))
            with patch('torch.cuda.is_available', return_value=False):
                with self.assertRaisesRegex(ValueError, 'CUDA was requested'):
                    load_bundle(bundle, 'cuda', digest)
            changed = read_json(bundle/'bundle.json'); changed['required_torch_release'] = 'unsupported'
            write_json(bundle/'bundle.json', changed)
            with self.assertRaisesRegex(ValueError, 'PyTorch release'):
                load_bundle(bundle, 'cpu', file_hash(bundle/'bundle.json'))

    def test_inputs_and_model_changes_during_scoring_are_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); _, _, bundle, digest, inputs = self.fixture(base)
            original_load = load_bundle
            def changing_model(*args):
                loaded = original_load(*args); model = loaded[1]
                def change_weights(module, _args, _output):
                    with torch.no_grad(): next(module.parameters()).add_(1)
                model.register_forward_hook(change_weights)
                return loaded
            with patch('research.ml.label_free.inference.load_bundle', side_effect=changing_model):
                with self.assertRaisesRegex(ValueError, 'changed during scoring'):
                    score(bundle, inputs, base/'changed-model', 'cpu', digest)
            self.assertFalse((base/'changed-model').exists())
            def changing_input(*args):
                loaded = original_load(*args)
                def change_input(*_):
                    inputs.write_bytes(b'changed')
                loaded[1].register_forward_hook(change_input)
                return loaded
            with patch('research.ml.label_free.inference.load_bundle', side_effect=changing_input):
                with self.assertRaisesRegex(ValueError, 'changed during scoring'):
                    score(bundle, inputs, base/'changed-input', 'cpu', digest)
            self.assertFalse((base/'changed-input').exists())


if __name__ == '__main__':
    unittest.main()
