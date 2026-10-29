"""Plot post-evaluation residual distributions and numerical feature shares."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot(report_path,output):
    if output.exists():
        raise ValueError('Use a fresh diagnostic chart output path')
    report=json.loads(report_path.read_text())
    if report['status']!='frozen_post_evaluation_error_analysis_complete':
        raise ValueError('A completed frozen-model error analysis is required')
    fig,axes=plt.subplots(1,2,figsize=(13,4.8),gridspec_kw={'width_ratios':[1,1.5]})
    roles=('train','development','holdout');stats=[]
    for role in roles:
        d=report['partitions'][role]['sample_mse']
        stats.append(dict(label=f"{role.title()}\n(n={d['count']})",q1=d['p25'],med=d['median'],q3=d['p75'],
            whislo=d['min'],whishi=d['max'],mean=d['mean'],fliers=[]))
    axes[0].bxp(stats,showmeans=True,showfliers=False)
    if all(s['whislo']>0 for s in stats):axes[0].set_yscale('log')
    axes[0].set(title='Per-sample reconstruction error',ylabel='MSE (log scale)' if axes[0].get_yscale()=='log' else 'MSE')
    axes[0].text(.5,-.19,'Box: 25%-75%; line: median; triangle: mean; whiskers: min-max',
                 ha='center',transform=axes[0].transAxes,fontsize=8)
    top=list(reversed(report['partitions']['holdout']['features'][:8]))
    values=[100*f['squared_error_share'] for f in top]
    bars=axes[1].barh([f['feature'] for f in top],values,color='#2563eb')
    axes[1].bar_label(bars,fmt='%.1f%%',padding=4,fontsize=8)
    axes[1].set_xlim(0,max(values,default=1)*1.2 if any(values) else 1)
    axes[1].set(title='Largest numerical holdout residual shares',xlabel='Share of total squared residual (%)')
    for axis in axes:axis.grid(axis='y' if axis is axes[0] else 'x',alpha=.2);axis.set_axisbelow(True)
    fig.suptitle('DARPA frozen-model error analysis',fontsize=14)
    fig.text(.5,.015,'Post-evaluation diagnostics only; no retraining, attack labels or security thresholds.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.055,1,.94));output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=160,bbox_inches='tight');plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();plot(args.report,args.output)


if __name__=='__main__':main()
