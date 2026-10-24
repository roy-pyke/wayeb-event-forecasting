"""Standalone scientific figure from saved aggregate evidence."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import REPORT


def main():
    r=json.loads((REPORT/'test_summary.json').read_text())
    b=json.loads((REPORT/'baseline_audit.json').read_text())['datasets']
    m=json.loads((REPORT/'independent_r2c.json').read_text())
    mech=json.loads((REPORT/'mechanism_audit.json').read_text())['trace_mechanisms']
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(13,8.4),layout='constrained')
    names=['Web\n132 windows','PlanetLab\n28 windows','Corporate PCs\n489 groups / 26 time blocks']
    colors=['#2563a6','#d17c23']
    ax=axes[0,0]
    for j,baseline in enumerate(['independent_two_step','joint_two_step_no_observation']):
        gains=[];lower=[];upper=[]
        for dataset in ['web_sites','pl-app','microsoft']:
            if dataset=='microsoft':
                d=m['capacities']['2']['joint_two_step_minus'][baseline]
                ci=d['time_block_bootstrap_95'];n=d['n_groups']
                mean=m['capacities']['2']['aggregates'][baseline]['completed_value']/n
            else:
                d=b[dataset]['joint_two_step_minus'][baseline]
                ci=d['clustered_bootstrap']['1']['interval']
                n=r[dataset]['2']['aggregates'][baseline]['n_windows']
                mean=r[dataset]['2']['aggregates'][baseline]['completed_value']/n
            pct=d['relative_gain']*100;gains.append(pct)
            lower.append(pct-ci[0]/mean*100);upper.append(ci[1]/mean*100-pct)
        x=np.arange(3)+(j-.5)*.32
        ax.bar(x,gains,width=.3,color=colors[j],label=['vs additive 2-step','vs no-observation lookahead'][j])
        ax.errorbar(x,gains,yerr=[lower,upper],fmt='none',color='#222222',capsize=3,lw=1)
    ax.axhline(0,color='#555555',lw=.8);ax.set_xticks(range(3),names)
    ax.set_ylabel('Completed-value difference (%)')
    ax.set_title('A. Shared capacity K=2; clustered 95% intervals',loc='left',fontweight='bold')
    ax.legend(frameon=False,fontsize=9,loc='upper left')
    ax=axes[0,1]
    counts=[mech['web_sites']['windows_with_up_down_up'],mech['pl-app']['windows_with_up_down_up'],m['data']['groups_with_up_down_up']]
    den=[132,28,m['data']['evaluated_groups']]
    bars=ax.bar(range(3),100*np.array(counts)/den,color=['#2563a6','#8b99a5','#20805e'])
    for i,bar in enumerate(bars):ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+2,f'{counts[i]}/{den[i]}',ha='center')
    ax.set_xticks(range(3),['Web','PlanetLab','Corporate PCs']);ax.set_ylim(0,85)
    ax.set_ylabel('Evaluated groups with UP-DOWN-UP (%)')
    ax.set_title('B. Does the independent sample contain recurrence?',loc='left',fontweight='bold')
    ax=axes[1,0]
    for dataset,label,color in [('web_sites','Web','#2563a6'),('pl-app','PlanetLab','#8b99a5')]:
        gains=[r[dataset][str(k)]['candidate_minus']['independent_two_step']['relative_completed_value_gain']*100 for k in [1,2,4,6]]
        ax.plot([1,2,4,6],gains,marker='o',label=label,color=color)
    ax.plot([2,6],[m['capacities'][str(k)]['joint_two_step_minus']['independent_two_step']['relative_gain']*100 for k in [2,6]],'o-',label='Corporate PCs',color='#20805e')
    ax.axhline(0,color='#555555',lw=.8);ax.axvline(2,color='#999999',lw=.8,ls=':')
    ax.set_xticks([1,2,4,6]);ax.set_xlabel('Attempt budget K (six destinations)')
    ax.set_ylabel('Difference vs additive 2-step (%)');ax.legend(frameon=False,fontsize=9)
    ax.set_title('C. Capacity sensitivity (K=2 was primary)',loc='left',fontweight='bold')
    ax=axes[1,1]
    policies=['independent_two_step','joint_two_step','priced_horizon8']
    times=[1e6*m['capacities']['2']['aggregates'][p]['runtime_seconds']/m['data']['evaluated_slots'] for p in policies]
    ax.barh(range(3),times,color=['#8b99a5','#2563a6','#20805e'])
    ax.set_yticks(range(3),['Additive 2-step','Joint 2-step','Priced deadline DP']);ax.invert_yaxis()
    for i,x in enumerate(times):ax.text(x+1,i,f'{x:.1f}',va='center')
    ax.set_xlim(0,max(times)*1.2);ax.set_xlabel('Microseconds per slot; cached local Python replay')
    ax.set_title('D. Runtime in the independent PC replay',loc='left',fontweight='bold')
    fig.suptitle('Recurrent availability + shared capacity: evidence, not a novelty claim',fontsize=15,fontweight='bold')
    fig.supxlabel('Real historical availability; synthetic request values, deadlines and traffic. No Flink production-performance claim.',fontsize=10)
    for suffix in ['png','svg','pdf']:
        fig.savefig(REPORT/f'R2_EVIDENCE.{suffix}',dpi=180)
    plt.close(fig)


if __name__=='__main__':main()
