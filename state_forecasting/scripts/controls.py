"""Independent synthetic controls; no MetroPT holdout access."""
import json
from collections import deque
from pathlib import Path
import numpy as np
from stateforecast.data import PACKAGE, episode_rows
from stateforecast.model import StateSurvival
from stateforecast.mixer import causal_mix
from stateforecast.evaluate import metrics, paired_bootstrap


def simulate(seed, count, informative, offset=0):
    rng=np.random.default_rng(seed)
    records=[]
    history=deque(maxlen=3)
    now=offset
    for episode in range(count):
        p=0.0
        rate=rng.uniform(.004,.015)
        times=[];sensors=[]
        start=now
        while p<1:
            times.append(now)
            if informative:
                z=[7+3*p+rng.normal(0,.01),7+3*p+rng.normal(0,.01),
                   2*p+rng.normal(0,.01),rng.normal(),9+2*p,50+5*p,rate*500]
            else:
                z=rng.normal(size=7).tolist()
            sensors.append(z)
            now+=10
            rate=np.clip(rate+rng.normal(0,.0004),.002,.02)
            p+=rate*10
        times.append(now);sensors.append([0]*7)
        rows=episode_rows(np.asarray(times),np.asarray(sensors),0,len(times)-1,True,history,20)
        for t,r,observed,x in rows:records.append((episode,t,r,observed,start,x))
        history.append(now-start)
        now+=rng.uniform(20,100)
    eid,t,r,observed,start,x=zip(*records)
    return dict(instance=np.asarray(eid),time=np.asarray(t),residual=np.asarray(r),
                observed=np.asarray(observed),start=np.asarray(start),X=np.asarray(x))


def main():
    protocol=json.loads((PACKAGE/'configs/PROTOCOL.json').read_text());h=protocol['horizons_seconds']
    report={}
    for informative in [True,False]:
        datasets=[simulate(seed,n,informative,offset=i*1000000) for i,(seed,n) in enumerate([(10,1000),(20,400),(30,1000)])]
        pred={}
        for mode in ['M0','M1','M2']:
            model=StateSurvival(mode,protocol['hazard_edges_seconds'],bins=16).fit(datasets[0]).calibrate(datasets[1],h)
            pred[mode]=model.predict_cdf(datasets[2]['X'],h)
        pred['G2'],_,audit=causal_mix(datasets[2],pred['M0'],pred['M2'],h)
        name='informative_physical_progress' if informative else 'independent_noise_context'
        # Synthetic instances are independently generated; resample instances,
        # not the arbitrary three calendar days occupied by the simulator.
        bootstrap_data=dict(datasets[2],start=datasets[2]['instance']*86400)
        comparison=paired_bootstrap(bootstrap_data,pred['M0'],pred['G2'],h)
        comparison['independent_instances']=comparison.pop('days')
        report[name]=dict(models={n:metrics(datasets[2],p,h) for n,p in pred.items()},feedback=audit,
                          comparison=comparison)
        print(name,{n:round(m['mean_brier'],5) for n,m in report[name]['models'].items()},flush=True)
    report['interpretation']='Mechanism controls, not real industrial accuracy. Hidden work integrates forward; no final-duration normalization.'
    (PACKAGE/'reports/controls.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
