"""Frozen same-information forecasting comparison, including unseen stations."""
import argparse,time
import joblib
import numpy as np
from patternforecast.common import FAMILY,REPORTS,RUNS,write_json,experiment_cfg,protocol
from patternforecast.freeze import verify_freeze
from patternforecast.data import load,targets
from patternforecast.models import score,subset
from patternforecast.automata import PatternFamily
from patternforecast.polytope import FeasiblePolytope
from patternforecast.communication import weekly,block_interval

p=argparse.ArgumentParser();p.add_argument('--datasets',nargs='+',default=['air','power']);a=p.parse_args()
for name in a.datasets:
    frozen=verify_freeze(name);cfg=experiment_cfg(name,'short');entry=frozen['datasets'][name]
    data=load(name,'confirmation');y,known=targets(data,cfg['horizon_samples']);complete=known.all((1,2))
    family=PatternFamily();polys=[FeasiblePolytope(family.feasible(q,tuple(cfg['horizon_samples']))) for q in range(len(family.states))]
    groups={'all':np.ones(len(y),dtype=bool)}
    if name=='air':
        groups['seen_stations']=np.isin(data['entity'],cfg['training_entities'])
        groups['unseen_stations']=~groups['seen_stations']
    report=dict(dataset=name,family=FAMILY,split='confirmation',frozen_commit=frozen['code_commit'],
                backbone=entry['backbone'],metrics={},comparisons={})
    predictions={}
    for key in entry['models']:
        start=time.perf_counter();model=joblib.load(RUNS/name/f'{key}.joblib')
        pred=model.predict(data).astype(np.float32).astype(float)
        projected=pred.reshape(-1,9).copy()
        for q in np.unique(data['q']):
            ix=data['q']==q;projected[ix]=polys[q].project(projected[ix])
        projected=projected.reshape(-1,3,3)
        predictions[key]=projected
        row=dict(seconds=time.perf_counter()-start,groups={})
        for group,mask in groups.items():
            local=subset(data,np.flatnonzero(mask));valid=complete&mask
            base=float(np.mean(y[valid]**2));loss=np.mean((projected-y)**2,(1,2))
            _,sums,counts=weekly(data,loss,valid)
            row['groups'][group]=dict(unprojected=score(local,pred[mask],cfg['horizon_samples']),
                 coherent=score(local,projected[mask],cfg['horizon_samples']),zero_brier=base,
                 coherent_brier_ci=block_interval(sums,counts),week_loss_sums=sums,week_scored_counts=counts,
                 per_horizon_brier=np.mean((projected[valid]-y[valid])**2,axis=0),
                 brier_skill_vs_zero=1-float(np.mean(loss[valid]))/base if base>0 else None)
        report['metrics'][key]=row
        print(FAMILY,name,key,row['groups']['all']['coherent']['brier_complete'],flush=True)
        write_json(REPORTS/f'confirmation-models-{name}.json',report)
    primary=predictions[entry['backbone']]
    for key,pred in predictions.items():
        delta=np.mean((primary-y)**2-(pred-y)**2,(1,2))
        _,sums,counts=weekly(data,delta,complete)
        report['comparisons'][key]=dict(primary_minus_comparator=float(delta[complete].mean()),
                                         paired_ci=block_interval(sums,counts))
    write_json(REPORTS/f'confirmation-models-{name}.json',report)
