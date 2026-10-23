import argparse
import json
import sys
import time
import numpy as np
import torch
from patternforecast.polytope import FeasiblePolytope
from queryforecast.common import PACKAGE,CACHE,REPORTS,PROTOCOL,digest,save
from queryforecast.model import Source
sys.path.insert(0,str(PACKAGE/'compositional'))
sys.path.insert(0,str(PACKAGE/'overflow'))
from guarded import guarded
from context import setup,reference

parser=argparse.ArgumentParser();parser.add_argument('domain',choices=['air','power'])
parser.add_argument('--limit',type=int);parser.add_argument('--repetitions',type=int)
args=parser.parse_args();torch.set_num_threads(1)
data,qs,mon=setup(args.domain)
checkpoint=torch.load(CACHE/args.domain/'world.pt',weights_only=False)
count=args.limit or 48;reps=args.repetitions or 32
mode='overflow' if args.limit is None and args.repetitions is None else f'overflow-pilot-{count}-{reps}'
folder=CACHE/args.domain/mode;folder.mkdir(parents=True,exist_ok=True)
identity={'model':digest(CACHE/args.domain/'world.pt'),'count':count,'replicates':reps,'script':digest(__file__),
 'protocol':digest(PACKAGE/'configs/OVERFLOW_BALANCING.json'),
 'sources':{str(p.relative_to(PACKAGE)):digest(p) for p in sorted((PACKAGE/'src').rglob('*.py'))+
            sorted((PACKAGE/'compositional').glob('*.py'))+sorted((PACKAGE/'overflow').glob('*.py'))}}
manifest=folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text())!=identity:raise RuntimeError('run changed')
save(manifest,identity)
methods=['harmonic','mass','known_bits','uniform'];budgets=[512,2048]
records=[];started=time.perf_counter()
for i in range(count):
 path=folder/f'origin-{i:03d}.npz'
 if path.exists():records.append(dict(np.load(path)));continue
 source=Source(checkpoint,data['x'][i]);q=mon.encode(qs[i]);truth=reference(args.domain,i,mon,qs[i],source)
 polys=[FeasiblePolytope(m.vectors(m.codes((0,int(s),0,0)))) for m,s in zip(mon.monitors,qs[i])]
 shape=(2,4,reps);est=np.zeros((*shape,36));rows=np.zeros(shape);timing=np.zeros(shape)
 overflow=np.zeros(shape,int);coherent=np.zeros(shape,bool);moment_error=np.zeros(shape);mass_error=np.zeros(shape)
 stages=[]
 for b,budget in enumerate(budgets):
  for r in range(reps):
   for k,name in enumerate(methods):
    rng=np.random.default_rng(PROTOCOL['seed']+100000*i+10*r+b);begin=time.perf_counter()
    v,meta=guarded(source,mon,q,budget,rng,name)
    timing[b,k,r]=time.perf_counter()-begin;rows[b,k,r]=meta['rows'];est[b,k,r]=v
    overflow[b,k,r]=meta['overflows'];moment_error[b,k,r]=meta['moment_error'];mass_error[b,k,r]=meta['mass_error']
    matrix=v.reshape(3,12)
    coherent[b,k,r]=all(poly.contains(matrix[:,j*3:j*3+3].ravel())[0] for j,poly in enumerate(polys))
    if r==0 and k==0:stages.append(meta['stages'])
  print(args.domain,mode,i,budget,'done',round(time.perf_counter()-started,1),flush=True)
 rec={'estimates':est,'truth':truth,'rows':rows,'seconds':timing,'family_coherent':coherent,
      'overflows':overflow,'moment_error':moment_error,'mass_error':mass_error}
 np.savez_compressed(path,**rec);save(folder/f'stages-{i:03d}.json',stages);records.append(rec)
result={'domain':args.domain,'mode':mode,'origins':count,'replicates':reps,'methods':methods,'results':[],
 'comparison_status':'Q3 and overflow controls must all be included; this file alone is not a gate result'}
for b,budget in enumerate(budgets):
 e=np.array([np.mean((v['estimates'][b]-v['truth'][None,None])**2,axis=(-2,-1)) for v in records])
 for k,name in enumerate(methods):
  result['results'].append({'budget':budget,'method':name,'mse':float(e[:,k].mean()),
   'rows':float(np.mean([v['rows'][b,k] for v in records])),'seconds':float(np.mean([v['seconds'][b,k] for v in records])),
   'family_incoherent_runs':int(sum((~v['family_coherent'][b,k]).sum() for v in records)),
   'overflow_run_fraction':float(np.mean([v['overflows'][b,k]>0 for v in records])),
   'overflow_steps_mean':float(np.mean([v['overflows'][b,k] for v in records]))})
result['max_mass_error']=float(max(v['mass_error'].max() for v in records))
result['max_moment_error']=float(max(v['moment_error'].max() for v in records))
save(REPORTS/f'{args.domain}-{mode}.json',result)
print([v for v in result['results'] if v['budget']==2048],flush=True)
