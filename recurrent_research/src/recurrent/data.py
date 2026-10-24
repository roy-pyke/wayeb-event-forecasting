"""Availability intervals with explicit measurement-boundary censoring."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import numpy as np


@dataclass
class Trace:
    name: str
    nodes: list[str]
    intervals: list[np.ndarray]
    times: np.ndarray
    states: np.ndarray  # -1 unknown, 0 unreachable, 1 reachable
    step: int


def read_avt(path: Path, step: int) -> Trace:
    nodes, intervals = [], []
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        parts = line.split()
        a = np.asarray(parts[2:], dtype=float).reshape(-1, 2)
        if len(a) != int(parts[1]):
            raise ValueError('Invalid interval count')
        if len(a) and (np.any(a[:, 1] < a[:, 0]) or np.any(a[1:, 0] < a[:-1, 1])):
            raise ValueError('Reversed or overlapping intervals')
        nodes.append(parts[0]); intervals.append(a)
    if len(set(nodes)) != len(nodes):
        raise ValueError('Duplicate node identifiers')
    end = max(a[-1, 1] for a in intervals if len(a))
    start = min(a[0, 0] for a in intervals if len(a))
    times = np.arange(np.ceil(start / step) * step, end, step)
    states = np.full((len(nodes), len(times)), -1, dtype=np.int8)
    for i, a in enumerate(intervals):
        if not len(a):
            continue
        valid = (times >= a[0, 0]) & (times < a[-1, 1])
        idx = np.searchsorted(a[:, 0], times, side='right') - 1
        up = (idx >= 0) & (times < a[np.maximum(idx, 0), 1])
        states[i, valid] = up[valid].astype(np.int8)
    return Trace(path.stem, nodes, intervals, times, states, step)


def fit_rates(trace: Trace, stop: float) -> dict:
    """Pooled exposure estimator. First/last endpoints are never transitions."""
    exposure_up = exposure_down = 0.0
    up_to_down = down_to_up = 0
    start = float(trace.times[0])
    for a in trace.intervals:
        if not len(a):
            continue
        lo, hi = max(start, a[0, 0]), min(stop, a[-1, 1])
        if hi <= lo:
            continue
        up = np.maximum(0.0, np.minimum(a[:, 1], hi) - np.maximum(a[:, 0], lo)).sum()
        exposure_up += float(up)
        exposure_down += float(hi - lo - up)
        up_to_down += int(((a[:-1, 1] > lo) & (a[:-1, 1] < hi)).sum())
        down_to_up += int(((a[1:, 0] > lo) & (a[1:, 0] < hi)).sum())
    if min(exposure_up, exposure_down) <= 0:
        raise ValueError('Need positive exposure in both states')
    return {'up_to_down_per_second': (up_to_down + 0.5) / exposure_up,
            'down_to_up_per_second': (down_to_up + 0.5) / exposure_down,
            'exposure_up_seconds': exposure_up, 'exposure_down_seconds': exposure_down,
            'up_to_down_events': up_to_down, 'down_to_up_events': down_to_up,
            'training_stop_seconds': stop, 'source': trace.name}


def transition(rates: dict, seconds: float) -> tuple[float, float]:
    """Return P(up next | down), P(up next | up), allowing repeated flips."""
    down = rates['up_to_down_per_second']
    up = rates['down_to_up_per_second']
    stationary = up / (up + down)
    decay = np.exp(-(up + down) * seconds)
    return float(stationary * (1 - decay)), float(stationary + (1 - stationary) * decay)


def split_bounds(trace: Trace) -> dict:
    n = len(trace.times)
    return {'train': (1, int(n * .6)), 'dev': (int(n * .6), int(n * .8)),
            'test': (int(n * .8), n)}


def windows(trace: Trace, split: str, limit: int, slots: int = 32, nodes: int = 6):
    lo, hi = split_bounds(trace)[split]
    starts = np.arange(lo, hi - slots + 1, slots)
    if len(starts) > limit:
        starts = starts[np.linspace(0, len(starts) - 1, limit, dtype=int)]
    for start in starts:
        # No test-outcome-based filtering: only earlier first observed up.
        candidates = [i for i, a in enumerate(trace.intervals)
                      if len(a) and a[0, 0] <= trace.times[start - 1]]
        candidates.sort(key=lambda i: hashlib.sha256(
            f'{trace.name}/{int(start)}/{trace.nodes[i]}'.encode()).hexdigest())
        chosen = candidates[:nodes]
        if len(chosen) < nodes:
            yield int(start), chosen, np.empty((0, nodes), dtype=np.int8), np.zeros(nodes), 'inventory'
            continue
        state = trace.states[chosen, start:start + slots].T
        initial = trace.states[chosen, start - 1]
        if np.any(initial < 0):
            yield int(start), chosen, state[:0], initial, 'initial_unknown'
            continue
        unknown = np.flatnonzero((state < 0).any(axis=1))
        length = int(unknown[0]) if len(unknown) else slots
        yield int(start), chosen, state[:length], initial, ('right_censored' if length < slots else 'complete')


def audit(trace: Trace) -> dict:
    transitions = (trace.states[:, 1:] != trace.states[:, :-1]) & (trace.states[:, 1:] >= 0) & (trace.states[:, :-1] >= 0)
    out = {'nodes': len(trace.nodes), 'intervals': sum(map(len, trace.intervals)),
           'grid_start_seconds': float(trace.times[0]), 'grid_end_seconds': float(trace.times[-1]),
           'step_seconds': trace.step, 'grid_points': len(trace.times),
           'known_node_slots': int((trace.states >= 0).sum()),
           'up_node_slots': int((trace.states == 1).sum()), 'down_node_slots': int((trace.states == 0).sum()),
           'grid_state_changes': int(transitions.sum()),
           'nodes_with_at_least_two_up_intervals': sum(len(a) >= 2 for a in trace.intervals), 'splits': {}}
    for name, (lo, hi) in split_bounds(trace).items():
        s = trace.states[:, lo:hi]
        out['splits'][name] = {'start': float(trace.times[lo]), 'end': float(trace.times[hi-1]),
                               'known_slots': int((s >= 0).sum()), 'down_slots': int((s == 0).sum())}
    for name, limit in [('dev', 240), ('test', 480)]:
        sampled = list(windows(trace, name, limit))
        out['splits'][name]['replay'] = {
            'selected_windows': len(sampled), 'usable_windows': sum(len(x[2]) > 0 for x in sampled),
            'complete_windows': sum(x[4] == 'complete' for x in sampled),
            'initial_unknown': sum(x[4] == 'initial_unknown' for x in sampled),
            'right_censored': sum(x[4] == 'right_censored' for x in sampled),
            'evaluated_slots': sum(len(x[2]) for x in sampled)}
    return out
