from pathlib import Path
import hashlib
import json
import os
import numpy as np

PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE.parent
FAMILY=os.environ.get('PATTERN_FAMILY','nested')
if FAMILY not in ('nested','directional','multisignal'): raise ValueError('unknown pattern family')
CONFIG=PACKAGE/'configs' if FAMILY=='nested' else PACKAGE/'configs'/FAMILY
CACHE = ROOT / '.cache/pattern_forecasting' if FAMILY=='nested' else ROOT/'.cache/pattern_forecasting'/FAMILY
RUNS = ROOT / 'runs/pattern-forecasting' if FAMILY=='nested' else ROOT/'runs/pattern-forecasting'/FAMILY
REPORTS=PACKAGE/'reports' if FAMILY=='nested' else PACKAGE/'reports'/FAMILY
NAMES = {'nested':('ordered','branch_loop','overlap_loop'),
         'directional':('rising','falling','excursion'),
         'multisignal':('response_up','response_down','response_any')}[FAMILY]


def protocol():
    return json.loads((CONFIG / 'PROTOCOL.json').read_text())


def experiment_cfg(name,profile='long'):
    cfg=protocol()['datasets'][name]
    cfg['pattern_family']=FAMILY
    if profile=='short':
        cfg['horizon_samples']=json.loads((PACKAGE/'configs/SHORT_HORIZON.json').read_text())['horizon_samples']
    elif profile!='long': raise ValueError('unknown experiment profile')
    return cfg


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False, default=lambda v: v.tolist() if isinstance(v, np.ndarray) else v.item())+'\n')
