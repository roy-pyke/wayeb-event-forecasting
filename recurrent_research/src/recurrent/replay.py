"""Bounded read-only request model on exogenous reachability traces."""
import hashlib
import time
import numpy as np
from .control import select

POLICIES = ['edf', 'fixed_backoff_2', 'exponential_backoff_1_2_4', 'myopic_value',
            'urgency_value', 'independent_two_step', 'joint_two_step',
            'joint_two_step_absorbing', 'joint_two_step_no_observation', 'current_state_oracle']


def arrivals_for(name, start, slots=32, n=6):
    seed = int.from_bytes(hashlib.sha256(f'23027/{name}/{start}'.encode()).digest()[:8], 'little')
    rng = np.random.default_rng(seed)
    arrival = rng.random((slots, n)) < .35
    value = rng.choice([1, 2, 4], size=(slots, n))
    ttl = rng.choice([2, 4, 8], size=(slots, n))
    return arrival, value, ttl


def simulate(states, initial, arrivals, policy, k, p01, p11, keep_history=False):
    T, n = states.shape
    arrival, values, ttls = arrivals
    if policy == 'joint_two_step_absorbing':
        p11 = 1.
    p = p01 + (p11-p01)*np.asarray(initial, dtype=float)
    queues = [[] for _ in range(n)]
    due, failures = np.zeros(n, dtype=int), np.zeros(n, dtype=int)
    stats = dict(completed_value=0, completed_records=0, attempts=0, failed_attempts=0,
                 expired_value=0, expired_records=0, rejected_value=0, rejected_records=0,
                 arrived_value=0, arrived_records=0, max_buffer=0, observed_slots=0,
                 prediction_squared_error=0., selected_prediction_sum=0., selected_outcome_sum=0.)
    history = []
    started = time.perf_counter()
    for t in range(T):
        for i in range(n):
            expired = [x for x in queues[i] if x[1] <= t]
            stats['expired_value'] += sum(x[0] for x in expired)
            stats['expired_records'] += len(expired)
            queues[i] = [x for x in queues[i] if x[1] > t]
            if arrival[t, i]:
                v, deadline = int(values[t,i]), t + int(ttls[t,i])
                stats['arrived_value'] += v; stats['arrived_records'] += 1
                if len(queues[i]) == 2:
                    stats['rejected_value'] += v; stats['rejected_records'] += 1
                else:
                    queues[i].append((v, deadline))
        stats['max_buffer'] = max(stats['max_buffer'], sum(map(len, queues)))
        selected = select(policy, p.copy(), queues, t, k, p01, p11, due,
                          current_truth=states[t] if policy == 'current_state_oracle' else None)
        if len(set(selected.tolist())) != len(selected) or len(selected) > k:
            raise AssertionError('Capacity or uniqueness violation')
        if keep_history:
            history.append({'t':t, 'belief':p.tolist(), 'queue':[list(q) for q in queues],
                            'selected':selected.tolist(), 'response':states[t,selected].tolist()})
        for i in selected:
            if not queues[i]:
                raise AssertionError('Request without a payload')
            y = int(states[t,i])
            if y not in [0, 1]:
                raise AssertionError('Unobserved trace state entered replay')
            stats['attempts'] += 1
            stats['prediction_squared_error'] += float((p[i]-y)**2)
            stats['selected_prediction_sum'] += float(p[i]); stats['selected_outcome_sum'] += y
            if y:
                stats['completed_value'] += queues[i].pop(0)[0]
                stats['completed_records'] += 1
                failures[i] = 0; due[i] = t+1
            else:
                stats['failed_attempts'] += 1
                failures[i] += 1
                gap = 2 if policy == 'fixed_backoff_2' else 2**min(int(failures[i])-1, 2)
                due[i] = t+gap
            p[i] = y
        p = p01 + (p11-p01)*p
        stats['observed_slots'] += 1
    stats['runtime_seconds'] = time.perf_counter()-started
    stats['pending_value'] = sum(x[0] for q in queues for x in q)
    stats['pending_records'] = sum(map(len, queues))
    if stats['arrived_value'] != sum(stats[x] for x in ['completed_value','expired_value','rejected_value','pending_value']):
        raise AssertionError('Value conservation failed')
    if stats['arrived_records'] != sum(stats[x] for x in ['completed_records','expired_records','rejected_records','pending_records']):
        raise AssertionError('Record conservation failed')
    if stats['max_buffer'] > 2*n or stats['attempts'] > k*T:
        raise AssertionError('Resource limit violated')
    return stats, history
