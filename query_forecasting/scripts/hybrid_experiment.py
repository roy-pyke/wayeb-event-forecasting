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
from hybrid import hybrid

parser = argparse.ArgumentParser()
parser.add_argument('domain', choices=['air', 'power'])
args = parser.parse_args()
torch.set_num_threads(1)
data = load(args.domain, 'development')
checkpoint = torch.load(CACHE/args.domain/'world.pt', weights_only=False)
folder = CACHE/args.domain/'hybrid'; folder.mkdir(parents=True, exist_ok=True)
identity = {'model': digest(CACHE/args.domain/'world.pt'), 'script': digest(__file__),
    'protocol': digest(PACKAGE/'configs/HYBRID_AUDIT.json'),
    'sources': {str(p.relative_to(PACKAGE)): digest(p) for p in
                sorted((PACKAGE/'src').rglob('*.py')) + [PACKAGE/'experiments/pooling.py', PACKAGE/'audits/hybrid.py']}}
manifest = folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text()) != identity:
    raise RuntimeError('run changed')
save(manifest, identity)
monitors = [Monitor(f, PROTOCOL['horizons_native_ticks']) for f in PROTOCOL['families']]
methods = ['hybrid_raw', 'hybrid_projected']; records = []
start = time.perf_counter()
for i in range(48):
    path = folder/f'origin-{i:03d}.npz'
    if path.exists():
        records.append(dict(np.load(path))); continue
    reference = dict(np.load(CACHE/args.domain/'registered'/f'origin-{i:03d}.npz'))
    source = Source(checkpoint, data['x'][i])
    shape = (3, 2, 2, 32)
    estimates = np.zeros((*shape, 9)); costs = np.zeros(shape); seconds = np.zeros(shape)
    coherent = np.zeros(shape, bool)
    for j, mon in enumerate(monitors):
        q = int(data['q'][i, j]); poly = FeasiblePolytope(mon.vectors(mon.codes((0,q,0,0))))
        for b, budget in enumerate(PROTOCOL['budgets_model_rows']):
            for r in range(32):
                rng = np.random.default_rng(PROTOCOL['seed']+100000*i+1000*j+10*r+b)
                begin = time.perf_counter()
                v, meta = hybrid(source, mon, q, budget, rng)
                elapsed = time.perf_counter()-begin
                for k, value in enumerate([v, poly.project(v)]):
                    estimates[j,b,k,r] = value; costs[j,b,k,r] = meta['rows']
                    seconds[j,b,k,r] = elapsed if k == 0 else time.perf_counter()-begin
                    coherent[j,b,k,r] = poly.contains(value)[0]
    record = {'estimates': estimates, 'rows': costs, 'seconds': seconds, 'coherent': coherent,
              'truth': reference['truth'], 'timestamp': reference['timestamp']}
    np.savez_compressed(path, **record); records.append(record)
    print(args.domain, 'hybrid', i+1, round(time.perf_counter()-start, 1), flush=True)
result = {'domain': args.domain, 'origins': 48, 'replicates': 32, 'methods': methods, 'results': []}
for b, budget in enumerate(PROTOCOL['budgets_model_rows']):
    errors = np.array([np.mean((v['estimates'][:,b]-v['truth'][:,None,None])**2, axis=(-2,-1)) for v in records])
    for k, method in enumerate(methods):
        result['results'].append({'budget': budget, 'method': method, 'mse': float(errors[:,:,k].mean()),
            'family_mse': errors[:,:,k].mean(0), 'rows': float(np.mean([v['rows'][:,b,k] for v in records])),
            'seconds': float(np.mean([v['seconds'][:,b,k] for v in records])),
            'incoherent_runs': int(sum((~v['coherent'][:,b,k]).sum() for v in records))})
save(REPORTS/f'{args.domain}-hybrid.json', result)
