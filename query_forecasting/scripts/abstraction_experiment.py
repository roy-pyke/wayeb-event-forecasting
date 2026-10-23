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
sys.path.insert(0, str(PACKAGE/'audits'))
from abstractions import abstract_pooled, abstract_partition
from pooling import build_frontier, partition

parser = argparse.ArgumentParser(); parser.add_argument('domain', choices=['air', 'power'])
args = parser.parse_args(); torch.set_num_threads(1)
data = load(args.domain, 'development')
checkpoint = torch.load(CACHE/args.domain/'world.pt', weights_only=False)
folder = CACHE/args.domain/'abstractions'; folder.mkdir(parents=True, exist_ok=True)
identity = {'model': digest(CACHE/args.domain/'world.pt'), 'script': digest(__file__),
    'protocol': digest(PACKAGE/'configs/ABSTRACTION_AUDIT.json'),
    'sources': {str(p.relative_to(PACKAGE)): digest(p) for p in
       sorted((PACKAGE/'src').rglob('*.py'))+[PACKAGE/'experiments/pooling.py',PACKAGE/'audits/abstractions.py']}}
manifest = folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text()) != identity: raise RuntimeError('run changed')
save(manifest, identity)
monitors = [Monitor(f, PROTOCOL['horizons_native_ticks']) for f in PROTOCOL['families']]
methods = ['known_bits', 'marginal_support', 'monitor_state']; records = []
start = time.perf_counter()
for i in range(48):
    path = folder/f'origin-{i:03d}.npz'
    if path.exists(): records.append(dict(np.load(path))); continue
    previous = dict(np.load(CACHE/args.domain/'registered'/f'origin-{i:03d}.npz'))
    source = Source(checkpoint, data['x'][i]); shape = (3,3,32)
    est = np.zeros((*shape,9)); rows = np.zeros(shape); timing = np.zeros(shape)
    coherent = np.zeros(shape,bool); group_count = np.zeros(shape); equivalent = []
    for j, mon in enumerate(monitors):
        q = int(data['q'][i,j]); poly = FeasiblePolytope(mon.vectors(mon.codes((0,q,0,0))))
        frontier, _, _ = build_frontier(source, mon, q, 512)
        full = partition(mon, frontier, 'semantic')
        boxes = abstract_partition(mon, frontier, 'marginal_support')
        equivalent.append(len(full) == len(boxes))  # box partition is a coarsening
        for r in range(32):
            for k, name in enumerate(methods):
                rng = np.random.default_rng(PROTOCOL['seed']+100000*i+1000*j+10*r+1)
                begin = time.perf_counter()
                v, meta = abstract_pooled(source, mon, q, 512, rng, name)
                timing[j,k,r] = time.perf_counter()-begin; est[j,k,r] = v
                rows[j,k,r] = meta['rows']; group_count[j,k,r] = meta['groups']
                coherent[j,k,r] = poly.contains(v)[0]
    rec = {'estimates':est,'rows':rows,'seconds':timing,'coherent':coherent,'groups':group_count,
           'truth':previous['truth'],'box_partition_equal':equivalent}
    np.savez_compressed(path, **rec); records.append(rec)
    print(args.domain, 'abstractions', i+1, round(time.perf_counter()-start,1), flush=True)
e = np.array([np.mean((v['estimates']-v['truth'][:,None,None])**2,axis=(-2,-1)) for v in records])
candidate = [dict(np.load(CACHE/args.domain/'pooling'/f'origin-{i:03d}.npz')) for i in range(48)]
ce = np.array([np.mean((v['estimates'][:,1,-1]-v['truth'][:,None])**2) for v in candidate])
result = {'domain':args.domain,'origins':48,'replicates':32,'budget':512,'methods':methods,
          'box_partition_equal_queries':int(np.sum([v['box_partition_equal'] for v in records])),
          'queries':144,'results':[]}
for k, name in enumerate(methods):
    result['results'].append({'method':name,'mse':float(e[:,:,k].mean()),'family_mse':e[:,:,k].mean(0),
       'rows':float(np.mean([v['rows'][:,k] for v in records])),
       'seconds':float(np.mean([v['seconds'][:,k] for v in records])),
       'groups':float(np.mean([v['groups'][:,k] for v in records])),
       'incoherent_runs':int(sum((~v['coherent'][:,k]).sum() for v in records))})
best = int(np.argmin(e.mean((0,1)))); be = e[:,:,best].mean(1)
ids = np.random.default_rng(PROTOCOL['seed']).integers(48,size=(2000,48))
ci = np.quantile(1-ce[ids].mean(1)/be[ids].mean(1),[.025,.975]); gain = 1-ce.mean()/be.mean()
result['mechanism_gate'] = {'best_baseline':methods[best],'relative_mse_reduction':float(gain),
                          'origin_bootstrap_95':ci,'passed':bool(gain>=.2 and ci[0]>0)}
save(REPORTS/f'{args.domain}-abstractions.json', result)
print(result['mechanism_gate'],flush=True)
