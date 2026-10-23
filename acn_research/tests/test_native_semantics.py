from types import SimpleNamespace
import numpy as np
from acnresearch.native import AvailabilityBattery, DeclaredRequestInterface
from acnportal.acnsim.interface import SessionInfo
from acnportal.algorithms.preprocessing import apply_upper_bound_estimate


def test_distinct_station_and_session_keys_apply_bound():
    session = SessionInfo('station-X', 'session-Y', 5, 0, 0, 10, 10, 0)
    estimator = SimpleNamespace(get_maximum_rates=lambda _: {'session-Y': 11})
    result = apply_upper_bound_estimate(estimator, [session])
    assert np.all(result[0].max_rates == 11)


def test_new_action_regenerates_response_and_future_cap_cannot_change_prefix():
    a = AvailabilityBattery(10, [32]*10+[0]*10)
    b = AvailabilityBattery(10, [32]*20)
    for _ in range(10):
        assert a.charge(12,208,1) == b.charge(12,208,1)
    c = AvailabilityBattery(10, [32]*10)
    d = AvailabilityBattery(10, [32]*10)
    assert c.charge(0,208,1) == 0
    assert d.charge(12,208,1) == 12


def test_actual_departure_never_enters_declared_request_interface():
    ev = SimpleNamespace(station_id='s',session_id='q',requested_energy=5,
                         energy_delivered=1,arrival=0,departure=20,estimated_departure=50)
    sim = SimpleNamespace(iteration=4,get_active_evs=lambda:[ev])
    interface = DeclaredRequestInterface(sim)
    assert interface._active_sessions()[0].departure == 50
    ev.departure = 90
    assert interface._active_sessions()[0].departure == 50
