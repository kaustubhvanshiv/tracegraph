"""Export and verify a small trusted inference bundle; never train or refit."""
import json
import os
from pathlib import Path
import shutil
import sys
import numpy as np
import torch
import torch_geometric
from research.ml.gnn_full.model import GraphReconstructor
from research.ml.label_free.model import state_digest
from research.ml.node_benchmark.audit_protocol import file_hash,text_hash

KIND='darpa_graphsage_masked_reconstruction_v1'
WIDTH=115
FILES=('best.pt','scaler.json','config.json','feature_schema.json','source_run.json','source_test.json','source_verification.json')
ROOT=Path(__file__).resolve().parents[3]


def require(condition,message):
    if not condition:raise ValueError(message)


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def write(path,value):
    path.write_bytes((json.dumps(value,indent=2,allow_nan=False)+'\n').encode())


def code_hashes():
    paths=list(Path(__file__).parent.glob('*.py'))+[ROOT/'research/ml/gnn_full/model.py',
        ROOT/'research/ml/label_free/model.py',ROOT/'research/ml/node_benchmark/audit_protocol.py']
    return {p.relative_to(ROOT).as_posix():text_hash(p) for p in sorted(paths)}


def fresh_output(output,*protected):
    output=output.resolve()
    require(not output.exists(),'Use a fresh output path; existing outputs are preserved')
    for path in protected:
        path=path.resolve()
        require(not (output==path or output.is_relative_to(path) or path.is_relative_to(output)),
                'Output must be separate from protected model and input artifacts')
    return output


def names_for(config):
    actions=config['action_vocabulary']+['UNKNOWN']
    return ['out_ref_'+a for a in actions]+['in_ref_'+a for a in actions]+['subject_no_predicate_event_count']


def validate_metadata(bundle,config,run,test,verification,schema,scaler):
    require(bundle['version']==1 and bundle['weights_updated'] is False and bundle['scaler_refit'] is False
            and bundle['security_threshold'] is None and bundle['attack_detection_metrics_available'] is False,
            'Invalid inference-only bundle contract')
    require(bundle['kind']==KIND and run['family']=='graphsage' and run['epochs_completed']==5,
            'Require completed GraphSAGE reconstruction training')
    require(run['status']=='gnn_training_complete_test_not_read' and test['status']=='frozen_gnn_feature_reconstruction_test_complete',
            'Require completed training and final test receipts')
    require(config==run['config'] and config['task']=='self_supervised_masked_node_feature_reconstruction'
            and config['security_labels_used'] is False,'Invalid reconstruction objective')
    require((config['hidden_dim'],config['latent_dim'],config['batch_size'],config['fanouts'],config['seed'])==(64,32,256,[10,5],42)
            and config['training_mask_probability']==.2,'Frozen architecture or sampling protocol differs')
    require(test['checkpoint_sha256']==run['checkpoint_sha256']==bundle['files_sha256']['best.pt'],
            'Checkpoint provenance mismatch')
    require(verification['status']=='completed_full_local_gnn_artifacts_verified' and
            verification['models']['graphsage']['checkpoint_sha256']==run['checkpoint_sha256'] and
            verification['models']['graphsage']['run_sha256']==bundle['files_sha256']['source_run.json'] and
            verification['models']['graphsage']['test_sha256']==bundle['files_sha256']['source_test.json'],
            'Verified source receipts differ')
    require(run['security_threshold'] is None and test['security_threshold'] is None and
            run['attack_detection_metrics_available'] is False and test['attack_detection_metrics_available'] is False,
            'Security claims are not supported by this scorer')
    require(schema['kind']==KIND and schema['feature_count']==WIDTH and schema['feature_names']==names_for(config)
            and len(set(schema['feature_names']))==WIDTH and schema['window_nanos']==300_000_000_000
            and schema['adjacency']=='undirected_unique_no_native_self_edges' and schema['security_labels_used'] is False,
            'Feature contract differs')
    require(run['code_sha256_utf8_lf']['model.py']==text_hash(ROOT/'research/ml/gnn_full/model.py'),
            'Original model and sampling implementation changed')
    require(schema['source_graph_manifest_sha256']==verification['graph_manifest_sha256']==run['graph_manifest_sha256'],
            'Graph representation binding differs')
    require(bundle['files_sha256']['scaler.json']==run['scaler_sha256']==verification['scaler_sha256'],
            'Scaler fingerprint differs')
    require(scaler['transform']=='log1p_training_population_zscore' and scaler['fitted_on']=='train_only'
            and scaler['node_windows']==verification['partitions']['train']['node_windows'],'Invalid scaler provenance')
    require(len(scaler['means'])==len(scaler['stds'])==WIDTH and np.isfinite(scaler['means']).all()
            and np.isfinite(scaler['stds']).all() and min(scaler['stds'])>0,'Invalid frozen scaler values')
    require(bundle['selected_epoch']==run['best_epoch'] and bundle['parameter_count']==run['parameter_count']==22707,
            'Selected GraphSAGE metadata differs')


