"""Denoising must preserve clean targets, constant columns and holdout separation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import torch
from research.ml.label_free.denoising_train import corrupt, train
from research.ml.tests.test_label_free_training import LabelFreeTrainingTests


class DenoisingTests(unittest.TestCase):
    def test_masking_is_repeatable_and_preserves_constants_and_clean_targets(self):
        values=torch.ones(20,8); original=values.clone()
        variable=torch.tensor([True]*4+[False]*4)
        a=corrupt(values,torch.Generator().manual_seed(42),variable,.2)
        b=corrupt(values,torch.Generator().manual_seed(42),variable,.2)
        self.assertTrue(torch.equal(a,b)); self.assertTrue(torch.equal(values,original))
        self.assertTrue(torch.equal(a[:,4:],values[:,4:])); self.assertTrue((a[:,:4]==0).any())

    def test_full_training_repeats_without_opening_holdout(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder); data,config=LabelFreeTrainingTests().fixture(base)
            settings=json.loads(config.read_text())
            settings.update(experiment_type='denoising_autoencoder',mask_probability=.2,
                mask_constant_columns=False,selection_input='clean_development',mask_seed=1051)
            config.write_text(json.dumps(settings),encoding='utf-8')
            original_open=Path.open
            def guarded(path,*args,**kwargs):
                if path.name=='holdout.jsonl': raise AssertionError('Holdout must not be opened')
                return original_open(path,*args,**kwargs)
            with patch.object(Path,'open',guarded):
                a=train(data,config,base/'a','full'); b=train(data,config,base/'b','full')
            self.assertEqual(a['checkpoint_state_sha256'],b['checkpoint_state_sha256'])
            self.assertEqual(a['history_sha256'],b['history_sha256'])
            self.assertFalse(a['holdout_vectors_read']); self.assertEqual(a['selection_input'],'clean_development')
            self.assertTrue(a['checkpoint_reload_verified'])
            history=[json.loads(line) for line in (base/'a/history.jsonl').read_text().splitlines()]
            self.assertIsNotNone(history[1]['masked_input_training_mse'])
            self.assertEqual(a['best_epoch'],min(history,key=lambda r:r['development']['mse'])['epoch'])


if __name__=='__main__': unittest.main()
