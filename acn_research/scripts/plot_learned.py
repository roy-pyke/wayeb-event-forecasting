"""Compact scientific figure from frozen R1 aggregate evidence."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parents[1]; OUT=HERE/'reports/r1'


def main():
    evaluation=json.loads((OUT/'evaluation.json').read_text())['groups']
    office=json.loads((OUT/'office_audit.json').read_text())['groups']
    service=json.loads((OUT/'service_summary.json').read_text())['groups']
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(2,2,figsize=(12,8.2),layout='constrained')
    labels=['Office train','Office dev','Office test','Caltech','JPL']; prevalence=[]
    for label in ['train','development','office_test','caltech','jpl']:
        group=office[label] if label in office else json.loads((OUT/f'{label}_audit.json').read_text())['groups'][label]
        prevalence.append([100*group['horizons'][str(h)]['positive']/group['horizons'][str(h)]['known'] for h in [15,60]])
    x=np.arange(5); p=np.array(prevalence); ax=axes[0,0]
    ax.bar(x-.18,p[:,0],.36,label='Within 15 min',color='#326aa8')
    ax.bar(x+.18,p[:,1],.36,label='Within 60 min',color='#e9a443')
    ax.set_xticks(x,labels,rotation=15); ax.set_ylabel('Sustained recovery (%)')
    ax.set_title('A. Rare events and temporal shift',loc='left',fontweight='bold'); ax.legend(frameon=False)
    sites=['office_test','caltech','jpl']; pretty=['Office test','Caltech','JPL']
    ax=axes[0,1]; x=np.arange(3)
    models=['empirical','elapsed_logistic','full_logistic','full_gbdt']
    for j,name in enumerate(models):
        y=[evaluation[s]['prediction'][name]['60']['brier'] for s in sites]
        ax.bar(x+(j-1.5)*.18,y,.18,label=name.replace('_',' '))
    ax.set_xticks(x,pretty); ax.set_ylabel('Brier score at 60 min (lower is better)')
    ax.set_title('B. Frozen models, no external retuning',loc='left',fontweight='bold'); ax.legend(frameon=False,fontsize=8)
    ax=axes[1,0]
    for j,(policy,color) in enumerate([('learned_dp','#b84949'),('perfect_recovery','#619b87')]):
        vals=[]; lo=[]; hi=[]
        for s in sites:
            r=service[f'{s}_30A_recovery_36A_feeder']['comparisons'][policy+'_minus_every_4']
            vals.append(r['mean_kwh']); lo.append(r['mean_kwh']-r['bootstrap_95pct_kwh'][0]); hi.append(r['bootstrap_95pct_kwh'][1]-r['mean_kwh'])
        ax.bar(x+(j-.5)*.32,vals,.32,color=color,label='Learned CDF' if j==0 else 'Full survival oracle',yerr=[lo,hi],capsize=3)
    ax.axhline(0,color='black',lw=.8); ax.set_xticks(x,pretty); ax.set_ylabel('Delivered kWh difference vs 20-min probing')
    ax.set_title('C. Conditional six-EV service, 36A feeder',loc='left',fontweight='bold')
    ax.set_ylim(-.05,.35)
    ax.legend(frameon=False,fontsize=8,loc='upper left',bbox_to_anchor=(.01,.83),ncol=2)
    ax.text(.02,.98,'30A recovery assumption; synthetic requests\nSeed intervals conditional on sampled episodes',transform=ax.transAxes,va='top',fontsize=8)
    ax=axes[1,1]
    for j,(variant,name,color) in enumerate([('full_gbdt_dp','Natural forecast','#326aa8'),('full_gbdt_dp_inflate_0p2','CDF + 0.2 stress','#b84949')]):
        vals=[]; lo=[]; hi=[]
        for s in sites:
            r=evaluation[s]['discovery_comparisons']['4.0:'+variant+'_minus_fixed']
            vals.append(r['mean']); lo.append(r['mean']-r['ci95'][0]); hi.append(r['ci95'][1]-r['mean'])
        ax.bar(x+(j-.5)*.32,vals,.32,color=color,label=name,yerr=[lo,hi],capsize=3)
    ax.axhline(0,color='black',lw=.8); ax.set_xticks(x,pretty); ax.set_ylabel('Discovery cost difference (lower is better)')
    ax.set_title('D. Error sensitivity does not transfer',loc='left',fontweight='bold')
    ax.set_ylim(-1.8,1.8)
    ax.legend(frameon=False,fontsize=8,loc='upper left',bbox_to_anchor=(.01,.84))
    ax.text(.02,.98,'Delay weight = 4; day-clustered 95% intervals\nNormalized cost, not observed money or energy',transform=ax.transAxes,va='top',fontsize=8)
    fig.suptitle('ACN R1: trained forecasts do not reproduce oracle gains',fontsize=16,fontweight='bold')
    for ext in ['png','svg','pdf']: fig.savefig(OUT/f'R1_EVIDENCE.{ext}',dpi=180)
    plt.close(fig)


if __name__=='__main__': main()
