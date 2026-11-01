"""Overlap bounded CPU batch preparation with unchanged CUDA model updates."""
from contextlib import contextmanager
from queue import Queue, Empty, Full
from threading import Thread, Event
import json
import random
import time
import numpy as np
import torch
from research.ml.gnn_full.model import sample, features
from research.ml.gnn_full.train import seed_for
from research.ml.node_benchmark.audit_protocol import file_hash


@contextmanager
def prefetched(items, depth=2):
    """Single ordered producer, bounded lookahead, propagated failures and cancellation."""
    queue=Queue(maxsize=depth); stop=Event(); end=object()
    def put(value):
        while not stop.is_set():
            try:queue.put(value,timeout=.05);return True
            except Full:pass
        return False
    def produce():
        try:
            for item in items:
                if not put((True,item)):break
        except BaseException as error:put((False,error))
        finally:
            close=getattr(items,'close',None)
            if close:close()
            put((True,end))
    def consume():
        while True:
            try:ok,value=queue.get(timeout=.1)
            except Empty:
                if not worker.is_alive():raise RuntimeError('CPU producer exited without a completion marker')
                continue
            if not ok:raise value
            if value is end:return
            yield value
    worker=Thread(target=produce,name='gnn-cpu-prefetch',daemon=True);worker.start()
    try:yield consume()
    finally:
        stop.set();worker.join()


def batches(graphs,work,scaler,seed,training,pin=True):
    order=list(graphs)
    if training:random.Random(seed).shuffle(order)
    for graph_index,entry in enumerate(order):
        path=work/entry['file']
        if file_hash(path)!=entry['sha256']:raise ValueError('Graph fingerprint changed before reuse')
        with np.load(path) as archive:
            raw,indptr,indices=archive['raw'],archive['indptr'],archive['indices']
        rng=np.random.default_rng(seed_for(entry,seed))
        seeds=rng.permutation(len(raw)) if training else np.arange(len(raw))
        for start in range(0,len(seeds),256):
            chosen=seeds[start:start+256];nodes,edge=sample(indptr,indices,chosen,rng)
            clean=features(raw,nodes,scaler)
            mask=rng.random(len(nodes))<.2
            if not training:mask[:len(chosen)]=True
            elif not mask[:len(chosen)].any():mask[int(rng.integers(len(chosen)))]=True
            tensors=(clean,torch.as_tensor(edge,dtype=torch.long),torch.as_tensor(mask))
            if pin:tensors=tuple(t.pin_memory() for t in tensors)
            yield (len(chosen),graph_index,*tensors)
        if file_hash(path)!=entry['sha256']:raise ValueError('Graph changed while scoring')


def epoch(model,graphs,work,scaler,seed,optimizer=None):
    training=optimizer is not None;model.train(training)
    totals=np.zeros(3);target_count=0;visited=0;started=time.perf_counter()
    with prefetched(batches(graphs,work,scaler,seed,training)) as prepared:
        for count,graph_index,clean_cpu,edge_cpu,mask_cpu in prepared:
            clean=clean_cpu.to('cuda',non_blocking=True)
            edge=edge_cpu.to('cuda',non_blocking=True)
            mask=mask_cpu.to('cuda',non_blocking=True)
            inputs=clean.clone();inputs[mask]=0;targets=mask[:count]
            if training:optimizer.zero_grad(set_to_none=True)
            with torch.set_grad_enabled(training):
                predicted=model(inputs,edge)[:count][targets];wanted=clean[:count][targets]
                residual=predicted-wanted;loss=residual.square().mean()
                if not torch.isfinite(loss):raise ValueError('Nonfinite graph reconstruction loss')
                if training:
                    loss.backward()
                    flags=[torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None]
                    if flags and not bool(torch.stack(flags).all()):raise ValueError('Nonfinite GNN gradient')
                    optimizer.step()
            totals+=torch.stack((residual.square().sum(),residual.abs().sum(),wanted.square().sum())).detach().cpu().numpy()
            target_count+=wanted.numel();visited+=count
            if visited%25_600<count:
                print(json.dumps(dict(phase='training_batches' if training else 'evaluation_batches',
                    visited_seed_nodes=visited,graphs_completed=graph_index,graphs_total=len(graphs),
                    execution='bounded_cpu_prefetch_cuda')),flush=True)
    torch.cuda.synchronize()
    if not target_count:raise ValueError('Empty reconstruction target cohort')
    return dict(mse=float(totals[0]/target_count),mae=float(totals[1]/target_count),
        mean_reference_mse=float(totals[2]/target_count),seed_nodes_visited=visited,
        target_node_count=target_count//len(scaler['means']),seconds=time.perf_counter()-started)
