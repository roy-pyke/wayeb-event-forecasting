import argparse
import json
from pathlib import Path
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
from pooling import pooled

parser = argparse.ArgumentParser()
parser.add_argument('domain', choices=['air', 'power'])
parser.add_argument('--limit', type=int)
parser.add_argument('--repetitions', type=int)
args = parser.parse_args()
torch.set_num_threads(1)
checkpoint = torch.load(CACHE/args.domain/'world.pt', weights_only=False)
data = load(args.domain, 'development')
reps = args.repetitions or 32
count = min(args.limit or len(data['x']), len(data['x']))
mode = 'pooling' if args.limit is None and args.repetitions is None else f'pooling-pilot-{count}-{reps}'
folder = CACHE/args.domain/mode
folder.mkdir(parents=True, exist_ok=True)
identity = {'model': digest(CACHE/args.domain/'world.pt'), 'replicates': reps, 'origins': count,
    'sources': {str(p.relative_to(PACKAGE)): digest(p) for p in
                sorted((PACKAGE/'src').rglob('*.py')) + [PACKAGE/'experiments/pooling.py']},
    'script': digest(__file__), 'protocol': digest(PACKAGE/'configs/POOLING.json')}
manifest = folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text()) != identity: raise RuntimeError('run changed')
save(manifest, identity)
monitors = [Monitor(f, PROTOCOL['horizons_native_ticks']) for f in PROTOCOL['families']]
methods = ['single', 'depth', 'symbol', 'mass_buckets', 'semantic']
budgets = PROTOCOL['budgets_model_rows']
records = []
start = time.perf_counter()
for i in range(count):
    path = folder/f'origin-{i:03d}.npz'
    if path.exists(): records.append(dict(np.load(path, allow_pickle=False))); continue
    previous = dict(np.load(CACHE/args.domain/'registered'/f'origin-{i:03d}.npz', allow_pickle=False))
    source = Source(checkpoint, data['x'][i])
    shape = (3, 2, len(methods), reps)
    estimates = np.zeros((*shape, 9)); rows = np.zeros(shape); seconds = np.zeros(shape)
    coherent = np.zeros(shape, dtype=bool); group_count = np.zeros(shape); frontier = np.zeros(shape)
    for j, mon in enumerate(monitors):
        q = int(data['q'][i, j]); poly = FeasiblePolytope(mon.vectors(mon.codes((0, q, 0, 0))))
        for b, budget in enumerate(budgets):
            for r in range(reps):
                for k, method in enumerate(methods):
                    rng = np.random.default_rng(PROTOCOL['seed']+100000*i+1000*j+10*r+b)
                    begin = time.perf_counter()
                    value, meta = pooled(source, mon, q, budget, rng, method)
                    seconds[j,b,k,r] = time.perf_counter()-begin
                    estimates[j,b,k,r] = value; rows[j,b,k,r] = meta['rows']
                    coherent[j,b,k,r] = poly.contains(value)[0]
                    group_count[j,b,k,r] = meta['groups']; frontier[j,b,k,r] = meta['frontier']
    record = {'estimates': estimates, 'rows': rows, 'seconds': seconds, 'coherent': coherent,
        'groups': group_count, 'frontier': frontier, 'truth': previous['truth'], 'timestamp': previous['timestamp']}
    np.savez_compressed(path, **record); records.append(record)
    print(args.domain, mode, f'{i+1}/{count}', round(time.perf_counter()-start,1), flush=True)
result = {'domain': args.domain, 'mode': mode, 'origins': count, 'replicates': reps, 'methods': methods,
          'results': []}
errors_by_budget = []
for b, budget in enumerate(budgets):
    errors = np.array([np.mean((v['estimates'][:,b]-v['truth'][:,None,None])**2, axis=(-2,-1)) for v in records])
    errors_by_budget.append(errors)
    for k, method in enumerate(methods):
        result['results'].append({'budget': budget, 'method': method, 'mse': float(errors[:,:,k].mean()),
            'family_mse': errors[:,:,k].mean(0),
            'rows': float(np.mean([v['rows'][:,b,k] for v in records])),
            'seconds': float(np.mean([v['seconds'][:,b,k] for v in records])),
            'incoherent_runs': int(sum((~v['coherent'][:,b,k]).sum() for v in records)),
            'groups': float(np.mean([v['groups'][:,b,k] for v in records])),
            'frontier': float(np.mean([v['frontier'][:,b,k] for v in records]))})
e = errors_by_budget[1].mean(1)
old = [dict(np.load(CACHE/args.domain/'registered'/f'origin-{i:03d}.npz', allow_pickle=False)) for i in range(count)]
oe = np.array([np.mean((v['estimates'][:,1]-v['truth'][:,None,None])**2, axis=(0,2,3)) for v in old])
combined = np.concatenate([oe, e], axis=1)
names = ['Q1_mc','Q1_mass','Q1_semantic','Q1_IS','Q1_ISproject',*methods]
best = min(range(9), key=lambda k: combined[:,k].mean())
rng = np.random.default_rng(PROTOCOL['seed']); ids = rng.integers(count, size=(2000,count))
means = combined[ids].mean(1)
interval = np.quantile(1-means[:,-1]/np.maximum(means[:,best],1e-30),[.025,.975])
gain = 1-combined[:,-1].mean()/combined[:,best].mean()
candidate_time = np.mean([v['seconds'][:,1,-1] for v in records])
baseline_time = np.mean([v['seconds'][:,1,best] for v in old]) if best<5 else np.mean([v['seconds'][:,1,best-5] for v in records])
result['primary'] = {'best_baseline': names[best], 'relative_mse_reduction': float(gain),
    'query_bootstrap_95_interval': interval, 'time_ratio': float(candidate_time/baseline_time),
    'passed': bool(gain>=.2 and interval[0]>0 and candidate_time/baseline_time<=2 and
                   all(v['coherent'][:,1,-1].all() for v in records))}
save(REPORTS/f'{args.domain}-{mode}.json', result)
print(result['primary'], flush=True)
