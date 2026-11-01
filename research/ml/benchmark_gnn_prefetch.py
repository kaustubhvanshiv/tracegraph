import sys,json,time,statistics
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
from research.ml.gnn_full.train import epoch as serial,setup
from research.ml.gnn_accel.prefetch import epoch as prefetch
from research.ml.gnn_full.model import GraphReconstructor
from research.ml.node_benchmark.audit_protocol import file_hash
import torch
work=Path(r'D:\Deep Learning\tracegraph-gnn-workspace')
metadata=json.loads((work/'graphs.json').read_text())
graphs=[g for g in metadata['graphs'] if g['role']=='train' and 8000<=g['nodes']<=20000][:3]
assert len(graphs)==3
scaler=json.loads((work/'scaler.json').read_text())
assert file_hash(work/'scaler.json')==metadata['scaler_sha256']
setup(42)
# Warm up kernels and file cache equally; no benchmark artifacts enter training.
for impl in (serial,prefetch):
    model=GraphReconstructor('gat',metadata['feature_count']).cuda()
    opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.0001)
    impl(model,graphs[:1],work,scaler,43,opt)
times={'serial':[],'prefetch':[]};metrics={}
for repeat in range(3):
    order=[('serial',serial),('prefetch',prefetch)]
    if repeat%2:order.reverse()
    for name,impl in order:
        setup(42);model=GraphReconstructor('gat',metadata['feature_count']).cuda()
        opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.0001)
        result=impl(model,graphs,work,scaler,43,opt)
        times[name].append(result['seconds']);metrics[name]=result
        print(json.dumps(dict(mode=name,repeat=repeat,metrics=result)),flush=True)
medians={k:statistics.median(v) for k,v in times.items()}
for key in ('mse','mae','mean_reference_mse'):
    assert abs(metrics['serial'][key]-metrics['prefetch'][key])<1e-5
assert metrics['serial']['seed_nodes_visited']==metrics['prefetch']['seed_nodes_visited']
result=dict(status='real_training_graph_throughput_benchmark',family='gat',training_graphs=graphs,
    repeats=3,seconds=times,median_seconds=medians,speedup=medians['serial']/medians['prefetch'],
    benchmark_only=True,test_partition_read=False,selected_checkpoints_modified=False,
    model_protocol_unchanged=True,seed_nodes=sum(g['nodes'] for g in graphs),
    limitation='Small training-only workload; does not guarantee full-epoch speedup.')
path=root/'.cache/gnn_prefetch_benchmark.json';path.write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
