"""R2B post-hoc falsification audit: stronger fixed methods, no tuning."""
import csv
import json
import numpy as np
from common import DATA,REPORT,save
from recurrent.data import read_avt,windows,transition
from recurrent.replay import arrivals_for,simulate
from recurrent.pricing import solver


def cluster_interval(d,starts,step,days):
    # Resample contiguous physical-time blocks, keeping every window in a block.
    labels=(np.asarray(starts)*step//(days*86400)).astype(int)
    unique=np.unique(labels)
    totals=np.array([d[labels==i].sum() for i in unique])
    counts=np.array([(labels==i).sum() for i in unique])
    rng=np.random.default_rng(23029+days)
    draws=rng.integers(0,len(unique),(2000,len(unique)))
    averages=totals[draws].sum(axis=1)/counts[draws].sum(axis=1)
    return {'n_blocks':len(unique),'interval':np.percentile(averages,[2.5,97.5]).tolist()}


def main():
    rates=json.loads((REPORT/'model.json').read_text())
    with (REPORT/'test_windows.csv').open() as f:old=list(csv.DictReader(f))
    result={'label':'post-hoc fixed stronger baseline audit, not independent confirmation', 'datasets':{}}
    rows=[]
    for filename,step in [('web_sites.avt',600),('pl-app.avt',900)]:
        trace=read_avt(DATA/filename,step);a,b=transition(rates,step)
        for number,(start,chosen,states,initial,status) in enumerate(windows(trace,'test',480)):
            if len(states)==0:continue
            arrivals=arrivals_for(trace.name,start)
            for control in ['trace','always_up']:
                for p in ['unpriced_horizon8','priced_horizon8']:
                    st=states if control=='trace' else np.ones_like(states)
                    ini=initial if control=='trace' else np.ones_like(initial)
                    pa,pb=(a,b) if control=='trace' else (1.,1.)
                    stats,_=simulate(st,ini,arrivals,p,2,pa,pb)
                    rows.append({'dataset':trace.name,'window_start':start,'control':control,'policy':p,**stats})
            if number%40==0:print(trace.name,number,'rows',len(rows),flush=True)
        summary={}
        for control in ['trace','always_up']:
            use=[r for r in rows if r['dataset']==trace.name and r['control']==control]
            summary[control]={p:{'completed_value':sum(r['completed_value'] for r in use if r['policy']==p),
                                 'failed_attempts':sum(r['failed_attempts'] for r in use if r['policy']==p),
                                 'runtime_seconds':sum(r['runtime_seconds'] for r in use if r['policy']==p),
                                 'windows':sum(r['policy']==p for r in use)} for p in ['unpriced_horizon8','priced_horizon8']}
        candidate={int(r['window_start']):float(r['completed_value']) for r in old
                   if r['dataset']==trace.name and r['capacity']=='2' and r['policy']=='joint_two_step'}
        comparisons={}
        for p in ['independent_two_step','joint_two_step_no_observation','priced_horizon8','unpriced_horizon8']:
            if p.endswith('horizon8'):
                base={r['window_start']:r['completed_value'] for r in rows if r['dataset']==trace.name and r['control']=='trace' and r['policy']==p}
            else:
                base={int(r['window_start']):float(r['completed_value']) for r in old if r['dataset']==trace.name and r['capacity']=='2' and r['policy']==p}
            assert set(base)==set(candidate)
            keys=sorted(base);d=np.asarray([candidate[t]-base[t] for t in keys])
            comparisons[p]={'mean_value_difference':float(d.mean()),'relative_gain':float(d.sum()/sum(base.values())),
                            'total_difference':float(d.sum()),'wins':int((d>0).sum()),'losses':int((d<0).sum()),
                            'clustered_bootstrap':{str(days):cluster_interval(d,keys,step,days) for days in [1,3,7]}}
        summary['joint_two_step_minus']=comparisons
        summary['solver_cache']=str(solver(a,b).solve.cache_info())
        result['datasets'][trace.name]=summary
        print(trace.name,summary,flush=True)
        save(REPORT/'baseline_audit.json',result)
    with (REPORT/'baseline_audit_windows.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


if __name__=='__main__':main()
