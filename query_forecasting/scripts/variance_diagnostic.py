import argparse
import sys
import numpy as np
import torch
from queryforecast.common import CACHE, REPORTS, PROTOCOL, PACKAGE, digest, save
from queryforecast.data import load
from queryforecast.model import Source
from queryforecast.monitor import Monitor
from queryforecast.estimators import stratified
sys.path.insert(0, str(PACKAGE/'experiments'))
sys.path.insert(0, str(PACKAGE/'audits'))
from pooling import build_frontier, partition
from advanced import hidden_partition
from moments import conditional_moments, allocation, decomposition

parser = argparse.ArgumentParser(); parser.add_argument('domain', choices=['air', 'power'])
args = parser.parse_args(); torch.set_num_threads(1)
data = load(args.domain, 'development')
checkpoint = torch.load(CACHE/args.domain/'world.pt', weights_only=False)
records = []
for i in range(0,48,4):
    source = Source(checkpoint, data['x'][i])
    for j, family in enumerate(PROTOCOL['families']):
        mon = Monitor(family, PROTOCOL['horizons_native_ticks']); q = int(data['q'][i,j])
        frontier, settled, expanded = build_frontier(source, mon, q, 512)
        source.rows = 0
        means, seconds = conditional_moments(source, mon, frontier)
        oracle_rows = source.rows
        reference = np.load(CACHE/args.domain/'registered'/f'origin-{i:03d}.npz')['truth'][j]
        reconstructed = settled+np.array([n.mass for n in frontier])@means
        # Batch shape differences in float32 GRU give tiny numerical differences.
        np.testing.assert_allclose(reconstructed, reference, atol=3e-7, rtol=1e-6)
        _, old = stratified(source, mon, q, 512, np.random.default_rng(0), semantic=True)
        entry = {'origin': i, 'family': family, 'frontier': len(frontier), 'expansions': expanded,
                 'Q1_expansions': old['expansions'], 'Q1_strata': old['strata'],
                 'offline_oracle_rows': oracle_rows, 'policies': {}}
        for name in ['single', 'depth', 'symbol', 'mass_buckets', 'hidden_cluster', 'semantic']:
            groups = hidden_partition(mon, frontier) if name == 'hidden_cluster' else partition(mon, frontier, name)
            groups, masses, counts, costs, caps = allocation(mon, groups, expanded, 512)
            terms = decomposition(mon, frontier, groups, masses, counts, means, seconds)
            terms.update({'groups': len(groups), 'samples': int(counts.sum()),
                          'worst_case_rows': int(expanded+counts@costs),
                          'bound_mse': float(np.sum(masses**2*caps/counts)/mon.d)})
            if terms['exact_mse'] > terms['bound_mse']+1e-12:
                raise AssertionError('variance bound invalid')
            entry['policies'][name] = terms
        records.append(entry)
    print(args.domain, 'variance diagnostic', i, flush=True)
summary = {name: {metric: float(np.mean([r['policies'][name][metric] for r in records]))
                 for metric in records[0]['policies'][name]} for name in records[0]['policies']}
result = {'domain': args.domain, 'role': 'offline mechanism diagnosis; not used for allocation or model selection',
          'model_sha256': digest(CACHE/args.domain/'world.pt'), 'script_sha256': digest(__file__),
          'oracle_sha256': digest(PACKAGE/'audits/moments.py'), 'records': records, 'summary': summary,
          'mean_Q1_expansions': float(np.mean([r['Q1_expansions'] for r in records])),
          'mean_Q2_expansions': float(np.mean([r['expansions'] for r in records]))}
save(REPORTS/f'{args.domain}-variance-diagnostic.json', result)
print(summary, flush=True)
