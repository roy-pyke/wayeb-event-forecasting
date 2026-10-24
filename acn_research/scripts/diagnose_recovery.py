"""Post-evaluation diagnosis; no model refit, retuning, or new success gate."""
from pathlib import Path
from collections import Counter
import hashlib,json,pickle,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]; HERE=ROOT/'acn_research'
sys.path.insert(0,str(HERE/'src'))
from acnresearch.recovery import FEATURES
from acnresearch.learned_service import make_service_world,run_service
from acnresearch.recovery import complete_episode_mask


def main():
    private=ROOT/'artifacts/acn/r1'; out=HERE/'reports/r1'
    train=pd.read_pickle(private/'office_episodes.pkl'); train=train.loc[train.split.eq('train')]
    with (private/'evaluation_predictions.pkl').open('rb') as f: payload=pickle.load(f)
    data=payload['frame']; selection=json.loads((out/'selection.json').read_text()); model=selection['forecast']
    results={}
    for site,g in data.groupby('split'):
        rawsite='office' if site=='office_test' else site
        manifest=json.loads((ROOT/'artifacts/acn'/rawsite/('full_download_manifest.json' if rawsite=='office' else 'r1_download_manifest.json')).read_text())
        paths={hashlib.sha256((rawsite+'/'+Path(m['path']).name).encode()).hexdigest():ROOT/m['path'] for m in manifest}
        valid=g.loc[g.event_min.notna()]; c=Counter(); counter_energy=[]
        for _,r in valid.iterrows():
            df=pd.read_csv(paths[r.key],index_col=0); df.index=pd.to_datetime(df.index,utc=True)
            confirmed=pd.Timestamp(r.alarm_time)+pd.Timedelta(seconds=round(r.event_min*60,6))
            # Exact row lookup with numerical nanosecond tolerance.
            times=df.index.asi8/1e9; j=int(np.argmin(abs(times-confirmed.timestamp())))
            assert abs(times[j]-confirmed.timestamp())<.001
            c['confirmed_recoveries']+=1
            current=df['Charging Current (A)'].to_numpy(float); pilot=df['Actual Pilot (A)'].to_numpy(float)
            states=df['Charging State'].to_numpy(); energy=df['Energy Delivered (kWh)'].to_numpy(float)
            low_start=None; relapse=False; last=j; ended='file_end'
            for k in range(j+1,len(df)):
                dt=times[k]-times[k-1]
                if dt<=0 or dt>15 or not np.isfinite(current[k]) or not np.isfinite(pilot[k]): ended='gap_or_missing'; break
                if states[k]=='UNPLUGGED': ended='unplug'; break
                if pilot[k]<6: ended='pilot_withdrawal'; break
                if times[k]-times[j]>900: ended='15min'; break
                last=k
                if current[k]<6:
                    if low_start is None: low_start=times[k]
                    if times[k]-low_start>=60: relapse=True
                else: low_start=None
            c['relapsed_below_6_for_60s_within_observation']+=relapse
            c['post_recovery_end_'+ended]+=1
            # A descriptive energy increment, never counterfactual utility.
            eligible=np.isfinite(r.remaining_kwh) and r.remaining_kwh>=.1 and r.slack_min>r.event_min
            if eligible:
                c['known_unmet_request_before_declared_deadline']+=1
                deadline=pd.Timestamp(r.alarm_time).timestamp()+r.slack_min*60
                last=j
                for k in range(j+1,len(df)):
                    dt=times[k]-times[k-1]
                    if dt<=0 or dt>15 or states[k]=='UNPLUGGED' or times[k]>=deadline or not np.isfinite(energy[k]) or not np.isfinite(energy[k-1]) or energy[k]<energy[k-1]-1e-6: break
                    last=k
                extra=float(max(0,energy[last]-energy[j])) if np.isfinite(energy[j]) else 0.
                counter_energy.append(extra)
                c['observed_extra_at_least_0p1_kwh_before_deadline']+=extra>=.1
        drift={}
        for f in FEATURES:
            a=train[f].dropna(); b=g[f].dropna()
            drift[f]={'train_nonmissing':len(a),'test_nonmissing':len(b),
                      'train_unique':int(a.nunique()),
                      'test_outside_train_range':int(((b<a.min())|(b>a.max())).sum()) if len(a) else None}
        p=payload['cdf'][model][g.index]
        results[site]={'post_recovery_audit':dict(c),'known_request_extra_kwh_sum':float(sum(counter_energy)),
                       'cdf15_quantiles':np.quantile(p[:,2],[0,.5,1]).tolist(),
                       'cdf60_quantiles':np.quantile(p[:,-1],[0,.5,1]).tolist(),
                       'confirmation_current_quantiles':np.quantile(valid.confirmation_current,[0,.5,1]).tolist(),
                       'feature_drift':drift}
    g=data.loc[data.split.eq('office_test')]; g=g.loc[complete_episode_mask(g)]
    world=make_service_world(703,36,30,g,payload['cdf'][model][g.index],payload['cdf']['empirical'][g.index])
    a,ta=run_service(world,kind='every_4'); b,tb=run_service(world); e,te=run_service(world,empirical=True)
    example={'seed':703,'public_synthetic_demand_quanta':world.public.demand.tolist(),
             'public_synthetic_deadlines_slots':world.public.departure.tolist(),
             'all_three_sampled_paused_episodes_do_not_recover':bool((world.recovery[3:]>12).all()),
             'delivered_kwh':{'fixed':a['delivered_kwh'],'learned':b['delivered_kwh'],'empirical':e['delivered_kwh']},
             'different_slots':[]}
    for t in np.flatnonzero((ta['pilot']!=tb['pilot']).any(axis=0)):
        example['different_slots'].append({'slot':int(t),'fixed_pilot_quanta':ta['pilot'][:,t].tolist(),
            'learned_pilot_quanta':tb['pilot'][:,t].tolist(),'fixed_actual_quanta':ta['actual'][:,t].tolist(),
            'learned_actual_quanta':tb['actual'][:,t].tolist()})
    result={'scope':'Post-hoc descriptive failure diagnosis only; models and evaluation unchanged',
            'sites':results,'counterexample':example}
    (out/'diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v['post_recovery_audit'] for k,v in results.items()},indent=2))


if __name__=='__main__': main()
