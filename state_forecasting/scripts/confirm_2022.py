import argparse
import json
from pathlib import Path
import platform
import time
import joblib
import numpy as np
from stateforecast.data import PACKAGE,load_split,sha256
from stateforecast.metro2022 import prepare_2022
from stateforecast.rolling import replay,concatenate
from stateforecast.online_fast import raw_and_calibrated
from stateforecast.fast_feedback import FastOutcomeExpert
from stateforecast.mixer import DelayedExpertMixer
from evaluate_fast import evaluate


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    frozen=json.loads((PACKAGE/'configs/FROZEN_2022.json').read_text())
    for name,digest in frozen['hashes'].items():
        if sha256(PACKAGE/name)!=digest:raise ValueError(f'frozen confirmation source changed: {name}')
    config=json.loads((PACKAGE/'configs/CONFIRMATION_2022.json').read_text())
    protocol=json.loads((PACKAGE/'configs/PROTOCOL.json').read_text())
    directory=prepare_2022()
    before,data=[load_split(directory,n) for n in ['warmup','confirmation']]
    strategy=config['strategy'];h=config['horizons_seconds']
    daily=replay(concatenate([before,data]),data,protocol,args.output,
                 window_days=strategy['daily_training_window_days'],calibration_days=strategy['calibration_days'],
                 iterations=strategy['iterations'],leaves=strategy['leaves'])
    raw=dict(np.load(args.output/'raw_predictions.npz'));cal=dict(np.load(args.output/'predictions.npz'))
    report,p,w=evaluate(data,raw,cal,h)
    report['scope']='new 2022 confirmation cohort; architecture frozen using only 2020 development/diagnostics'
    report['frozen']=frozen;report['data']=json.loads((directory/'manifest.json').read_text())
    report['platform']=platform.platform()
    last=daily['updates'][-1]['date'];m0=joblib.load(args.output/f'{last}-M0.joblib');m2=joblib.load(args.output/f'{last}-M2.joblib')
    mixer=DelayedExpertMixer(5);fast=FastOutcomeExpert(h);times=[]
    for i in range(220):
        x=data['X'][i:i+1];start=time.perf_counter()
        raw0,cal0=raw_and_calibrated(m0,x,h);raw2,cal2=raw_and_calibrated(m2,x,h);dynamic,_=fast.predict(x[0])
        mixer.predict(np.stack([raw0,cal0,raw2,cal2,dynamic]))
        if i>=20:times.append((time.perf_counter()-start)*1000)
    report['performance']=dict(p95_ms=float(np.quantile(times,.95)),p50_ms=float(np.median(times)),
                               model_MiB=sum((args.output/f'{last}-{n}.joblib').stat().st_size for n in ['M0','M2'])/2**20)
    rule=config['criteria']
    report['checks']=dict(relative_reduction=report['relative_reduction']>=rule['relative_brier_reduction_vs_F0'],
                          paired_ci=report['comparisons']['F2']['ci95'][0]>0,
                          calibration=report['models']['F2']['60']['ece']<=rule['ECE_60s_at_most'],
                          positive_months=sum(v['F2']<v['F0'] for v in report['monthly'].values())>=rule['positive_months_at_least'],
                          latency=report['performance']['p95_ms']<=rule['single_query_p95_ms_at_most'],
                          model_size=report['performance']['model_MiB']<=rule['models_MiB_at_most'])
    report['quality_pass']=all(report['checks'].values())
    np.savez_compressed(args.output/'fast_predictions.npz',**p);np.savez_compressed(args.output/'fast_weights.npz',**w)
    (args.output/'confirmation.json').write_text(json.dumps(report,indent=2)+'\n')
    (PACKAGE/'reports/confirmation-2022.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['relative_reduction','continuous_vs_discrete','monthly','performance','checks','quality_pass']},indent=2))


if __name__=='__main__':main()
