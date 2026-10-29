"""Export and reuse the frozen label-free model for standalone offline scoring.

Consumes named native actor-window aggregates, never raw logs or security labels.
Scores are normalized reconstruction errors, not attack predictions.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
from time import perf_counter

import torch

from research.ml.label_free.model import ActivityAutoencoder, state_digest
from research.ml.label_free.runtime import configure_runtime, runtime_details, synchronize
from research.ml.node_benchmark.audit_protocol import file_hash, text_hash

FILES = ('best.pt', 'config.json', 'run.json', 'evaluation.json', 'feature_schema.json',
         'scaler.json', 'preparation_plan.json', 'preparation_manifest.json',
         'preparation_verification.json')
SOURCE = Path(__file__).parent
CODE = ('model.py', 'runtime.py', 'inference.py')
MAX_ROWS = 10_000
MAX_INPUT_BYTES = 50 * 1024**2


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False)+'\n').encode())


def export_bundle(directory, run_directory, evaluation_path, plan_path, output):
    """Verify the evaluated run before copying a local, data-independent bundle."""
    from research.ml.label_free.error_analysis import load_frozen_model

    if output.exists():
        raise ValueError('Use a fresh bundle output directory')
    run, evaluation, metadata, model, _, _ = load_frozen_model(directory, run_directory, evaluation_path)
    if text_hash(plan_path) != metadata['manifest']['plan_sha256_utf8_lf']:
        raise ValueError('Preparation plan differs from the frozen data')
    paths = [run_directory/'best.pt', run_directory/'config.json', run_directory/'run.json',
             evaluation_path, directory/'feature_schema.json', directory/'scaler.json', plan_path,
             directory/'manifest.json', directory/'verification.json']
    hashes = {name: file_hash(path) for name, path in zip(FILES, paths)}
    output.mkdir(parents=True, exist_ok=False)
    for name, path in zip(FILES, paths):
        shutil.copyfile(path, output/name)
    manifest = dict(version=1, status='frozen_label_free_offline_bundle', files_sha256=hashes,
        code_sha256_utf8_lf={name: text_hash(SOURCE/name) for name in CODE},
        checkpoint_state_sha256=state_digest(model), best_epoch=run['best_epoch'],
        source_run_sha256_utf8_lf=text_hash(run_directory/'run.json'),
        source_evaluation_sha256_utf8_lf=text_hash(evaluation_path),
        required_torch_release=torch.__version__.split('+')[0],
        security_threshold=None, security_labels_assigned=False, production_integration=False,
        input_scope='Named raw actor-window aggregates; host/window contract checked, native evidence not reverified',
        limitations=metadata['manifest']['limitations'] + [
            'Already evaluated and inspected holdout; replay is a reuse check, not a new benchmark',
            'Hashes detect changed artifacts relative to a trusted bundle digest; no digital signature'])
    write_json(output/'bundle.json', manifest)
    # Validate the copied files, cross-artifact bindings and safe CPU reload.
    load_bundle(output, 'cpu', file_hash(output/'bundle.json'))
    if any(file_hash(path) != hashes[name] for name, path in zip(FILES, paths)):
        raise ValueError('An export source changed during copying')
    return dict(bundle_sha256=file_hash(output/'bundle.json'), **manifest)


def load_bundle(directory, device, expected_sha256):
    if device not in ('cpu', 'cuda'):
        raise ValueError('Choose cpu or cuda explicitly')
    if file_hash(directory/'bundle.json') != expected_sha256:
        raise ValueError('Bundle differs from the expected trusted digest')
    bundle = read_json(directory/'bundle.json')
    if (bundle.get('version') != 1 or bundle.get('status') != 'frozen_label_free_offline_bundle'
            or set(bundle['files_sha256']) != set(FILES) or set(bundle['code_sha256_utf8_lf']) != set(CODE)
            or bundle['security_threshold'] is not None or bundle['security_labels_assigned'] is not False
            or bundle['production_integration'] is not False):
        raise ValueError('Unsupported offline reconstruction bundle')
    for name, digest in bundle['files_sha256'].items():
        if file_hash(directory/name) != digest:
            raise ValueError('Bundle artifact changed: '+name)
    for name, digest in bundle['code_sha256_utf8_lf'].items():
        if text_hash(SOURCE/name) != digest:
            raise ValueError('Scoring source differs from the bundle: '+name)
    if torch.__version__.split('+')[0] != bundle['required_torch_release']:
        raise ValueError('Install the bundle PyTorch release (CPU/CUDA build may differ)')
    config, run, evaluation, schema, scaler, plan, prepared, verification = [read_json(directory/name)
        for name in FILES[1:]]
    names = schema['names']; width = config['input_dim']
    if (run.get('full_training_completed') is not True or run.get('mode') != 'full'
            or evaluation.get('status') != 'final_label_free_reconstruction_evaluated'
            or evaluation['weights_updated'] is not False or evaluation['security_threshold'] is not None
            or evaluation['frozen_run_sha256_utf8_lf'] != text_hash(directory/'run.json')
            or bundle['source_run_sha256_utf8_lf'] != text_hash(directory/'run.json')
            or bundle['source_evaluation_sha256_utf8_lf'] != text_hash(directory/'evaluation.json')
            or run['config_sha256_utf8_lf'] != text_hash(directory/'config.json')
            or evaluation['config_sha256_utf8_lf'] != run['config_sha256_utf8_lf']
            or run['checkpoint_sha256'] != bundle['files_sha256']['best.pt']
            or evaluation['checkpoint_sha256'] != run['checkpoint_sha256']
            or run['dataset_manifest_sha256_utf8_lf'] != text_hash(directory/'preparation_manifest.json')
            or evaluation['dataset_manifest_sha256_utf8_lf'] != run['dataset_manifest_sha256_utf8_lf']
            or verification['manifest_sha256_utf8_lf'] != run['dataset_manifest_sha256_utf8_lf']
            or verification.get('status') != 'verified_label_free_preparation'
            or verification['all_security_labels_unknown'] is not True
            or verification['training_only_scaler_recomputed'] is not True
            or prepared['plan_sha256_utf8_lf'] != text_hash(directory/'preparation_plan.json')
            or prepared['scaler_sha256'] != bundle['files_sha256']['scaler.json']
            or prepared['feature_schema_sha256'] != bundle['files_sha256']['feature_schema.json']
            or run['scaler_sha256'] != prepared['scaler_sha256']
            or run['feature_schema_sha256'] != prepared['feature_schema_sha256']
            or config['security_labels_used'] is not False
            or len(names) != width or schema['width'] != width or len(set(names)) != width
            or prepared['feature_names'] != names or schema['security_label_is_predictor'] is not False
            or names != ['event_count']+['count_'+a for a in plan['action_vocabulary']]+[
                'count_unknown_action', 'predicate_reference_count', 'second_predicate_event_count',
                'no_predicate_event_count', 'active_span_seconds']):
        raise ValueError('Bundle provenance or feature contract is inconsistent')
    if (scaler['transform'] != 'log1p_then_training_population_zscore' or scaler['fitted_on'] != 'train_only'
            or scaler['training_samples'] != prepared['partition_sample_counts']['train']
            or len(scaler['means']) != width or len(scaler['standard_deviations']) != width
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in scaler['means'])
            or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                   for v in scaler['standard_deviations'])):
        raise ValueError('Frozen training-only scaler is invalid')
    saved = torch.load(directory/'best.pt', map_location='cpu', weights_only=True)
    if (saved['mode'] != 'full' or saved['best_epoch'] != run['best_epoch']
            or bundle['best_epoch'] != run['best_epoch'] or saved['feature_names'] != names
            or any(saved[key] != run[key] for key in ('config_sha256_utf8_lf',
                'dataset_manifest_sha256_utf8_lf', 'feature_schema_sha256', 'scaler_sha256'))):
        raise ValueError('Checkpoint differs from the frozen reconstruction run')
    runtime_config = dict(config, device=device, matmul_precision='highest', cublas_workspace_config=':4096:8')
    selected = configure_runtime(runtime_config)
    model = ActivityAutoencoder(width, config['hidden_dim'], config['latent_dim']).float().to(selected)
    model.load_state_dict(saved['model_state_dict'], strict=True); model.eval()
    if state_digest(model) != bundle['checkpoint_state_sha256'] or state_digest(model) != run['checkpoint_state_sha256']:
        raise ValueError('Frozen model state differs')
    baseline = saved['training_mean_baseline'].float().to(selected)
    if tuple(baseline.shape) != (width,) or not torch.isfinite(baseline).all():
        raise ValueError('Invalid stored training-mean reference')
    return bundle, model, baseline, selected, names, scaler, plan, prepared


def normalize_row(row, names, scaler, plan):
    required = {'sample_id', 'host_uuid', 'window_nanos', 'raw_features'}
    if (not required <= row.keys() or row.keys()-required-{'security_label'}
            or type(row['sample_id']) is not str or not row['sample_id'] or len(row['sample_id']) > 256
            or row.get('security_label') is not None or row['host_uuid'] != plan['host_uuid']
            or type(row['window_nanos']) is not int or row['window_nanos'] != plan['window_nanos']
            or type(row['raw_features']) is not dict or set(row['raw_features']) != set(names)):
        raise ValueError('Require unique sample identity, frozen host/window, named raw features and unknown label')
    raw = [row['raw_features'][name] for name in names]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in raw):
        raise ValueError('Raw features must be finite nonnegative numbers')
    if any(v > 2**53 or int(v) != v for v in raw[:-1]):
        raise ValueError('Native Event counts must be exact nonnegative integers')
    events, references, second, missing, span = raw[0], *raw[-4:]
    # A second predicate may occur without a first predicate in native records.
    # With only these aggregate features, the feasible reference range is bounded.
    if (events < 1 or sum(raw[1:-4]) != events or second+missing > events
            or not events-missing <= references <= events-missing+second or span >= plan['window_nanos']/1e9
            or (events == 1 and span != 0)):
        raise ValueError('Inconsistent native Event aggregate counts or active span')
    values = [(math.log1p(v)-mean)/std for v, mean, std
              in zip(raw, scaler['means'], scaler['standard_deviations'])]
    if any(not math.isfinite(v) for v in values):
        raise ValueError('Nonfinite normalized input')
    return values


def score(directory, input_path, output, device, expected_sha256, batch_size=256):
    if output.exists() or type(batch_size) is not int or not 1 <= batch_size <= 4096:
        raise ValueError('Use a fresh output directory and batch size from 1 to 4096')
    if input_path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError('Input exceeds the explicit 50 MiB offline scoring limit')
    bundle, model, baseline, selected, names, scaler, plan, _ = load_bundle(directory, device, expected_sha256)
    input_sha = file_hash(input_path); rows = []; vectors = []; seen = set()
    with input_path.open(encoding='utf-8') as stream:
        for line in stream:
            if len(rows) >= MAX_ROWS:
                raise ValueError('Input exceeds the explicit 10000-row offline scoring limit')
            row = json.loads(line); values = normalize_row(row, names, scaler, plan)
            if row['sample_id'] in seen:
                raise ValueError('Duplicate sample identity')
            rows.append(row); vectors.append(values); seen.add(row['sample_id'])
    if not rows:
        raise ValueError('Input must contain at least one row')
    values = torch.tensor(vectors, dtype=torch.float32, device=selected)
    if not torch.isfinite(values).all():
        raise ValueError('Float32 normalization overflowed')
    synchronize(selected); started = perf_counter(); scored = []
    with torch.inference_mode():
        for offset in range(0, len(rows), batch_size):
            batch = values[offset:offset+batch_size]; residual = model(batch)-batch
            metrics = torch.stack((residual.square().mean(1), residual.abs().mean(1),
                                   (batch-baseline).square().mean(1)), dim=1).cpu().tolist()
            for row, (mse, mae, reference) in zip(rows[offset:offset+batch_size], metrics):
                if any(not math.isfinite(v) for v in (mse, mae, reference)):
                    raise ValueError('Nonfinite reconstruction score')
                scored.append(dict(sample_id=row['sample_id'], reconstruction_mse=mse,
                    reconstruction_mae=mae, training_mean_baseline_mse=reference,
                    security_label=None, security_threshold=None))
    synchronize(selected); elapsed = perf_counter()-started
    if (file_hash(input_path) != input_sha or state_digest(model) != bundle['checkpoint_state_sha256']
            or file_hash(directory/'bundle.json') != expected_sha256
            or any(file_hash(directory/name) != digest for name, digest in bundle['files_sha256'].items())):
        raise ValueError('Input, bundle or frozen model changed during scoring')
    report = dict(status='standalone_label_free_scoring_complete', input_sha256=input_sha,
        bundle_sha256=expected_sha256, checkpoint_state_sha256=state_digest(model), rows=len(rows),
        feature_count=len(names), batch_size=batch_size, torch_version=torch.__version__,
        device=str(selected), model_parameter_device=str(next(model.parameters()).device),
        runtime=runtime_details(selected), scoring_seconds_including_row_metrics=elapsed,
        reconstruction_mse=math.fsum(r['reconstruction_mse'] for r in scored)/len(rows),
        reconstruction_mae=math.fsum(r['reconstruction_mae'] for r in scored)/len(rows),
        weights_updated=False, preprocessing_refit=False, security_labels_assigned=False,
        security_threshold=None, attack_detection_metrics_available=False,
        native_source_evidence_reverified=False, production_integration=False,
        limitations=bundle['limitations'])
    output.mkdir(parents=True, exist_ok=False)
    (output/'scores.jsonl').write_bytes(''.join(json.dumps(row, allow_nan=False)+'\n' for row in scored).encode())
    report['scores_sha256'] = file_hash(output/'scores.jsonl')
    write_json(output/'summary.json', report)
    return report


def replay_input(data, directory, role, output, expected_sha256):
    """Convert already verified prepared rows to the named-input contract."""
    if role not in ('train', 'development', 'holdout') or output.exists():
        raise ValueError('Choose a prepared partition and a fresh replay input path')
    _, _, _, _, names, scaler, plan, prepared = load_bundle(directory, 'cpu', expected_sha256)
    path = data/(role+'.jsonl'); before = file_hash(path)
    if before != prepared['partition_file_sha256'][role]:
        raise ValueError('Replay partition differs from the frozen preparation')
    result = []
    for line in path.read_text(encoding='utf-8').splitlines():
        original = json.loads(line); trace = original['trace']
        if len(original['raw_features']) != len(names) or trace['window_end_nanos']-trace['window_start_nanos'] != plan['window_nanos']:
            raise ValueError('Prepared replay feature/window mismatch')
        row = dict(sample_id=original['sample_id'], host_uuid=trace['host_uuid'],
            window_nanos=plan['window_nanos'], raw_features=dict(zip(names, original['raw_features'])),
            security_label=original['security_label'])
        normalized = normalize_row(row, names, scaler, plan)
        if normalized != original['features']:
            raise ValueError('Frozen normalization does not exactly reproduce the prepared vector')
        result.append(row)
    if len(result) != prepared['partition_sample_counts'][role] or file_hash(path) != before:
        raise ValueError('Replay input changed or has an unexpected row count')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(''.join(json.dumps(row, allow_nan=False)+'\n' for row in result).encode())
    return dict(rows=len(result), partition=role, input_sha256=file_hash(output),
                purpose='Already scored data replay, not new evaluation evidence')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser('export')
    for name in ('data', 'run', 'evaluation', 'plan', 'output'):
        export.add_argument('--'+name, type=Path, required=True)
    replay = commands.add_parser('replay-input')
    replay.add_argument('--data', type=Path, required=True)
    replay.add_argument('--partition', choices=('train', 'development', 'holdout'), required=True)
    scoring = commands.add_parser('score')
    scoring.add_argument('--input', type=Path, required=True)
    scoring.add_argument('--device', choices=('cpu', 'cuda'), required=True)
    scoring.add_argument('--batch-size', type=int, default=256)
    for command in (replay, scoring):
        command.add_argument('--bundle', type=Path, required=True)
        command.add_argument('--expected-bundle-sha256', required=True)
        command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'export':
        report = export_bundle(args.data, args.run, args.evaluation, args.plan, args.output)
        report = dict(status=report['status'], bundle_sha256=report['bundle_sha256'])
    elif args.command == 'replay-input':
        report = replay_input(args.data, args.bundle, args.partition, args.output, args.expected_bundle_sha256)
    else:
        report = score(args.bundle, args.input, args.output, args.device, args.expected_bundle_sha256, args.batch_size)
    print(json.dumps(report, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
