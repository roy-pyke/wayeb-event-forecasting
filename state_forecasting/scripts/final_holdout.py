"""One frozen prequential holdout evaluation; no architecture choices are made here."""
import argparse
import json
import platform
from pathlib import Path
import time
import joblib
import numpy as np
import pandas as pd
from stateforecast.data import PACKAGE, ROOT, CACHE, load_split, sha256
from stateforecast.rolling import concatenate, replay
from stateforecast.mixer import causal_mix, DelayedExpertMixer
from stateforecast.evaluate import metrics, paired_bootstrap, subset


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    frozen=json.loads((PACKAGE/'configs/FROZEN.json').read_text())
    for path,digest in frozen['source_hashes'].items():
        if sha256(PACKAGE/path)!=digest:raise ValueError(f'frozen source changed: {path}')
    protocol=json.loads((PACKAGE/'configs/PROTOCOL.json').read_text())
    assert sha256(PACKAGE/'configs/PROTOCOL.json')==frozen['protocol_sha256']
    h=protocol['horizons_seconds']
    parts=[load_split(CACHE/'prepared',s) for s in ['train','select','calibrate','development','holdout']]
    holdout=parts[-1]
    model_report=replay(concatenate(parts),holdout,protocol,args.output,
                        window_days=frozen['window_days'],calibration_days=frozen['calibration_days'],
                        iterations=frozen['iterations'],leaves=frozen['leaves'])
    predictions=dict(np.load(args.output/'predictions.npz'))
    report=dict(scope='frozen prequential holdout; earlier holdout outcomes may update later days causally',
                frozen_config=frozen,platform=platform.platform(),
                data_manifest=json.loads((CACHE/'prepared/manifest.json').read_text()),models={},comparisons={},feedback={})
    weights={}
    for name,source in [('G1','M1-16'),('G2','M2')]:
        predictions[name],weights[name],report['feedback'][name]=causal_mix(
            holdout,predictions['M0'],predictions[source],h,eta=frozen['eta'],share=frozen['share'])
    for name,p in predictions.items():report['models'][name]=metrics(holdout,p,h)
    for name in ['M1-16','M2','G1','G2']:
        report['comparisons'][name]=paired_bootstrap(holdout,predictions['M0'],predictions[name],h)
    report['continuous_vs_discrete']=paired_bootstrap(holdout,predictions['G1'],predictions['G2'],h)
    selected=frozen['selected'];report['selected']=selected
    report['relative_reduction']=1-report['models'][selected]['mean_brier']/report['models']['M0']['mean_brier']
    report['monthly']={}
    months=pd.to_datetime(holdout['start'],unit='s').strftime('%Y-%m')
    for month in np.unique(months):
        mask=months==month;part=subset(holdout,mask)
        scores={name:metrics(part,p[mask],h)['mean_brier'] for name,p in predictions.items()}
        report['monthly'][month]=scores
    last=model_report['updates'][-1]['date']
    baseline=joblib.load(args.output/f'{last}-M0.joblib')
    context=joblib.load(args.output/f'{last}-M2.joblib')
    mixer=DelayedExpertMixer(eta=frozen['eta'],share=frozen['share'])
    runtimes=[]
    for i in range(220):
        x=holdout['X'][i:i+1]
        start=time.perf_counter()
        mixer.predict(np.stack([baseline.predict_cdf(x,h)[0],context.predict_cdf(x,h)[0]]))
        if i>=20:runtimes.append((time.perf_counter()-start)*1000)
    report['performance']=dict(single_query_prediction_p50_ms=float(np.median(runtimes)),
                                single_query_prediction_p95_ms=float(np.quantile(runtimes,.95)),
                                combined_expert_model_MiB=sum((args.output/f'{last}-{n}.joblib').stat().st_size for n in ['M0','M2'])/2**20,
                                latency_scope='two hazard experts + shared calibration + mixture, excludes network and training')
    checks=protocol['excellence_criteria']
    report['quality_checks']={
        'relative_brier_reduction':report['relative_reduction']>=checks['relative_brier_reduction_vs_M0_at_least'],
        'paired_improvement_ci':report['comparisons'][selected]['ci95'][0]>0,
        'calibration_60s':report['models'][selected]['60']['ece']<=checks['primary_60s_equal_width_ECE_at_most'],
        'positive_months':sum(v[selected]<v['M0'] for v in report['monthly'].values())>=checks['positive_vs_M0_months_at_least'],
        'model_size':report['performance']['combined_expert_model_MiB']<=checks['saved_model_size_MiB_at_most'],
        'latency':report['performance']['single_query_prediction_p95_ms']<=checks['single_query_latency_p95_ms_at_most'],
        'no_early_feedback':all(v['early_feedback']==0 for v in report['feedback'].values()),
        'causal_daily_training':all(u['train_latest_information']<=u['update_time'] and u['calibration_latest_information']<=u['update_time'] for u in model_report['updates'])}
    report['quality_pass']=all(report['quality_checks'].values())
    report['independent_checks_required']=['reports/recognition.json','unittest results','controls and stress reports']
    np.savez_compressed(args.output/'all_predictions.npz',**predictions)
    np.savez_compressed(args.output/'mixture_weights.npz',**weights)
    (args.output/'holdout.json').write_text(json.dumps(report,indent=2)+'\n')
    (PACKAGE/'reports/holdout.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['relative_reduction','continuous_vs_discrete','monthly','performance','quality_checks','quality_pass']},indent=2))


if __name__=='__main__':main()
