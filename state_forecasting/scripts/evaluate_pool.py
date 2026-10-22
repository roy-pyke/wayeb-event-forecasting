import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from stateforecast.data import CACHE,PACKAGE,load_split
from stateforecast.adaptive_pool import causal_pool
from stateforecast.evaluate import metrics,paired_bootstrap,subset


def evaluate(data,raw,cal,h):
    p={};w={};audit={}
    baseline=[raw['M0'],cal['M0']]
    for name,experts in [('B0',baseline),('B1',baseline+[raw['M1-16'],cal['M1-16']]),('B2',baseline+[raw['M2'],cal['M2']])]:
        p[name],w[name],audit[name]=causal_pool(data,np.stack(experts,axis=1),h)
    r=dict(models={n:metrics(data,v,h) for n,v in p.items()},feedback=audit,
           comparisons={n:paired_bootstrap(data,p['B0'],p[n],h) for n in ['B1','B2']},
           continuous_vs_discrete=paired_bootstrap(data,p['B1'],p['B2'],h))
    r['relative_reduction']=1-r['models']['B2']['mean_brier']/r['models']['B0']['mean_brier']
    r['monthly']={}
    months=pd.to_datetime(data['start'],unit='s').strftime('%Y-%m')
    for m in np.unique(months):
        mask=months==m;r['monthly'][m]={n:metrics(subset(data,mask),v[mask],h)['mean_brier'] for n,v in p.items()}
    return r,p,w


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--split',choices=['development','holdout'],required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    data=load_split(CACHE/'prepared',args.split)
    raw=dict(np.load(args.run/'raw_predictions.npz'));cal=dict(np.load(args.run/'predictions.npz'))
    h=json.loads((PACKAGE/'configs/PROTOCOL.json').read_text())['horizons_seconds']
    report,p,w=evaluate(data,raw,cal,h)
    report['scope']='post-holdout diagnostic; not independent confirmation'
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    np.savez_compressed(args.output/'predictions.npz',**p);np.savez_compressed(args.output/'weights.npz',**w)
    print('Relative reduction',report['relative_reduction'])
    for n,v in report['models'].items():print(n,v['mean_brier'],'ECE60',v['60']['ece'])
    print(report['comparisons'])


if __name__=='__main__':main()
