import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from stateforecast.data import PACKAGE


def main():
    r=json.loads((PACKAGE/'reports/confirmation-2022.json').read_text())
    colors={'F0':'#647584','F1':'#71b3a4','F2':'#006e66'}
    labels={'F0':'F0: business history','F1':'F1: 16-bin context','F2':'F2: numeric context'}
    fig,axs=plt.subplots(2,2,figsize=(12,9))
    fig.subplots_adjust(left=.09,right=.97,bottom=.14,top=.87,wspace=.34,hspace=.44)
    fig.suptitle('State-aware forecasting: independent 2022 confirmation',fontsize=18,fontweight='bold',y=.975)
    fig.text(.5,.924,'10,326 instances | 68,197 forecasts | fixed LoadStart -> LoadEnd semantics',ha='center',fontsize=11,color='#54616d')
    names=['F0','F1','F2'];values=[r['models'][n]['mean_brier'] for n in names]
    bars=axs[0,0].bar(names,values,color=[colors[n] for n in names],width=.58)
    axs[0,0].bar_label(bars,fmt='%.5f',padding=4,fontsize=10)
    axs[0,0].set(ylim=(0,max(values)*1.3),ylabel='Mean Brier score (lower is better)',title='A. Same task, stronger temporal baseline')
    axs[0,0].text(.03,.92,f"F2 vs F0: {100*r['relative_reduction']:.1f}% lower error",transform=axs[0,0].transAxes,color=colors['F2'],fontsize=11)
    axs[0,1].plot([0,1],[0,1],'--',color='#aeb5bb',linewidth=1)
    for n in ['F0','F2']:
        b=r['models'][n]['60']['reliability'];axs[0,1].plot([v['mean_probability'] for v in b],[v['frequency'] for v in b],'-o',color=colors[n],label=n,markersize=4)
    axs[0,1].set(xlim=(0,1),ylim=(0,1),xlabel='Predicted completion probability',ylabel='Observed completion frequency',title='B. Calibration at 60 seconds')
    axs[0,1].legend(frameon=False)
    months=list(r['monthly']);x=np.arange(len(months))
    for j,n in enumerate(['F0','F2']):axs[1,0].bar(x+(j-.5)*.34,[r['monthly'][m][n] for m in months],.34,color=colors[n],label=n)
    axs[1,0].set(xticks=x,xticklabels=['Jan*','Feb','Mar','Apr','May'],ylabel='Mean Brier score',title='C. Improvement in every month')
    axs[1,0].legend(frameon=False)
    h=[30,60,120];x=np.arange(3)
    for j,n in enumerate(names):axs[1,1].bar(x+(j-1)*.24,[r['models'][n][str(t)]['brier'] for t in h],.24,color=colors[n],label=n)
    axs[1,1].set(xticks=x,xticklabels=['30 s','60 s','120 s'],ylabel='Brier score',title='D. Fixed wall-clock horizons')
    axs[1,1].legend(frameon=False)
    for ax in axs.ravel():ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.text(.09,.065,'F0, F1 and F2 all receive the same fast business-feedback expert. F2 adds numeric telemetry.\nEqual-instance weighting; 95% day-block bootstrap for F0 - F2: [0.01339, 0.01630].\n*January confirmation begins Jan 15. One compressor process; observed cycle completion, not fault prediction.',fontsize=9,color='#4e5b66')
    fig.savefig(PACKAGE/'reports/confirmation-2022.png',dpi=180)
    fig.savefig(PACKAGE/'reports/confirmation-2022.pdf')
    plt.close(fig)


if __name__=='__main__':main()
