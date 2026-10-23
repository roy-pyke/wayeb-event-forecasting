import argparse
import json
import sys
import time
import numpy as np
import pandas as pd
import torch
from patternforecast.polytope import FeasiblePolytope
from queryforecast.common import ROOT,PACKAGE,CACHE,REPORTS,PROTOCOL,digest,save
from queryforecast.data import load
from queryforecast.model import Source
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
sys.path.insert(0,str(PACKAGE/'experiments'))
sys.path.insert(0,str(PACKAGE/'audits'))
sys.path.insert(0,str(PACKAGE/'compositional'))
from abstractions import abstract_pooled
from monitor import JointMonitor,HarmonicPotential
from propagation import propagate,sample

parser=argparse.ArgumentParser();parser.add_argument('domain',choices=['air','power'])
parser.add_argument('--limit',type=int);parser.add_argument('--repetitions',type=int)
args=parser.parse_args();torch.set_num_threads(1)
data=load(args.domain,'development');checkpoint=torch.load(CACHE/args.domain/'world.pt',weights_only=False)
cfg=json.loads((PACKAGE/'configs/BALANCED_PROPAGATION.json').read_text())
count=args.limit or 48;reps=args.repetitions or 32
mode='balanced' if args.limit is None and args.repetitions is None else f'balanced-pilot-{count}-{reps}'
folder=CACHE/args.domain/mode;folder.mkdir(parents=True,exist_ok=True)
identity={'model':digest(CACHE/args.domain/'world.pt'),'count':count,'replicates':reps,'script':digest(__file__),
 'protocol':digest(PACKAGE/'configs/BALANCED_PROPAGATION.json'),
 'sources':{str(p.relative_to(PACKAGE)):digest(p) for p in sorted((PACKAGE/'src').rglob('*.py'))+
            sorted((PACKAGE/'compositional').glob('*.py'))+[PACKAGE/'experiments/pooling.py',PACKAGE/'audits/abstractions.py']}}
manifest=folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text())!=identity:raise RuntimeError('run changed')
save(manifest,identity)
payload=json.loads((PACKAGE/'configs/heldout_structure/dfa.json').read_text())
families=['nested','directional','multisignal','heldout_structure']
parts=[Monitor(f,(2,4,8),payload if f=='heldout_structure' else None) for f in families]
mon=JointMonitor(parts)
newq=np.zeros(48,int)
events=pd.read_csv(ROOT/'.cache/pattern_forecasting/multisignal'/args.domain/'development-business.csv')
for (entity,segment),group in events.groupby(['entity','segment'],sort=False):
 ix=np.flatnonzero((data['entity']==entity)&(data['segment']==segment))
 if not len(ix):continue
 q=0;states=[]
 for a in group.symbol:q=int(parts[-1].next[q,ord(a)-65]);states.append(q)
 pos=np.searchsorted(group.timestamp.to_numpy(),data['t'][ix],side='right')-1
 newq[ix]=np.where(pos>=0,np.array(states)[np.maximum(pos,0)],0)
methods=['harmonic','mass','monitor_we','mc','potential','potential_lhs','potential_family_projected',
         'potential_lhs_family_projected','independent_monitor_pool','surrogate_only']
