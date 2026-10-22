import argparse,json,time
import joblib
import numpy as np
import pandas as pd
from patternforecast.automata import PatternFamily
from patternforecast.common import PACKAGE,RUNS,CACHE,protocol,write_json,sha256
from patternforecast.data import load
from patternforecast.certificates import batch_bounds
from patternforecast.communication import replay_policy,evaluate,block_interval

parser=argparse.ArgumentParser();parser.add_argument('--datasets',nargs='+',default=['air','power','metro'])
parser.add_argument('--split',default='development',choices=['development','confirmation'])
parser.add_argument('--backbone',default=None);args=parser.parse_args()
family=PatternFamily()
if args.split=='confirmation' and not (PACKAGE/'configs/FROZEN.json').exists(): raise RuntimeError('not frozen')
for name in args.datasets:
    cfg=protocol()['datasets'][name];data=load(name,args.split);out=RUNS/name
    selection=json.loads((PACKAGE/'reports'/f'models-{name}.json').read_text())
    key=args.backbone or selection['communication_backbone'];model_path=out/f'{key}.joblib'
    pred_path=out/f'{key}-{args.split}-lags.npy'
    pred_meta=pred_path.with_suffix('.json')
    identity={'model_sha256':sha256(model_path),'data_sha256':sha256(CACHE/name/f'{args.split}.npz'),
              'model_code_sha256':sha256(PACKAGE/'src/patternforecast/models.py')}
    if pred_path.exists() and pred_meta.exists() and json.loads(pred_meta.read_text())==identity:
        predictions=np.load(pred_path)
    else:
        model=joblib.load(model_path);predictions=[]
        for lag in range(17):
            start=time.perf_counter();predictions.append(model.predict(data,lag).astype(np.float32))
            print(name,args.split,key,'lag',lag,'seconds',time.perf_counter()-start,flush=True)
        predictions=np.array(predictions);np.save(pred_path,predictions);write_json(pred_meta,identity)
    bounds={k:[] for k in ['bernoulli','cdf','nested','joint','delta']};bound_seconds=[]
    for lag in range(17):
        start=time.perf_counter();b=batch_bounds(predictions[lag],predictions[0],data['q'],family,cfg['horizon_samples'])
        bound_seconds.append(time.perf_counter()-start)
        for k in bounds: bounds[k].append(b[k])
    bounds={k:np.array(v) for k,v in bounds.items()}
    report={'dataset':name,'split':args.split,'backbone':key,'source':identity,'policies':{},
            'strict_joint_vs_cdf_fraction':float((bounds['joint']<bounds['cdf']-1e-9)[1:].mean()),
            'strict_joint_vs_nested_fraction':float((bounds['joint']<bounds['nested']-1e-9)[1:].mean()),
            'certificate_batch_seconds_per_lag':bound_seconds}
    policies=[('all',0)]+[('periodic',k) for k in [2,4,8,16]]
    policies += [(k,e) for k in ['bernoulli','cdf','nested','joint'] for e in protocol()['certificate_epsilons']]
    policies += [('delta',e) for e in [.005,.01,.02,.05,.1,.2]]
    for policy,threshold in policies:
        pred,sends,cert,lags=replay_policy(data,predictions,bounds,policy,threshold)
        epsilon=threshold if policy in ['bernoulli','cdf','nested','joint'] else None
        result=evaluate(data,pred,predictions[0],sends,cert,cfg['horizon_samples'],epsilon)
        report['policies'][f'{policy}:{threshold}']=result
        print(name,policy,threshold,'packets',result['aux_packet_rate'],'brier',result['brier'],flush=True)
    # Same-data paired comparison, preserving policy-specific cache histories.
    report['paired_packet_savings_vs_cdf']={}
    for e in protocol()['certificate_epsilons']:
        a=report['policies'][f'joint:{e}'];b=report['policies'][f'cdf:{e}']
        diff=b['week_packet_sums']-a['week_packet_sums']
        report['paired_packet_savings_vs_cdf'][str(e)]={'absolute_rate_reduction':float(b['aux_packet_rate']-a['aux_packet_rate']),
               'relative_packet_reduction':float(1-a['aux_packet_rate']/b['aux_packet_rate']),
               'absolute_rate_reduction_ci':block_interval(diff,a['week_query_counts'])}
    biz=pd.read_csv(CACHE/name/f'{args.split}-business.csv')
    raw_bytes=24+4*int(np.prod(data['telemetry'].shape[1:]))
    # Explicit payload model: timestamp + entity/sequence metadata + float32 array.
    # Link-layer overhead/compression are not measured by this replay.
    report['byte_accounting']={'telemetry_snapshot_bytes':raw_bytes,'business_event_bytes':17,
          'business_event_count':len(biz),'business_payload_bytes':len(biz)*17,
          'all_telemetry_aux_bytes':len(data['t'])*raw_bytes,
          'all_forecast_vector_aux_bytes':len(data['t'])*(24+9*4),
          'scope':'uncompressed application payload; edge sensing and inference not saved'}
    for result in report['policies'].values():
        result['aux_payload_bytes']=int(round(result['aux_packet_rate']*len(data['t'])))*raw_bytes
    write_json(PACKAGE/'reports'/f'communication-{name}-{args.split}-{key}.json',report)
