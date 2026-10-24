import itertools
import numpy as np
import pandas as pd
from acnresearch.recovery import prefix_features, followup, horizon_labels
from acnresearch.discovery import dp_schedule, run_discovery, monotone_cdf


def frame(current,pilot=None):
    n=len(current)
    return pd.DataFrame({'Charging Current (A)':current,'Actual Pilot (A)':pilot if pilot is not None else np.full(n,30.),
                         'Energy Delivered (kWh)':np.arange(n)/100,'Charging State':['CONNECTED']*n},
                        index=pd.date_range('2020-01-01',periods=n,freq='10s',tz='UTC'))


def test_future_telemetry_does_not_change_prefix_features():
    a=frame([12]*10+[0]*10+[30]*10); b=a.copy(); b.iloc[20:,0:3]=99
    np.testing.assert_allclose(list(prefix_features(a,19).values()),list(prefix_features(b,19).values()),equal_nan=True)


def test_spikes_are_not_sustained_recovery_and_confirmation_is_causal():
    a=frame([0]*7+[.8]*7+[10]*7)
    result=followup(a,0)
    assert result['rebound_min']==70/60
    assert result['event_min']==200/60
    assert np.isnan(followup(a.iloc[:-1],0)['event_min'])


def test_pilot_withdrawal_censors_and_unplug_is_competing_event():
    a=frame([0]*10,[30]*5+[0]*5)
    r=followup(a,0); assert r['reason']=='pilot_below_6' and r['observed_min']==40/60
    a.iloc[5,a.columns.get_loc('Charging State')]='UNPLUGGED'
    r=followup(a,0); assert r['terminal']
    d=pd.DataFrame([r]); y,known=horizon_labels(d,15)
    assert known[0] and y[0]==0


def test_gap_before_apparent_recovery_is_censored():
    a=frame([0]*7+[12]*7)
    a.index=list(a.index[:7])+list(a.index[7:]+pd.Timedelta(minutes=5))
    assert followup(a,0)['reason']=='gap'


def test_dp_matches_exhaustive_schedules_and_wait_is_bounded():
    cdf=np.array([.1,.3,.35,.8]); nxt,v=dp_schedule(cdf,max_gap=2)
    mass=np.diff(np.r_[0,cdf,1.])
    costs=[]
    for flags in itertools.product([False,True],repeat=3):
        probes=[j+1 for j,x in enumerate(flags) if x]+[4]
        if max(np.diff([0]+probes))>2: continue
        expected=0.
        for recovery,prob in enumerate(mass,start=1):
            fail=sum(t<recovery for t in probes)
            delay=next((t-recovery for t in probes if t>=recovery),0)
            expected+=prob*(fail+delay)
        costs.append(expected)
    assert abs(v[0]-min(costs))<1e-10
    assert all(1<=nxt[t]-t<=2 for t in range(4))


def test_wrong_forecast_has_finite_fallback_and_no_future_oracle():
    a=run_discovery(5,60,np.zeros(12),'dp')
    b=run_discovery(55,60,np.zeros(12),'dp')
    assert a['probe_slots'][0]==b['probe_slots'][0]==4
    assert a['delay_slots']<=3 and b['delay_slots']<=3
    assert np.all(np.diff(monotone_cdf([.2,.1,.6]))>=0)
