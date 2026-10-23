"""Registered development test; reserves intentionally unsupported here."""
import argparse
import hashlib
import json
import time
import joblib
import numpy as np
from sklearn.cluster import KMeans
from patternforecast.common import PACKAGE, CONFIG, RUNS, REPORTS, FAMILY, write_json, sha256
from patternforecast.models import subset
from patternforecast.data import load
from patternforecast.automata import PatternFamily
from patternforecast.safe_codebook import ForecastCodebook, replay, offline_switches
from patternforecast.communication import evaluate, weekly, block_interval

p = argparse.ArgumentParser()
p.add_argument('--dataset', choices=['air', 'power'], required=True)
a = p.parse_args()
assert FAMILY == 'multisignal'
protocol = json.loads((PACKAGE/'configs/SAFE_CODEBOOK.json').read_text())
modelpath = RUNS/a.dataset/f"{protocol['models'][a.dataset]}.joblib"
model = joblib.load(modelpath)
family = PatternFamily()
start = time.perf_counter()
train = load(a.dataset, 'train')
rng = np.random.default_rng(protocol['codebook_seed'])
ids = np.sort(rng.choice(len(train['t']), min(protocol['fit_queries'], len(train['t'])), replace=False))
sample = subset(train, ids)
reference = model.predict(sample).astype(np.float32)
temporary = ForecastCodebook(np.zeros((1, 9)), family, protocol['horizons'])
reference = temporary.project_full(sample['q'], reference)
km = KMeans(n_clusters=protocol['codebook_size']-1, n_init=10,
            random_state=protocol['codebook_seed']).fit(reference)
centers = np.vstack([np.zeros(9), km.cluster_centers_]).astype(np.float32)
codebook = ForecastCodebook(centers, family, protocol['horizons'])
center_bytes = centers.astype('>f4').tobytes()
codebook_sha = hashlib.sha256(center_bytes).hexdigest()
artifact = REPORTS/f'safe-codebook-{a.dataset}.json'
write_json(artifact, dict(centers=centers, sha256=codebook_sha, model_sha256=sha256(modelpath),
    fit_split='train', fit_queries=len(ids), sample_indices_sha256=hashlib.sha256(ids.astype('>i8').tobytes()).hexdigest(),
    protocol_sha256=sha256(PACKAGE/'configs/SAFE_CODEBOOK.json'), seconds=time.perf_counter()-start))
print('codebook fitted', a.dataset, 'seconds', time.perf_counter()-start, flush=True)

data = load(a.dataset, 'development')
full = codebook.project_full(data['q'], model.predict(data).astype(np.float32))
start = time.perf_counter()
bounds, distances = codebook.certificates(data['q'], full)
precompute_seconds = time.perf_counter()-start
safe = bounds <= protocol['epsilon']+1e-12
version = int(hashlib.sha256((codebook_sha+sha256(modelpath)+sha256(CONFIG/'dfa.json')).encode()).hexdigest()[:8], 16)
report = dict(dataset=a.dataset, family=FAMILY, split='development',
    backbone=protocol['models'][a.dataset], model_sha256=sha256(modelpath),
    codebook_sha256=codebook_sha, source_sha256=sha256(PACKAGE/'src/patternforecast/safe_codebook.py'),
    protocol_sha256=sha256(PACKAGE/'configs/SAFE_CODEBOOK.json'), epsilon=protocol['epsilon'],
    coverage=float(safe.any(1).mean()), safe_count_quantiles=np.quantile(safe.sum(1), [0,.25,.5,.75,1]),
    precompute_seconds=precompute_seconds, **offline_switches(safe, data['segment']), policies={})
output = REPORTS/f'safe-codebook-{a.dataset}-development.json'
policies = [protocol['candidate'].split(':')[0]]+protocol['same_codebook_baselines']
for policy in policies:
    seeds = protocol['policy_seeds'] if policy in ['phase_uniform', 'uniform_current'] else [protocol['codebook_seed']]
    for seed in seeds:
        start = time.perf_counter()
        r = replay(data, full, codebook, bounds, distances, protocol['epsilon'], policy, seed, version)
        scores = evaluate(data, r['pred'], r['full'], r['sends'], r['certificate'], protocol['horizons'], protocol['epsilon'])
        _, bs, bc = weekly(data, r['bytes'])
        scores.update(bytes_per_query=float(r['bytes'].mean()), total_payload_bytes=int(r['bytes'].sum()),
            bytes_per_query_ci=block_interval(bs,bc), week_byte_sums=bs,
            setup_bytes=r['setup_bytes'], total_with_setup=int(r['bytes'].sum()+r['setup_bytes']),
            bytes_per_query_with_setup=float((r['bytes'].sum()+r['setup_bytes'])/len(full)),
            codeword_packets=r['codeword_packets'], fallback_packets=r['fallback_packets'],
            fallback_queries=int(r['fallback'].sum()), phases=r['phases'], seconds=time.perf_counter()-start)
        report['policies'][f'{policy}-s{seed}'] = scores
        write_json(output, report)
        print(policy, seed, {k:scores[k] for k in ['bytes_per_query','excess_brier','codeword_packets','fallback_packets','seconds']}, flush=True)
