"""Verify pinned inputs and load only the requested numerical partition."""
import json
import math

import torch

from research.ml.node_benchmark.audit_protocol import file_hash, text_hash


def validate_config(config):
    if (config['version'] != 1 or config['objective'] != 'normalized_activity_reconstruction'
            or config['device'] != 'cpu' or config['dtype'] != 'float32'
            or config['optimizer'] != 'adam'
            or config['activation'] != 'relu_hidden_linear_latent_and_output'
            or config['checkpoint_selection'] != 'development_mse_including_initialization'
            or config['security_labels_used'] is not False
            or config['holdout_used_for_training_or_readiness'] is not False):
        raise ValueError('Unsupported or unsafe label-free training contract')
    for key in ('input_dim','hidden_dim','latent_dim','batch_size','max_epochs','smoke_epochs','patience','cpu_threads'):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError('Positive integer setting required: '+key)
    if not config['latent_dim'] < config['hidden_dim'] < config['input_dim']:
        raise ValueError('Require a strictly smaller reconstruction bottleneck')
    if type(config['seed']) is not int or config['seed'] < 0 or config['smoke_epochs'] >= config['max_epochs']:
        raise ValueError('Invalid seed or smoke/full epoch budgets')
    for key in ('learning_rate','weight_decay','minimum_improvement'):
        if type(config[key]) not in (float,int) or not math.isfinite(config[key]) or config[key] < 0:
            raise ValueError('Finite nonnegative optimization setting required: '+key)
    if config['learning_rate'] == 0:
        raise ValueError('Learning rate must be positive')
    if torch.__version__ != config['torch_version']:
        raise ValueError('Install the pinned PyTorch runtime before reproducing this run')


def snapshot(directory, config):
    validate_config(config)
    manifest_path, verification_path = directory/'manifest.json',directory/'verification.json'
    if (text_hash(manifest_path) != config['dataset_manifest_sha256_utf8_lf']
            or text_hash(verification_path) != config['dataset_verification_sha256_utf8_lf']):
        raise ValueError('Dataset or independent verification differs from the pinned configuration')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    verification = json.loads(verification_path.read_text(encoding='utf-8'))
    schema = json.loads((directory/'feature_schema.json').read_text(encoding='utf-8'))
    if (manifest['status'] != 'complete_label_free_preparation_not_trained'
            or verification['status'] != 'verified_label_free_preparation'
            or verification['manifest_sha256_utf8_lf'] != text_hash(manifest_path)
            or verification['all_security_labels_unknown'] is not True
            or verification['training_only_scaler_recomputed'] is not True
            or manifest['feature_count'] != config['input_dim']
            or schema['width'] != config['input_dim'] or len(schema['names']) != config['input_dim']
            or manifest['scaler_fit_on'] != 'train_only'):
        raise ValueError('Prepared input contract or reconstruction feature schema is invalid')
    for name,key in (('feature_schema.json','feature_schema_sha256'),('scaler.json','scaler_sha256')):
        if file_hash(directory/name) != manifest[key]:
            raise ValueError('Frozen preprocessing artifact changed: '+name)
    return dict(manifest=manifest,feature_names=schema['names'],
                manifest_sha256_utf8_lf=text_hash(manifest_path))


def partition(directory, metadata, role):
    if role not in ('train','development','holdout'):
        raise ValueError('Unknown dataset partition')
    manifest = metadata['manifest']
    path = directory/(role+'.jsonl')
    if file_hash(path) != manifest['partition_file_sha256'][role]:
        raise ValueError('Partition fingerprint changed: '+role)
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    if len(rows) != manifest['partition_sample_counts'][role] or not rows:
        raise ValueError('Partition row count changed or is empty')
    vectors, identifiers, actors = [],set(),set()
    for row in rows:
        values,trace = row['features'],row['trace']
        if (row['security_label'] is not None or row['sample_id'] in identifiers
                or len(values) != manifest['feature_count']
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in values)):
            raise ValueError('Invalid vectors, duplicate samples or fabricated security labels')
        bounds = [w for w in manifest['windows'] if w['role']==role
                  and (w['start_nanos'],w['end_nanos'])==(trace['window_start_nanos'],trace['window_end_nanos'])]
        if len(bounds)!=1 or not trace['window_start_nanos'] <= trace['first_event_nanos'] <= trace['last_event_nanos'] < trace['window_end_nanos']:
            raise ValueError('Event context does not fit its declared partition history')
        identifiers.add(row['sample_id']);actors.add((trace['host_uuid'],trace['subject_uuid']))
        vectors.append(values)
    tensor = torch.tensor(vectors,dtype=torch.float32,device='cpu')
    if not torch.isfinite(tensor).all():
        raise ValueError('Float32 conversion overflowed')
    return tensor,identifiers,actors
