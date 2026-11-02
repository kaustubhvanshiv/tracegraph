"""Frozen all-test residual analysis; no optimization, tuning or security labels."""
import argparse
import heapq
import json
from pathlib import Path
import time
import numpy as np
import torch
from research.ml.gnn_accel.prefetch import batches,prefetched
from research.ml.gnn_full.model import GraphReconstructor
from research.ml.gnn_full.train import setup
from research.ml.gnn_full.prepare import save
from research.ml.node_benchmark.audit_protocol import file_hash
from research.ml.gnn_results.verify import FAMILIES,require
from research.ml.label_free.model import state_digest


def distribution(scores):
    values=np.asarray(scores,dtype=np.float64)
    require(values.ndim==1 and len(values)>0 and np.isfinite(values).all() and (values>=0).all(),'Invalid row errors')
    total=values.sum();ordered=np.sort(values)
    share=lambda k:float(ordered[-min(k,len(values)):].sum()/total) if total else 0.
    return dict(rows=len(values),median=float(np.median(values)),p95=float(np.quantile(values,.95)),
        p99=float(np.quantile(values,.99)),maximum=float(values.max()),
        top_10_squared_error_share=share(10),top_1_percent_squared_error_share=share(max(1,int(np.ceil(len(values)*.01)))))


def analyze(work,verification_path,output):
    complete=json.loads((work/'complete.json').read_text());verification=json.loads(verification_path.read_text())
    require(verification['status']=='completed_full_local_gnn_artifacts_verified' and
            verification['complete_sha256']==file_hash(work/'complete.json'),'Completed artifacts must be verified first')
    metadata=json.loads((work/'graphs.json').read_text());scaler=json.loads((work/'scaler.json').read_text())
    require(file_hash(work/'graphs.json')==verification['graph_manifest_sha256'],'Graph manifest changed')
    require(file_hash(work/'scaler.json')==verification['scaler_sha256'],'Scaler changed')
    setup(42);models={};width=metadata['feature_count']
    for family in FAMILIES:
        path=work/f'runs/{family}/best.pt'
        require(file_hash(path)==verification['models'][family]['checkpoint_sha256'],'Checkpoint changed')
        model=GraphReconstructor(family,width).cuda()
        model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True)['state_dict'],strict=True)
        model.eval();models[family]=model
    graphs=[g for g in metadata['graphs'] if g['role']=='test'];rows=sum(g['nodes'] for g in graphs)
    sums={f:np.zeros(3,dtype=np.float64) for f in FAMILIES}
    feature_sse={f:np.zeros(width,dtype=np.float64) for f in FAMILIES}
    scores={f:np.empty(rows,dtype=np.float32) for f in FAMILIES}
    tops={f:[] for f in FAMILIES};graph_stats={f:[] for f in FAMILIES}
    offset=0;row_index=0;previous=None;graph_sums={f:0. for f in FAMILIES};started=time.perf_counter()
    with torch.no_grad(),prefetched(batches(graphs,work,scaler,42,False)) as prepared:
        for count,index,clean_cpu,edge_cpu,mask_cpu in prepared:
            if index!=previous:
                if previous is not None:
                    require(row_index==graphs[previous]['nodes'],'Graph row coverage mismatch')
                    for family in FAMILIES:graph_stats[family].append(graph_sums[family]/(row_index*width))
                previous=index;row_index=0;graph_sums={f:0. for f in FAMILIES}
            clean=clean_cpu.to('cuda',non_blocking=True);edges=edge_cpu.to('cuda',non_blocking=True)
            mask=mask_cpu.to('cuda',non_blocking=True);inputs=clean.clone();inputs[mask]=0
            wanted=clean[:count]
            for family,model in models.items():
                residual=model(inputs,edges)[:count]-wanted
                require(bool(torch.isfinite(residual).all()),'Nonfinite analysis residual')
                squared=residual.square()
                values=torch.stack((squared.sum(),residual.abs().sum(),wanted.square().sum())).cpu().numpy()
                sums[family]+=values;graph_sums[family]+=float(values[0])
                feature_sse[family]+=squared.sum(0).cpu().numpy()
                errors=squared.mean(1).cpu().numpy();scores[family][offset:offset+count]=errors
                candidates=np.argpartition(errors,-min(10,count))[-min(10,count):]
                for j in candidates:
                    value=(float(errors[j]),index,row_index+int(j))
                    if len(tops[family])<10:heapq.heappush(tops[family],value)
                    elif value>tops[family][0]:heapq.heapreplace(tops[family],value)
            offset+=count;row_index+=count
            if offset%256_000<count:print(json.dumps(dict(phase='frozen_error_analysis',test_rows=offset,total=rows)),flush=True)
    require(offset==rows and row_index==graphs[-1]['nodes'],'Final analysis coverage mismatch')
    for family in FAMILIES:graph_stats[family].append(graph_sums[family]/(row_index*width))
    torch.cuda.synchronize();duration=time.perf_counter()-started
    public={};local={}
    output.mkdir(parents=True,exist_ok=True)
    for family,model in models.items():
        replay=dict(zip(('mse','mae','mean_reference_mse'),map(float,sums[family]/(rows*width))))
        frozen=complete['models'][family]['final_reconstruction_test']
        for key in replay:require(np.isclose(replay[key],frozen[key],rtol=1e-5,atol=1e-7),'Frozen test replay differs')
        require(state_digest(model)==verification['models'][family]['state_sha256'],'Analysis modified model state')
        require(file_hash(work/f'runs/{family}/best.pt')==verification['models'][family]['checkpoint_sha256'],'Saved checkpoint changed')
        sse=feature_sse[family];total=float(sse.sum());names=metadata['feature_names']
        features=[dict(feature=n,mse=float(v/rows),squared_error_share=float(v/total) if total else 0.) for n,v in zip(names,sse)]
        public[family]=dict(replayed_test=replay,row_errors=distribution(scores[family]),
            top_features=sorted(features,key=lambda f:f['squared_error_share'],reverse=True)[:10],
            all_feature_errors=features,graph_mse_median=float(np.median(graph_stats[family])),
            graph_mse_maximum=float(max(graph_stats[family])),model_state_unchanged=True)
        witnesses=[]
        for error,index,node_index in sorted(tops[family],reverse=True):
            graph=graphs[index]
            with np.load(work/graph['file']) as archive:uid=bytes(archive['nodes'][node_index]).hex()
            witnesses.append(dict(mse=error,graph_file=graph['file'],host=graph['host'],node_uuid=uid,
                window_start_nanos=graph['window_start_nanos'],native_node_index=node_index,security_label='unknown'))
        local[family]=witnesses
    result=dict(status='frozen_full_test_error_analysis_complete',models=public,test_rows=rows,test_graphs=len(graphs),
        verification_sha256=file_hash(verification_path),complete_sha256=file_hash(work/'complete.json'),
        elapsed_seconds=duration,training_performed=False,checkpoint_selection_changed=False,
        security_metrics_available=False,security_threshold=None,
        limitation='Descriptive inspection of an already evaluated test cohort. Do not tune on it; errors do not label attacks.')
    save(output/'error_analysis.json',result)
    save(output/'local_unknown_review_rows.json',dict(status='descriptive_reconstruction_review_only',models=local))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--verification',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=analyze(args.work,args.verification,args.output)
    print(json.dumps(dict(status=result['status'],test_rows=result['test_rows'],elapsed_seconds=result['elapsed_seconds'])))
