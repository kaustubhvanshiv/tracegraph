"""Verify completion of both approved models without training or holdout access."""
import argparse
import json
import math
from pathlib import Path
import torch
from research.ml.label_free.model import ActivityAutoencoder, reconstruction_metrics, state_digest
from research.ml.label_free.runtime import configure_runtime
from research.ml.label_free.training_data import snapshot, partition
from research.ml.node_benchmark.audit_protocol import file_hash, text_hash


def verify(data, ordinary, denoising, output):
    if output.exists(): raise ValueError('Use a fresh completion report path')
    results={}
    for family, directory in (('ordinary_autoencoder',ordinary),('denoising_autoencoder',denoising)):
        runs=[]
        for name in ('full-a','full-b'):
            folder=directory/name
            run=json.loads((folder/'run.json').read_text(encoding='utf-8'))
            config=json.loads((folder/'config.json').read_text(encoding='utf-8'))
            expected=('full_training_complete_holdout_not_evaluated' if family=='ordinary_autoencoder'
                      else 'denoising_full_training_complete_holdout_not_evaluated')
            if (run['status']!=expected or not run['full_training_completed'] or run['mode']!='full'
                    or run['holdout_vectors_read'] is not False or run['security_labels_used'] is not False
                    or run['threshold_created'] is not False
                    or text_hash(folder/'config.json')!=run['config_sha256_utf8_lf']
                    or file_hash(folder/'best.pt')!=run['checkpoint_sha256']
                    or file_hash(folder/'history.jsonl')!=run['history_sha256']):
                raise ValueError('Incomplete or changed training artifacts: '+family+'/'+name)
            if family=='denoising_autoencoder' and (config['mask_probability']!=.2
                    or config['mask_constant_columns'] is not False or config['selection_input']!='clean_development'):
                raise ValueError('Denoising protocol differs from approval')
            for source,digest in run['code_sha256_utf8_lf'].items():
                if Path(source).name!=source or text_hash(Path(__file__).parent/source)!=digest:
                    raise ValueError('Frozen training source differs')
            metadata=snapshot(data,config); device=configure_runtime(config)
            saved=torch.load(folder/'best.pt',map_location='cpu',weights_only=True)
            if saved['config_sha256_utf8_lf']!=run['config_sha256_utf8_lf'] or saved['feature_names']!=metadata['feature_names']:
                raise ValueError('Saved configuration or feature order differs')
            model=ActivityAutoencoder(config['input_dim'],config['hidden_dim'],config['latent_dim']).to(device)
            model.load_state_dict(saved['model_state_dict'],strict=True)
            if state_digest(model)!=run['checkpoint_state_sha256']:
                raise ValueError('Selected model state changed')
            history=[json.loads(line) for line in (folder/'history.jsonl').read_text(encoding='utf-8').splitlines()]
            if (len(history)!=run['epochs_completed']+1
                    or [h['epoch'] for h in history]!=list(range(len(history)))
                    or min(history,key=lambda h:h['development']['mse'])['epoch']!=run['best_epoch']
                    or saved['best_epoch']!=run['best_epoch']):
                raise ValueError('Checkpoint is not the recorded development minimum')
            metrics={}
            for role in ('train','development'):
                values,_,_=partition(data,metadata,role)
                metrics[role]=reconstruction_metrics(model,values.to(device))
                for key,value in metrics[role].items():
                    if not math.isclose(value,run['selected_checkpoint_metrics'][role][key],rel_tol=2e-6,abs_tol=1e-7):
                        raise ValueError('Reloaded metrics do not match frozen results')
            if state_digest(model)!=run['checkpoint_state_sha256'] or file_hash(folder/'best.pt')!=run['checkpoint_sha256']:
                raise ValueError('Weights changed during verification')
            runs.append(dict(run=name,epochs=run['epochs_completed'],best_epoch=run['best_epoch'],
                checkpoint_sha256=run['checkpoint_sha256'],state_sha256=run['checkpoint_state_sha256'],
                history_sha256=run['history_sha256'],config_sha256_utf8_lf=run['config_sha256_utf8_lf'],
                metrics=metrics,parameter_device=str(next(model.parameters()).device)))
        if any(runs[0][key]!=runs[1][key] for key in ('state_sha256','history_sha256','config_sha256_utf8_lf')):
            raise ValueError('Repeated runs differ: '+family)
        results[family]=dict(training_complete=True,repeatability_verified=True,runs=runs)
    report=dict(status='all_approved_two_model_training_verified',models=results,
        verifier_sha256_utf8_lf=text_hash(Path(__file__)),additional_optimization_performed=False,
        holdout_read_by_completion_check=False,new_final_evaluation_performed=False,
        attack_detection_metrics_available=False,security_threshold=None,production_integration=False,
        scope='Two approved label-free vector models; not completion of deferred supervised/GNN training',
        remaining_evaluation='Fresh source-verified cohort needed for a final comparison')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('data','ordinary','denoising','output'): parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    result=verify(args.data,args.ordinary,args.denoising,args.output)
    print(json.dumps(dict(status=result['status'],models=list(result['models']))),flush=True)
