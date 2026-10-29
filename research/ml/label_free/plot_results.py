"""Plot aggregate reconstruction history and final errors; requires matplotlib."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot(run_directory, evaluation_path, output):
    if output.exists():
        raise ValueError('Use a fresh plot output path')
    run=json.loads((run_directory/'run.json').read_text())
    evaluation=json.loads(evaluation_path.read_text())
    history=[json.loads(line) for line in (run_directory/'history.jsonl').read_text().splitlines()]
    if not run['full_training_completed'] or evaluation['status']!='final_label_free_reconstruction_evaluated':
        raise ValueError('Plot only a completed full run and its frozen holdout evaluation')
    fig,axes=plt.subplots(1,2,figsize=(12,4.3),gridspec_kw={'width_ratios':[1.7,1]})
    epochs=[h['epoch'] for h in history]
    axes[0].plot(epochs,[h['train']['mse'] for h in history],label='Training',color='#2563eb')
    axes[0].plot(epochs,[h['development']['mse'] for h in history],label='Development',color='#d97706')
    axes[0].axhline(run['baseline_metrics']['development']['mse'],color='#64748b',linestyle='--',
                    label='Development mean baseline',linewidth=1)
    axes[0].axvline(run['best_epoch'],color='#475569',linestyle=':',label='Selected checkpoint')
    axes[0].set(xlabel='Epoch',ylabel='Mean squared reconstruction error',title='Training and checkpoint selection',ylim=(0,None))
    axes[0].legend(fontsize=8)
    metrics=('mse','mae');positions=(0,1);width=.35
    for offset,key,label,color in ((-width/2,'reconstruction_metrics','Autoencoder','#2563eb'),
                                    (width/2,'training_mean_baseline_metrics','Training-mean baseline','#d97706')):
        values=[evaluation[key][m] for m in metrics]
        bars=axes[1].bar([p+offset for p in positions],values,width,label=label,color=color)
        axes[1].bar_label(bars,fmt='%.4f',padding=3,fontsize=8)
    axes[1].set_xticks(positions,['MSE','MAE'])
    axes[1].set(ylabel='Error on normalized features',title=f"Frozen holdout ({evaluation['holdout_samples']} rows)")
    axes[1].set_ylim(0,1.25*max(evaluation[k][m] for k in
        ('reconstruction_metrics','training_mean_baseline_metrics') for m in metrics))
    axes[1].legend(fontsize=8)
    for axis in axes:
        axis.grid(axis='y',alpha=.2);axis.set_axisbelow(True)
    name=run.get('runtime',{}).get('device_name',run['device'])
    fig.suptitle(f'DARPA label-free reconstruction | {name}',fontsize=13)
    fig.text(.5,.015,'Unlabeled same-host/day pilot with shared object context; these are not attack-detection metrics.',
             ha='center',fontsize=8,color='#475569')
    fig.tight_layout(rect=(0,.045,1,.94))
    output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=160,bbox_inches='tight');plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('run','evaluation','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();plot(args.run,args.evaluation,args.output)


if __name__=='__main__':
    main()
