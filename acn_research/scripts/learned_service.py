"""R1-S1: paired synthetic service worlds driven by held-out real predictions."""
from pathlib import Path
import hashlib,json,pickle,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]; HERE=ROOT/'acn_research'
sys.path.insert(0,str(HERE/'src'))
from acnresearch.recovery import complete_episode_mask
from acnresearch.learned_service import make_service_world,run_service,offline_service
from acnresearch.value import SOLVER_DIAGNOSTICS
from analyze_value import paired_summary


def main():
    out=HERE/'reports/r1'; private=ROOT/'artifacts/acn/r1'
    cfg=json.loads((HERE/'configs/LEARNED_SERVICE_R1.json').read_text())
    selection=json.loads((out/'selection.json').read_text()); model=selection['forecast']
    assert hashlib.sha256((private/'models.pkl').read_bytes()).hexdigest()==selection['models_sha256']
    with (private/'evaluation_predictions.pkl').open('rb') as f: payload=pickle.load(f)
    data=payload['frame']; fixed=selection['policy']['1.0']['fixed']
    threshold=selection['policy']['1.0']['thresholds'][model]
    settings={s:{'kind':s} for s in ['every_1','every_2','every_4','backoff']}
    settings.update(empirical_dp={'empirical':True},learned_dp={},
                    learned_threshold={'kind':'threshold','threshold':threshold},
                    learned_restore={'restore':True},perfect_recovery={'oracle':True})
    for perturb in ['early_10min','late_10min','inflate_0p2']: settings[perturb]={'perturb':perturb}
    rows=[]
    for site,g in data.groupby('split'):
        m=complete_episode_mask(g); g=g.loc[m]
        probs=payload['cdf'][model][g.index]; empirical=payload['cdf']['empirical'][g.index]
        for rate in [6,30]:
            for cap in cfg['feeder_amp']:
                for seed in cfg['seeds']:
                    world=make_service_world(seed,cap,rate,g,probs,empirical)
                    bound=offline_service(world)
                    for policy,kwargs in settings.items():
                        result,trace=run_service(world,**kwargs)
                        assert result['delivered_kwh']<=bound+1e-8
                        if cap==180: assert abs(result['delivered_kwh']-bound)<1e-8
                        rows.append(dict(site=site,recovery_amp=rate,feeder_amp=cap,seed=seed,policy=policy,offline_kwh=bound,**result))
                print(site,rate,cap,'complete',flush=True)
    frame=pd.DataFrame(rows); frame.to_csv(out/'service.csv',index=False)
    groups={}
    for (site,rate,cap),g in frame.groupby(['site','recovery_amp','feeder_amp']):
        pivot=g.pivot(index='seed',columns='policy',values='delivered_kwh')
        groups[f'{site}_{rate}A_recovery_{cap}A_feeder']={
            'mean_kwh':{k:float(v) for k,v in pivot.mean().items()},
            'offline_mean_kwh':float(g.groupby('seed').offline_kwh.first().mean()),
            'comparisons':{f'{policy}_minus_{fixed}':paired_summary(pivot[policy]-pivot[fixed]) for policy in pivot.columns},
            'learned_minus_same_cdf_threshold':paired_summary(pivot.learned_dp-pivot.learned_threshold),
            'learned_minus_empirical_dp':paired_summary(pivot.learned_dp-pivot.empirical_dp)}
    result={'scope':'Conditional exogenous response stress test, real held-out prefix forecasts; synthetic requests/deadlines. Seed CI is conditional on finite resampled episodes, not independent real-world CI.',
            'forecast':model,'selected_fixed':fixed,'worlds':len(frame.groupby(['site','recovery_amp','feeder_amp','seed'])),
            'policy_runs':len(frame),'constraint_violations':0,'groups':groups}
    (out/'service_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'service_solver_diagnostics.json').write_text(json.dumps(SOLVER_DIAGNOSTICS,indent=2)+'\n')
    print(result['worlds'],result['policy_runs'],'saved',flush=True)


if __name__=='__main__': main()
