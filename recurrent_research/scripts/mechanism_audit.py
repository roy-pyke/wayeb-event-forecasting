"""Post-hoc structural explanation, not another model-selection stage."""
import json
import numpy as np
from common import DATA,REPORT,save
from recurrent.data import read_avt,windows,transition
from recurrent.replay import arrivals_for,simulate
from recurrent.control import select,head_arrays,joint_values


def first_recovery_counterexample():
    # Both destinations were down at t=-1; p01=0.5 implies b(t=0)=0.5.
    # The first recovery distribution is geometric(0.5) in both models.
    p=np.array([.5,.5]);queues=[[(4,3)],[(3,3)]]
    v,_,f=head_arrays(queues,0)
    out={'p01':.5,'initial_belief':p.tolist(),'queue':queues,'capacity':1,'reward_horizon':2,
         'first_recovery_cdf':[1-.5**n for n in range(1,9)],'models':{}}
    for persist in [.55,.99]:
        actions,values=joint_values(p,v,f,.5,persist,1)
        out['models'][str(persist)]={'p11':persist,'actions':actions.tolist(),'expected_values':values.tolist(),
                                     'unique_optimal_action':actions[int(np.argmax(values))].tolist()}
    assert out['models']['0.55']['unique_optimal_action']==[0]
    assert out['models']['0.99']['unique_optimal_action']==[1]
    return out


def main():
    model=json.loads((REPORT/'model.json').read_text())
    output={'first_recovery_insufficiency':first_recovery_counterexample(),'trace_mechanisms':{}}
    for file,step in [('web_sites.avt',600),('pl-app.avt',900)]:
        trace=read_avt(DATA/file,step);a,b=transition(model,step)
        info={'windows':0,'windows_with_down':0,'windows_with_recovery':0,
              'windows_with_up_down_up':0,'windows_with_two_recoveries_same_node':0,
              'recovery_transitions':0,'interruption_transitions':0,'decision_slots':0,
              'same_snapshot_action_disagreements':{p:0 for p in ['myopic_value','independent_two_step','joint_two_step_no_observation']},
              'model_two_slot_value_advantage_over_no_observation_sum':0.,'strict_info_action_value_improvements':0}
        for start,_,states,initial,status in windows(trace,'test',480):
            if not len(states):continue
            info['windows']+=1
            whole=np.vstack([initial,states]);diff=np.diff(whole,axis=0)
            rec=(diff==1).sum(axis=0);loss=(diff==-1).sum(axis=0)
            info['windows_with_down']+=int((states==0).any())
            info['windows_with_recovery']+=int((rec>0).any())
            info['windows_with_two_recoveries_same_node']+=int((rec>=2).any())
            info['recovery_transitions']+=int(rec.sum());info['interruption_transitions']+=int(loss.sum())
            cycle=False
            for i in range(states.shape[1]):
                last_down=-1
                for t in range(len(diff)):
                    if diff[t,i]==-1:last_down=t
                    if diff[t,i]==1 and last_down>=0:cycle=True
            info['windows_with_up_down_up']+=int(cycle)
            _,history=simulate(states,initial,arrivals_for(trace.name,start),'joint_two_step',2,a,b,True)
            for row in history:
                t=row['t'];p=np.asarray(row['belief']);q=row['queue'];selected=set(row['selected'])
                info['decision_slots']+=1
                for policy in info['same_snapshot_action_disagreements']:
                    other=select(policy,p,q,t,2,a,b)
                    info['same_snapshot_action_disagreements'][policy]+=int(set(other)!=selected)
                    if policy=='joint_two_step_no_observation' and t<31 and len(selected)>0:
                        value,_,future=head_arrays(q,t)
                        actions,vals=joint_values(p,value,future,a,b,2)
                        idx=next(i for i,x in enumerate(actions) if set(x)==set(other))
                        delta=float(max(vals)-vals[idx])
                        info['model_two_slot_value_advantage_over_no_observation_sum']+=delta
                        info['strict_info_action_value_improvements']+=int(delta>1e-10)
        output['trace_mechanisms'][trace.name]=info
    save(REPORT/'mechanism_audit.json',output)
    print(json.dumps(output,indent=2))


if __name__=='__main__':main()
