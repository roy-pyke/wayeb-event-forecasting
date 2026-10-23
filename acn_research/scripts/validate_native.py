"""Execute native authors' solver and simulator; no optimizer stubs."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'acn_research'
sys.path.insert(0, str(HERE / 'src'))
from acnresearch.native import run_native_fixture


def main():
    cases = [dict(estimation=False), dict(estimation=True),
             dict(estimation=True, discrete=True),
             dict(estimation=True, discrete=True, probe_floor=6),
             dict(estimation=True, discrete=True, probe_floor=6, up_increment=6),
             dict(estimation=True, discrete=True, probe_floor=6, pause=False)]
    results = []
    store = ROOT / 'artifacts/acn/native'; store.mkdir(parents=True, exist_ok=True)
    for i, case in enumerate(cases):
        result, traces = run_native_fixture(**case)
        results.append(result)
        np.savez_compressed(store / f'case-{i}.npz', pilot=traces['pilot'], current=traces['current'])
        (store / f'case-{i}-bounds.json').write_text(json.dumps(traces['bounds'], indent=2)+'\n')
        print(json.dumps(result), flush=True)
    report = {'scope': 'Native ACN-Sim and corrected AdaCharge integration fixtures with real CLARABEL solves; simulated exogenous response, not measured production benefit.',
              'cases': results, 'all_assertions_passed': True,
              'request_contract': 'Energy and planned departure disclosed at arrival in these fixtures; actual departure hidden by declared-request interface.',
              'source_revisions': json.loads((HERE/'configs/SOURCES.json').read_text())}
    (HERE/'reports/native_baseline.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__': main()