records=[];start=time.perf_counter()
for i in range(count):
 path=folder/f'origin-{i:03d}.npz'
 if path.exists():records.append(dict(np.load(path)));continue
 source=Source(checkpoint,data['x'][i]);qs=[*map(int,data['q'][i]),int(newq[i])];q=mon.encode(qs)
 old=CACHE/args.domain/'generalization'/f'origin-{i:03d}.npz'
 if old.exists(): truths=np.load(old)['truth']
 else: truths=np.array([exact(source,m,s) for m,s in zip(parts,qs)])
 truth=np.concatenate([v.reshape(3,3) for v in truths],axis=1).ravel()
 polys=[FeasiblePolytope(m.vectors(m.codes((0,s,0,0)))) for m,s in zip(parts,qs)]
 shape=(2,len(methods),reps)
 est=np.zeros((*shape,36));rows=np.zeros(shape);seconds=np.zeros(shape);coherent=np.zeros(shape,bool)
 mass_error=np.zeros((2,reps));moment_error=np.zeros((2,reps))
 for b,budget in enumerate(cfg['budgets']):
  for r in range(reps):
   for k,name in enumerate(methods):
    rng=np.random.default_rng(PROTOCOL['seed']+100000*i+10*r+b);begin=time.perf_counter()
    if name in ['harmonic','mass','monitor_we']:
     value,meta=propagate(source,mon,q,budget,rng,name)
     if name=='harmonic':mass_error[b,r]=meta['mass_error'];moment_error[b,r]=meta['moment_error']
    elif name=='independent_monitor_pool':
     values=[];total=0
     for m,s in zip(parts,qs):
      v,mm=abstract_pooled(source,m,s,budget//4,rng,'monitor_state');values.append(v.reshape(3,3));total+=mm['rows']
     value=np.concatenate(values,axis=1).ravel();meta={'rows':total}
    elif name=='surrogate_only':
     source.rows=0;_,p=source.evaluate([source.initial],[5]);value=HarmonicPotential(mon,p[0])([(0,q,0,0)])[0];meta={'rows':source.rows}
    else:
     base=name.replace('_family_projected','');value,meta=sample(source,mon,q,budget,rng,base)
     if name.endswith('_family_projected'):
      pieces=value.reshape(3,12).copy()
      for j,poly in enumerate(polys):pieces[:,j*3:j*3+3]=poly.project(pieces[:,j*3:j*3+3].ravel()).reshape(3,3)
      value=pieces.ravel()
    seconds[b,k,r]=time.perf_counter()-begin;est[b,k,r]=value;rows[b,k,r]=meta['rows']
    matrix=value.reshape(3,12)
    coherent[b,k,r]=all(poly.contains(matrix[:,j*3:j*3+3].ravel())[0] for j,poly in enumerate(polys))
  print(args.domain,mode,i,budget,'done',round(time.perf_counter()-start,1),flush=True)
 rec={'estimates':est,'truth':truth,'rows':rows,'seconds':seconds,'family_coherent':coherent,
      'mass_error':mass_error,'moment_error':moment_error,'actual':mon.targets(data['y'][i,:8],q)}
 np.savez_compressed(path,**rec);records.append(rec)
result={'domain':args.domain,'mode':mode,'origins':count,'replicates':reps,'outputs':36,'methods':methods,
        'coherence_note':'Family projections enforce each family polytope only. Positive path estimators additionally have a joint constructive mass certificate.',
        'results':[]}
errors=[]
for b,budget in enumerate(cfg['budgets']):
 e=np.array([np.mean((v['estimates'][b]-v['truth'][None,None])**2,axis=(-2,-1)) for v in records]);errors.append(e)
 for k,name in enumerate(methods):
  result['results'].append({'budget':budget,'method':name,'mse':float(e[:,k].mean()),
   'rows':float(np.mean([v['rows'][b,k] for v in records])),'seconds':float(np.mean([v['seconds'][b,k] for v in records])),
   'family_incoherent_runs':int(sum((~v['family_coherent'][b,k]).sum() for v in records))})
e=errors[1];best=min(range(1,len(methods)),key=lambda k:e[:,k].mean())
ids=np.random.default_rng(PROTOCOL['seed']).integers(count,size=(2000,count));means=e[ids].mean(1)
ci=np.quantile(1-means[:,0]/np.maximum(means[:,best],1e-30),[.025,.975]);gain=1-e[:,0].mean()/e[:,best].mean()
time_ratio=np.mean([v['seconds'][1,0] for v in records])/np.mean([v['seconds'][1,best] for v in records])
result['primary']={'best_baseline':methods[best],'relative_mse_reduction':float(gain),'origin_bootstrap_95':ci,
 'time_ratio':float(time_ratio),'passed':bool(gain>=.2 and ci[0]>0 and time_ratio<=2 and all(v['family_coherent'][:,0].all() for v in records))}
result['max_mass_error']=float(max(v['mass_error'].max() for v in records))
result['max_moment_error']=float(max(v['moment_error'].max() for v in records))
save(REPORTS/f'{args.domain}-{mode}.json',result);print(result['primary'],flush=True)
