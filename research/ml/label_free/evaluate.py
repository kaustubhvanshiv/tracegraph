"""Explicit frozen full-run holdout reconstruction evaluation; never trains."""
import argparse
import json
from pathlib import Path

import torch

from research.ml.label_free.model import ActivityAutoencoder, baseline_metrics, reconstruction_metrics, state_digest
from research.ml.label_free.training_data import partition, snapshot
from research.ml.node_benchmark.audit_protocol import file_hash, text_hash


def evaluate(directory, run_directory, output):
    if output.exists():
        raise ValueError('Use a fresh final evaluation report path')
    run_path = run_directory/'run.json'
    run = json.loads(run_path.read_text(encoding='utf-8'))
    # Check before loading any dataset vectors, including before a holdout hash.
    if run.get('status') != 'full_training_complete_holdout_not_evaluated' or run.get('full_training_completed') is not True:
        raise ValueError('Holdout evaluation requires a completed full run, never a readiness smoke checkpoint')
    config_path = run_directory/'config.json'
    if text_hash(config_path) != run['config_sha256_utf8_lf']:
        raise ValueError('Frozen training configuration changed')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    metadata = snapshot(directory,config)
    for name,digest in run['code_sha256_utf8_lf'].items():
        if name not in ('model.py','training_data.py','train.py') or text_hash(Path(__file__).parent/name) != digest:
            raise ValueError('Training code changed since the checkpoint was frozen')
    checkpoint = run_directory/'best.pt'
    if file_hash(checkpoint) != run['checkpoint_sha256']:
        raise ValueError('Selected checkpoint fingerprint changed')
    saved = torch.load(checkpoint,map_location='cpu',weights_only=True)
    if (saved['mode'] != 'full' or saved['config_sha256_utf8_lf'] != run['config_sha256_utf8_lf']
            or saved['dataset_manifest_sha256_utf8_lf'] != metadata['manifest_sha256_utf8_lf']
            or saved['feature_schema_sha256'] != metadata['manifest']['feature_schema_sha256']
            or saved['scaler_sha256'] != metadata['manifest']['scaler_sha256']
            or saved['feature_names'] != metadata['feature_names'] or saved['best_epoch'] != run['best_epoch']):
        raise ValueError('Checkpoint, feature order or frozen data provenance differs')
    model = ActivityAutoencoder(config['input_dim'],config['hidden_dim'],config['latent_dim']).float()
    model.load_state_dict(saved['model_state_dict'],strict=True)
    if state_digest(model) != run['checkpoint_state_sha256']:
        raise ValueError('Selected model weights differ from the training report')
    torch.set_num_threads(config['cpu_threads']);torch.use_deterministic_algorithms(True)
    heldout,_,_ = partition(directory,metadata,'holdout')
    model_metrics = reconstruction_metrics(model,heldout)
    baseline = baseline_metrics(saved['training_mean_baseline'],heldout)
    result = dict(status='final_label_free_reconstruction_evaluated',
        frozen_run_sha256_utf8_lf=text_hash(run_path),checkpoint_sha256=run['checkpoint_sha256'],
        config_sha256_utf8_lf=run['config_sha256_utf8_lf'],dataset_manifest_sha256_utf8_lf=metadata['manifest_sha256_utf8_lf'],
        evaluator_sha256_utf8_lf=text_hash(Path(__file__)),holdout_samples=len(heldout),
        reconstruction_metrics=model_metrics,training_mean_baseline_metrics=baseline,
        mse_improvement_over_mean_baseline=baseline['mse']-model_metrics['mse'],
        holdout_used_for_checkpoint_selection=False,weights_updated=False,security_labels_used=False,
        attack_detection_metrics_available=False,security_threshold=None,
        limitations=metadata['manifest']['limitations'])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data','run','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.data,args.run,args.output)),flush=True)


if __name__=='__main__':
    main()
