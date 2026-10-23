"""Presentation-only figures; original frozen computations remain unchanged."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from patternforecast.common import PACKAGE
from closed_loop_counterexample import run, forecasts

out = PACKAGE/'reports/figures'
markers = {.001:'s', .002:'o', .005:'^'}
colors = {'all':'#be723c', 'basis':'#1c607d'}
fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex='col', sharey='col')
for col, dataset in enumerate(['air','power']):
    model = 'short-gru-32-0.01-s20261022' if dataset=='air' else 'short-gru-64-0.05-s20261022'
    for row, split in enumerate(['development','confirmation']):
        ax = axes[row,col]
        reports = [json.loads(p.read_text()) for p in sorted((PACKAGE/'reports/multisignal').glob(f'codec-{dataset}-{split}-{model}-e*-n0.json'))]
        for mode in ['all','basis']:
            points = sorted((r['epsilon'],r['policies'][mode]) for r in reports)
            ax.plot([p['excess_brier'] for _,p in points],[p['bytes_per_query'] for _,p in points],color=colors[mode],lw=1.5)
            for epsilon,p in points:
                ax.scatter(p['excess_brier'],p['bytes_per_query'],marker=markers[epsilon],s=50,color=colors[mode],zorder=3)
        ax.set_title(f'{dataset} / {split}')
        ax.grid(alpha=.2)
        ax.margins(x=.1,y=.15)
        ax.ticklabel_format(axis='x',style='sci',scilimits=(0,0),useMathText=True)
        if col==0:ax.set_ylabel('Application bytes/query')
        if row==1:ax.set_xlabel('Observed mean Brier increase')
handles = [Line2D([],[],color=colors[k],label=v) for k,v in [('all','Full coordinates'),('basis','Independent coordinates')]]
handles += [Line2D([],[],color='#555',ls='',marker=m,label=f'epsilon={e}') for e,m in markers.items()]
fig.legend(handles=handles,loc='upper center',ncol=5,frameon=False,bbox_to_anchor=(.5,.955),fontsize=9)
fig.suptitle('Secondary trade-offs: markers denote different worst-case tolerances',y=.995)
fig.tight_layout(rect=[0,0,1,.91])
for ext in ['png','pdf']:fig.savefig(out/f'codec-frontier-clear.{ext}',dpi=180)
plt.close(fig)

_, trace = run(forecasts[1:3]+forecasts[3:5]*12)
fig, axes = plt.subplots(1,2,figsize=(9,3.8))
ax=axes[0]
f=np.array([[float(x) for x in p] for p in forecasts])
ax.fill([0,1,0],[0,0,1],color='#e8edf1',label='Coherent probability triangle')
ax.plot(f[:,0],f[:,1],'o-',color='#376b86',lw=1)
for i,(x,y) in enumerate(f):
    ax.annotate('initial' if i==0 else str(i),(x,y),xytext=(5,5),textcoords='offset points')
ax.set_xlim(0,.65);ax.set_ylim(0,.65)
ax.set_xlabel('Probability of outcome A');ax.set_ylabel('Probability of outcome B')
ax.set_title('All reference forecasts are coherent')
ax=axes[1]
x=np.arange(1,len(trace)+1)
for label,key,color in [('Tighter feasible set','strong_send','#ac493a'),('Looser feasible set','weak_send','#376b86')]:
    ax.step(x,np.cumsum([r[key] for r in trace]),where='post',label=label,color=color)
ax.set_xlabel('Query (repeat references 3 and 4)');ax.set_ylabel('Cumulative transmitted packets')
ax.set_title('Closed-loop packet counts diverge')
ax.legend(fontsize=8);ax.grid(alpha=.2)
fig.suptitle('Exact rational counterexample, epsilon=0.1; not an empirical forecast-quality result',fontsize=10)
fig.tight_layout()
for ext in ['png','pdf']:fig.savefig(out/f'closed-loop-counterexample.{ext}',dpi=180)
print('rendered presentation figures without changing experimental computations')
