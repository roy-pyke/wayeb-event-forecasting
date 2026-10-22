"""Compare semantic coordinate representations with identical strong codecs."""
import argparse,json,time
import joblib
import numpy as np
from patternforecast.common import CONFIG,REPORTS,RUNS,FAMILY,write_json,experiment_cfg,sha256
from patternforecast.data import load
from patternforecast.automata import PatternFamily
from patternforecast.communication import evaluate,weekly,block_interval
from patternforecast.affine import replay
from patternforecast.models import subset

p=argparse.ArgumentParser()
p.add_argument('--dataset',default='air');p.add_argument('--split',default='development')
p.add_argument('--backbone',default='short-hgb-31-180-s20261022')
p.add_argument('--epsilon',type=float,default=.002);p.add_argument('--limit',type=int,default=0)
p.add_argument('--representations',nargs='+',default=['all','static','zero','basis'])
p.add_argument('--no-partial',action='store_true');a=p.parse_args()
if a.split=='confirmation' and not (CONFIG/'FROZEN.json').exists():raise RuntimeError('not frozen')
data=load(a.dataset,a.split);modelpath=RUNS/a.dataset/f'{a.backbone}.joblib'
cfg=experiment_cfg(a.dataset,'short' if a.backbone.startswith('short-') else 'long')
full=joblib.load(modelpath).predict(data).astype(np.float32)
if a.limit:data=subset(data,np.arange(min(a.limit,len(full))));full=full[:a.limit]
family=PatternFamily()
report=dict(dataset=a.dataset,family=FAMILY,split=a.split,backbone=a.backbone,
            model_sha256=sha256(modelpath),epsilon=a.epsilon,limit=a.limit,
            partial=not a.no_partial,policies={})
for representation in a.representations:
    start=time.perf_counter()
    r=replay(data,full,family,cfg['horizon_samples'],representation,a.epsilon,not a.no_partial)
    scores=evaluate(data,r['pred'],r['full'],r['sends'],r['certificate'],cfg['horizon_samples'],a.epsilon)
    _,bs,bc=weekly(data,r['bytes'])
    scores.update(bytes_per_query=float(r['bytes'].mean()),total_payload_bytes=int(r['bytes'].sum()),
                  bytes_per_query_ci=block_interval(bs,bc),week_byte_sums=bs,
                  wire_precision_counts={str(int(b)):int(np.sum(r['precision']==b)) for b in np.unique(r['precision'])},
                  seconds=time.perf_counter()-start,maps=r['maps'])
    report['policies'][representation]=scores
    print(representation,{k:scores[k] for k in ['bytes_per_query','aux_packet_rate','excess_brier','seconds','wire_precision_counts']},flush=True)
    tag='-full-only' if a.no_partial else ''
    write_json(REPORTS/f'codec-{a.dataset}-{a.split}-{a.backbone}-e{a.epsilon}-n{a.limit}{tag}.json',report)
