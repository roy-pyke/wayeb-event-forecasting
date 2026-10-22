"""Verify immutable source/model identities before any confirmation access."""
import json
from .common import CONFIG,CACHE,ROOT,RUNS,sha256


def verify_freeze(dataset=None,backbone=None):
    path=CONFIG/'FROZEN.json'
    if not path.exists():raise RuntimeError('Confirmation selection is not frozen')
    frozen=json.loads(path.read_text())
    for name,digest in frozen['source_sha256'].items():
        if sha256(ROOT/name)!=digest:raise RuntimeError(f'Frozen source changed: {name}')
    if dataset is not None:
        entry=frozen['datasets'][dataset]
        if sha256(CACHE/dataset/'cuts.json')!=entry['cuts_sha256']:
            raise RuntimeError('Frozen eventization thresholds changed')
        keys=[backbone] if backbone is not None else list(entry['models'])
        for key in keys:
            if key not in entry['models']:raise RuntimeError(f'Unregistered confirmation model: {key}')
            if sha256(RUNS/dataset/f'{key}.joblib')!=entry['models'][key]['model_sha256']:
                raise RuntimeError(f'Frozen model changed: {key}')
    return frozen
