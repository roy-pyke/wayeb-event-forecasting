"""Rebuild comparison statistics and scientific figures from committed reports."""
import json
from pathlib import Path
import numpy as np
from patternforecast.common import PACKAGE,write_json


def paired(primary,baseline):
    assert primary['weeks']==baseline['weeks']
    p,b=[np.array(x['week_byte_sums'],dtype=float) for x in [primary,baseline]]
    rng=np.random.default_rng(20261022);ix=rng.integers(len(p),size=(1000,len(p)))
    savings=1-p[ix].sum(1)/b[ix].sum(1)
    ps,bs=[np.array(x['week_excess_sums'],dtype=float) for x in [primary,baseline]]
    n=np.array(primary['week_scored_counts'],dtype=float)
    assert np.array_equal(n,baseline['week_scored_counts'])
    loss=(ps-bs)[ix].sum(1)/n[ix].sum(1)
    return dict(relative_byte_saving=1-p.sum()/b.sum(),relative_byte_saving_ci=np.quantile(savings,[.025,.975]),
                brier_difference=primary['brier']-baseline['brier'],brier_difference_ci=np.quantile(loss,[.025,.975]))


rows=[]
for path in sorted((PACKAGE/'reports').rglob('codec-*-e*-n0.json')):
    r=json.loads(path.read_text());policies=r['policies']
    if 'basis' not in policies or not all(k in policies for k in ['all','zero']):continue
    primary=policies['basis']
    for key in ['all','static','zero']:
        if key not in policies:continue
        row=dict(family=r['family'],dataset=r['dataset'],split=r['split'],backbone=r['backbone'],
                 epsilon=r['epsilon'],comparator=key,primary_bytes=primary['bytes_per_query'],
                 comparator_bytes=policies[key]['bytes_per_query'],primary_brier=primary['brier'],
                 certificate_violations=primary['bound_violations'],**paired(primary,policies[key]))
        row['source']=str(path.relative_to(PACKAGE));rows.append(row)
write_json(PACKAGE/'reports/codec-comparisons.json',dict(rows=rows,
    note='Pointwise 95% paired weekly intervals; not simultaneous multiple-comparison intervals. Seed spread is separate.'))
if rows:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    chosen=[r for r in rows if r['comparator']=='all' and r['epsilon']==.002]
    fig,ax=plt.subplots(figsize=(10,max(3,.38*len(chosen)+1)))
    for i,r in enumerate(chosen):
        center=100*r['relative_byte_saving'];lo,hi=100*np.asarray(r['relative_byte_saving_ci'])
        ax.errorbar(center,i,xerr=[[max(0,center-lo)],[max(0,hi-center)]],fmt='o',capsize=3,
                    color='#185a78' if r['split']=='confirmation' else '#8797a3')
    ax.set_yticks(range(len(chosen)),[f"{r['split']} | {r['dataset']} | {r['backbone'].replace('short-','')}" for r in chosen])
    ax.axvline(0,color='#555',lw=1);ax.axvline(5,color='#ac4b36',ls='--',label='Registered 5% gate')
    ax.set_xlabel('Application bytes saved vs shared adaptive-precision full-coordinate codec (%)')
    ax.set_title('Semantic coordinate codec: paired calendar-week uncertainty')
    ax.legend(loc='best');ax.grid(axis='x',alpha=.2);fig.tight_layout()
    folder=PACKAGE/'reports/figures';folder.mkdir(exist_ok=True)
    fig.savefig(folder/'codec-comparisons.png',dpi=180);fig.savefig(folder/'codec-comparisons.pdf')
    plt.close(fig)
print('summarized',len(rows),'paired comparisons')
