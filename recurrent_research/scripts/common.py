from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
DATA = ROOT / 'artifacts/recurrent/r2'
REPORT = HERE / 'reports/r2'
sys.path.insert(0, str(HERE / 'src'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def protocol():
    return json.loads((HERE / 'configs/PROTOCOL_R2.json').read_text())
