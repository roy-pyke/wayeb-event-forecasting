from pathlib import Path
import hashlib
import json
import numpy as np

PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE.parent
CACHE = ROOT / '.cache/query_forecasting'
REPORTS = PACKAGE / 'reports'
PROTOCOL = json.loads((PACKAGE / 'configs/PROTOCOL.json').read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    def convert(x):
        if isinstance(x, np.ndarray): return x.tolist()
        if isinstance(x, np.generic): return x.item()
        raise TypeError(type(x))
    path.write_text(json.dumps(value, indent=2, default=convert, allow_nan=False) + '\n')
