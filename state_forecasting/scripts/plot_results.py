"""Portable scientific figure, with data and model definitions in the report."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from stateforecast.data import PACKAGE


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,default=PACKAGE/'reports/holdout.json');args=parser.parse_args()
    r=json.loads(args.report.read_text())
    colors={'M0':'#526879','M1-16':'#cab17e','M2':'#c8754d','G1':'#64a59b','G2':'#096e65'}
    fig,axes=plt.subplots(2,2,figsize=(12,8.8),layout='constrained')
    fig.suptitle('Fixed event semantics, adaptive state forecasting',fontsize=19,fontweight='bold')
    names=list(colors);means=[r['models'][n]['mean_brier'] for n in names]
    bars=axes[0,0].bar(names,means,color=[colors[n] for n in names],width=.65)
    axes[0,0].bar_label(bars,fmt='%.4f',padding=4,fontsize=9)
    axes[0,0].set(ylim=(0,max(means)*1.22),ylabel='Mean Brier score (lower is better)',title='A. Frozen prequential holdout, May-August 2020')
    axes[0,0].text(.02,.92,f"G2 reduction vs M0: {100*r['relative_reduction']:.1f}%",transform=axes[0,0].transAxes,fontsize=11,color=colors['G2'])
    axes[0,1].plot([0,1],[0,1],'--',color='#aaa',linewidth=1)
    for name in ['M0','G2']:
        bins=r['models'][name]['60']['reliability']
        axes[0,1].plot([b['mean_probability'] for b in bins],[b['frequency'] for b in bins],'-o',color=colors[name],label=name)
    axes[0,1].set(xlabel='Predicted P(completion within 60 seconds)',ylabel='Observed completion frequency',title='B. Reliability / calibration',xlim=(0,1),ylim=(0,1))
    axes[0,1].legend(frameon=False)
    months=list(r['monthly']);x=np.arange(len(months))
    for j,name in enumerate(['M0','G2']):
        axes[1,0].bar(x+(j-.5)*.35,[r['monthly'][m][name] for m in months],width=.35,color=colors[name],label=name)
    axes[1,0].set(xticks=x,xticklabels=[m[-2:] for m in months],xlabel='Month, 2020',ylabel='Mean Brier score',title='C. Chronological robustness')
    axes[1,0].legend(frameon=False)
    labels=['Static context (R1)','Daily context (R2)','Delayed mixture (R3)']
    values=[]
    for version in [1,2]:
        v=json.loads((PACKAGE/f'reports/development-v{version}.json').read_text())
        values.append(v['models']['M2']['calibrated']['mean_brier'])
    v=json.loads((PACKAGE/'reports/development-v3.json').read_text());values.append(v['models']['G2']['metrics']['mean_brier'])
    bars=axes[1,1].barh(labels,values,color=['#c8754d','#cab17e','#096e65'],height=.55)
    axes[1,1].bar_label(bars,fmt='%.4f',padding=4)
    axes[1,1].set(xlim=(0,max(values)*1.2),xlabel='Mean Brier, April development set only',title='D. Failed iterations retained')
    axes[1,1].invert_yaxis()
    for ax in axes.ravel():
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.get_layout_engine().set(rect=(0,.07,1,.86))
    fig.text(.02,.012,'M0: business history + time. M1: 16-bin context. M2: numeric context. G1/G2: delayed-feedback mixture with M0.\nOne real compressor; observed load-cycle completion, not fault prediction. Equal-instance weighting; all models use the same causal update policy.',fontsize=9,color='#48525a')
    out=PACKAGE/'reports';fig.savefig(out/'results.png',dpi=180);fig.savefig(out/'results.pdf');plt.close(fig)


if __name__=='__main__':main()
