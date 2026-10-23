"""Two distinct information contracts, with seed-level uncertainty."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE=Path(__file__).resolve().parents[1]


def main():
    c2=json.loads((HERE/'reports/c2/value_summary.json').read_text())
    p2=json.loads((HERE/'reports/probing_p2/summary.json').read_text())
    caps=[36,60,180]
    left=[c2['groups'][f'pause_{c}A']['paired']['lead3_mpc_minus_current_mpc'] for c in caps]
    right=[p2['groups'][f'pause_{c}A']['notice15_minus_selected'] for c in caps]
    fig,axes=plt.subplots(1,2,figsize=(10,4.8),sharey=True)
    for ax,rows,title in zip(axes,[left,right],['C2: Current acceptance is already known','P2: Causal probing + spare-budget fill']):
        y=np.array([r['mean_kwh'] for r in rows]); ci=np.array([r['bootstrap_95pct_kwh'] for r in rows])
        error=np.array([y-ci[:,0],ci[:,1]-y])
        ax.bar(range(3),y,color=['#2b6989','#168d87','#8a9ca5'],width=.55)
        ax.errorbar(range(3),y,yerr=error,fmt='none',color='#333333',capsize=5)
        for i,v in enumerate(y):
            ax.annotate(f'{v:.3f}',(i,v),xytext=(10 if v else 0,9),textcoords='offset points',
                        ha='left' if v else 'center',fontsize=10)
        ax.set_xticks(range(3),[f'{c} A' for c in caps]); ax.set_xlabel('Feeder capacity')
        ax.set_title(title,fontsize=10); ax.set_ylim(0,.82); ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
    axes[0].set_ylabel('Added delivered energy\n(kWh per six-vehicle world)')
    fig.suptitle('Value of a perfect 15-minute recovery notice',fontsize=14,y=.97)
    fig.text(.5,.025,'Separate held-out simulation seeds; paired bootstrap 95% intervals.\nExogenous acceptance model and perfect notices — not measured production gains.',ha='center',fontsize=9,color='#555555')
    fig.subplots_adjust(left=.1,right=.98,bottom=.23,top=.84,wspace=.12)
    for extension in ['png','svg']: fig.savefig(HERE/f'reports/FINAL_FIGURE.{extension}',dpi=180)


if __name__=='__main__': main()
