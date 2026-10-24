"""R2C: frozen independent recurrence study, no fitting or policy selection."""
import csv
import hashlib
import json
import tarfile
import numpy as np
from common import DATA,REPORT,save
from recurrent.data import read_avt,transition
from recurrent.replay import POLICIES,arrivals_for,simulate

EXPECTED='4056736665eb4c1d4ddaabf140c9193696d640c31dc41bf1ad6e268f97d76285'


def source():
    archive=DATA/'availability-0.3.tar.bz2'
    if hashlib.sha256(archive.read_bytes()).hexdigest()!='043a7d81c0b98de1a093d7aa9fbe57527924eb4bb013d7d39cbd313683ce46e0':
        raise ValueError('Archive checksum mismatch')
    with tarfile.open(archive,'r:bz2') as tar:
        data=tar.extractfile('availability-0.3/traces/microsoft.avt').read()
    if hashlib.sha256(data).hexdigest()!=EXPECTED:raise ValueError('Independent trace changed')
    (DATA/'microsoft.avt').write_bytes(data)
    save(REPORT/'sources_r2c.json',{'member':'microsoft.avt','sha256':EXPECTED,'bytes':len(data),
                                   'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})


def selected_groups(trace):
    for start in range(1,len(trace.times)-31,32):
        eligible=[i for i,a in enumerate(trace.intervals) if len(a) and a[0,0]<=trace.times[start-1]]
        eligible.sort(key=lambda i:hashlib.sha256(f'microsoft/{start}/{trace.nodes[i]}'.encode()).hexdigest())
        for group in range(20):
            chosen=eligible[6*group:6*(group+1)]
            if len(chosen)<6:
                yield start,group,chosen,np.empty((0,6)),np.zeros(6),'inventory'
                continue
            initial=trace.states[chosen,start-1]
            states=trace.states[chosen,start:start+32].T
            if (initial<0).any():
                yield start,group,chosen,states[:0],initial,'initial_unknown'
                continue
            bad=np.flatnonzero((states<0).any(axis=1))
            length=int(bad[0]) if len(bad) else 32
            yield start,group,chosen,states[:length],initial,'right_censored' if length<32 else 'complete'


def contrast(rows,k,baseline):
    target={(r['window_start'],r['group']):r['completed_value'] for r in rows if r['policy']=='joint_two_step' and r['capacity']==k}
    base={(r['window_start'],r['group']):r['completed_value'] for r in rows if r['policy']==baseline and r['capacity']==k}
    assert set(target)==set(base)
    keys=sorted(base);d=np.asarray([target[key]-base[key] for key in keys],dtype=float)
    blocks=np.asarray([key[0] for key in keys]);unique=np.unique(blocks)
    total=np.asarray([d[blocks==b].sum() for b in unique]);count=np.asarray([(blocks==b).sum() for b in unique])
    rng=np.random.default_rng(23031);draw=rng.integers(0,len(unique),(2000,len(unique)))
    boot=total[draw].sum(axis=1)/count[draw].sum(axis=1)
    return {'mean_difference':float(d.mean()),'total_difference':float(d.sum()),
            'relative_gain':float(d.sum()/sum(base.values())),
            'time_block_bootstrap_95':np.percentile(boot,[2.5,97.5]).tolist(),
            'n_groups':len(d),'n_time_blocks':len(unique),'wins':int((d>0).sum()),
            'ties':int((d==0).sum()),'losses':int((d<0).sum())}


def main():
    source();trace=read_avt(DATA/'microsoft.avt',3600)
    rates=json.loads((REPORT/'model.json').read_text());a,b=transition(rates,trace.step)
    x,y=trace.states[:,:-1],trace.states[:,1:]
    counts=[[int(((x==i)&(y==j)).sum()) for j in [0,1]] for i in [0,1]]
    n=sum(map(sum,counts));prob=[a,b]
    save(REPORT/'calibration_r2c.json',{
        'counts':counts,'known_pairs':n,'p01':a,'p11':b,
        'observed_down_to_up_rate':counts[0][1]/sum(counts[0]),
        'markov_brier':sum(counts[i][j]*(prob[i]-j)**2 for i in [0,1] for j in [0,1])/n,
        'last_observation_brier':(counts[0][1]+counts[1][0])/n,
        'empty_interval_nodes':sum(len(i)==0 for i in trace.intervals)})
    policies=POLICIES+['unpriced_horizon8','priced_horizon8']
    info={'nodes':len(trace.nodes),'intervals':sum(map(len,trace.intervals)),
          'grid_points':len(trace.times),'step_seconds':3600,'p01':a,'p11':b,
          'selected_groups':0,'complete':0,'initial_unknown':0,'right_censored':0,'inventory':0,
          'evaluated_groups':0,'evaluated_slots':0,'recovery_transitions':0,'interruption_transitions':0,
          'groups_with_up_down_up':0,'groups_with_two_recoveries_same_node':0}
    rows=[];seen_nodes=set();seen_times=set()
    for start,group,chosen,states,initial,status in selected_groups(trace):
        info['selected_groups']+=1;info[status]+=1
        if not len(states):continue
        info['evaluated_groups']+=1;info['evaluated_slots']+=len(states)
        seen_nodes.update(chosen);seen_times.add(start)
        diff=np.diff(np.vstack([initial,states]),axis=0);recovery=(diff==1).sum(axis=0)
        info['recovery_transitions']+=int(recovery.sum())
        info['interruption_transitions']+=int((diff==-1).sum())
        info['groups_with_two_recoveries_same_node']+=int((recovery>=2).any())
        cycles=any(any(diff[t,i]==1 and (diff[:t,i]==-1).any() for t in range(len(diff))) for i in range(6))
        info['groups_with_up_down_up']+=int(cycles)
        arr=arrivals_for('microsoft',start*100+group)
        for k in [2,6]:
            for policy in policies:
                stats,_=simulate(states,initial,arr,policy,k,a,b)
                rows.append({'dataset':'microsoft','window_start':start,'group':group,
                             'capacity':k,'policy':policy,'measurement_status':status,**stats})
        if group==0:print('time block',start,'groups evaluated',info['evaluated_groups'],flush=True)
    info['unique_evaluated_nodes']=len(seen_nodes);info['evaluated_time_blocks']=len(seen_times)
    summary={'protocol':'INDEPENDENT_R2C.json','data':info,'capacities':{}}
    for k in [2,6]:
        agg={p:{key:float(sum(r[key] for r in rows if r['policy']==p and r['capacity']==k))
                for key in ['completed_value','completed_records','failed_attempts','attempts','expired_value','rejected_value','runtime_seconds']}
             for p in policies}
        summary['capacities'][str(k)]={'aggregates':agg,'joint_two_step_minus':{p:contrast(rows,k,p) for p in policies if p!='joint_two_step'}}
    d=summary['capacities']['2']['joint_two_step_minus']
    summary['gate']={'coverage':len(seen_times)>=20 and info['groups_with_up_down_up']>=50,
                     'selected_baseline':d['independent_two_step']['time_block_bootstrap_95'][0]>0,
                     'information_component':d['joint_two_step_no_observation']['time_block_bootstrap_95'][0]>0,
                     'novelty_established':False}
    save(REPORT/'independent_r2c.json',summary)
    with (REPORT/'independent_r2c_windows.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    print(info,flush=True);print('Gate',summary['gate'],flush=True)
    for p in ['independent_two_step','joint_two_step_no_observation','priced_horizon8']:
        print('K2 minus',p,d[p],flush=True)


if __name__=='__main__':main()
