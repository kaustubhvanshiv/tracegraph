"""Execution parity, integrity and cancellation checks for bounded GNN prefetch."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import torch
from research.ml.gnn_accel.prefetch import prefetched,batches,epoch
from research.ml.gnn_full.model import GraphReconstructor,sample,features
from research.ml.gnn_full.train import seed_for,setup,epoch as serial_epoch
from research.ml.node_benchmark.audit_protocol import file_hash


class PrefetchTests(unittest.TestCase):
    def test_execution_profile_rejects_changed_adapter_and_preserved_reports(self):
        from research.ml.gnn_accel.run import validate_profile,execution_code
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder);(work/'contract.json').write_text('{}')
            report=work/'runs/gcn/run.json';report.parent.mkdir(parents=True);report.write_text('{}')
            profile=dict(status='reviewed_bounded_cpu_prefetch_revision',execution_code_sha256_utf8_lf=execution_code(),
                original_contract_sha256=file_hash(work/'contract.json'),preserved_completed_reports={'gcn':file_hash(report)})
            (work/'execution_profile_prefetch.json').write_text(json.dumps(profile))
            validate_profile(work)
            with patch('research.ml.gnn_accel.run.execution_code',return_value={}):
                with self.assertRaisesRegex(ValueError,'adapter code changed'):validate_profile(work)
            report.write_text('{"modified":true}')
            with self.assertRaisesRegex(ValueError,'completed report changed'):validate_profile(work)

    @unittest.skipUnless(torch.cuda.is_available(),'CUDA orchestration check')
    def test_prefetch_runs_original_selection_reload_and_all_three_final_tests(self):
        from research.ml.tests.test_gnn_full import FullGNNTests
        with patch('research.ml.gnn_full.train.epoch',epoch):
            FullGNNTests().test_graph_preparation_and_three_model_loop_complete_before_final_test()

    def fixture(self,folder,n=777):
        work=Path(folder);rng=np.random.default_rng(9)
        raw=rng.integers(0,10,(n,7))
        indices=np.asarray([(i+j)%n for i in range(n) for j in range(1,14)])
        indptr=np.arange(n+1)*13
        np.savez(work/'graph.npz',raw=raw,indptr=indptr,indices=indices)
        entry=dict(file='graph.npz',sha256=file_hash(work/'graph.npz'))
        scaler=dict(means=[.2]*7,stds=[1.2]*7)
        return work,entry,scaler,raw,indptr,indices

    def test_batches_preserve_exact_sampling_mask_rng_features_and_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            work,entry,scaler,raw,indptr,indices=self.fixture(folder)
            for training in (False,True):
                rng=np.random.default_rng(seed_for(entry,42))
                seeds=rng.permutation(len(raw)) if training else np.arange(len(raw))
                expected=[]
                for start in range(0,len(seeds),256):
                    chosen=seeds[start:start+256];nodes,edge=sample(indptr,indices,chosen,rng)
                    mask=rng.random(len(nodes))<.2
                    if not training:mask[:len(chosen)]=True
                    elif not mask[:len(chosen)].any():mask[int(rng.integers(len(chosen)))]=True
                    expected.append((len(chosen),features(raw,nodes,scaler),edge,mask))
                with prefetched(batches([entry],work,scaler,42,training,pin=False)) as items:
                    actual=list(items)
                self.assertEqual(sum(b[0] for b in actual),len(raw))
                for (count,_,clean,edge,mask),(n,x,e,m) in zip(actual,expected):
                    self.assertEqual(count,n);self.assertTrue(torch.equal(clean,x))
                    np.testing.assert_array_equal(edge.numpy(),e);np.testing.assert_array_equal(mask.numpy(),m)

    def test_producer_failure_propagates_and_closes(self):
        closed=[]
        def items():
            try:
                yield 1
                raise ValueError('source integrity failure')
            finally:closed.append(True)
        with self.assertRaisesRegex(ValueError,'source integrity'):
            with prefetched(items()) as stream:list(stream)
        self.assertEqual(closed,[True])

    def test_early_consumer_exit_cancels_bounded_producer(self):
        closed=[]
        def items():
            try:
                for n in range(100000):yield n
            finally:closed.append(True)
        with prefetched(items()) as stream:self.assertEqual(next(stream),0)
        self.assertEqual(closed,[True])

    def test_modified_graph_is_rejected_before_and_after_iteration(self):
        with tempfile.TemporaryDirectory() as folder:
            work,entry,scaler,*_=self.fixture(folder)
            iterator=batches([entry],work,scaler,42,False,pin=False)
            next(iterator)
            with (work/'graph.npz').open('ab') as out:out.write(b'changed')
            with self.assertRaisesRegex(ValueError,'changed while scoring'):list(iterator)
            with prefetched(batches([entry],work,scaler,42,False,pin=False)) as stream:
                with self.assertRaisesRegex(ValueError,'fingerprint changed'):list(stream)

    @unittest.skipUnless(torch.cuda.is_available(),'CUDA parity check')
    def test_all_families_preserve_optimizer_updates_and_evaluation_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            work,entry,scaler,*_=self.fixture(folder,n=300)
            for family in ('gcn','graphsage','gat'):
                outcomes=[]
                for implementation in (serial_epoch,epoch):
                    setup(42);model=GraphReconstructor(family,7).cuda()
                    optimizer=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.0001)
                    training=implementation(model,[entry],work,scaler,43,optimizer)
                    evaluation=implementation(model,[entry],work,scaler,42)
                    outcomes.append((training,evaluation,{k:v.detach().cpu().clone() for k,v in model.state_dict().items()}))
                for index in (0,1):
                    for key in ('mse','mae','mean_reference_mse'):
                        self.assertAlmostEqual(outcomes[0][index][key],outcomes[1][index][key],places=5)
                    for key in ('seed_nodes_visited','target_node_count'):
                        self.assertEqual(outcomes[0][index][key],outcomes[1][index][key])
                for key in outcomes[0][2]:torch.testing.assert_close(outcomes[0][2][key],outcomes[1][2][key],rtol=1e-5,atol=1e-7)


if __name__=='__main__':unittest.main()
