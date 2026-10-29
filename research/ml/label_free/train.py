"""Train/development only autoencoder execution; holdout is never loaded here."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import random
import shutil

import torch

from research.ml.label_free.model import ActivityAutoencoder, baseline_metrics, reconstruction_metrics, state_digest
from research.ml.label_free.training_data import partition, snapshot
from research.ml.node_benchmark.audit_protocol import file_hash, text_hash


def train(directory, config_path, output, mode):
    if output.exists() or mode not in ('smoke','full'):
        raise ValueError('Use a fresh output directory and an explicit smoke/full mode')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    metadata = snapshot(directory,config)
    training,train_ids,train_actors = partition(directory,metadata,'train')
    development,dev_ids,dev_actors = partition(directory,metadata,'development')
    if train_ids&dev_ids or train_actors&dev_actors:
        raise ValueError('Training and development sample/actor identities overlap')
    random.seed(config['seed']);torch.manual_seed(config['seed'])
    torch.set_num_threads(config['cpu_threads']);torch.use_deterministic_algorithms(True)
    model = ActivityAutoencoder(config['input_dim'],config['hidden_dim'],config['latent_dim']).float()
    optimizer = torch.optim.Adam(model.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'])
    generator = torch.Generator(device='cpu').manual_seed(config['seed'])
    baseline = training.mean(dim=0)
    initial_digest = state_digest(model)
    output.mkdir(parents=True)
    shutil.copyfile(config_path,output/'config.json')
    code_hashes = {name:text_hash(Path(__file__).parent/name) for name in ('model.py','training_data.py','train.py')}
    report = dict(status='running',mode=mode,config_sha256_utf8_lf=text_hash(config_path),code_sha256_utf8_lf=code_hashes,
        dataset_manifest_sha256_utf8_lf=metadata['manifest_sha256_utf8_lf'],
        feature_schema_sha256=metadata['manifest']['feature_schema_sha256'],
        scaler_sha256=metadata['manifest']['scaler_sha256'],seed=config['seed'],
        python_version=platform.python_version(),torch_version=torch.__version__,device='cpu',
        parameter_count=sum(p.numel() for p in model.parameters()),
        partition_samples=dict(train=len(training),development=len(development)),
        security_labels_used=False,holdout_vectors_read=False,holdout_metrics=None,
        attack_detection_metrics_available=False,full_training_completed=False,
        baseline_metrics=dict(train=baseline_metrics(baseline,training),development=baseline_metrics(baseline,development)))
    save_report = lambda:(output/'run.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    save_report()
    checkpoint = output/'best.pt'
    history = []
    def metrics(epoch):
        item = dict(epoch=epoch,train=reconstruction_metrics(model,training),
                    development=reconstruction_metrics(model,development))
        history.append(item)
        (output/'history.jsonl').write_bytes(b''.join((json.dumps(h,sort_keys=True)+'\n').encode() for h in history))
        return item
    def save_checkpoint(epoch,loss):
        torch.save(dict(model_state_dict={k:v.detach().cpu().clone() for k,v in model.state_dict().items()},
            training_mean_baseline=baseline.detach().cpu().clone(),best_epoch=epoch,development_mse=loss,
            mode=mode,config=config,config_sha256_utf8_lf=text_hash(config_path),
            dataset_manifest_sha256_utf8_lf=metadata['manifest_sha256_utf8_lf'],
            feature_schema_sha256=metadata['manifest']['feature_schema_sha256'],
            scaler_sha256=metadata['manifest']['scaler_sha256'],feature_names=metadata['feature_names']),checkpoint)
    try:
        initial = metrics(0)
        best_loss = significant_reference = initial['development']['mse']
        best_epoch,bad_epochs,optimizer_steps = 0,0,0
        save_checkpoint(0,best_loss)
        budget = config['smoke_epochs'] if mode=='smoke' else config['max_epochs']
        for epoch in range(1,budget+1):
            model.train()
            order = torch.randperm(len(training),generator=generator)
            for batch in order.split(config['batch_size']):
                optimizer.zero_grad(set_to_none=True)
                values = training[batch]
                loss = (model(values)-values).square().mean()
                if not torch.isfinite(loss):
                    raise ValueError('Nonfinite training loss')
                loss.backward()
                if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                    raise ValueError('Nonfinite model gradient')
                optimizer.step();optimizer_steps+=1
                if any(not torch.isfinite(p).all() for p in model.parameters()):
                    raise ValueError('Nonfinite model parameter')
            item = metrics(epoch)
            current = item['development']['mse']
            if current < best_loss:
                best_loss,best_epoch = current,epoch;save_checkpoint(epoch,current)
            if current < significant_reference-config['minimum_improvement']:
                significant_reference,bad_epochs = current,0
            else:
                bad_epochs+=1
            if mode=='full' and bad_epochs >= config['patience']:
                break
        updated_digest = state_digest(model)
        if updated_digest == initial_digest or optimizer_steps < 1:
            raise ValueError('Optimizer did not update the model')
        saved = torch.load(checkpoint,map_location='cpu',weights_only=True)
        model.load_state_dict(saved['model_state_dict'],strict=True)
        selected = dict(train=reconstruction_metrics(model,training),development=reconstruction_metrics(model,development))
        if abs(selected['development']['mse']-best_loss)>1e-10:
            raise ValueError('Reloaded checkpoint does not reproduce selected development loss')
        report.update(status='smoke_passed_training_ready' if mode=='smoke' else 'full_training_complete_holdout_not_evaluated',
            full_training_completed=mode=='full',epochs_completed=history[-1]['epoch'],best_epoch=best_epoch,
            optimizer_steps=optimizer_steps,initial_metrics=initial,selected_checkpoint_metrics=selected,
            checkpoint_sha256=file_hash(checkpoint),checkpoint_state_sha256=state_digest(model),
            optimizer_changed_weights=True,checkpoint_reload_verified=True,
            history_sha256=file_hash(output/'history.jsonl'),
            development_mse_improvement_over_mean_baseline=report['baseline_metrics']['development']['mse']-best_loss,
            evaluation_scope='Reconstruction only; unlabeled same-host/day pilot with shared object context',
            threshold_created=False)
        save_report();return report
    except BaseException as error:
        report.update(status='incomplete_failed',error=str(error));save_report();raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('data','config','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--mode',required=True,choices=('smoke','full'))
    args = parser.parse_args()
    print(json.dumps(train(args.data,args.config,args.output,args.mode)),flush=True)


if __name__=='__main__':
    main()
