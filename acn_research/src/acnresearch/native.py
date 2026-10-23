"""Actual ACN-Sim + corrected AdaCharge execution, with a causal interface."""
from datetime import datetime, timezone
import hashlib
import inspect
import time
import warnings
import numpy as np
from acnportal import acnsim, algorithms
from acnportal.acnsim.interface import Interface, SessionInfo
from acnportal.algorithms import preprocessing
from adacharge import AdaptiveSchedulingAlgorithm
from adacharge.adaptive_charging_optimization import ObjectiveComponent, total_energy, quick_charge


class DeclaredRequestInterface(Interface):
    """Expose declared departure, rather than EV.departure from the simulator.

    These fixtures disclose their energy requests at arrival. Real data must
    additionally use request_asof; this interface is not a raw-data adapter.
    """
    def _active_sessions(self):
        return [SessionInfo(ev.station_id, ev.session_id, ev.requested_energy,
                            ev.energy_delivered, ev.arrival,
                            max(ev.estimated_departure, self.current_time + 1),
                            max(ev.estimated_departure, self.current_time + 1),
                            self.current_time)
                for ev in self._active_evs]


class AvailabilityBattery(acnsim.Battery):
    """Explicit exogenous cap; new pilots always regenerate actual response.

    The cap curve is a simulated latent input, not replayed historical current.
    A native simulator calls charge each connected period, including zero pilot.
    """
    def __init__(self, energy_kwh, caps_amp, voltage=208):
        super().__init__(energy_kwh, 0, 32 * voltage / 1000)
        self.caps_amp = np.asarray(caps_amp, dtype=float)
        self.local_step = 0

    def charge(self, pilot, voltage, period):
        cap = self.caps_amp[min(self.local_step, len(self.caps_amp)-1)]
        self.local_step += 1
        return super().charge(min(pilot, cap), voltage, period)


class AuditedRampdown(algorithms.SimpleRampdown):
    def __init__(self, floor=0, up_increment=1):
        super().__init__(up_increment=up_increment)
        self.floor = floor
        self.history = []

    def get_maximum_rates(self, sessions):
        bounds = super().get_maximum_rates(sessions)
        if self.floor:
            # Explicit conventional probing guard, not part of the ID patch.
            for s in sessions:
                bounds[s.session_id] = max(self.floor, bounds[s.session_id])
        self.history.append({'time': int(self.interface.current_time),
                             'bounds': {str(k): float(v) for k, v in bounds.items()}})
        return bounds


class AuditedASA(AdaptiveSchedulingAlgorithm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.solve_calls = 0

    def schedule(self, active_sessions):
        self.solve_calls += bool(active_sessions)
        return super().schedule(active_sessions)


def run_native_fixture(*, estimation=True, discrete=False, probe_floor=0, up_increment=1, pause=True):
    source = inspect.getsource(preprocessing.apply_upper_bound_estimate)
    assert 'upper_bounds.get(session.session_id' in source, 'Run setup.py first'
    network = acnsim.ChargingNetwork()
    stations = ['station-A', 'station-B', 'station-C']
    for sid in stations:
        evse = acnsim.FiniteRatesEVSE(sid, [0,6,12,18,24,30]) if discrete else acnsim.EVSE(sid, max_rate=32)
        network.register_evse(evse, 208, 0)
    capacity = 36 if discrete else 40
    network.add_constraint(acnsim.Current(stations), capacity, name='shared-feeder')
    events = []
    evs = []
    for i, sid in enumerate(stations):
        caps = np.full(60, 30.0 if discrete else 32.0)
        if pause and i == 0:
            caps[10:30] = 0
        ev = acnsim.EV(0, 60, 2.0, sid, f'session-{i}',
                      AvailabilityBattery(2.0, caps), estimated_departure=60)
        events.append(acnsim.PluginEvent(0, ev)); evs.append(ev)
    estimator = AuditedRampdown(probe_floor, up_increment)
    scheduler = AuditedASA(
        [ObjectiveComponent(total_energy, 1), ObjectiveComponent(quick_charge, 1e-5)],
        solver='CLARABEL', constraint_type='LINEAR',
        estimate_max_rate=estimation, max_rate_estimator=estimator,
        max_recompute=1, quantize=discrete, reallocate=discrete,
        uninterrupted_charging=False)
    sim = acnsim.Simulator(network, scheduler, acnsim.EventQueue(events),
                          datetime(2020,1,1,tzinfo=timezone.utc), period=1,
                          verbose=False, interface_type=DeclaredRequestInterface)
    start = time.perf_counter()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always')
        sim.run()
    elapsed = time.perf_counter() - start
    current, pilot = sim.charging_rates[:, :60], sim.pilot_signals[:, :60]
    delivered = np.array([ev.energy_delivered for ev in evs])
    assert np.max(pilot.sum(axis=0)) <= capacity + 1e-4
    assert np.max(current.sum(axis=0)) <= capacity + 1e-4
    assert np.all(current <= pilot + 1e-6) and np.min(current) >= -1e-8
    assert np.all(delivered <= 2 + 1e-6)
    assert np.allclose(current.sum(axis=1) * 208 / 60000, delivered, atol=1e-9)
    if pause: assert np.max(np.abs(current[0,10:30])) < 1e-10
    if discrete:
        assert np.max(np.abs(pilot/6-np.rint(pilot/6))) < 1e-6
    raw_warning_messages = sorted({str(w.message) for w in captured})
    assert not any('Invalid schedule' in x for x in raw_warning_messages), raw_warning_messages
    return ({'estimation': estimation, 'discrete_6A_pilots': discrete,
            'probe_floor_amp': probe_floor, 'pause': pause,
            'up_increment_amp': up_increment,
            'delivered_kwh': delivered.tolist(), 'total_delivered_kwh': float(delivered.sum()),
            'shortfall_kwh': float(6-delivered.sum()), 'actual_peak_amp': float(current.sum(axis=0).max()),
            'pilot_peak_amp': float(pilot.sum(axis=0).max()), 'capacity_amp': capacity,
            'recovered_vehicle_energy_after_resume_kwh': float(current[0,30:].sum()*208/60000),
            'solver_calls': scheduler.solve_calls,
            'runtime_seconds': elapsed, 'warnings': raw_warning_messages,
            'patch_lookup_verified': True, 'energy_and_feasibility_assertions': 'passed'},
            {'pilot': pilot, 'current': current, 'bounds': estimator.history})
