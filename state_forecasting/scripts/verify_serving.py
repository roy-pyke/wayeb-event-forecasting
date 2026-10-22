"""Check every saved confirmation probability and benchmark equivalent serving."""
import argparse
import json
from pathlib import Path
import platform
import time
import joblib
import numpy as np
import pandas as pd
from stateforecast.data import CACHE, PACKAGE, load_split, sha256
from stateforecast.serving import BatchedSurvival
from stateforecast.online_fast import raw_and_calibrated
from stateforecast.fast_feedback import FastOutcomeExpert
from stateforecast.mixer import DelayedExpertMixer


def benchmark(models, x, horizons):
    fast, mixer = FastOutcomeExpert(horizons), DelayedExpertMixer(5)
    times = []
    for i in range(220):
        row = x[i:i + 1]
        begin = time.perf_counter()
        raw0, cal0 = raw_and_calibrated(models[0], row, horizons)
        raw2, cal2 = raw_and_calibrated(models[1], row, horizons)
        dynamic, _ = fast.predict(row[0])
        mixer.predict(np.stack([raw0, cal0, raw2, cal2, dynamic]))
        if i >= 20:
            times.append((time.perf_counter() - begin) * 1000)
    return dict(p50_ms=float(np.median(times)), p95_ms=float(np.quantile(times, .95)),
                measured_queries=len(times), warmup_queries=20)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    data = load_split(CACHE / 'metropt2022', 'confirmation')
    confirmation = json.loads((args.run / 'confirmation.json').read_text())
    config = json.loads((PACKAGE / 'configs/CONFIRMATION_2022.json').read_text())
    horizons = config['horizons_seconds']
    raw = dict(np.load(args.run / 'raw_predictions.npz'))
    calibrated = dict(np.load(args.run / 'predictions.npz'))
    dates = pd.to_datetime(data['time'], unit='s').strftime('%Y-%m-%d')
    differences = {name: dict(raw=0., calibrated=0.) for name in raw}
    calls = 0
    for day in np.unique(dates):
        mask = dates == day
        for name in raw:
            model = joblib.load(args.run / f'{day}-{name}.joblib')
            serving = BatchedSurvival(model)
            for kind, expected in [('raw', raw[name]), ('calibrated', calibrated[name])]:
                actual = serving.predict_cdf(data['X'][mask], horizons, calibrated=kind == 'calibrated')
                differences[name][kind] = max(differences[name][kind], float(np.max(abs(actual - expected[mask]))))
                np.testing.assert_array_equal(actual, expected[mask])
            calls += 1
    last = np.unique(dates)[-1]
    models = [joblib.load(args.run / f'{last}-{name}.joblib') for name in ['M0', 'M2']]
    original = benchmark(models, data['X'], horizons)
    batched = benchmark([BatchedSurvival(m) for m in models], data['X'], horizons)
    checks = dict(confirmation['checks'])
    checks['latency'] = batched['p95_ms'] <= config['criteria']['single_query_p95_ms_at_most']
    checks['prediction_equivalence'] = all(v == 0 for d in differences.values() for v in d.values())
    report = dict(scope='execution-only optimization; frozen learned models, features, calibration and expert rules unchanged',
                  platform=platform.platform(), source_sha256=sha256(PACKAGE / 'src/stateforecast/serving.py'),
                  model_days_checked=calls, queries=len(data['X']), max_abs_differences=differences,
                  original_performance=original, batched_performance=batched,
                  ensemble_calls_per_query_before=18, ensemble_calls_per_query_after=2,
                  speedup_p95=original['p95_ms'] / batched['p95_ms'], checks=checks,
                  quality_pass=all(checks.values()))
    output = json.dumps(report, indent=2) + '\n'
    (args.run / 'serving.json').write_text(output)
    (PACKAGE / 'reports/serving-2022.json').write_text(output)
    print(output)
    if not report['quality_pass']:
        raise SystemExit('Equivalent serving failed one or more frozen acceptance criteria')


if __name__ == '__main__':
    main()
