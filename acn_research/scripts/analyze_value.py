"""Paired seed-level summaries, preserving all controls and negative results."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]; HERE=ROOT/'acn_research'


def paired_summary(delta):
    x=np.asarray(delta,float); rng=np.random.default_rng(20261023)
    means=x[rng.integers(0,len(x),(2000,len(x)))].mean(axis=1)
    return {'seeds':len(x),'mean_kwh':float(x.mean()),'median_kwh':float(np.median(x)),
            'min_kwh':float(x.min()),'max_kwh':float(x.max()),
            'bootstrap_95pct_kwh':[float(v) for v in np.quantile(means,[.025,.975])],
            'positive':int((x>1e-6).sum()),'negative':int((x< -1e-6).sum()),'zero':int((np.abs(x)<=1e-6).sum())}


def main():
    path=HERE/'reports/value_evaluation.csv'; table=pd.read_csv(path)
    selection=json.loads((HERE/'reports/value_selection.json').read_text())
    baseline=selection['selected_causal_policy']; groups={}
    for (condition,capacity),group in table.groupby(['condition','feeder_amp']):
        pivot=group.pivot(index='seed',columns='policy',values='delivered_kwh')
        comparisons={}
        for a,b in [('current_mpc',baseline),('lead1_mpc','current_mpc'),('lead3_mpc','current_mpc'),
                    ('resume_oracle_mpc','current_mpc'),('offline',baseline),('offline','current_mpc'),
                    ('resume_oracle_mpc','native')]:
            comparisons[a+'_minus_'+b]=paired_summary(pivot[a]-pivot[b])
        means={}
        for name,rows in group.groupby('policy'):
            means[name]={k:float(rows[k].mean()) for k in ['delivered_kwh','shortfall_kwh','fully_served','wasted_reserved_kwh','runtime_seconds']}
        trace_root=ROOT/'artifacts/acn/value/evaluation'
        action_diffs={}
        duration=selection['duration_slots']
        for policy in ['lead1_mpc','lead3_mpc','resume_oracle_mpc']:
            changed_slots=0; worlds_changed=0
            for seed in sorted(group.seed.unique()):
                a=np.load(trace_root/f'{condition}-{capacity}-{seed}-current_mpc-{duration}.npz')['pilot']
                b=np.load(trace_root/f'{condition}-{capacity}-{seed}-{policy}-{duration}.npz')['pilot']
                count=int(np.any(a!=b,axis=0).sum()); changed_slots+=count; worlds_changed+=count>0
            action_diffs[policy]={'worlds_with_different_actions':worlds_changed,'different_dispatch_slots':changed_slots}
        groups[f'{condition}_{capacity}A']={'mean_requested_kwh':float(group.groupby('seed').requested_kwh.first().mean()),
                                         'means':means,'paired':comparisons,'action_differences_from_current_mpc':action_diffs}
    out={'scope':'Fixed held-out synthetic acceptance worlds; not production benefit or a learned predictor evaluation',
         'worlds':int(table.groupby(['condition','feeder_amp','seed']).ngroups),'policy_world_runs':len(table),
         'native_solver_calls':int(table.native_solver_calls.sum()),
         'constraint_violations':int(table.constraint_violations.sum()),
         'selection':selection,'groups':groups,'evaluation_csv_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
         'uncertainty':'Paired 2000-resample bootstrap over simulation seeds within each condition/capacity, not physical sites or telemetry rows'}
    (HERE/'reports/value_summary.json').write_text(json.dumps(out,indent=2)+'\n')
    names=[baseline,'native','current_mpc','resume_oracle_mpc','offline']
    labels=['EDF (selected)','Native corrected','Current-state MPC','Recovery oracle MPC','Offline optimum']
    fig,axes=plt.subplots(1,3,figsize=(13,4),sharey=True,layout='constrained')
    for ax,capacity in zip(axes,[36,60,180]):
        g=groups[f'pause_{capacity}A']; values=[g['means'][n]['delivered_kwh'] for n in names]
        ax.bar(np.arange(len(names)),values,color=['#5b6f89','#8397a5','#198a83','#bd8a2d','#3e4146'])
        ax.set_xticks(np.arange(len(names)),labels,rotation=38,ha='right',fontsize=8)
        ax.set_title(f'{capacity} A feeder'); ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
    axes[0].set_ylabel('Mean delivered energy (kWh / 6-EV world)')
    fig.suptitle('Recovery information vs. current observability — synthetic held-out worlds',fontsize=12)
    fig.savefig(HERE/'reports/value_comparison.png',dpi=180)
    print(json.dumps({'worlds':out['worlds'],'runs':len(table),'native_solves':out['native_solver_calls'],
                      'comparisons':{k:v['paired'] for k,v in groups.items()}},indent=2))


if __name__=='__main__': main()
