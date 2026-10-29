"""Full node-window passes, clean targets, development-only GNN selection."""
import hashlib
import json
from pathlib import Path
import random
import os
import time
import numpy as np
import torch
import torch_geometric
from research.ml.gnn_full.model import GraphReconstructor,sample,features
from research.ml.gnn_full.prepare import save,disk_guard
from research.ml.label_free.model import state_digest
from research.ml.node_benchmark.audit_protocol import file_hash,text_hash


def seed_for(entry,seed):
    return (int(hashlib.sha256(entry['file'].encode()).hexdigest()[:8],16)+seed)%2**32


def epoch(model,graphs,work,scaler,seed,optimizer=None):
    training=optimizer is not None; model.train(training); totals=np.zeros(3);target_count=0;visited=0
    order=list(graphs)
    if training:random.Random(seed).shuffle(order)
    started=time.perf_counter()
    for graph_index,entry in enumerate(order):
        path=work/entry['file']
        if file_hash(path)!=entry['sha256']:raise ValueError('Graph fingerprint changed before reuse')
        with np.load(path) as archive:
            raw,indptr,indices=archive['raw'],archive['indptr'],archive['indices']
        rng=np.random.default_rng(seed_for(entry,seed));seeds=rng.permutation(len(raw)) if training else np.arange(len(raw))
        for start in range(0,len(seeds),256):
            chosen=seeds[start:start+256];nodes,edge=sample(indptr,indices,chosen,rng)
            clean=features(raw,nodes,scaler).to('cuda');inputs=clean.clone()
            mask=torch.as_tensor(rng.random(len(nodes))<.2,device='cuda')
            if not training:mask[:len(chosen)]=True
            elif not bool(mask[:len(chosen)].any()):mask[int(rng.integers(len(chosen)))]=True
            inputs[mask]=0;targets=mask[:len(chosen)]
            edge=torch.as_tensor(edge,dtype=torch.long,device='cuda')
            if training:optimizer.zero_grad(set_to_none=True)
            with torch.set_grad_enabled(training):
                predicted=model(inputs,edge)[:len(chosen)][targets];wanted=clean[:len(chosen)][targets]
                residual=predicted-wanted;loss=residual.square().mean()
                if not torch.isfinite(loss):raise ValueError('Nonfinite graph reconstruction loss')
                if training:
                    loss.backward()
                    if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                        raise ValueError('Nonfinite GNN gradient')
                    optimizer.step()
            values=torch.stack((residual.square().sum(),residual.abs().sum(),wanted.square().sum())).detach().cpu().numpy()
            totals+=values;target_count+=wanted.numel();visited+=len(chosen)
            if visited%25_600<len(chosen):
                print(json.dumps(dict(phase='training_batches' if training else 'evaluation_batches',
                    visited_seed_nodes=visited,graphs_completed=graph_index,graphs_total=len(order))),flush=True)
        if file_hash(path)!=entry['sha256']:raise ValueError('Graph changed while scoring')
    torch.cuda.synchronize()
    if target_count==0:raise ValueError('Empty reconstruction target cohort')
    return dict(mse=float(totals[0]/target_count),mae=float(totals[1]/target_count),
        mean_reference_mse=float(totals[2]/target_count),seed_nodes_visited=visited,
        target_node_count=target_count//len(scaler['means']),seconds=time.perf_counter()-started)


def setup(seed):
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    if not torch.cuda.is_available():raise RuntimeError('The approved CUDA GNN run cannot fall back to CPU')
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(4);torch.set_float32_matmul_precision('highest')
    # PyG CUDA scatter kernels can be nondeterministic. Never claim exact repeatability.
    torch.use_deterministic_algorithms(True,warn_only=True)


def train_all(work,config):
    metadata=json.loads((work/'graphs.json').read_text(encoding='utf-8'))
    if metadata['status']!='full_local_graph_preparation_verified':raise ValueError('Graphs are not ready')
    scaler=json.loads((work/'scaler.json').read_text(encoding='utf-8'))
    if file_hash(work/'scaler.json')!=metadata['scaler_sha256']:raise ValueError('Frozen scaler changed')
    grouped={role:[g for g in metadata['graphs'] if g['role']==role] for role in ('train','development','test')}
    code={name:text_hash(Path(__file__).parent/name) for name in ('model.py','train.py','prepare.py')}
    graph_sha=file_hash(work/'graphs.json');results={}
    for family in ('gcn','graphsage','gat'):
        output=work/'runs'/family;output.mkdir(parents=True,exist_ok=True)
        if (output/'run.json').exists():
            report=json.loads((output/'run.json').read_text(encoding='utf-8'))
            if report['status']!='gnn_training_complete_test_not_read' or report['code_sha256_utf8_lf']!=code:
                raise ValueError('Existing run requires inspection before resuming')
            if file_hash(output/'best.pt')!=report['checkpoint_sha256']:raise ValueError('Saved GNN changed')
            results[family]=report;continue
        setup(config['seed']);model=GraphReconstructor(family,metadata['feature_count']).cuda()
        optimizer=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.0001)
        history=[];best=float('inf');best_epoch=0;started=time.perf_counter()
        for number in range(config['epochs']+1):
            disk_guard(work)
            save(work/'progress.json',dict(phase='gnn_training',model=family,epoch=number,maximum_epochs=config['epochs']))
            training=epoch(model,grouped['train'],work,scaler,config['seed']+number,optimizer) if number else None
            development=epoch(model,grouped['development'],work,scaler,config['seed'])
            history.append(dict(epoch=number,training=training,development=development))
            save(output/'history.json',history)
            if development['mse']<best:
                best=development['mse'];best_epoch=number
                torch.save(dict(state_dict={k:v.detach().cpu() for k,v in model.state_dict().items()},
                    family=family,feature_count=metadata['feature_count'],epoch=number,config=config,
                    graph_manifest_sha256=graph_sha,scaler_sha256=metadata['scaler_sha256']),output/'best.pt')
            print(json.dumps(dict(model=family,epoch=number,development=development,best_epoch=best_epoch)),flush=True)
        saved=torch.load(output/'best.pt',map_location='cpu',weights_only=True)
        model.load_state_dict(saved['state_dict'],strict=True)
        selected=epoch(model,grouped['development'],work,scaler,config['seed'])
        if not np.isclose(selected['mse'],best,rtol=1e-5,atol=1e-7):raise ValueError('Reloaded development score differs')
        report=dict(status='gnn_training_complete_test_not_read',family=family,config=config,best_epoch=best_epoch,
            development=selected,checkpoint_sha256=file_hash(output/'best.pt'),checkpoint_state_sha256=state_digest(model),
            code_sha256_utf8_lf=code,graph_manifest_sha256=graph_sha,scaler_sha256=metadata['scaler_sha256'],
            parameter_count=sum(p.numel() for p in model.parameters()),epochs_completed=config['epochs'],
            torch_version=torch.__version__,pyg_version=torch_geometric.__version__,gpu=torch.cuda.get_device_name(0),
            parameter_device=str(next(model.parameters()).device),elapsed_seconds=time.perf_counter()-started,
            cuda_scatter_nondeterminism_possible=True,exact_repeatability_claimed=False,test_read=False,
            security_threshold=None,attack_detection_metrics_available=False)
        save(output/'run.json',report);results[family]=report
    # All models must be selected/frozen before any final test scoring.
    for family in ('gcn','graphsage','gat'):
        output=work/'runs'/family;setup(config['seed'])
        if file_hash(output/'best.pt')!=results[family]['checkpoint_sha256']:raise ValueError('Selected checkpoint changed')
        model=GraphReconstructor(family,metadata['feature_count']).cuda()
        model.load_state_dict(torch.load(output/'best.pt',map_location='cpu',weights_only=True)['state_dict'])
        metrics=epoch(model,grouped['test'],work,scaler,config['seed'])
        save(output/'test.json',dict(status='frozen_gnn_feature_reconstruction_test_complete',metrics=metrics,
            checkpoint_sha256=results[family]['checkpoint_sha256'],security_threshold=None,
            attack_detection_metrics_available=False,within_window_feature_imputation=True))
        results[family]['final_reconstruction_test']=metrics
    return results
