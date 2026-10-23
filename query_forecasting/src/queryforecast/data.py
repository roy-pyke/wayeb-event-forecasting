"""Only previously exposed train/calibration/development caches are accepted."""
import json
import numpy as np
import pandas as pd
from .common import ROOT, CACHE, PROTOCOL, digest, save
from .monitor import Monitor


def load(domain, split):
    if domain not in ('air', 'power') or split not in ('train', 'calibrate', 'development'):
        raise ValueError('confirmation and reserve are closed')
    folder = ROOT / '.cache/pattern_forecasting/multisignal' / domain
    cache = CACHE / domain / f'{split}.npz'
    source = folder / f'{split}.npz'
    business = folder / f'{split}-business.csv'
    identity = {'input': digest(source), 'events': digest(business),
                'data_source': digest(__file__), 'horizon': PROTOCOL['model_training_horizon']}
    if cache.exists() and json.loads(cache.with_suffix('.json').read_text()) == identity:
        return dict(np.load(cache, allow_pickle=False))
    old = dict(np.load(source, allow_pickle=False))
    H = PROTOCOL['model_training_horizon']
    keep = np.flatnonzero(old['coverage'] >= H)
    # Sampling never conditions on future outcomes or pattern progress.
    limit = {'train': PROTOCOL['model']['train_origins'],
             'calibrate': PROTOCOL['model']['calibration_origins'], 'development': 48}[split]
    rng = np.random.default_rng(PROTOCOL['seed'])
    idx = np.sort(rng.choice(keep, min(limit, len(keep)), replace=False))
    data = {k: old[k][idx] for k in ['t', 'segment', 'entity']}
    tele = old['telemetry'][idx].reshape(len(idx), -1)
    data['x'] = np.concatenate([old['business'][idx], tele,
                               np.isfinite(tele).astype(float)], axis=1).astype(np.float32)
    data['y'] = np.full((len(idx), H), 4, dtype=np.int64)
    events = pd.read_csv(business)
    native = 3600 if domain == 'air' else 60
    monitors = [Monitor(name) for name in PROTOCOL['families']]
    data['q'] = np.zeros((len(idx), len(monitors)), dtype=np.int64)
    groups = events.groupby(['entity', 'segment'], sort=False)
    pairs = set(zip(data['entity'], data['segment']))
    for entity, segment in pairs:
        rows = np.flatnonzero((data['entity'] == entity) & (data['segment'] == segment))
        try: group = groups.get_group((entity, segment))
        except KeyError: continue
        ts = group['timestamp'].to_numpy()
        symbols = np.array([ord(s)-65 for s in group['symbol']], dtype=np.int64)
        future = data['t'][rows, None] + native*np.arange(1, H+1)
        pos = np.searchsorted(ts, future)
        clipped = np.minimum(pos, len(ts)-1)
        valid = (pos < len(ts)) & (ts[clipped] == future)
        data['y'][rows] = np.where(valid, symbols[clipped], 4)
        current = np.searchsorted(ts, data['t'][rows], side='right')-1
        for j, mon in enumerate(monitors):
            q = 0; states = []
            for a in symbols:
                q = int(mon.next[q, a]); states.append(q)
            data['q'][rows, j] = np.where(current >= 0, np.asarray(states)[np.maximum(current, 0)], 0)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, **data)
    save(cache.with_suffix('.json'), identity)
    return data
