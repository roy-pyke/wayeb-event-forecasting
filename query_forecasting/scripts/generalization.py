import argparse
import json
import sys
import time
import numpy as np
import pandas as pd
import torch
from patternforecast.polytope import FeasiblePolytope
from queryforecast.common import ROOT,CACHE,REPORTS,PROTOCOL,PACKAGE,digest,save
from queryforecast.data import load
from queryforecast.model import Source
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact,stratified
sys.path.insert(0,str(PACKAGE/'experiments'))
from pooling import pooled
from advanced import clustered,sampling

parser=argparse.ArgumentParser();parser.add_argument('domain',choices=['air','power'])
parser.add_argument('--limit',type=int);parser.add_argument('--repetitions',type=int)
args=parser.parse_args();torch.set_num_threads(1)
cfg=json.loads((PACKAGE/'configs/GENERALIZATION.json').read_text())
data=load(args.domain,'development');checkpoint=torch.load(CACHE/args.domain/'world.pt',weights_only=False)
indices=list(range(0,48,4));indices=indices[:args.limit] if args.limit else indices
reps=args.repetitions or cfg['replicates']
mode='generalization' if args.limit is None and args.repetitions is None else f'generalization-pilot-{len(indices)}-{reps}'
folder=CACHE/args.domain/mode;folder.mkdir(parents=True,exist_ok=True)
identity={'model':digest(CACHE/args.domain/'world.pt'),'indices':indices,'replicates':reps,
 'sources':{str(p.relative_to(PACKAGE)):digest(p) for p in sorted((PACKAGE/'src').rglob('*.py'))+sorted((PACKAGE/'experiments').glob('*.py'))},
 'script':digest(__file__),'protocol':digest(PACKAGE/'configs/GENERALIZATION.json'),
 'dfa':digest(PACKAGE/'configs/heldout_structure/dfa.json')}
manifest=folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text())!=identity:raise RuntimeError('run changed')
save(manifest,identity)
payload=json.loads((PACKAGE/'configs/heldout_structure/dfa.json').read_text())
monitors=[Monitor(f,cfg['horizons'],payload if f=='heldout_structure' else None) for f in cfg['families']]
newq=np.zeros(48,dtype=int)
events=pd.read_csv(ROOT/'.cache/pattern_forecasting/multisignal'/args.domain/'development-business.csv')
for (entity,segment),group in events.groupby(['entity','segment'],sort=False):
 rows=np.flatnonzero((data['entity']==entity)&(data['segment']==segment))
 if not len(rows):continue
 q=0;states=[]
 for a in group.symbol:q=int(monitors[-1].next[q,ord(a)-65]);states.append(q)
 pos=np.searchsorted(group.timestamp.to_numpy(),data['t'][rows],side='right')-1
 newq[rows]=np.where(pos>=0,np.array(states)[np.maximum(pos,0)],0)
methods=['mass','semantic_priority','single','depth','semantic_pool','hidden_cluster','arithmetic','sobol']
records=[];started=time.perf_counter()
for i in indices:
 path=folder/f'origin-{i:03d}.npz'
 if path.exists():records.append(dict(np.load(path)));continue
 source=Source(checkpoint,data['x'][i]);shape=(4,2,len(methods),reps)
 est=np.zeros((*shape,9));cost=np.zeros(shape);timing=np.zeros(shape);coherent=np.zeros(shape,bool)
 truth=[];actual=[];refrows=[];reftime=[]
 for j,mon in enumerate(monitors):
  q=int(data['q'][i,j]) if j<3 else int(newq[i]);source.rows=0;start=time.perf_counter()
  reference=exact(source,mon,q);truth.append(reference);refrows.append(source.rows);reftime.append(time.perf_counter()-start)
  actual.append(mon.targets(data['y'][i,:mon.H],q));poly=FeasiblePolytope(mon.vectors(mon.codes((0,q,0,0))))
  for b,budget in enumerate(cfg['budgets']):
   for r in range(reps):
    for k,name in enumerate(methods):
     rng=np.random.default_rng(PROTOCOL['seed']+100000*i+1000*j+10*r+b);begin=time.perf_counter()
     if name in ['mass','semantic_priority']:v,m=stratified(source,mon,q,budget,rng,semantic=name=='semantic_priority')
     elif name in ['arithmetic','sobol']:v,m=sampling(source,mon,q,budget,rng,name)
     elif name=='hidden_cluster':v,m=clustered(source,mon,q,budget,rng)
     else:v,m=pooled(source,mon,q,budget,rng,'semantic' if name=='semantic_pool' else name)
     timing[j,b,k,r]=time.perf_counter()-begin;est[j,b,k,r]=v;cost[j,b,k,r]=m['rows'];coherent[j,b,k,r]=poly.contains(v)[0]
  print(args.domain,mode,i,mon.family,'done',round(time.perf_counter()-started,1),flush=True)
 rec={'estimates':est,'rows':cost,'seconds':timing,'coherent':coherent,'truth':np.array(truth),
      'actual':np.array(actual),'reference_rows':refrows,'reference_seconds':reftime,'timestamp':data['t'][i]}
 np.savez_compressed(path,**rec);records.append(rec)
result={'domain':args.domain,'mode':mode,'indices':indices,'replicates':reps,'methods':methods,'families':cfg['families'],
 'model_brier_observed':float(np.mean([(v['truth']-v['actual'])**2 for v in records])),
 'reference_rows_mean':float(np.mean([v['reference_rows'] for v in records])),
 'results':[]}
errors=[]
for b,budget in enumerate(cfg['budgets']):
 e=np.array([np.mean((v['estimates'][:,b]-v['truth'][:,None,None])**2,axis=(-2,-1)) for v in records]);errors.append(e)
 for k,name in enumerate(methods):
  result['results'].append({'budget':budget,'method':name,'mse':float(e[:,:,k].mean()),'family_mse':e[:,:,k].mean(0),
   'rows':float(np.mean([v['rows'][:,b,k] for v in records])),'seconds':float(np.mean([v['seconds'][:,b,k] for v in records])),
   'incoherent_runs':int(sum((~v['coherent'][:,b,k]).sum() for v in records))})
e=errors[1].mean(1);best=min([0,1,2,3,5,6,7],key=lambda k:e[:,k].mean())
ids=np.random.default_rng(PROTOCOL['seed']).integers(len(indices),size=(2000,len(indices)));means=e[ids].mean(1)
ci=np.quantile(1-means[:,4]/np.maximum(means[:,best],1e-30),[.025,.975]);gain=1-e[:,4].mean()/e[:,best].mean()
result['primary']={'best_baseline':methods[best],'relative_mse_reduction':float(gain),'origin_bootstrap_95':ci,
 'passed':bool(gain>=.2 and ci[0]>0 and all(v['coherent'][:,:,4].all() for v in records))}
save(REPORTS/f'{args.domain}-{mode}.json',result);print(result['primary'],flush=True)
