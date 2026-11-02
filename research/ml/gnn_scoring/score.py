"""Offline masked reconstruction with bounded CPU preparation and optional CUDA."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import csv
import hashlib
import json
from pathlib import Path
import shutil
import time
import numpy as np
import torch
import torch_geometric
from research.ml.gnn_full.model import sample,features
from research.ml.label_free.model import state_digest
from research.ml.node_benchmark.audit_protocol import file_hash
from research.ml.gnn_scoring.artifacts import WIDTH,require,write,fresh_output,load_bundle,code_hashes
from research.ml.gnn_scoring.inputs import input_manifest,load_graph


def batches(manifest,root,scaler,pin):
    """Keep canonical sampling identities stable even when physical paths move."""
    for graph_index,entry in enumerate(manifest['graphs']):
        path=root/entry['file'];uuids,raw,indptr,indices=load_graph(path,entry)
        seed=(int(hashlib.sha256(entry['sampling_key'].encode()).hexdigest()[:8],16)+42)%2**32
        rng=np.random.default_rng(seed)
        for start in range(0,entry['nodes'],256):
            chosen=np.arange(start,min(start+256,entry['nodes']))
            nodes,edge=sample(indptr,indices,chosen,rng)
            clean=features(raw,nodes,scaler);mask=rng.random(len(nodes))<.2;mask[:len(chosen)]=True
            tensors=(clean,torch.as_tensor(edge,dtype=torch.long),torch.as_tensor(mask))
            if pin:tensors=tuple(t.pin_memory() for t in tensors)
            yield graph_index,start,[bytes(u).hex() for u in uuids[chosen]],tensors
        require(file_hash(path)==entry['sha256'],'Graph changed during scoring')


@contextmanager
def prefetched(items):
    """One ordered producer with at most one future batch ahead; propagate errors."""
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='scorer-cpu') as pool:
        future=pool.submit(next,items,None)
        def consume():
            nonlocal future
            while True:
                value=future.result()
                if value is None:return
                future=pool.submit(next,items,None)
                yield value
        try:yield consume()
        finally:
            future.cancel()
            # Wait before closing: a generator cannot be closed while its worker runs.
            if not future.cancelled():
                try:future.result()
                except BaseException:pass
            items.close()


def metrics(totals,rows):
    values=totals/(rows*WIDTH)
    return dict(mse=float(values[0]),mae=float(values[1]),mean_reference_mse=float(values[2]),
        seed_nodes_visited=rows,target_node_count=rows)


def score(bundle_path,input_path,output,device,bundle_sha):
    output=fresh_output(output,bundle_path,input_path.parent)
    bundle,model,schema,scaler=load_bundle(bundle_path,device,bundle_sha)
    manifest=input_manifest(input_path,bundle['files_sha256']['feature_schema.json'])
    input_sha=file_hash(input_path);expected=sum(e['nodes'] for e in manifest['graphs'])
    output.parent.mkdir(parents=True,exist_ok=True)
    require(shutil.disk_usage(output.parent).free>expected*256+64*1024**2,'Insufficient disk for complete row scores')
    output.mkdir();started=time.perf_counter();totals=np.zeros(3);visited=0;completed=0
    row_path=output/'scores.csv.partial';graph_path=output/'graphs.csv.partial'
    try:
        with row_path.open('w',encoding='utf-8',newline='') as rows,graph_path.open('w',encoding='utf-8',newline='') as graphs:
            row_writer=csv.writer(rows);graph_writer=csv.writer(graphs)
            row_writer.writerow(['graph_id','node_index','node_uuid','reconstruction_mse','reconstruction_mae',
                'training_mean_reference_mse','security_label','security_threshold'])
            graph_writer.writerow(['graph_id','host_uuid','window_start_nanos','role','node_windows',
                'native_events','adjacency_edges','mse','mae','mean_reference_mse'])
            per_graph=np.zeros(3);graph_rows=0
            with prefetched(batches(manifest,input_path.parent,scaler,device=='cuda')) as prepared,torch.inference_mode():
                for graph_index,start,uuids,tensors in prepared:
                    entry=manifest['graphs'][graph_index];count=len(uuids)
                    require(graph_index==completed and start==graph_rows,'Seed ordering or coverage differs')
                    clean,edge,mask=(t.to(device,non_blocking=device=='cuda') for t in tensors)
                    inputs=clean.clone();inputs[mask]=0
                    wanted=clean[:count];residual=model(inputs,edge)[:count]-wanted
                    squared=residual.square();absolute=residual.abs();reference=wanted.square()
                    values=torch.stack((squared.sum(),absolute.sum(),reference.sum())).cpu().numpy()
                    require(np.isfinite(values).all(),'Nonfinite reconstruction output')
                    row_values=torch.stack((squared.mean(dim=1),absolute.mean(dim=1),reference.mean(dim=1)),dim=1).cpu().numpy()
                    require(np.isfinite(row_values).all(),'Nonfinite row reconstruction output')
                    row_writer.writerows((entry['graph_id'],start+i,uid,*map(float,row),'','') for i,(uid,row) in enumerate(zip(uuids,row_values)))
                    totals+=values;per_graph+=values;visited+=count;graph_rows+=count
                    if graph_rows==entry['nodes']:
                        gm=metrics(per_graph,graph_rows)
                        graph_writer.writerow([entry['graph_id'],entry['host_uuid'],entry['window_start_nanos'],entry['role'],
                            graph_rows,entry['native_events'],entry['adjacency_edges'],gm['mse'],gm['mae'],gm['mean_reference_mse']])
                        completed+=1;per_graph=np.zeros(3);graph_rows=0
                        progress=dict(phase='reconstruction_scoring',graphs_completed=completed,graphs_total=len(manifest['graphs']),
                            rows_scored=visited,rows_total=expected,seconds=time.perf_counter()-started)
                        write(output/'progress.json',progress)
                        if completed%25==0 or completed==len(manifest['graphs']):print(json.dumps(progress),flush=True)
        require(visited==expected and completed==len(manifest['graphs']),'Incomplete scoring coverage')
        require(state_digest(model)==bundle['checkpoint_state_sha256'],'Model parameters changed during scoring')
        require(file_hash(input_path)==input_sha,'Input manifest changed during scoring')
        require(file_hash(bundle_path/'bundle.json')==bundle_sha and bundle['scoring_code_sha256_utf8_lf']==code_hashes(),
                'Bundle manifest or scorer source changed during scoring')
        for name,digest in bundle['files_sha256'].items():require(file_hash(bundle_path/name)==digest,'Bundle file changed during scoring')
        for entry in manifest['graphs']:require(file_hash(input_path.parent/entry['file'])==entry['sha256'],'Input graph changed before completion')
        row_path.rename(output/'scores.csv');graph_path.rename(output/'graphs.csv')
        summary=dict(status='standalone_graphsage_reconstruction_complete',model='graphsage',selected_epoch=bundle['selected_epoch'],
            parameter_count=bundle['parameter_count'],bundle_sha256=bundle_sha,input_manifest_sha256=input_sha,
            checkpoint_sha256=bundle['files_sha256']['best.pt'],checkpoint_state_sha256=bundle['checkpoint_state_sha256'],
            scaler_sha256=bundle['files_sha256']['scaler.json'],feature_schema_sha256=bundle['files_sha256']['feature_schema.json'],
            scoring_code_sha256_utf8_lf=bundle['scoring_code_sha256_utf8_lf'],device=device,
            runtime=dict(torch=torch.__version__,numpy=np.__version__,pyg=torch_geometric.__version__),
            gpu=torch.cuda.get_device_name(0) if device=='cuda' else None,
            graph_count=completed,metrics=metrics(totals,visited),selection=manifest['selection'],
            seconds=time.perf_counter()-started,input_graph_hashes_checked=completed,
            files_sha256={name:file_hash(output/name) for name in ('scores.csv','graphs.csv')},
            weights_updated=False,scaler_refit=False,security_labels_used=False,security_threshold=None,
            attack_detection_metrics_available=False,within_window_feature_imputation=True,
            cuda_scatter_nondeterminism_possible=device=='cuda',exact_repeatability_claimed=False,
            input_event_semantics_independently_reverified=False,backend_integration=False)
        write(output/'summary.json',summary)
        return summary
    except BaseException as error:
        write(output/'failure.json',dict(status='standalone_scoring_failed',error_type=type(error).__name__,error=str(error),
            graphs_completed=completed,rows_scored=visited,bundle_sha256=bundle_sha,input_manifest_sha256=input_sha))
        raise
