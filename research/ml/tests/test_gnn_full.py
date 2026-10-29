"""Integrity/scalability checks for the full-local-source GNN workflow."""
import json
from pathlib import Path
import tempfile
import shutil
import unittest
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch
from research.ml.gnn_full.prepare import SCHEMA,extract,deduplicate,compile_graphs,graph_arrays,independently_check,role,TRAIN_END,DEV_END,WINDOW
from research.ml.gnn_full.model import GraphReconstructor,sample
from research.ml.tests.test_label_free import LabelFreeTests


class FullGNNTests(unittest.TestCase):
    def test_full_archive_counts_global_duplicates_and_conflicts_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source,_,audit=LabelFreeTests().fixture(base)
            path=audit/'reference_report.json';report=json.loads(path.read_text(encoding='utf-8'))
            original=next(source.glob('*.gz'));copied=source/'second-source.gz';shutil.copyfile(original,copied)
            item=dict(report['files'][0],filename=copied.name,compressed_bytes=copied.stat().st_size,
                modified_time_ns=copied.stat().st_mtime_ns)
            report['files'].append(item)
            report['all_files_fully_scanned']=True;path.write_text(json.dumps(report),encoding='utf-8')
            work=base/'work';extract(source,audit,work,['EVENT_READ','EVENT_WRITE'])
            result=deduplicate(work)
            self.assertEqual(result['conflicting_event_keys_quarantined'],1)
            self.assertGreater(result['identical_repeats_removed'],1)
            self.assertEqual(len(list((work/'staged').glob('*.json'))),2)
            self.assertTrue((work/'buckets').exists())
            self.assertFalse(list((work/'staged').glob('*.parquet')))
            self.assertTrue(list((work/'staged').glob('*.json')))

    def test_all_node_features_match_independent_sql_and_csr_has_no_false_direction(self):
        a,b,c=[bytes([i])*16 for i in (1,2,3)]
        rows=[dict(host=a,event=bytes([10+i])*16,actor=actor,obj1=one,obj2=two,ts=i+1,
                   action=action,source=0,ordinal=i+1,fp=bytes(32)) for i,(actor,one,two,action) in
              enumerate([(a,b,c,0),(a,None,None,1),(b,a,None,2),(b,b,None,0)])]
        table=pa.Table.from_pylist(rows,schema=SCHEMA)
        nodes,raw,indptr,indices=graph_arrays(table,3)
        independently_check(table,nodes,raw,indptr,indices,3)
        self.assertEqual(raw.shape,(3,7));self.assertEqual(raw[:,:3].sum(),4)
        self.assertEqual(raw[:,3:6].sum(),4);self.assertEqual(raw[:,-1].sum(),1)
        edges={(i,int(j)) for i in range(len(nodes)) for j in indices[indptr[i]:indptr[i+1]]}
        self.assertTrue(all((b,a) in edges and a!=b for a,b in edges))
        raw[0,0]+=1
        with self.assertRaises(ValueError):independently_check(table,nodes,raw,indptr,indices,3)

    def test_temporal_windows_do_not_cross_five_minute_purge_gaps(self):
        self.assertEqual(role(TRAIN_END-WINDOW),'train')
        self.assertEqual(role(TRAIN_END),'purge')
        self.assertEqual(role(TRAIN_END+WINDOW),'development')
        self.assertEqual(role(DEV_END),'purge')
        self.assertEqual(role(DEV_END+WINDOW),'test')

    def test_sampler_is_bounded_repeatable_and_keeps_seeds_first(self):
        indptr=np.array([0,99]+[99]*99);indices=np.arange(1,100)
        nodes,edge=sample(indptr,indices,[0],np.random.default_rng(42))
        repeated=sample(indptr,indices,[0],np.random.default_rng(42))
        self.assertEqual(nodes[0],0);self.assertLessEqual(len(nodes),61)
        self.assertTrue(np.array_equal(nodes,repeated[0]));self.assertTrue(np.array_equal(edge,repeated[1]))
        self.assertEqual(len(set(map(int,nodes))),len(nodes))

    def test_all_three_real_pyg_layers_have_finite_gpu_gradients(self):
        device='cuda' if torch.cuda.is_available() else 'cpu'
        for family in ('gcn','graphsage','gat'):
            with self.subTest(family=family):
                torch.manual_seed(42);model=GraphReconstructor(family,7).to(device)
                clean=torch.randn(5,7,device=device);values=clean.clone();values[:2]=0
                edges=torch.tensor([[0,1,1,2,2,3,3,4],[1,0,2,1,3,2,4,3]],device=device)
                loss=(model(values,edges)[:2]-clean[:2]).square().mean();loss.backward()
                self.assertTrue(torch.isfinite(loss));self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters()))

    @unittest.skipUnless(torch.cuda.is_available(),'The complete GNN loop requires CUDA')
    def test_graph_preparation_and_three_model_loop_complete_before_final_test(self):
        from research.ml.gnn_full.train import train_all
        from research.ml.gnn_full.prepare import save
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder);a,b,c=[bytes([i])*16 for i in (1,2,3)]
            for window in (TRAIN_END-WINDOW,TRAIN_END+WINDOW,DEV_END+WINDOW):
                part=work/'buckets'/('host_key='+a.hex())/('window='+str(window));part.mkdir(parents=True)
                table=pa.Table.from_pylist([dict(host=a,event=bytes([10+i])*16,actor=actor,obj1=one,obj2=None,
                    ts=window+i,action=i%2,source=0,ordinal=i+1,fp=bytes(32))
                    for i,(actor,one) in enumerate([(a,b),(b,c),(a,None)])],schema=SCHEMA)
                pq.write_table(table,part/'data.parquet')
            metadata=compile_graphs(work,['EVENT_READ','EVENT_WRITE'])
            self.assertEqual({g['role'] for g in metadata['graphs']},{'train','development','test'})
            self.assertTrue(all(g['independent_sql_vector_check'] for g in metadata['graphs']))
            results=train_all(work,dict(seed=42,epochs=1))
            self.assertEqual(set(results),{'gcn','graphsage','gat'})
            self.assertTrue(all('final_reconstruction_test' in r for r in results.values()))
            self.assertTrue(all(r['test_read'] is False for r in results.values()))


if __name__=='__main__':unittest.main()
