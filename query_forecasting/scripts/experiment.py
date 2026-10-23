"""Registered development comparison; resumable per-origin raw estimates."""
import argparse
import time
import numpy as np
import torch
from patternforecast.polytope import FeasiblePolytope
from queryforecast.common import CACHE, REPORTS, PROTOCOL, PACKAGE, digest, save
from queryforecast.data import load
from queryforecast.model import Source
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact, monte_carlo, stratified, importance

parser = argparse.ArgumentParser()
parser.add_argument('domain', choices=['air', 'power'])
parser.add_argument('--limit', type=int)
parser.add_argument('--repetitions', type=int)
args = parser.parse_args()
torch.set_num_threads(1)
checkpoint = torch.load(CACHE/args.domain/'world.pt', weights_only=False)
data = load(args.domain, 'development')
reps = args.repetitions or PROTOCOL['monte_carlo_replicates']
count = min(args.limit or len(data['x']), len(data['x']))
mode = 'registered' if args.limit is None and args.repetitions is None else f'pilot-{count}-{reps}'
folder = CACHE/args.domain/mode
folder.mkdir(parents=True, exist_ok=True)
monitors = [Monitor(f, PROTOCOL['horizons_native_ticks']) for f in PROTOCOL['families']]
methods = ['mc', 'mass', 'semantic', 'importance', 'importance_projected']
identity = {'model': digest(CACHE/args.domain/'world.pt'), 'replicates': reps, 'origins': count,
            'sources': {str(p.relative_to(PACKAGE)): digest(p)
                        for p in sorted((PACKAGE/'src').rglob('*.py'))},
            'script': digest(__file__), 'protocol': digest(PACKAGE/'configs/PROTOCOL.json')}
manifest = folder/'identity.json'
if manifest.exists():
    import json
    if json.loads(manifest.read_text()) != identity:
        raise RuntimeError('Run inputs changed; choose a new registered run instead of mixing results')
else: save(manifest, identity)
budgets = PROTOCOL['budgets_model_rows']
all_records = []
start = time.perf_counter()
for i in range(count):
    path = folder/f'origin-{i:03d}.npz'
    if path.exists():
        all_records.append(dict(np.load(path, allow_pickle=False)))
        continue
    source = Source(checkpoint, data['x'][i])
    estimates = np.zeros((len(monitors), len(budgets), len(methods), reps, 9))
    costs = np.zeros(estimates.shape[:-1])
    times = np.zeros_like(costs)
    coherent = np.zeros_like(costs, dtype=bool)
    truth, actual, reference_rows = [], [], []
    for j, mon in enumerate(monitors):
        q = int(data['q'][i, j])
        source.rows = 0
        reference = exact(source, mon, q)
        truth.append(reference); reference_rows.append(source.rows)
        actual.append(mon.targets(data['y'][i, :mon.H], q))
        poly = FeasiblePolytope(mon.vectors(mon.codes((0, q, 0, 0))))
        if not poly.contains(reference)[0]: raise AssertionError('exact reference incoherent')
        for b, budget in enumerate(budgets):
            for r in range(reps):
                for k, name in enumerate(methods[:-1]):
                    rng = np.random.default_rng(PROTOCOL['seed']+100000*i+1000*j+10*r+b)
                    begin = time.perf_counter()
                    if name == 'mc': value, meta = monte_carlo(source, mon, q, budget, rng)
                    elif name == 'importance': value, meta = importance(source, mon, q, budget, rng)
                    else: value, meta = stratified(source, mon, q, budget, rng, semantic=name == 'semantic')
                    elapsed = time.perf_counter()-begin
                    estimates[j, b, k, r] = value
                    costs[j, b, k, r] = meta['rows']
                    times[j, b, k, r] = elapsed
                    coherent[j, b, k, r] = poly.contains(value)[0]
                    if meta['rows'] > budget: raise AssertionError('budget exceeded')
                    if name == 'importance':
                        pstart = time.perf_counter()
                        estimates[j, b, k+1, r] = poly.project(value)
                        costs[j, b, k+1, r] = meta['rows']
                        times[j, b, k+1, r] = elapsed+time.perf_counter()-pstart
                        coherent[j, b, k+1, r] = poly.contains(estimates[j, b, k+1, r])[0]
    record = {'estimates': estimates, 'costs': costs, 'seconds': times, 'coherent': coherent,
              'truth': np.array(truth), 'actual': np.array(actual), 'reference_rows': reference_rows,
              'timestamp': data['t'][i], 'entity': data['entity'][i]}
    np.savez_compressed(path, **record)
    all_records.append(record)
    print(args.domain, mode, f'{i+1}/{count}', 'seconds', round(time.perf_counter()-start, 1), flush=True)
summary = {'domain': args.domain, 'mode': mode, 'origins': count, 'replicates': reps,
           'model_sha256': digest(CACHE/args.domain/'world.pt'), 'methods': methods,
           'families': PROTOCOL['families'], 'budgets': budgets, 'results': [],
           'model_brier_against_observed': float(np.mean([(v['truth']-v['actual'])**2 for v in all_records])),
           'exact_reference_rows_mean': float(np.mean([v['reference_rows'] for v in all_records]))}
query = []
for b, budget in enumerate(budgets):
    errors = np.array([np.mean((v['estimates'][:, b]-v['truth'][:, None, None])**2, axis=(-2, -1))
                       for v in all_records])  # origin, family, method
    query.append(errors)
    for k, method in enumerate(methods):
        summary['results'].append({'budget': budget, 'method': method,
            'mse': float(errors[:, :, k].mean()),
            'family_mse': errors[:, :, k].mean(0),
            'rows': float(np.mean([v['costs'][:, b, k] for v in all_records])),
            'seconds': float(np.mean([v['seconds'][:, b, k] for v in all_records])),
            'incoherent_runs': int(sum((~v['coherent'][:, b, k]).sum() for v in all_records))})
errors = query[budgets.index(512)].mean(1)
baseline_indices = [0, 1, 3, 4]
best = min(baseline_indices, key=lambda k: errors[:, k].mean())
rng = np.random.default_rng(PROTOCOL['seed'])
sampled = rng.integers(count, size=(2000, count))
means = errors[sampled].mean(1)
gains = 1-means[:, 2]/np.maximum(means[:, best], 1e-30)
ci = np.quantile(gains, [.025, .975])
gain = 1-errors[:, 2].mean()/errors[:, best].mean()
timing = [v for v in summary['results'] if v['budget'] == 512]
time_ratio = timing[2]['seconds']/timing[best]['seconds']
summary['primary'] = {'best_baseline': methods[best], 'relative_mse_reduction': float(gain),
    'query_bootstrap_95_interval': ci, 'wall_time_ratio': time_ratio,
    'passed': bool(gain >= .2 and ci[0] > 0 and time_ratio <= 2 and timing[2]['incoherent_runs'] == 0)}
save(REPORTS/f'{args.domain}-{mode}.json', summary)
print(summary['primary'], flush=True)
