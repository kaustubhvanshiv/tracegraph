"""Software-only fixtures test frozen inference contracts; no training results."""
import copy
import csv
import io
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import numpy as np
import torch
from research.ml.gnn_full.model import GraphReconstructor,features,sample
from research.ml.gnn_scoring.artifacts import (KIND,ROOT,WIDTH,export_bundle,load_bundle,names_for,
    read,write,validate_metadata)
from research.ml.gnn_scoring.inputs import export_inputs,input_manifest,load_graph
from research.ml.gnn_scoring.score import score,prefetched
from research.ml.gnn_scoring import score as scoring_module
from research.ml.label_free.model import state_digest
from research.ml.node_benchmark.audit_protocol import file_hash,text_hash
from research.ml.gnn_results.verify_scoring import checked_summary,row_values


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.work=self.root/'software_fixture';self.work.mkdir()
        self.directory=self.work/'runs/graphsage';self.directory.mkdir(parents=True)
        self.config=dict(task='self_supervised_masked_node_feature_reconstruction',security_labels_used=False,
            hidden_dim=64,latent_dim=32,batch_size=256,fanouts=[10,5],seed=42,training_mask_probability=.2,
            action_vocabulary=[f'A{i:02}' for i in range(56)])
        self.scaler=dict(transform='log1p_training_population_zscore',fitted_on='train_only',node_windows=11,
            means=[.1]*WIDTH,stds=[1.]*WIDTH)
        write(self.work/'scaler.json',self.scaler)
        torch.manual_seed(7);self.model=GraphReconstructor('graphsage',WIDTH)
        self.graph=self.make_graph(300)
        metadata=dict(feature_names=names_for(self.config),graphs=[self.graph])
        write(self.work/'graphs.json',metadata)
        saved=dict(family='graphsage',feature_count=WIDTH,epoch=5,config=self.config,
            graph_manifest_sha256=file_hash(self.work/'graphs.json'),scaler_sha256=file_hash(self.work/'scaler.json'),
            state_dict=self.model.state_dict())
        torch.save(saved,self.directory/'best.pt')
        run=dict(status='gnn_training_complete_test_not_read',family='graphsage',epochs_completed=5,best_epoch=5,
            config=self.config,checkpoint_sha256=file_hash(self.directory/'best.pt'),checkpoint_state_sha256=state_digest(self.model),
            graph_manifest_sha256=saved['graph_manifest_sha256'],scaler_sha256=saved['scaler_sha256'],parameter_count=22707,
            security_threshold=None,attack_detection_metrics_available=False,
            code_sha256_utf8_lf={'model.py':text_hash(ROOT/'research/ml/gnn_full/model.py')})
        test=dict(status='frozen_gnn_feature_reconstruction_test_complete',checkpoint_sha256=run['checkpoint_sha256'],
            security_threshold=None,attack_detection_metrics_available=False,metrics={'software_fixture':True})
        write(self.directory/'run.json',run);write(self.directory/'test.json',test)
        write(self.work/'complete.json',dict(status='all_three_full_local_gnn_experiments_complete',
            models={'graphsage':{'final_reconstruction_test':test['metrics']}}))
        verification=dict(status='completed_full_local_gnn_artifacts_verified',complete_sha256=file_hash(self.work/'complete.json'),
            graph_manifest_sha256=saved['graph_manifest_sha256'],scaler_sha256=saved['scaler_sha256'],
            partitions={'train':{'node_windows':11}},models={'graphsage':dict(checkpoint_sha256=run['checkpoint_sha256'],
            run_sha256=file_hash(self.directory/'run.json'),test_sha256=file_hash(self.directory/'test.json'))})
        self.verification=self.root/'verification.json';write(self.verification,verification)
        self.bundle=self.root/'bundle';self.digest=export_bundle(self.work,self.verification,self.bundle)['bundle_sha256']
        self.inputs=self.root/'inputs'
        export_inputs(self.work,self.bundle,self.digest,'test',self.inputs)
        self.manifest=self.inputs/'input.json'

    def make_graph(self,n):
        host='1'*32;window=1557461700000000000;key=f'graphs/{host}_{window}.npz'
        path=self.work/key;path.parent.mkdir(exist_ok=True)
        nodes=np.array([i.to_bytes(16,'big') for i in range(1,n+1)],dtype='V16')
        raw=np.zeros((n,WIDTH),dtype=np.uint32);raw[:,0]=1;raw[:,57]=1
        # Sorted symmetric ring, degree two, counts represent one Event per edge.
        neighbors=[sorted([(i-1)%n,(i+1)%n]) for i in range(n)]
        indptr=np.arange(0,2*n+1,2,dtype=np.int64);indices=np.array(neighbors,dtype=np.int32).ravel()
        np.savez_compressed(path,nodes=nodes,raw=raw,indptr=indptr,indices=indices)
        return dict(file=key,sha256=file_hash(path),host=host,window_start_nanos=window,role='test',
            nodes=n,adjacency_edges=2*n,native_events=n)

    def input(self):return read(self.manifest)

    def array_change(self,change):
        entry=self.input()['graphs'][0];path=self.inputs/entry['file']
        with np.load(path) as a:arrays={k:a[k] for k in a.files}
        change(arrays);np.savez_compressed(path,**arrays);entry['sha256']=file_hash(path)
        return path,entry

    def test_offline_cpu_inference_covers_every_node_without_optimizer_or_source_folder(self):
        source_hash=file_hash(self.directory/'best.pt');self.work.rename(self.root/'hidden_original_source')
        with patch('torch.optim.Adam',side_effect=AssertionError('Training is forbidden')):
            report=score(self.bundle,self.manifest,self.root/'cpu','cpu',self.digest)
        self.assertEqual(report['metrics']['target_node_count'],300)
        self.assertFalse(report['weights_updated']);self.assertFalse(report['scaler_refit'])
        self.assertIsNone(report['security_threshold']);self.assertFalse(report['attack_detection_metrics_available'])
        with (self.root/'cpu/scores.csv').open(newline='') as stream:rows=list(csv.DictReader(stream))
        self.assertEqual([int(r['node_index']) for r in rows],list(range(300)))
        self.assertEqual(len({r['node_uuid'] for r in rows}),300)
        self.assertTrue(all(r['security_label']==r['security_threshold']=='' for r in rows))
        # Independent direct CPU forward with the frozen all-seed mask, two batches.
        entry=self.input()['graphs'][0];_,raw,ptr,idx=load_graph(self.inputs/entry['file'],entry)
        seed=(int(sha256(entry['sampling_key'].encode()).hexdigest()[:8],16)+42)%2**32;rng=np.random.default_rng(seed)
        expected=[];self.model.eval()
        with torch.inference_mode():
            for start in range(0,300,256):
                chosen=np.arange(start,min(start+256,300));nodes,edges=sample(ptr,idx,chosen,rng)
                clean=features(raw,nodes,self.scaler);mask=rng.random(len(nodes))<.2;mask[:len(chosen)]=True
                masked=clean.clone();masked[mask]=0
                expected.extend((self.model(masked,torch.as_tensor(edges))[:len(chosen)]-clean[:len(chosen)]).square().mean(1).tolist())
        np.testing.assert_allclose([float(r['reconstruction_mse']) for r in rows],expected,rtol=1e-6,atol=1e-8)
        self.assertEqual(source_hash,file_hash(self.root/'hidden_original_source/runs/graphsage/best.pt'))
        self.assertEqual(report['checkpoint_state_sha256'],state_digest(self.model))

    def test_bundle_tampering_rejected_before_deserialization(self):
        (self.bundle/'best.pt').write_bytes(b'changed')
        with patch('torch.load',side_effect=AssertionError('Must verify before deserializing')):
            with self.assertRaisesRegex(ValueError,'artifact changed'):load_bundle(self.bundle,'cpu',self.digest)

    def test_trusted_digest_and_source_code_are_required(self):
        with self.assertRaisesRegex(ValueError,'trusted digest'):load_bundle(self.bundle,'cpu','0'*64)
        with patch('research.ml.gnn_scoring.artifacts.code_hashes',return_value={}):
            with self.assertRaisesRegex(ValueError,'Scoring source'):load_bundle(self.bundle,'cpu',self.digest)

    def test_invalid_scaler_feature_order_architecture_and_security_claims_rejected(self):
        original=[read(self.bundle/name) for name in ('bundle.json','config.json','source_run.json','source_test.json',
            'source_verification.json','feature_schema.json','scaler.json')]
        for which,change in [(6,lambda x:x['stds'].__setitem__(0,0.)),(6,lambda x:x['means'].__setitem__(0,float('nan'))),
                (5,lambda x:x['feature_names'].reverse()),(0,lambda x:x.update(security_threshold=.5)),
                (1,lambda x:x.update(hidden_dim=63)),(3,lambda x:x.update(attack_detection_metrics_available=True)),
                (2,lambda x:x['code_sha256_utf8_lf'].update({'model.py':'0'*64}))]:
            args=copy.deepcopy(original);change(args[which])
            with self.subTest(which=which),self.assertRaises(ValueError):validate_metadata(*args)

    def test_manifest_rejects_schema_labels_duplicate_graphs_and_unsafe_paths(self):
        original=self.input();schema=read(self.bundle/'bundle.json')['files_sha256']['feature_schema.json']
        for change in [lambda m:m.update(feature_schema_sha256='0'*64),
                lambda m:m['graphs'][0].update(security_label='benign'),
                lambda m:m['graphs'].append(copy.deepcopy(m['graphs'][0])),
                lambda m:m['graphs'][0].update(file='../outside.npz'),
                lambda m:m['graphs'][0].update(sampling_key='renamed.npz'),
                lambda m:m['graphs'][0].update(nodes=0),
                lambda m:m['graphs'][0].update(window_start_nanos=1)]:
            modified=copy.deepcopy(original);change(modified);write(self.manifest,modified)
            with self.subTest(modified=modified['graphs'][0]['file']),self.assertRaises(ValueError):input_manifest(self.manifest,schema)

    def test_normalized_counts_invalid_width_and_duplicate_nodes_rejected(self):
        for change in [lambda a:a.update(raw=a['raw'].astype(np.float32)),lambda a:a.update(raw=a['raw'][:,:114]),
                lambda a:a['nodes'].__setitem__(0,a['nodes'][1]),lambda a:a['raw'].__setitem__((0,0),0)]:
            # Restore a pristine exported graph before each independent mutation.
            import shutil
            entry=self.input()['graphs'][0];shutil.copyfile(self.work/entry['file'],self.inputs/entry['file'])
            path,bad=self.array_change(change)
            with self.assertRaises(ValueError):load_graph(path,bad)

    def test_invalid_csr_bounds_symmetry_and_self_edges_rejected(self):
        for change in [lambda a:a['indptr'].__setitem__(-1,599),lambda a:a['indices'].__setitem__(0,9999),
                lambda a:a['indices'].__setitem__(0,0),lambda a:a['indices'].__setitem__(0,2),
                lambda a:a['indices'].__setitem__(1,-1)]:
            import shutil
            entry=self.input()['graphs'][0];shutil.copyfile(self.work/entry['file'],self.inputs/entry['file'])
            path,bad=self.array_change(change)
            with self.assertRaises(ValueError):load_graph(path,bad)

    def test_forged_large_npy_header_is_rejected_before_array_allocation(self):
        entry=self.input()['graphs'][0];path=self.inputs/entry['file']
        with zipfile.ZipFile(path) as archive:members={name:archive.read(name) for name in archive.namelist()}
        header=io.BytesIO()
        np.lib.format.write_array_header_1_0(header,dict(descr='<u4',fortran_order=False,shape=(10**12,115)))
        members['raw.npy']=header.getvalue()
        with zipfile.ZipFile(path,'w') as archive:
            for name,data in members.items():archive.writestr(name,data)
        entry['sha256']=file_hash(path)
        with patch('numpy.load',side_effect=AssertionError('Must validate header before allocation')):
            with self.assertRaisesRegex(ValueError,'NPY header'):load_graph(path,entry)

    def test_csr_overflow_offsets_rejected_before_neighbor_expansion(self):
        def overflowing(arrays):
            arrays['indptr'][1:4]=[np.iinfo(np.int64).max,np.iinfo(np.int64).min+1,-1]
        path,entry=self.array_change(overflowing)
        with patch('numpy.repeat',side_effect=AssertionError('CSR bounds must be checked first')):
            with self.assertRaisesRegex(ValueError,'CSR offsets'):load_graph(path,entry)

    def test_moving_physical_graph_paths_preserves_sampling_and_scores(self):
        first=score(self.bundle,self.manifest,self.root/'original','cpu',self.digest)
        manifest=self.input();entry=manifest['graphs'][0]
        (self.inputs/entry['file']).rename(self.inputs/'moved.npz');entry['file']='moved.npz';write(self.manifest,manifest)
        second=score(self.bundle,self.manifest,self.root/'moved','cpu',self.digest)
        self.assertEqual(first['metrics'],second['metrics'])
        self.assertEqual(first['files_sha256']['scores.csv'],second['files_sha256']['scores.csv'])

    def test_graph_failure_leaves_no_success_receipt_or_final_csv(self):
        entry=self.input()['graphs'][0];(self.inputs/entry['file']).write_bytes(b'broken')
        with self.assertRaisesRegex(ValueError,'fingerprint'):score(self.bundle,self.manifest,self.root/'failed','cpu',self.digest)
        self.assertTrue((self.root/'failed/failure.json').exists())
        self.assertFalse((self.root/'failed/summary.json').exists());self.assertFalse((self.root/'failed/scores.csv').exists())
        self.assertEqual(file_hash(self.bundle/'best.pt'),file_hash(self.directory/'best.pt'))

    def test_artifact_changed_after_first_batch_prevents_success(self):
        original=scoring_module.batches
        def changing(*args):
            for index,batch in enumerate(original(*args)):
                yield batch
                if index==0:
                    path=self.bundle/'scaler.json';path.write_bytes(path.read_bytes()+b' ')
        with patch.object(scoring_module,'batches',changing):
            with self.assertRaisesRegex(ValueError,'Bundle file changed'):
                score(self.bundle,self.manifest,self.root/'changed','cpu',self.digest)
        self.assertTrue((self.root/'changed/scores.csv.partial').exists())
        self.assertFalse((self.root/'changed/summary.json').exists())

    def test_isolated_subjects_without_predicates_are_supported(self):
        manifest=self.input();entry=manifest['graphs'][0];path=self.inputs/entry['file'];n=entry['nodes']
        with np.load(path) as archive:nodes=archive['nodes']
        raw=np.zeros((n,WIDTH),dtype=np.uint32);raw[:,-1]=1
        np.savez_compressed(path,nodes=nodes,raw=raw,indptr=np.zeros(n+1,dtype=np.int64),indices=np.empty(0,dtype=np.int32))
        entry['adjacency_edges']=0;entry['sha256']=file_hash(path);write(self.manifest,manifest)
        report=score(self.bundle,self.manifest,self.root/'isolated','cpu',self.digest)
        self.assertEqual(report['metrics']['target_node_count'],n);self.assertTrue(np.isfinite(report['metrics']['mse']))

    def test_existing_or_overlapping_outputs_are_preserved(self):
        for output in [self.inputs,self.bundle/'nested',self.root]:
            with self.subTest(output=str(output)),self.assertRaises(ValueError):score(self.bundle,self.manifest,output,'cpu',self.digest)
        self.assertTrue(self.manifest.exists())

    def test_reporting_verifier_rejects_changed_csv_and_security_claims(self):
        folder=self.root/'checked';report=score(self.bundle,self.manifest,folder,'cpu',self.digest)
        bundle=read(self.bundle/'bundle.json')
        checked_summary(folder,self.manifest,bundle,self.digest,'cpu')
        write(folder/'summary.json',dict(report,attack_detection_metrics_available=True))
        with self.assertRaisesRegex(ValueError,'Unsupported inference/security'):
            checked_summary(folder,self.manifest,bundle,self.digest,'cpu')
        write(folder/'summary.json',report)
        with (folder/'scores.csv').open('a') as stream:stream.write('extra row\n')
        with self.assertRaisesRegex(ValueError,'CSV fingerprint'):
            checked_summary(folder,self.manifest,bundle,self.digest,'cpu')

    def test_reporting_verifier_rejects_nonfinite_negative_or_labelled_rows(self):
        row=dict(graph_id='fixture',node_index='0',node_uuid='1'*32,reconstruction_mse='0.1',
            reconstruction_mae='0.2',training_mean_reference_mse='0.3',security_label='',security_threshold='')
        np.testing.assert_allclose(row_values(row),[.1,.2,.3])
        for change in [dict(reconstruction_mse='nan'),dict(reconstruction_mae='-1'),dict(security_label='benign'),
                dict(security_threshold='.3')]:
            with self.assertRaises(ValueError):row_values(dict(row,**change))

    def test_requested_unavailable_cuda_never_silently_uses_cpu(self):
        with patch('torch.cuda.is_available',return_value=False):
            with self.assertRaisesRegex(ValueError,'CUDA is unavailable'):load_bundle(self.bundle,'cuda',self.digest)

    @unittest.skipUnless(torch.cuda.is_available(),'CUDA parity requires NVIDIA hardware')
    def test_cpu_cuda_row_scores_agree_within_tolerance(self):
        cpu=score(self.bundle,self.manifest,self.root/'cpu','cpu',self.digest)
        gpu=score(self.bundle,self.manifest,self.root/'cuda','cuda',self.digest)
        for key in ('mse','mae','mean_reference_mse'):
            np.testing.assert_allclose(cpu['metrics'][key],gpu['metrics'][key],rtol=1e-5,atol=1e-7)
        def values(folder):
            with (self.root/folder/'scores.csv').open(newline='') as stream:
                return [float(r['reconstruction_mse']) for r in csv.DictReader(stream)]
        np.testing.assert_allclose(values('cpu'),values('cuda'),rtol=1e-5,atol=1e-7)

    def test_prefetch_propagates_producer_failure(self):
        def broken():
            yield 1
            raise ValueError('producer failed')
        with self.assertRaisesRegex(ValueError,'producer failed'),prefetched(broken()) as batches:
            self.assertEqual(next(batches),1);next(batches)


if __name__=='__main__':unittest.main()
