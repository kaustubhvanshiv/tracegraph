"""Post-evaluation reconstruction diagnostics for a frozen, already scored model.

Produces numerical residual summaries and local evidence-review rows. It never
trains, changes settings, chooses thresholds or assigns security labels.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3

import torch

from research.ml.label_free.model import ActivityAutoencoder,residual_metrics,state_digest
from research.ml.label_free.runtime import configure_runtime,runtime_details
from research.ml.label_free.training_data import partition,snapshot
from research.ml.node_benchmark.audit_protocol import file_hash,text_hash

ROLES=('train','development','holdout')


def quantile(values, fraction):
    if not values or not 0 <= fraction <= 1 or any(not math.isfinite(v) for v in values):
        raise ValueError('Quantiles need finite values and a fraction from zero to one')
    values=sorted(values);position=(len(values)-1)*fraction
    lower=int(position);upper=min(lower+1,len(values)-1)
    return values[lower]+(values[upper]-values[lower])*(position-lower)


def distribution(values):
    return dict(count=len(values),mean=math.fsum(values)/len(values),
        min=min(values),p25=quantile(values,.25),median=quantile(values,.5),p75=quantile(values,.75),
        p90=quantile(values,.9),p95=quantile(values,.95),p99=quantile(values,.99),max=max(values))


def summarize(squared, absolute, names):
    width=len(names)
    if (not squared or len(squared)!=len(absolute) or not width or len(names)!=len(set(names))
            or any(len(row)!=width for row in squared+absolute)
            or any(not math.isfinite(v) or v<0 for row in squared+absolute for v in row)):
        raise ValueError('Residual matrices must be finite, nonnegative and match the unique feature schema')
    row_mse=[math.fsum(row)/width for row in squared]
    row_mae=[math.fsum(row)/width for row in absolute]
    totals=[math.fsum(row[i] for row in squared) for i in range(width)]
    total=math.fsum(totals)
    features=[dict(feature=name,mse=totals[i]/len(squared),
        mae=math.fsum(row[i] for row in absolute)/len(absolute),
        squared_error_share=totals[i]/total if total else 0.) for i,name in enumerate(names)]
    features.sort(key=lambda f:(-f['squared_error_share'],f['feature']))
    errors=sorted(row_mse,reverse=True);error_total=math.fsum(errors)
    tail={str(k):math.fsum(errors[:min(k,len(errors))])/error_total if error_total else 0.
          for k in (1,5,10)}
    return dict(sample_mse=distribution(row_mse),sample_mae=distribution(row_mae),
        quantile_method='linear interpolation at (n-1)*q; descriptive, not security thresholds',
        features=features,largest_sample_error_shares=tail),row_mse,row_mae


def profile_key(row):
    return hashlib.sha256(json.dumps(row['raw_features'],sort_keys=True,separators=(',',':')).encode()).hexdigest()


def profile_groups(rows, scores, training_profiles):
    groups={name:[] for name in ('exact_raw_profile_seen_in_training','exact_raw_profile_unseen_in_training')}
    for row,score in zip(rows,scores):
        name='exact_raw_profile_seen_in_training' if profile_key(row) in training_profiles else 'exact_raw_profile_unseen_in_training'
        groups[name].append(score)
    return {name:dict(rows=len(values),mean_mse=math.fsum(values)/len(values) if values else None,
                     median_mse=quantile(values,.5) if values else None) for name,values in groups.items()}


def witness_evidence(db, trace, windows):
    indices=[w['index'] for w in windows if (w['start_nanos'],w['end_nanos'])==
             (trace['window_start_nanos'],trace['window_end_nanos'])]
    row=db.execute('SELECT actor,window_idx,ts,source_file,record_idx,conflict,action,fingerprint '
        'FROM events WHERE host=? AND uuid=?',(trace['host_uuid'],trace['witness_event_uuid'])).fetchone()
    if (len(indices)!=1 or row is None or row[:6]!=(trace['subject_uuid'],indices[0],trace['first_event_nanos'],
            trace['witness_source_file'],trace['witness_record_index_1based'],0)):
        raise ValueError('Review witness does not match the native Event index')
    return dict(event_uuid=trace['witness_event_uuid'],action=row[6],timestamp_nanos=row[2],
        source_file=row[3],record_index_1based=row[4],raw_record_sha256=bytes(row[7]).hex(),
        evidence_scope='Saved native Event index; not a new raw-archive reread or security-intent annotation')


def load_frozen_model(directory,run_directory,evaluation_path):
    run_path=run_directory/'run.json';run=json.loads(run_path.read_text(encoding='utf-8'))
    evaluation=json.loads(evaluation_path.read_text(encoding='utf-8'))
    if (run.get('full_training_completed') is not True
            or evaluation.get('status')!='final_label_free_reconstruction_evaluated'
            or evaluation['frozen_run_sha256_utf8_lf']!=text_hash(run_path)
            or evaluation['checkpoint_sha256']!=run['checkpoint_sha256']):
        raise ValueError('Diagnostics require a frozen full run and its completed final evaluation')
    config_path=run_directory/'config.json'
    if text_hash(config_path)!=run['config_sha256_utf8_lf'] or evaluation['config_sha256_utf8_lf']!=run['config_sha256_utf8_lf']:
        raise ValueError('Frozen configuration changed')
    config=json.loads(config_path.read_text(encoding='utf-8'));metadata=snapshot(directory,config)
    for name,digest in run['code_sha256_utf8_lf'].items():
        if name not in ('model.py','training_data.py','train.py','runtime.py') or text_hash(Path(__file__).parent/name)!=digest:
            raise ValueError('Model/training code differs from the evaluated snapshot')
    if evaluation['evaluator_sha256_utf8_lf']!=text_hash(Path(__file__).parent/'evaluate.py'):
        raise ValueError('Final evaluator source changed')
    checkpoint_path=run_directory/'best.pt'
    if file_hash(checkpoint_path)!=run['checkpoint_sha256']:
        raise ValueError('Frozen checkpoint changed')
    saved=torch.load(checkpoint_path,map_location='cpu',weights_only=True)
    if (saved['mode']!='full' or saved['config_sha256_utf8_lf']!=run['config_sha256_utf8_lf']
            or saved['dataset_manifest_sha256_utf8_lf']!=metadata['manifest_sha256_utf8_lf']
            or saved['feature_names']!=metadata['feature_names'] or saved['best_epoch']!=run['best_epoch']
            or evaluation['dataset_manifest_sha256_utf8_lf']!=metadata['manifest_sha256_utf8_lf']):
        raise ValueError('Checkpoint/data/feature provenance does not match the completed evaluation')
    device=configure_runtime(config)
    model=ActivityAutoencoder(config['input_dim'],config['hidden_dim'],config['latent_dim']).float().to(device)
    model.load_state_dict(saved['model_state_dict'],strict=True);model.eval()
    if state_digest(model)!=run['checkpoint_state_sha256']:
        raise ValueError('Evaluated model state changed')
    return run,evaluation,metadata,model,saved['training_mean_baseline'].to(device),device


def analyze(directory,run_directory,evaluation_path,output,review_budget=10):
    if output.exists() or type(review_budget) is not int or review_budget<1:
        raise ValueError('Use a fresh analysis output directory and a positive review budget')
    run,evaluation,metadata,model,baseline,device=load_frozen_model(directory,run_directory,evaluation_path)
    index_path=directory/'events.sqlite';index_sha=file_hash(index_path)
    names=metadata['feature_names'];training_profiles=None;report_roles={};queue=[]
    for role in ROLES:
        values,_,_=partition(directory,metadata,role);values=values.to(device)
        rows=[json.loads(line) for line in (directory/(role+'.jsonl')).read_text(encoding='utf-8').splitlines()]
        if role=='train':training_profiles={profile_key(row) for row in rows}
        with torch.inference_mode():
            predictions=model(values);residual=predictions-values;reference=values-baseline
            measured=residual_metrics(residual);reference_measured=residual_metrics(reference)
            squared=residual.square().cpu().tolist();absolute=residual.abs().cpu().tolist()
            predictions=predictions.cpu().tolist();reference_rows=reference.square().mean(dim=1).cpu().tolist()
        expected=evaluation['reconstruction_metrics'] if role=='holdout' else run['selected_checkpoint_metrics'][role]
        expected_reference=evaluation['training_mean_baseline_metrics'] if role=='holdout' else run['baseline_metrics'][role]
        if any(not math.isclose(measured[k],expected[k],rel_tol=1e-6,abs_tol=1e-8)
               or not math.isclose(reference_measured[k],expected_reference[k],rel_tol=1e-6,abs_tol=1e-8) for k in ('mse','mae')):
            raise ValueError('Post-evaluation residuals do not reproduce the frozen aggregate metrics')
        summary,scores,mae=summarize(squared,absolute,names)
        comparisons=dict(autoencoder_lower_mse=0,mean_baseline_lower_mse=0,tied_mse=0)
        for actual,ref in zip(scores,reference_rows):
            key='tied_mse' if math.isclose(actual,ref,rel_tol=1e-6,abs_tol=1e-9) else (
                'autoencoder_lower_mse' if actual<ref else 'mean_baseline_lower_mse')
            comparisons[key]+=1
        summary.update(aggregate_metrics=measured,mean_baseline_metrics=reference_measured,
            per_sample_baseline_comparison=comparisons,
            exact_raw_profile_groups=profile_groups(rows,scores,training_profiles))
        report_roles[role]=summary
        order=sorted(range(len(rows)),key=lambda i:(-scores[i],rows[i]['sample_id']))[:review_budget]
        with closing(sqlite3.connect(index_path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            for rank,i in enumerate(order,1):
                row=rows[i]
                top=sorted(range(len(names)),key=lambda j:(-squared[i][j],names[j]))[:5]
                queue.append(dict(partition=role,rank=rank,sample_id=row['sample_id'],security_label=None,
                    reconstruction_mse=scores[i],reconstruction_mae=mae[i],mean_baseline_mse=reference_rows[i],
                    trace=row['trace'],witness=witness_evidence(db,row['trace'],metadata['manifest']['windows']),
                    largest_residual_features=[dict(feature=names[j],raw_observation=row['raw_features'][j],
                        normalized_observation=row['features'][j],normalized_reconstruction=predictions[i][j],
                        squared_residual=squared[i][j]) for j in top],
                    interpretation='Numerical reconstruction residual for review, not an attack classification',
                    security_threshold=None,review_status='independent_security_evidence_required'))
    if file_hash(index_path)!=index_sha or state_digest(model)!=run['checkpoint_state_sha256']:
        raise ValueError('Model state or native evidence index changed during analysis')
    if file_hash(run_directory/'best.pt')!=run['checkpoint_sha256']:
        raise ValueError('Frozen checkpoint file changed during analysis')
    for role in ROLES:
        if file_hash(directory/(role+'.jsonl'))!=metadata['manifest']['partition_file_sha256'][role]:
            raise ValueError('Prepared data changed during analysis')
    output.mkdir(parents=True)
    queue_path=output/'review_queue.jsonl'
    queue_path.write_bytes(b''.join((json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode() for row in queue))
    result=dict(status='frozen_post_evaluation_error_analysis_complete',analysis_code_sha256_utf8_lf=text_hash(Path(__file__)),
        frozen_run_sha256_utf8_lf=text_hash(run_directory/'run.json'),final_evaluation_sha256_utf8_lf=text_hash(evaluation_path),
        checkpoint_sha256=run['checkpoint_sha256'],checkpoint_state_sha256=run['checkpoint_state_sha256'],
        dataset_manifest_sha256_utf8_lf=metadata['manifest_sha256_utf8_lf'],native_event_index_sha256=index_sha,
        partition_rows={r:report_roles[r]['sample_mse']['count'] for r in ROLES},
        review_budget_per_partition=review_budget,review_queue_rows=len(queue),review_queue_sha256=file_hash(queue_path),
        partitions=report_roles,runtime=runtime_details(device),weights_updated=False,configuration_changed=False,
        preprocessing_refit=False,security_labels_assigned=False,security_threshold=None,
        original_supervised_tasks_completed=False,production_integration_performed=False,
        interpretation_limits=['Post-evaluation diagnostics; the holdout is already evaluated, not fresh tuning data',
            'Residual contributions are numerical error decomposition, not causal feature importance',
            'High or low reconstruction error does not establish attack/benign intent',
            'A native witness verifies identity/time/source, not intent or all actions in a window',
            'Exact raw profile overlap is a narrow descriptor; lack of it does not prove context/incident independence'])
    (output/'analysis.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('data','run','evaluation','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--review-budget',type=int,default=10)
    args=parser.parse_args()
    report=analyze(args.data,args.run,args.evaluation,args.output,args.review_budget)
    print(json.dumps({k:report[k] for k in ('status','partition_rows','review_queue_rows','weights_updated','security_labels_assigned')}),flush=True)


if __name__=='__main__':
    main()
