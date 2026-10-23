import argparse
import json
import sys
import time
import numpy as np
import torch
from patternforecast.polytope import FeasiblePolytope
from queryforecast.common import PACKAGE,CACHE,REPORTS,PROTOCOL,digest,save
from queryforecast.model import Source
for folder in ['compositional','overflow','occupancy','engineering','finite_control']:
    sys.path.insert(0,str(PACKAGE/folder))
from context import setup,reference
from propagate import InfeasibleRank
from finite_method import finite_estimate

parser=argparse.ArgumentParser();parser.add_argument('domain',choices=['air','power'])
parser.add_argument('--limit',type=int);parser.add_argument('--repetitions',type=int)
args=parser.parse_args();torch.set_num_threads(1)
data,qs,mon=setup(args.domain)
checkpoint=torch.load(CACHE/args.domain/'world.pt',weights_only=False)
count=args.limit or 48;reps=args.repetitions or 32
mode='finite-closure' if args.limit is None and args.repetitions is None else f'finite-closure-pilot-{count}-{reps}'
folder=CACHE/args.domain/mode;folder.mkdir(parents=True,exist_ok=True)
files=sorted((PACKAGE/'src').rglob('*.py'))
for name in ['compositional','overflow','occupancy','engineering','finite_control']:files+=sorted((PACKAGE/name).glob('*.py'))
identity={'model':digest(CACHE/args.domain/'world.pt'),'count':count,'replicates':reps,'script':digest(__file__),
 'protocol':digest(PACKAGE/'configs/FINITE_CLOSURE.json'),
 'sources':{str(p.relative_to(PACKAGE)):digest(p) for p in files}}
manifest=folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text())!=identity:raise RuntimeError('run changed')
save(manifest,identity)
methods=['finite_occupancy'];budgets=[512,2048]
records=[];started=time.perf_counter()
for i in range(count):
    path=folder/f'origin-{i:03d}.npz'
    if path.exists():records.append(dict(np.load(path)));continue
    source=Source(checkpoint,data['x'][i]);q=mon.encode(qs[i]);truth=reference(args.domain,i,mon,qs[i],source)
    polys=[FeasiblePolytope(m.vectors(m.codes((0,int(s),0,0)))) for m,s in zip(mon.monitors,qs[i])]
    shape=(2,len(methods),reps)
    est=np.full((*shape,36),np.nan);rows=np.zeros(shape);timing=np.zeros(shape)
    feasible=np.zeros(shape,bool);coherent=np.zeros(shape,bool);ranks=np.zeros(shape,int)
    mass_error=np.zeros(shape);moment_error=np.zeros(shape)
    for b,budget in enumerate(budgets):
        for r in range(reps):
            for k,name in enumerate(methods):
                rng=np.random.default_rng(PROTOCOL['seed']+100000*i+10*r+b);begin=time.perf_counter()
                try:
                    v,meta=finite_estimate(source,mon,q,budget,rng)
                    est[b,k,r]=v;feasible[b,k,r]=True;ranks[b,k,r]=meta['max_rank']
                    mass_error[b,k,r]=meta['mass_error'];moment_error[b,k,r]=meta['moment_error']
                    matrix=v.reshape(3,12)
                    coherent[b,k,r]=all(poly.contains(matrix[:,j*3:j*3+3].ravel())[0] for j,poly in enumerate(polys))
                except InfeasibleRank:pass
                rows[b,k,r]=source.rows;timing[b,k,r]=time.perf_counter()-begin
        print(args.domain,mode,i,budget,'done',round(time.perf_counter()-started,1),flush=True)
    rec={'estimates':est,'truth':truth,'rows':rows,'seconds':timing,'feasible':feasible,
         'family_coherent':coherent,'ranks':ranks,'mass_error':mass_error,'moment_error':moment_error}
    np.savez_compressed(path,**rec);records.append(rec)
result={'domain':args.domain,'mode':mode,'origins':count,'replicates':reps,'methods':methods,
        'status':'mechanism audit; final comparison requires completed Q3/Q4 and serial timings','results':[]}
for b,budget in enumerate(budgets):
    for k,name in enumerate(methods):
        good=np.array([v['feasible'][b,k] for v in records]);fail=int((~good).sum())
        e=np.array([np.mean((v['estimates'][b,k]-v['truth'])**2,axis=-1) for v in records])
        result['results'].append({'budget':budget,'method':name,
          'mse':float(e.mean()) if not fail else None,
          'infeasible_runs':fail,'family_incoherent_feasible_runs':int(sum((v['feasible'][b,k]&~v['family_coherent'][b,k]).sum() for v in records)),
          'max_rank':int(max(v['ranks'][b,k].max() for v in records)),
          'rows':float(np.mean([v['rows'][b,k] for v in records])),
          'seconds':float(np.mean([v['seconds'][b,k] for v in records]))})
result['max_mass_error']=float(max(v['mass_error'].max() for v in records))
result['max_moment_error']=float(max(v['moment_error'].max() for v in records))
save(REPORTS/f'{args.domain}-{mode}.json',result);print(result['results'][len(methods):],flush=True)
