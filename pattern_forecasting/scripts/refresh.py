import argparse,json,time
import numpy as np
from patternforecast.common import PACKAGE,RUNS,protocol,write_json,experiment_cfg
from patternforecast.data import load
from patternforecast.models import subset
from patternforecast.automata import PatternFamily
from patternforecast.communication import evaluate,weekly,block_interval
from patternforecast.refresh import refresh_replay

p=argparse.ArgumentParser();p.add_argument('--dataset',default='air');p.add_argument('--split',default='development')
p.add_argument('--backbone',default='hgb-31-180-s20261022');p.add_argument('--limit',type=int,default=0)
p.add_argument('--full-coherence',action='store_true')
p.add_argument('--epsilon',nargs='+',type=float,default=[.002,.005,.01,.02,.05]);a=p.parse_args()
if a.split=='confirmation' and not (PACKAGE/'configs/FROZEN.json').exists(): raise RuntimeError('not frozen')
data=load(a.dataset,a.split);cfg=experiment_cfg(a.dataset,'short' if a.backbone.startswith('short-') else 'long')
path=RUNS/a.dataset/f'{a.backbone}-{a.split}-lags.npy'
if path.exists(): full=np.load(path,mmap_mode='r')[0].copy()
else:
    import joblib
    full=joblib.load(RUNS/a.dataset/f'{a.backbone}.joblib').predict(data).astype(np.float32)
if a.limit: data=subset(data,np.arange(min(a.limit,len(full))));full=full[:a.limit]
report={'dataset':a.dataset,'split':a.split,'backbone':a.backbone,'limit':a.limit,'full_coherence':a.full_coherence,'policies':{}}
family=PatternFamily()
for epsilon in a.epsilon:
    for sparse in [False,True]:
        for mode in ['cdf','nested','joint']:
            start=time.perf_counter();r=refresh_replay(data,full,family,cfg['horizon_samples'],mode,epsilon,sparse,a.full_coherence)
            score=evaluate(data,r['pred'],r['full'],r['sends'],r['certificate'],cfg['horizon_samples'],epsilon)
            score['max_policy_certificate']=score.pop('max_joint_certificate')
            score['certificate_type']=mode
            weeks,bs,bc=weekly(data,r['bytes'])
            score.update(total_payload_bytes=int(r['bytes'].sum()),bytes_per_query=float(r['bytes'].mean()),
                    bytes_per_query_ci=block_interval(bs,bc),week_byte_sums=bs,
                    refreshed_coordinates=int(r['coordinates'].sum()),replay_seconds=time.perf_counter()-start,
                    max_coordinate_age_queries=int(r['coordinate_age'].max()))
            key=f'{"sparse" if sparse else "whole"}-{mode}:{epsilon}';report['policies'][key]=score
            print(a.dataset,key,{k:score[k] for k in ['bytes_per_query','aux_packet_rate','excess_brier','replay_seconds']},flush=True)
            tag='-coherent' if a.full_coherence else ''
            write_json(PACKAGE/'reports'/f'refresh-{a.dataset}-{a.split}-{a.backbone}-n{a.limit}{tag}.json',report)
