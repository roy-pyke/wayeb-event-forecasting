from pathlib import Path
import hashlib
import json
import numpy as np

PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE.parent
CACHE = ROOT / '.cache/pattern_forecasting'
RUNS = ROOT / 'runs/pattern-forecasting'
NAMES = ('ordered', 'branch_loop', 'overlap_loop')


def protocol():
    return json.loads((PACKAGE / 'configs/PROTOCOL.json').read_text())


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
