"""Rebuild aggregate tables and figures from verified frozen GNN evidence."""
import argparse
import csv
import io
import json
from pathlib import Path
import shutil
import hashlib

FAMILIES=('gcn','graphsage','gat')
LABELS={'gcn':'GCN','graphsage':'GraphSAGE','gat':'GAT'}


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build(work,verification_path,analysis_path,output):
    load=lambda path:json.loads(path.read_text(encoding='utf-8'))
    complete=load(work/'complete.json');verified=load(verification_path);analysis=load(analysis_path)
    if (verified['status']!='completed_full_local_gnn_artifacts_verified' or
        verified['complete_sha256']!=digest(work/'complete.json') or
        analysis['status']!='frozen_full_test_error_analysis_complete' or
        analysis['complete_sha256']!=verified['complete_sha256'] or
        analysis['verification_sha256']!=digest(verification_path)):
        raise ValueError('Reporting requires linked verified completion and error-analysis evidence')
    models={};histories={}
    for family in FAMILIES:
        report=complete['models'][family];test=report['final_reconstruction_test']
        for name in ('run','test','history'):
            filename='history.json' if name=='history' else name+'.json'
            if digest(work/f'runs/{family}/{filename}')!=verified['models'][family][name+'_sha256']:
                raise ValueError('Frozen evidence changed before reporting')
        models[family]=dict(development=report['development'],test=test,
            test_mse_reduction_percent=100*(1-test['mse']/test['mean_reference_mse']),
            parameter_count=report['parameter_count'],selected_epoch=report['best_epoch'],
            epochs_completed=report['epochs_completed'],training_function_seconds=report['elapsed_seconds'],
            checkpoint_sha256=report['checkpoint_sha256'],checkpoint_state_sha256=report['checkpoint_state_sha256'],
            training_execution='bounded_cpu_prefetch_cuda' if family=='gat' else 'original_serial_cuda',
            final_test_execution='bounded_cpu_prefetch_cuda')
        histories[family]=load(work/f'runs/{family}/history.json')
    summary=dict(status='verified_full_local_gnn_comparison_complete',date='2026-11-02',models=models,
        selected_family_by_development_mse=min(models,key=lambda f:models[f]['development']['mse']),
        partitions=complete['partitions'],sources=37,raw_records=345099571,eligible_unique_events=330788968,
        features=115,task=complete['task'],temporal_native_entity_overlap=complete['temporal_native_entity_overlap'],
        complete_sha256=verified['complete_sha256'],graph_manifest_sha256=verified['graph_manifest_sha256'],
        scaler_sha256=verified['scaler_sha256'],execution_profile_sha256=verified['execution_profile_sha256'],
        whole_darpa_release_claimed=False,attack_detection_metrics_available=False,security_threshold=None,
        training_seeds_per_family=1,independent_clean_machine_reproduction=False,
        runtime=dict(gpu=complete['models']['gat']['gpu'],torch=complete['models']['gat']['torch_version'],
                     pyg=complete['models']['gat']['pyg_version']))
    output.mkdir(parents=True,exist_ok=True)
    write=lambda name,value:(output/name).write_bytes((json.dumps(value,indent=2,allow_nan=False)+'\n').encode())
    write('results_20261102.json',summary);write('histories_20261102.json',histories)
    shutil.copyfile(verification_path,output/'verification_20261102.json')
    shutil.copyfile(analysis_path,output/'error_analysis_20261102.json')
    stream=io.StringIO(newline='');writer=csv.writer(stream)
    writer.writerow(['model','selected_epoch','parameters','development_mse','development_mae','test_mse','test_mae','test_mse_reduction_percent'])
    for f,m in models.items():writer.writerow([LABELS[f],m['selected_epoch'],m['parameter_count'],m['development']['mse'],
        m['development']['mae'],m['test']['mse'],m['test']['mae'],m['test_mse_reduction_percent']])
    writer.writerow(['Training mean','','',models['gcn']['development']['mean_reference_mse'],'',models['gcn']['test']['mean_reference_mse'],'',0])
    (output/'comparison_20261102.csv').write_bytes(stream.getvalue().encode())
    lines=['# Full local DARPA reconstruction results','',
        'Verified 2 November 2026. All three models completed five epochs and the same final test cohort.','',
        '| Model | Selected epoch | Parameters | Development MSE | Test MSE | Test MAE | Test MSE reduction vs mean |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for f,m in models.items():lines.append(f"| {LABELS[f]} | {m['selected_epoch']} | {m['parameter_count']:,} | {m['development']['mse']:.9f} | {m['test']['mse']:.9f} | {m['test']['mae']:.9f} | {m['test_mse_reduction_percent']:.2f}% |")
    reference=models['gcn']
    lines+=[f"| Training mean | — | 0 | {reference['development']['mean_reference_mse']:.9f} | {reference['test']['mean_reference_mse']:.9f} | Unrecorded | 0% |",'',
        'GraphSAGE has the lowest development MSE and the lowest observed test MSE/MAE in this run. ',
        'These are normalized masked-feature reconstruction scores. No attack labels, detection accuracy, F1 or security threshold were evaluated.','',
        '![Final test MSE](test_mse_20261102.png)','',
        '![Development curves](development_curves_20261102.png)','',
        '![Top residual features](residual_features_20261102.png)','',
        'The test set contains 2,664,540 node-window rows in 270 graphs. All 37 local archives were included in preparation; ',
        'the complete DARPA release is not claimed. Native entities recur across chronological partitions. ',
        'Five epochs and one seed per family do not establish optimality, uncertainty bounds, or independent incident generalization.','',
        'The ordinary and denoising autoencoder pilots use 62 features and different cohorts. Their MSE values do not form a matched comparison with these GNN results. ',
        'AE–1D-CNN–BiLSTM remains unimplemented/untrained in this experiment.','',
        '## Frozen test residuals','',
        '| Model | Median row MSE | 95th percentile | Maximum row MSE | Top 1% share of squared residual |',
        '|---|---:|---:|---:|---:|']
    for f in FAMILIES:
        r=analysis['models'][f]['row_errors'];lines.append(f"| {LABELS[f]} | {r['median']:.6f} | {r['p95']:.6f} | {r['maximum']:.6f} | {100*r['top_1_percent_squared_error_share']:.2f}% |")
    lines+=['','GraphSAGE has the lowest median row error, while GAT has the lowest 95th-percentile error. ',
        'GAT also has the largest maximum row error. The average-MSE ranking does not hold at every percentile. ',
        'Incoming LOGOUT counts contribute the largest single feature residual share for all three models. ',
        'Residual contribution measures numeric reconstruction error, not causal importance or malicious activity.','',
        'High reconstruction error is a review cue with unknown security intent. These descriptive test findings must not be used to tune the current models.','',
        '## Observed execution times','',
        '| Model | Training function minutes | Original final test seconds |','|---|---:|---:|']
    for f,m in models.items():lines.append(f"| {LABELS[f]} | {m['training_function_seconds']/60:.2f} | {m['test']['seconds']:.2f} |")
    lines+=['','Training wall times include evaluation/checkpointing and different resource conditions. GCN and GraphSAGE used serial batch preparation; ',
        'GAT used CPU prefetching. These durations are not a controlled architecture-speed benchmark. All original final tests used prefetching.','',
        'See [the research report](../../../../../research/ml/gnn_results/README.md) for methods, validity limits and teammate commands.']
    (output/'RESULTS_20261102.md').write_bytes(('\n'.join(line.rstrip() for line in lines)+'\n').encode())
    return summary


def plots(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary=json.loads((output/'results_20261102.json').read_text());histories=json.loads((output/'histories_20261102.json').read_text())
    analysis=json.loads((output/'error_analysis_20261102.json').read_text())
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    colors=['#2563A6','#25826B','#CE7634']
    fig,ax=plt.subplots(figsize=(7,3.6));values=[summary['models'][f]['test']['mse'] for f in FAMILIES]+[summary['models']['gcn']['test']['mean_reference_mse']]
    bars=ax.bar([LABELS[f] for f in FAMILIES]+['Training mean'],values,color=colors+['#9CA3AF'])
    for b,v in zip(bars,values):ax.text(b.get_x()+b.get_width()/2,v+.008,f'{v:.6f}',ha='center',fontsize=9)
    ax.set_ylim(0,.64);ax.set_ylabel('Masked reconstruction MSE');ax.set_title('Frozen test cohort · 2,664,540 node-windows')
    fig.tight_layout();fig.savefig(output/'test_mse_20261102.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.7))
    for f,color in zip(FAMILIES,colors):
        hist=histories[f]
        for ax in axes:ax.plot([h['epoch'] for h in hist],[h['development']['mse'] for h in hist],marker='o',label=LABELS[f],color=color)
        selected=summary['models'][f]['selected_epoch'];value=hist[selected]['development']['mse']
        axes[1].scatter([selected],[value],s=110,marker='*',color=color,zorder=5)
    for ax in axes:
        ax.set_xlabel('Completed epoch (0 = initialization)');ax.set_ylabel('Development masked MSE');ax.set_xticks(range(6));ax.legend()
    axes[0].set_title('Recorded development history');axes[0].axhline(.49179723806035647,color='#777777',linestyle='--',label='Training mean')
    axes[0].legend()
    axes[1].set_xlim(.8,5.2);axes[1].set_ylim(.27,.40);axes[1].set_title('Trained epochs · stars mark selected weights')
    fig.tight_layout();fig.savefig(output/'development_curves_20261102.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,f,color in zip(axes,FAMILIES,colors):
        rows=analysis['models'][f]['top_features'][:5][::-1]
        labels=[r['feature'].replace('out_ref_EVENT_','out / ').replace('in_ref_EVENT_','in / ') for r in rows]
        ax.barh(labels,[100*r['squared_error_share'] for r in rows],color=color)
        ax.set_xlabel('Share of squared residual (%)');ax.set_title(LABELS[f])
    fig.tight_layout();fig.savefig(output/'residual_features_20261102.png',dpi=180);plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path);parser.add_argument('--verification',type=Path);parser.add_argument('--analysis',type=Path)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--plots-only',action='store_true')
    args=parser.parse_args()
    if not args.plots_only:
        if not all((args.work,args.verification,args.analysis)):parser.error('work, verification and analysis are required')
        build(args.work,args.verification,args.analysis,args.output)
    plots(args.output)
