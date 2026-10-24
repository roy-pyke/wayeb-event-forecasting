from copy import deepcopy
import numpy as np
import pandas as pd
from acnresearch.learned_service import make_service_world,run_service,offline_service


def world(cap=36,rate=30):
    episodes=pd.DataFrame({'event_min':[5.,25.,np.nan],'terminal':[False]*3,'observed_min':[5.,25.,60.]})
    cdf=np.tile(np.linspace(.05,.5,12),(3,1))
    return make_service_world(724,cap,rate,episodes,cdf,cdf)


def test_future_cap_change_preserves_actions_until_feedback():
    w=world(); other=deepcopy(w); other.response_caps[:,6:]=0
    _,a=run_service(w); _,b=run_service(other)
    np.testing.assert_array_equal(a['pilot'][:,:7],b['pilot'][:,:7])


def test_spare_capacity_reaches_bound_for_both_capacity_assumptions():
    for rate in [6,30]:
        w=world(180,rate); bound=offline_service(w)
        for kind in ['every_1','every_4','backoff','dp','threshold']:
            result,_=run_service(w,kind=kind)
            assert abs(result['delivered_kwh']-bound)<1e-8


def test_predicted_notices_never_bypass_physical_response_or_flow_bound():
    w=world(36); w.cdf[:]=.99
    result,trace=run_service(w,restore=True)
    assert np.all(trace['actual']<=w.response_caps)
    assert result['delivered_kwh']<=offline_service(w)+1e-8