def export_bundle(work,verification_path,output):
    output=fresh_output(output,work)
    verification=read(verification_path);run_path=work/'runs/graphsage/run.json';test_path=work/'runs/graphsage/test.json'
    run=read(run_path);test=read(test_path);metadata=read(work/'graphs.json');complete=read(work/'complete.json')
    require(file_hash(work/'complete.json')==verification['complete_sha256'] and
            complete['status']=='all_three_full_local_gnn_experiments_complete','Completed experiment is not verified')
    expected=verification['models']['graphsage']
    require(file_hash(run_path)==expected['run_sha256'] and file_hash(test_path)==expected['test_sha256'] and
            file_hash(work/'runs/graphsage/best.pt')==expected['checkpoint_sha256'],'Frozen source files changed')
    require(file_hash(work/'graphs.json')==verification['graph_manifest_sha256'] and
            file_hash(work/'scaler.json')==verification['scaler_sha256'],'Prepared representation changed')
    require(complete['models']['graphsage']['final_reconstruction_test']==test['metrics'],'Final metric binding differs')
    schema=dict(kind=KIND,feature_count=WIDTH,feature_names=metadata['feature_names'],window_nanos=300_000_000_000,
        adjacency='undirected_unique_no_native_self_edges',node_identity='native_host_uuid_and_entity_uuid',
        source_graph_manifest_sha256=file_hash(work/'graphs.json'),security_labels_used=False)
    require(schema['feature_names']==names_for(run['config']),'Unexpected native feature order')
    output.mkdir(parents=True)
    for name,path in [('best.pt',work/'runs/graphsage/best.pt'),('scaler.json',work/'scaler.json'),
                      ('source_run.json',run_path),('source_test.json',test_path),('source_verification.json',verification_path)]:
        shutil.copyfile(path,output/name)
        require(file_hash(output/name)==file_hash(path),'Bundle copy changed')
    write(output/'config.json',run['config']);write(output/'feature_schema.json',schema)
    bundle=dict(version=1,kind=KIND,files_sha256={name:file_hash(output/name) for name in FILES},
        scoring_code_sha256_utf8_lf=code_hashes(),selected_epoch=run['best_epoch'],parameter_count=run['parameter_count'],
        checkpoint_state_sha256=run['checkpoint_state_sha256'],
        runtime=dict(python_minor='3.11',torch_base='2.15.0',numpy='2.4.6',pyg='2.8.1'),
        weights_updated=False,scaler_refit=False,security_threshold=None,attack_detection_metrics_available=False)
    validate_metadata(bundle,run['config'],run,test,verification,schema,read(output/'scaler.json'))
    write(output/'bundle.json',bundle)
    digest=file_hash(output/'bundle.json')
    load_bundle(output,'cpu',digest)
    return dict(status='frozen_graphsage_bundle_exported',bundle_sha256=digest,files=len(FILES)+1,
        bytes=sum(p.stat().st_size for p in output.iterdir()),checkpoint_sha256=run['checkpoint_sha256'])


def load_bundle(directory,device,expected_sha256):
    require(device in ('cpu','cuda'),'Choose cpu or cuda explicitly')
    require(isinstance(expected_sha256,str) and len(expected_sha256)==64 and
            file_hash(directory/'bundle.json')==expected_sha256,'Bundle does not match the trusted digest')
    bundle=read(directory/'bundle.json')
    require(set(bundle['files_sha256'])==set(FILES),'Unexpected bundle file contract')
    require(bundle['scoring_code_sha256_utf8_lf']==code_hashes(),'Scoring source differs from exported bundle')
    for name in FILES:
        require(file_hash(directory/name)==bundle['files_sha256'][name],'Bundle artifact changed: '+name)
    config=read(directory/'config.json');run=read(directory/'source_run.json');test=read(directory/'source_test.json')
    schema=read(directory/'feature_schema.json');scaler=read(directory/'scaler.json')
    validate_metadata(bundle,config,run,test,read(directory/'source_verification.json'),schema,scaler)
    runtime=bundle['runtime']
    require(f'{sys.version_info.major}.{sys.version_info.minor}'==runtime['python_minor'] and
            torch.__version__.split('+')[0]==runtime['torch_base'] and np.__version__==runtime['numpy'] and
            torch_geometric.__version__==runtime['pyg'],'Scoring runtime differs from supported versions')
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    if device=='cuda':require(torch.cuda.is_available(),'Requested CUDA is unavailable; no silent CPU fallback')
    torch.set_num_threads(4);torch.set_float32_matmul_precision('highest')
    torch.use_deterministic_algorithms(True,warn_only=True)
    saved=torch.load(directory/'best.pt',map_location='cpu',weights_only=True)
    require(saved['family']=='graphsage' and saved['epoch']==run['best_epoch'] and saved['feature_count']==WIDTH and
            saved['config']==config and saved['graph_manifest_sha256']==run['graph_manifest_sha256'] and
            saved['scaler_sha256']==run['scaler_sha256'],'Checkpoint metadata differs')
    model=GraphReconstructor('graphsage',WIDTH)
    model.load_state_dict(saved['state_dict'],strict=True)
    require(state_digest(model)==run['checkpoint_state_sha256']==bundle['checkpoint_state_sha256'],
            'Selected parameter state differs')
    require(sum(p.numel() for p in model.parameters())==bundle['parameter_count'],'Parameter count differs')
    require(all(torch.isfinite(p).all() for p in model.parameters()),'Nonfinite selected parameters')
    model=model.to(device);model.eval();model.requires_grad_(False)
    return bundle,model,schema,scaler
