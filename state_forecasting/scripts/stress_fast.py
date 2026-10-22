"""Final-system stresses with identical business events and query times."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from stateforecast.data import PACKAGE,CACHE,BASE,CONTEXT,load_split
from stateforecast.online_fast import raw_and_calibrated
from stateforecast.fast_feedback import adaptive_forecast
from stateforecast.evaluate import metrics


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);args=ap.parse_args()
    d=load_split(CACHE/'metropt2022','confirmation');h=[30,60,120]
    raw=dict(np.load(args.run/'raw_predictions.npz'));cal=dict(np.load(args.run/'predictions.npz'));clean=dict(np.load(args.run/'fast_predictions.npz'))
    dates=pd.to_datetime(d['time'],unit='s').strftime('%Y-%m-%d')
    contexts=slice(len(BASE),len(BASE)+len(CONTEXT));rng=np.random.default_rng(20261022)
    scenarios={}
    missing=d['X'].copy();missing[:,contexts]=np.nan;missing[:,-1]=np.inf;scenarios['all_telemetry_missing']=missing
    delayed=d['X'].copy()
    for eid in np.unique(d['instance']):
        ix=np.flatnonzero(d['instance']==eid)
        delayed[ix[0],contexts]=np.nan;delayed[ix[0],-1]=np.inf
        delayed[ix[1:],contexts]=d['X'][ix[:-1],contexts]
        delayed[ix[1:],-1]=d['time'][ix[1:]]-d['time'][ix[:-1]]
    scenarios['one_landmark_snapshot_delay']=delayed
    shuffled=d['X'].copy()
    for day in np.unique(dates):
        ix=np.flatnonzero(dates==day);shuffled[ix,contexts]=d['X'][rng.permutation(ix),contexts]
    scenarios['within_day_context_permutation']=shuffled
    report=dict(scope='final 2022 model; inference-time snapshot stress, not new training or network measurements',
                baseline=metrics(d,clean['F0'],h),clean=metrics(d,clean['F2'],h),scenarios={})
    for name,x in scenarios.items():
        p_raw=np.zeros_like(raw['M2']);p_cal=np.zeros_like(p_raw)
        stale=(x[:,-1]>30)|~np.isfinite(x[:,len(BASE)+1])
        for day in np.unique(dates):
            ix=np.flatnonzero(dates==day);m=joblib.load(args.run/f'{day}-M2.joblib')
            p_raw[ix]=m.predict_cdf(x[ix],h,calibrated=False)
            p_cal[ix]=m.calibrator.predict(p_raw[ix].ravel()).reshape(-1,3) if m.calibrator is not None else p_raw[ix]
        p_raw[stale]=raw['M0'][stale];p_cal[stale]=cal['M0'][stale]
        experts=np.stack([raw['M0'],cal['M0'],p_raw,p_cal],axis=1)
        p,_,audit=adaptive_forecast(dict(d,X=x),experts,h)
        p[stale]=clean['F0'][stale]
        if name=='all_telemetry_missing':np.testing.assert_allclose(p,clean['F0'],rtol=0,atol=1e-15)
        report['scenarios'][name]=dict(metrics=metrics(d,p,h),fallback_fraction=float(stale.mean()),audit=audit)
        print(name,report['scenarios'][name]['metrics']['mean_brier'],flush=True)
    (PACKAGE/'reports/stress-final-2022.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
