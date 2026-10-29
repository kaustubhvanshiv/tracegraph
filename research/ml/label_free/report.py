"""Rebuild the recorded pilot's results table from linked public evidence.

Reads aggregate JSON reports only. Does not read model weights or sample rows,
train, assign security labels, or perform a new model evaluation.
"""
import argparse
import json
import math
from pathlib import Path

from research.ml.node_benchmark.audit_protocol import text_hash

ARTIFACTS = {
    'plan': 'preparation_plan_20261029.json',
    'preparation': 'preparation_report_20261029.json',
    'verification': 'verification_report_20261029.json',
    'training': 'gpu_training_report_20261029.json',
    'evaluation': 'gpu_holdout_report_20261029.json',
    'repeatability': 'gpu_reproducibility_report_20261029.json',
    'analysis': 'error_analysis_report_20261029.json',
    'reuse': 'offline_scoring_report_20261029.json',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def build_report(directory, config_path, output):
    require(not output.exists(), 'Use a fresh report output directory')
    paths = {key: directory/name for key, name in ARTIFACTS.items()}
    hashes = {key: text_hash(path) for key, path in paths.items()}
    docs = {key: json.loads(path.read_text(encoding='utf-8')) for key, path in paths.items()}
    plan, prepared, verified, run, evaluation, repeated, analysis, reuse = [docs[key] for key in ARTIFACTS]
    config = json.loads(config_path.read_text(encoding='utf-8'))
    require(prepared['status']=='complete_label_free_preparation_not_trained'
        and verified['status']=='verified_label_free_preparation'
        and run['full_training_completed'] is True and run['mode']=='full'
        and evaluation['status']=='final_label_free_reconstruction_evaluated'
        and analysis['status']=='frozen_post_evaluation_error_analysis_complete'
        and reuse['status']=='frozen_offline_scoring_reuse_verified', 'Incomplete source milestone')
    require(prepared['plan_sha256_utf8_lf']==hashes['plan']==verified['plan_sha256_utf8_lf']
        and verified['manifest_sha256_utf8_lf']==hashes['preparation']
        and run['dataset_manifest_sha256_utf8_lf']==hashes['preparation']
        and config['dataset_manifest_sha256_utf8_lf']==hashes['preparation']
        and config['dataset_verification_sha256_utf8_lf']==hashes['verification']
        and evaluation['dataset_manifest_sha256_utf8_lf']==hashes['preparation']
        and analysis['dataset_manifest_sha256_utf8_lf']==hashes['preparation']
        and evaluation['frozen_run_sha256_utf8_lf']==hashes['training']==analysis['frozen_run_sha256_utf8_lf']
        and reuse['source_run_sha256_utf8_lf']==hashes['training']
        and analysis['final_evaluation_sha256_utf8_lf']==hashes['evaluation']==reuse['source_evaluation_sha256_utf8_lf']
        and run['config_sha256_utf8_lf']==text_hash(config_path)==evaluation['config_sha256_utf8_lf'],
        'Source report, dataset or configuration fingerprint mismatch')
    require(all(doc['checkpoint_sha256']==run['checkpoint_sha256'] for doc in (evaluation, analysis, reuse))
        and all(doc['checkpoint_state_sha256']==run['checkpoint_state_sha256'] for doc in (analysis, reuse, repeated))
        and repeated['status']=='gpu_full_run_reproducibility_verified'
        and repeated['exact_loss_history_match'] is True and repeated['exact_checkpoint_state_match'] is True
        and repeated['best_epoch']==run['best_epoch'], 'Frozen checkpoint or repeatability mismatch')
    require(run['security_labels_used'] is False and run['holdout_vectors_read'] is False
        and evaluation['holdout_used_for_checkpoint_selection'] is False
        and evaluation['weights_updated'] is False and evaluation['security_labels_used'] is False
        and evaluation['security_threshold'] is None and verified['all_security_labels_unknown'] is True
        and verified['training_only_scaler_recomputed'] is True
        and config['objective']=='normalized_activity_reconstruction'
        and config['security_labels_used'] is False
        and all(doc['security_labels_assigned'] is False and doc['weights_updated'] is False
                and doc['preprocessing_refit'] is False and doc['security_threshold'] is None
                for doc in (analysis, reuse)), 'Security-label, training or preprocessing contract differs')
    counts = dict(run['partition_samples'], holdout=evaluation['holdout_samples'])
    require(counts==prepared['partition_sample_counts']==verified['partition_sample_counts']==analysis['partition_rows']
        and config['input_dim']==prepared['feature_count']==verified['feature_count'], 'Sample counts or feature width differ')
    rows = []
    for role, count in counts.items():
        model = evaluation['reconstruction_metrics'] if role=='holdout' else run['selected_checkpoint_metrics'][role]
        baseline = evaluation['training_mean_baseline_metrics'] if role=='holdout' else run['baseline_metrics'][role]
        for kind, metrics in (('aggregate_metrics', model), ('mean_baseline_metrics', baseline)):
            for metric in ('mse', 'mae'):
                value = metrics[metric]
                require(type(value) in (int, float) and math.isfinite(value) and value>=0, 'Invalid numerical metric')
                require(math.isclose(value, analysis['partitions'][role][kind][metric], rel_tol=2e-6, abs_tol=1e-7),
                        'Analysis metrics differ from the frozen evaluation')
        require(reuse['replay_partitions'][role]['rows']==count, 'Replay sample count differs')
        for device in ('cpu', 'cuda'):
            for metric in ('mse', 'mae'):
                require(math.isclose(model[metric], reuse['replay_partitions'][role][device+'_'+metric],
                                     rel_tol=2e-6, abs_tol=1e-7), 'Replay metrics differ from frozen results')
        rows.append(dict(partition=role, rows=count, autoencoder=dict(model), training_mean_reference=dict(baseline)))
    result = dict(status='linked_label_free_experiment_summary_verified', objective=config['objective'],
        model='feedforward_autoencoder', architecture=[config['input_dim'], config['hidden_dim'],
            config['latent_dim'], config['hidden_dim'], config['input_dim']],
        parameter_count=run['parameter_count'], optimizer=config['optimizer'], learning_rate=config['learning_rate'],
        weight_decay=config['weight_decay'], batch_size=config['batch_size'], seed=config['seed'],
        epochs=run['epochs_completed'], best_epoch=run['best_epoch'], host_uuid=plan['host_uuid'],
        window_nanos=plan['window_nanos'], total_rows=sum(counts.values()), results=rows,
        source_reports_sha256_utf8_lf=hashes, configuration_sha256_utf8_lf=text_hash(config_path),
        checkpoint_sha256=run['checkpoint_sha256'], checkpoint_state_sha256=run['checkpoint_state_sha256'],
        holdout_mse_reduction_against_mean_reference=1-evaluation['reconstruction_metrics']['mse']/evaluation['training_mean_baseline_metrics']['mse'],
        scope='Existing limited same-host/day vector reconstruction experiment; not a new evaluation',
        software_checks_from_reuse_milestone=reuse['software_tests'],
        original_supervised_task_complete=False, gnn_experiment_complete=False,
        attack_detection_metrics_available=False, security_threshold=None, production_integration=False)
    table = ['# Frozen reconstruction results', '',
        '| Partition | Rows | Autoencoder MSE | Autoencoder MAE | Mean reference MSE | Mean reference MAE |',
        '|---|---:|---:|---:|---:|---:|']
    for row in rows:
        model, baseline = row['autoencoder'], row['training_mean_reference']
        table.append(f"| {row['partition']} | {row['rows']:,} | {model['mse']:.9f} | {model['mae']:.9f} | {baseline['mse']:.9f} | {baseline['mae']:.9f} |")
    table += ['', 'MSE/MAE average errors in normalized feature space. These are the original frozen',
        'results, not replay-rounded replacements or attack-detection metrics. The mean',
        'reference is fitted on training only. No rule/GNN security comparison is claimed.', '']
    require(all(text_hash(paths[key])==digest for key, digest in hashes.items())
            and text_hash(config_path)==result['configuration_sha256_utf8_lf'], 'Source changed during reporting')
    output.mkdir(parents=True, exist_ok=False)
    (output/'summary.json').write_bytes((json.dumps(result, indent=2, allow_nan=False)+'\n').encode())
    (output/'results_table.md').write_bytes('\n'.join(table).encode())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reports', 'config', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    result = build_report(args.reports, args.config, args.output)
    print(json.dumps(dict(status=result['status'], rows=result['total_rows'], best_epoch=result['best_epoch'])), flush=True)


if __name__=='__main__':
    main()
