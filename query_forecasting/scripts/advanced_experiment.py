import argparse
import json
import sys
import time
import numpy as np
import torch
from patternforecast.polytope import FeasiblePolytope
from queryforecast.common import CACHE, REPORTS, PROTOCOL, PACKAGE, digest, save
from queryforecast.data import load
from queryforecast.model import Source
from queryforecast.monitor import Monitor
sys.path.insert(0, str(PACKAGE/'experiments'))
from advanced import sampling, clustered

parser=argparse.ArgumentParser(); parser.add_argument('domain',choices=['air','power'])
parser.add_argument('--limit',type=int); parser.add_argument('--repetitions',type=int)
args=parser.parse_args(); torch.set_num_threads(1)
data=load(args.domain,'development'); checkpoint=torch.load(CACHE/args.domain/'world.pt',weights_only=False)
count=min(args.limit or 48,len(data['x'])); reps=args.repetitions or 32
mode='advanced' if args.limit is None and args.repetitions is None else f'advanced-pilot-{count}-{reps}'
folder=CACHE/args.domain/mode;folder.mkdir(parents=True,exist_ok=True)
identity={'model':digest(CACHE/args.domain/'world.pt'),'count':count,'replicates':reps,
 'sources':{str(p.relative_to(PACKAGE)):digest(p) for p in sorted((PACKAGE/'src').rglob('*.py'))+
            sorted((PACKAGE/'experiments').glob('*.py'))},'script':digest(__file__),
 'protocol':digest(PACKAGE/'configs/STRONG_BASELINES.json')}
manifest=folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text())!=identity:raise RuntimeError('run changed')
save(manifest,identity)
methods=['arithmetic','arithmetic_permuted','sobol','lhs','hidden_cluster']
monitors=[Monitor(f,PROTOCOL['horizons_native_ticks']) for f in PROTOCOL['families']]
records=[]; start=time.perf_counter()
for i in range(count):
 path=folder/f'origin-{i:03d}.npz'
 if path.exists():records.append(dict(np.load(path)));continue
 source=Source(checkpoint,data['x'][i]);old=dict(np.load(CACHE/args.domain/'registered'/f'origin-{i:03d}.npz'))
 shape=(3,2,len(methods),reps);est=np.zeros((*shape,9));cost=np.zeros(shape);timing=np.zeros(shape);coherent=np.zeros(shape,bool)
 for j,mon in enumerate(monitors):
  q=int(data['q'][i,j]);poly=FeasiblePolytope(mon.vectors(mon.codes((0,q,0,0))))
  for b,budget in enumerate(PROTOCOL['budgets_model_rows']):
   for r in range(reps):
    for k,name in enumerate(methods):
     rng=np.random.default_rng(PROTOCOL['seed']+100000*i+1000*j+10*r+b);begin=time.perf_counter()
     if name=='hidden_cluster':value,meta=clustered(source,mon,q,budget,rng)
     else:value,meta=sampling(source,mon,q,budget,rng,name)
     est[j,b,k,r]=value;cost[j,b,k,r]=meta['rows'];timing[j,b,k,r]=time.perf_counter()-begin
     coherent[j,b,k,r]=poly.contains(value)[0]
     if meta['rows']>budget:raise AssertionError('budget exceeded')
 rec={'estimates':est,'rows':cost,'seconds':timing,'coherent':coherent,'truth':old['truth']}
 np.savez_compressed(path,**rec);records.append(rec)
 print(args.domain,mode,f'{i+1}/{count}',round(time.perf_counter()-start,1),flush=True)
result={'domain':args.domain,'mode':mode,'count':count,'replicates':reps,'methods':methods,'results':[]}
for b,budget in enumerate(PROTOCOL['budgets_model_rows']):
 e=np.array([np.mean((v['estimates'][:,b]-v['truth'][:,None,None])**2,axis=(-2,-1)) for v in records])
 for k,name in enumerate(methods):
  result['results'].append({'budget':budget,'method':name,'mse':float(e[:,:,k].mean()),
   'family_mse':e[:,:,k].mean(0),'rows':float(np.mean([v['rows'][:,b,k] for v in records])),
   'seconds':float(np.mean([v['seconds'][:,b,k] for v in records])),
   'incoherent_runs':int(sum((~v['coherent'][:,b,k]).sum() for v in records))})
save(REPORTS/f'{args.domain}-{mode}.json',result)
