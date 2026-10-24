"""Pre-registered always-up control and transparent structural counterexamples."""
from functools import lru_cache
from itertools import combinations
import json
import numpy as np
from common import DATA, REPORT, save
from recurrent.data import read_avt,windows
from recurrent.control import head_arrays,joint_values,independent_scores,select
from recurrent.replay import arrivals_for,simulate


def structural():
    queues=[[(3,3)],[(2,1)],[(3,3)]]
    p=np.ones(3);v,_,f=head_arrays(queues,0)
    actions,q=joint_values(p,v,f,1.,1.,1)
    additive=independent_scores(p,v,f,1.,1.).tolist()
    @lru_cache(None)
    def optimum(t,remaining):
        alive=[i for i in remaining if queues[i][0][1]>t]
        if t==3 or not alive:return (0.,())
        choices=[]
        for i in alive:
            reward,seq=optimum(t+1,tuple(x for x in alive if x!=i))
            choices.append((queues[i][0][0]+reward,(i,)+seq))
        return max(choices,key=lambda x:x[0])
    true_opt,sequence=optimum(0,tuple(range(3)))
    selected=int(actions[np.argmax(q),0])
    constrained=queues[selected][0][0]+optimum(1,tuple(i for i in range(3) if i!=selected))[0]
    return {'assumptions':'all states known up; no new arrivals; capacity one; rewards only on completion',
            'queues':queues,'two_slot_actions':actions.tolist(),'two_slot_values':q.tolist(),
            'additive_scores':additive,'joint_two_slot_choice':selected,
            'three_slot_optimum_value':true_opt,'three_slot_optimum_order':sequence,
            'three_slot_value_after_two_slot_choice':constrained,
            'interpretation':'Coupled two-slot value is not additive; its horizon truncation can still lose to a simpler urgency-aware action. This is an illustrative counterexample, not a new theorem.'}


def main():
    result={'structural_counterexample':structural(),'always_up':{}}
    policies=['myopic_value','urgency_value','independent_two_step','joint_two_step']
    for name,step in [('web_sites.avt',600),('pl-app.avt',900)]:
        trace=read_avt(DATA/name,step)
        rows=[]
        for start,_,states,initial,status in windows(trace,'test',480):
            if not len(states):continue
            arr=arrivals_for(trace.name,start)
            for policy in policies:
                stats,_=simulate(np.ones_like(states),np.ones_like(initial),arr,policy,2,1.,1.)
                rows.append({'window_start':start,'policy':policy,**stats})
        means={p:float(np.mean([x['completed_value'] for x in rows if x['policy']==p])) for p in policies}
        result['always_up'][trace.name]={'n_windows':len(rows)//len(policies),'mean_completed_value':means,
                                        'joint_minus_independent':means['joint_two_step']-means['independent_two_step'],
                                        'joint_minus_myopic':means['joint_two_step']-means['myopic_value']}
    save(REPORT/'diagnostics.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
