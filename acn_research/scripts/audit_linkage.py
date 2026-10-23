"""Audit request versions available at real alarms, and independent linkage fields."""
from pathlib import Path
from collections import Counter
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'acn_research'
sys.path.insert(0, str(HERE / 'src'))
from acnresearch.requests import recording_filename, request_asof, timestamp


def main():
    sessions = json.loads((ROOT / 'artifacts/acn/requests/office_selected.json').read_text())
    byfile = {recording_filename(s['sessionID']): s for s in sessions}
    assert len(byfile) == len(sessions), 'Non-unique session linkage'
    alarms = pd.read_csv(HERE / 'reference/acn_probe/inactivity_alarms.csv')
    first = alarms.loc[alarms.threshold_amp.eq(.5)].sort_values('alarm_time').drop_duplicates('file')
    counts = Counter(first_alarm_sessions=len(first))
    strata = {}
    for _, row in first.iterrows():
        bucket = strata.setdefault(row.outcome, Counter(sessions=0, metadata_matched=0, any_request=0, available_request_at_alarm=0))
        bucket['sessions'] += 1
        s = byfile.get(row.file)
        if s is None:
            continue
        bucket['metadata_matched'] += 1
        bucket['any_request'] += bool(s.get('userInputs'))
        bucket['available_request_at_alarm'] += request_asof(s, row.alarm_time) is not None
    start_deltas, stop_deltas, energy_deltas = [], [], []
    fields = Counter()
    for name, s in byfile.items():
        df = pd.read_csv(ROOT / 'artifacts/acn/office/raw' / name, index_col=0)
        times = pd.to_datetime(df.index, utc=True)
        start_deltas.append((times[0].to_pydatetime() - timestamp(s['connectionTime'])).total_seconds())
        unplug = df['Charging State'].eq('UNPLUGGED').to_numpy()
        if unplug.any():
            stop_deltas.append((times[np.flatnonzero(unplug)[0]].to_pydatetime() - timestamp(s['disconnectTime'])).total_seconds())
        else:
            fields['matched_recordings_without_unplug'] += 1
            fields['recordings_end_before_metadata_disconnect'] += times[-1].to_pydatetime() < timestamp(s['disconnectTime'])
        # Retrospective validation only; this maximum is NEVER a predictor.
        energy_deltas.append(float(df['Energy Delivered (kWh)'].max()) - float(s['kWhDelivered']))
        fields['energy_mismatch_over_0p01_kwh'] += abs(energy_deltas[-1]) > .01
        fields['energy_mismatch_without_unplug'] += abs(energy_deltas[-1]) > .01 and not unplug.any()
        fields['request_available_at_first_record'] += request_asof(s, times[0].to_pydatetime()) is not None
    def summary(v):
        return {'n': len(v), 'min': float(np.min(v)), 'median': float(np.median(v)), 'max': float(np.max(v)), 'absolute_p95': float(np.quantile(np.abs(v), .95))} if v else {'n': 0}
    out = {'scope': 'Exploratory linkage and request availability, not a forecast evaluation',
           'matched_selected_sessions': len(sessions), 'selected_sessions': 128,
           'first_alarm_outcomes_and_request_availability': {k: dict(v) for k,v in strata.items()},
           'first_record_minus_metadata_connection_seconds': summary(start_deltas),
           'first_unplug_minus_metadata_disconnect_seconds': summary(stop_deltas),
           'retrospective_counter_max_minus_metadata_delivered_kwh': summary(energy_deltas),
           **dict(fields),
           'limitations': ['117 exact identifier matches do not prove identical extraction versions',
                           'Only submission-time availability is known; no receive timestamps',
                           'Unknown requests remain unknown; no final-energy imputation',
                           'Small requested-and-resumed subset cannot validate a control forecasting model']}
    (HERE / 'reports/request_linkage.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
