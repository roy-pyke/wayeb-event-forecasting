"""First low-current alarm. Features are prefix-only; outcomes are censored."""
import numpy as np


def first_alarm(df, threshold=.5, alarm_seconds=60, gap_seconds=15):
    times=df.index.asi8/1e9
    currents=df['Charging Current (A)'].to_numpy(float)
    pilots=df['Actual Pilot (A)'].to_numpy(float)
    states=df['Charging State'].to_numpy()
    had_active=False; start=None; alarm=None; min_pilot=np.inf
    def finish(reason,j):
        return dict(alarm, outcome=reason, outcome_index=j) if alarm is not None else None
    for j,(t,current,pilot,state) in enumerate(zip(times,currents,pilots,states)):
        if j and (t-times[j-1]<=0 or t-times[j-1]>gap_seconds):
            if alarm is not None: return finish('censored_gap',j)
            had_active=False; start=None; min_pilot=np.inf
        if state=='UNPLUGGED':
            return finish('unplug_without_observed_resumption',j)
        if not np.isfinite(current):
            if alarm is not None: return finish('censored_missing_current',j)
            had_active=False; start=None; min_pilot=np.inf
            continue
        if current>threshold:
            if alarm is not None: return finish('resumed',j)
            had_active=True; start=None; min_pilot=np.inf
            continue
        if not had_active: continue
        if start is None: start=t
        min_pilot=min(min_pilot,pilot) if np.isfinite(pilot) else -np.inf
        if alarm is None and t-start>=alarm_seconds:
            alarm={'alarm_index':j,'inactive_since':float(start),
                   'pilot_ge_6_through_prefix':bool(min_pilot>=6)}
    return finish('censored_file_end',len(df)-1)
