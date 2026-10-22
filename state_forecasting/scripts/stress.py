"""Report robustness boundaries without changing frozen models or thresholds."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from stateforecast.data import PACKAGE,CACHE,BASE,CONTEXT,load_split,prepare
from stateforecast.evaluate import metrics
from stateforecast.mixer import causal_mix


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True)
    args=ap.parse_args()
    protocol=json.loads((PACKAGE/'configs/PROTOCOL.json').read_text());h=protocol['horizons_seconds']
    clean=load_split(CACHE/'prepared','holdout')
    clean_prediction=dict(np.load(args.run/'all_predictions.npz'))
    dates=pd.to_datetime(clean['time'],unit='s').strftime('%Y-%m-%d')
    rng=np.random.default_rng(20261022)
    scenarios={}
    for name,delay,drop in [('delay_30_seconds',30.,0.),('drop_half_telemetry',0.,.5)]:
        d=load_split(prepare(protocol,delay=delay,drop_probability=drop),'holdout')
        np.testing.assert_array_equal(d['time'],clean['time']);np.testing.assert_array_equal(d['instance'],clean['instance'])
        scenarios[name]=d['X']
    missing=clean['X'].copy();missing[:,len(BASE):]=np.nan;missing[:,-1]=np.inf
    scenarios['missing_all_telemetry']=missing
    shuffled=clean['X'].copy()
    for day in np.unique(dates):
        ix=np.flatnonzero(dates==day);permutation=rng.permutation(ix)
        shuffled[ix,len(BASE):len(BASE)+len(CONTEXT)]=shuffled[permutation,len(BASE):len(BASE)+len(CONTEXT)]
    scenarios['permuted_context_within_day']=shuffled
    report=dict(scope='frozen models; telemetry stresses only; business events and forecast queries fixed',
                clean=metrics(clean,clean_prediction['G2'],h),baseline=metrics(clean,clean_prediction['M0'],h),scenarios={})
    for name,x in scenarios.items():
        raw=np.zeros_like(clean_prediction['M2']);fallback=(x[:,-1]>30)|(~np.isfinite(x[:,len(BASE)+1]))
        for day in np.unique(dates):
            ix=np.flatnonzero(dates==day)
            model=joblib.load(args.run/f'{day}-M2.joblib')
            raw[ix]=model.predict_cdf(x[ix],h)
        guarded=raw.copy();guarded[fallback]=clean_prediction['M0'][fallback]
        p,_,audit=causal_mix(clean,clean_prediction['M0'],guarded,h)
        report['scenarios'][name]=dict(raw_context=metrics(clean,raw,h),guarded_mixture=metrics(clean,p,h),
                                       fallback_fraction=float(fallback.mean()),feedback=audit)
        if name=='missing_all_telemetry':
            np.testing.assert_allclose(p,clean_prediction['M0'],rtol=0,atol=1e-15)
        print(name,report['scenarios'][name]['guarded_mixture']['mean_brier'],flush=True)
    (PACKAGE/'reports/stress.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
