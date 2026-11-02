"""Verify completed experiment receipts and load every selected checkpoint on CPU."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
import torch
from research.ml.gnn_full.model import GraphReconstructor
from research.ml.gnn_full.prepare import save
from research.ml.gnn_accel.run import validate_profile
from research.ml.label_free.model import state_digest
from research.ml.node_benchmark.audit_protocol import file_hash,text_hash

FAMILIES=('gcn','graphsage','gat')


def require(condition,message):
    if not condition:raise ValueError(message)


def metrics_valid(metrics,rows):
    require(all(math.isfinite(metrics[k]) and metrics[k]>=0 for k in ('mse','mae','mean_reference_mse')),
            'Nonfinite or negative reconstruction metric')
    require(metrics['seed_nodes_visited']==rows and metrics['target_node_count']==rows,'Metric coverage mismatch')


def history_valid(history,report,train_rows,dev_rows):
    require([h['epoch'] for h in history]==list(range(6)),'Incomplete epoch history')
    for h in history:
        metrics_valid(h['development'],dev_rows)
        if h['epoch']:
            tr=h['training']
            require(tr['seed_nodes_visited']==train_rows and 0<tr['target_node_count']<=train_rows,
                    'Training seed coverage mismatch')
            require(all(math.isfinite(tr[k]) and tr[k]>=0 for k in ('mse','mae','mean_reference_mse')),
                    'Invalid training metric')
        else:require(h['training'] is None,'Epoch zero must not train')
    selected=min(history,key=lambda h:h['development']['mse'])
    require(selected['epoch']==report['best_epoch'],'Checkpoint not selected by development MSE')
    for key in ('mse','mae','mean_reference_mse'):
        require(np.isclose(selected['development'][key],report['development'][key],rtol=1e-5,atol=1e-7),
                'Selected development metric mismatch')


def test_valid(test,report,aggregate,rows):
    require(test['status']=='frozen_gnn_feature_reconstruction_test_complete','Incomplete test report')
    require(test['checkpoint_sha256']==report['checkpoint_sha256'],'Test checkpoint mismatch')
    require(test['security_threshold'] is None and test['attack_detection_metrics_available'] is False,
            'Unsupported security claim')
    metrics_valid(test['metrics'],rows)
    require(test['metrics']==aggregate['final_reconstruction_test'],'Aggregate test mismatch')
    require({k:v for k,v in aggregate.items() if k!='final_reconstruction_test'}==report,'Aggregate training report mismatch')


def verify(work,output,source=None):
    root=Path(__file__).resolve().parents[3]
    load=lambda name:json.loads((work/name).read_text(encoding='utf-8'))
    complete=load('complete.json');metadata=load('graphs.json');contract=load('contract.json')
    require(complete['status']=='all_three_full_local_gnn_experiments_complete','No final completion marker')
    require(load('progress.json')['phase']=='complete','Current progress is not complete')
    require(not (work/'failure.json').exists(),'Current failure exists')
    require(set(complete['models'])==set(FAMILIES),'Missing model family')
    require(complete['task']=='self_supervised_masked_node_feature_reconstruction' and
            complete['attack_detection_metrics_available'] is False and complete['security_threshold'] is None,
            'Incorrect target or security claim')
    require(complete['all_local_sources_included'] is True and complete['whole_darpa_release_claimed'] is False,
            'Incorrect coverage claim')
    require(contract['code_sha256_utf8_lf']=={p.name:text_hash(p) for p in (root/'research/ml/gnn_full').glob('*.py')},
            'Frozen original code changed')
    require(contract['config_sha256_utf8_lf']==text_hash(root/'research/ml/gnn_full/config.json'),'Frozen config changed')
    _,profile_sha=validate_profile(work)
    require(profile_sha==complete['execution_profile_sha256'],'Execution profile mismatch')
    graph_sha=file_hash(work/'graphs.json');scaler_sha=file_hash(work/'scaler.json')
    require(metadata['status']=='full_local_graph_preparation_verified' and metadata['feature_count']==115,
            'Unverified graph representation')
    require(metadata['scaler_sha256']==scaler_sha,'Scaler changed')
    scaler=load('scaler.json')
    require(scaler['fitted_on']=='train_only' and len(scaler['means'])==115 and len(scaler['stds'])==115,
            'Invalid scaler contract')
    require(np.isfinite(scaler['means']).all() and np.isfinite(scaler['stds']).all() and min(scaler['stds'])>0,
            'Invalid scaler statistics')
    partitions={role:dict(graphs=sum(g['role']==role for g in metadata['graphs']),
        node_windows=sum(g['nodes'] for g in metadata['graphs'] if g['role']==role),
        native_events=sum(g['native_events'] for g in metadata['graphs'] if g['role']==role))
        for role in ('train','development','test')}
    require(partitions==complete['partitions']==load('preparation_summary.json')['partitions'],'Partition accounting mismatch')
    extraction=load('extraction.json');dedup=load('deduplication.json')
    require(len(extraction['sources'])==complete['local_sources']==37,'Incomplete source coverage')
    require(sum(s['records'] for s in extraction['sources'])==345099571,'Raw record accounting mismatch')
    require(all(s['gzip_exhaustion_verified'] for s in extraction['sources']),'Unverified extraction')
    require(sum(p['native_events'] for p in partitions.values())+metadata['purge_gap_events']==dedup['unique_usable_events'],
            'Event accounting mismatch')
    if source:
        for entry in extraction['sources']:
            item=entry['source'];stat=(source/item['filename']).stat()
            require(stat.st_size==item['compressed_bytes'] and stat.st_mtime_ns==item['modified_time_ns'],
                    'Raw source size or modification time changed')
    for index,graph in enumerate(metadata['graphs']):
        path=(work/graph['file']).resolve()
        require(path.is_relative_to(work.resolve()) and graph['independent_sql_vector_check'],'Invalid graph receipt')
        require(file_hash(path)==graph['sha256'],'Graph fingerprint mismatch')
        if index%200==0:print(json.dumps(dict(phase='verifying_graphs',checked=index,total=len(metadata['graphs']))),flush=True)
    verified={}
    for family in FAMILIES:
        report=load(f'runs/{family}/run.json');history=load(f'runs/{family}/history.json');test=load(f'runs/{family}/test.json')
        require(report['family']==family and report['status']=='gnn_training_complete_test_not_read' and report['epochs_completed']==5,
                'Incomplete model training')
        require(report['config']==contract['config'],'Model configuration differs')
        require(report['graph_manifest_sha256']==graph_sha and report['scaler_sha256']==scaler_sha,'Model input binding mismatch')
        require(report['code_sha256_utf8_lf']=={n:contract['code_sha256_utf8_lf'][n] for n in ('model.py','train.py','prepare.py')},
                'Model code binding mismatch')
        require(report['parameter_device']=='cuda:0' and report['torch_version']==contract['versions']['torch'] and
                report['pyg_version']==contract['versions']['torch-geometric'],'Training runtime binding mismatch')
        history_valid(history,report,partitions['train']['node_windows'],partitions['development']['node_windows'])
        test_valid(test,report,complete['models'][family],partitions['test']['node_windows'])
        checkpoint=work/'runs'/family/'best.pt'
        require(file_hash(checkpoint)==report['checkpoint_sha256'],'Checkpoint file changed')
        saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
        require(saved['family']==family and saved['epoch']==report['best_epoch'] and saved['feature_count']==115,
                'Checkpoint metadata mismatch')
        require(saved['config']==contract['config'] and saved['graph_manifest_sha256']==graph_sha and saved['scaler_sha256']==scaler_sha,
                'Checkpoint provenance mismatch')
        model=GraphReconstructor(family,115);model.load_state_dict(saved['state_dict'],strict=True)
        require(all(torch.isfinite(p).all() for p in model.parameters()),'Nonfinite checkpoint parameters')
        require(state_digest(model)==report['checkpoint_state_sha256'],'Loaded state fingerprint mismatch')
        require(sum(p.numel() for p in model.parameters())==report['parameter_count'],'Parameter count mismatch')
        execution=load(f'runs/{family}/execution.json')
        require(execution['execution_profile_sha256']==profile_sha,'Model execution receipt mismatch')
        verified[family]=dict(checkpoint_sha256=file_hash(checkpoint),state_sha256=state_digest(model),
            run_sha256=file_hash(work/f'runs/{family}/run.json'),test_sha256=file_hash(work/f'runs/{family}/test.json'),
            history_sha256=file_hash(work/f'runs/{family}/history.json'),epochs=5,selected_epoch=report['best_epoch'],
            cpu_strict_reload=True,parameter_count=report['parameter_count'])
    receipt=dict(status='completed_full_local_gnn_artifacts_verified',complete_sha256=file_hash(work/'complete.json'),
        graph_manifest_sha256=graph_sha,scaler_sha256=scaler_sha,execution_profile_sha256=profile_sha,
        graphs_hash_checked=len(metadata['graphs']),sources=37,raw_source_metadata_rechecked=source is not None,
        raw_source_bytes_rehashed=False,partitions=partitions,models=verified,
        security_metrics_available=False,independent_clean_machine_reproduction=False)
    save(output,receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source',type=Path)
    args=parser.parse_args();print(json.dumps(verify(args.work,args.output,args.source)))
