"""Prefix-only recovery features and supported, competing-risk follow-up."""
import numpy as np
from acnresearch.alarms import first_alarm
from acnresearch.requests import request_asof, timestamp

FEATURES = ['elapsed_min', 'energy_kwh', 'current_mean', 'current_std',
            'current_max', 'recent_mean', 'recent_std', 'recent_trend',
            'pilot_mean', 'pilot_now', 'recent_ratio', 'hour_sin', 'hour_cos',
            'weekday', 'request_known', 'remaining_kwh', 'slack_min']


def prefix_features(df, i, session=None):
    """Only df[:i+1] and request versions disclosed by df.index[i] may matter."""
    prefix = df.iloc[:i+1]
    at = prefix.index[-1]
    times = prefix.index.asi8 / 1e9
    current = prefix['Charging Current (A)'].to_numpy(float)
    pilot = prefix['Actual Pilot (A)'].to_numpy(float)
    energy = prefix['Energy Delivered (kWh)'].to_numpy(float)
    valid_energy = np.isfinite(energy).all() and (energy >= 0).all() and (np.diff(energy) >= -1e-6).all()
    recent = times >= times[-1]-600
    before = (times >= times[-1]-600) & (times < times[-1]-300)
    after = times >= times[-1]-300
    def mean(x):
        return float(np.mean(x[np.isfinite(x)])) if np.isfinite(x).any() else np.nan
    def std(x):
        return float(np.std(x[np.isfinite(x)])) if np.isfinite(x).any() else np.nan
    local = at.tz_convert('America/Los_Angeles')
    angle = 2*np.pi*(local.hour+local.minute/60)/24
    ratios = np.divide(current[recent],pilot[recent],out=np.full(recent.sum(),np.nan),where=pilot[recent]>=6)
    req = None
    if session and abs((timestamp(session['connectionTime'])-prefix.index[0]).total_seconds())<=60:
        try: req = request_asof(session, at)
        except ValueError: pass  # Ambiguous simultaneous revisions are unavailable.
    return dict(elapsed_min=float((times[-1]-times[0])/60),
                energy_kwh=float(energy[-1]) if valid_energy else np.nan,
                current_mean=mean(current), current_std=std(current),
                current_max=float(np.nanmax(current)) if np.isfinite(current).any() else np.nan,
                recent_mean=mean(current[recent]), recent_std=std(current[recent]),
                recent_trend=mean(current[after])-mean(current[before]),
                pilot_mean=mean(pilot), pilot_now=float(pilot[-1]), recent_ratio=mean(ratios),
                hour_sin=float(np.sin(angle)),hour_cos=float(np.cos(angle)), weekday=local.weekday(),
                request_known=int(req is not None),
                remaining_kwh=float(req['kwh_requested']-energy[-1]) if req and valid_energy else np.nan,
                slack_min=(req['requested_departure']-at).total_seconds()/60 if req else np.nan)


def followup(df, alarm_index, horizon=60):
    """Confirmed >=6A for60s; stop when positive-pilot support is lost.

    No assertion of causal identification: continuous pilot>=6 only rules out
    the simplest command-zero explanation. A future 30A response is unknown.
    """
    times = df.index.asi8/1e9
    current = df['Charging Current (A)'].to_numpy(float)
    pilot = df['Actual Pilot (A)'].to_numpy(float)
    state = df['Charging State'].to_numpy()
    origin = times[alarm_index]; last=origin; high_since=None; rebound=np.nan
    result = dict(event_min=np.nan, observed_min=0., terminal=False,
                  reason='file_end', rebound_min=np.nan, confirmation_current=np.nan)
    for j in range(alarm_index+1,len(df)):
        t=times[j]; dt=t-times[j-1]
        if dt<=0 or dt>15:
            result['reason']='gap'; break
        if state[j]=='UNPLUGGED':
            result.update(reason='unplug',terminal=True,observed_min=min(horizon,(t-origin)/60)); break
        if not np.isfinite(current[j]) or not np.isfinite(pilot[j]):
            result['reason']='missing'; break
        if pilot[j]<6:
            result['reason']='pilot_below_6'; break
        if (t-origin)/60>horizon:
            result.update(reason='horizon',observed_min=float(horizon)); break
        last=t; result['observed_min']=(last-origin)/60
        if current[j]>.5 and not np.isfinite(rebound): rebound=(t-origin)/60
        if current[j]>=6:
            if high_since is None: high_since=t
            if t-high_since>=60:
                result.update(event_min=(t-origin)/60,reason='sustained_recovery',
                              confirmation_current=float(current[j]))
                break
        else: high_since=None
    result['rebound_min']=float(rebound)
    return result


def extract_episode(df, session=None):
    alarm=first_alarm(df)
    if alarm is None: return None,'no_alarm'
    if not alarm['pilot_ge_6_through_prefix']: return None,'unsupported_alarm'
    i=alarm['alarm_index']
    return dict(alarm_time=df.index[i].isoformat(),**prefix_features(df,i,session),**followup(df,i)), 'eligible_alarm'


def horizon_labels(frame, minutes):
    event=frame.event_min.to_numpy(float)
    y=(np.isfinite(event)&(event<=minutes)).astype(int)
    # An observed event after h also proves no event through h.
    known=np.isfinite(event)|frame.terminal.to_numpy(bool)|(frame.observed_min.to_numpy(float)>=minutes)
    return y,known


def complete_episode_mask(frame):
    return np.isfinite(frame.event_min)|frame.terminal|(frame.observed_min>=60)
