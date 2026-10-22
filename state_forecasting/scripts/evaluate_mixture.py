import argparse
import json
from pathlib import Path
import numpy as np
from stateforecast.data import CACHE, PACKAGE, load_split
from stateforecast.mixer import causal_mix
from stateforecast.evaluate import metrics, paired_bootstrap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--eta', type=float, default=2.0)
    args = ap.parse_args()
    data = load_split(CACHE/'prepared', 'development')
    p = dict(np.load(args.run/'predictions.npz'))
    h = json.loads((PACKAGE/'configs/PROTOCOL.json').read_text())['horizons_seconds']
    report = dict(scope='development delayed feedback mixture', eta=args.eta, share=0.02, models={}, comparisons={})
    weights = {}
    for name, source in [('G1', 'M1-16'), ('G2', 'M2')]:
        p[name], weights[name], audit = causal_mix(data, p['M0'], p[source], h, eta=args.eta)
        report['models'][name] = dict(metrics=metrics(data, p[name], h), feedback=audit)
        report['comparisons'][name] = paired_bootstrap(data, p['M0'], p[name], h)
    report['continuous_vs_discrete'] = paired_bootstrap(data, p['G1'], p['G2'], h)
    report['selected'] = min(['G1','G2'], key=lambda n: report['models'][n]['metrics']['mean_brier'])
    baseline = metrics(data, p['M0'], h)['mean_brier']
    report['relative_reduction'] = 1-report['models'][report['selected']]['metrics']['mean_brier']/baseline
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    np.savez_compressed(args.output/'predictions.npz', **p)
    np.savez_compressed(args.output/'weights.npz', **weights)
    print(json.dumps({k:v for k,v in report.items() if k!='models'}, indent=2))
    for n,v in report['models'].items():
        print(n, 'Brier',v['metrics']['mean_brier'],'ECE60',v['metrics']['60']['ece'])


if __name__ == '__main__':
    main()
