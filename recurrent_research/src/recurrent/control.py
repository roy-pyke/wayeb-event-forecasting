"""Same-information baselines and exact two-slot shared recourse.

This is an explicit Bellman calculation, not a claimed new algorithm.
Controller inputs deliberately exclude future true availability and arrivals.
"""
from functools import lru_cache
from itertools import combinations, product
import numpy as np


@lru_cache(None)
def action_outcomes(n, k):
    k = min(n, k)
    actions = np.asarray(list(combinations(range(n), k)), dtype=int).reshape(-1, k)
    outcomes = np.asarray(list(product((0., 1.), repeat=k)), dtype=float).reshape(-1, k)
    return actions, outcomes


def head_arrays(queues, t):
    value = np.asarray([q[0][0] if q else 0 for q in queues], dtype=float)
    slack = np.asarray([q[0][1]-t if q else 1 for q in queues], dtype=float)
    # The next head after no completion / one successful completion, with expiry.
    future = np.zeros((len(queues), 2))
    for i, q in enumerate(queues):
        for success in [0, 1]:
            remaining = [x for x in q[success:] if x[1] > t + 1]
            if remaining:
                future[i, success] = remaining[0][0]
    return value, slack, future


def joint_values(p, value, future, p01, p11, k, observe=True):
    """All full-sized current actions; exact expectation of next top-K value."""
    eligible = np.flatnonzero(value > 0)
    n = len(eligible)
    if n == 0:
        return np.empty((1, 0), dtype=int), np.zeros(1)
    local_actions, outcomes = action_outcomes(n, k)
    actions = eligible[local_actions]
    a_count, o_count = len(actions), len(outcomes)
    prob_selected = p[actions]
    likelihood = np.prod(np.where(outcomes[None, :, :] > 0,
                                  prob_selected[:, None, :], 1-prob_selected[:, None, :]), axis=2)
    pnext = p01 + (p11-p01)*p
    next_values = np.broadcast_to(future[:, 0]*pnext,
                                  (a_count, o_count, len(p))).copy()
    for c in range(actions.shape[1]):
        ix = actions[:, c]
        response = outcomes[:, c].astype(int)
        beliefs = p01 + (p11-p01)*response[None, :] if observe else pnext[ix, None]
        next_values[np.arange(a_count)[:, None], np.arange(o_count)[None, :], ix[:, None]] = (
            future[ix[:, None], response[None, :]]*beliefs)
    future_reward = np.sort(next_values, axis=2)[:, :, -min(k, len(p)):].sum(axis=2)
    q = np.sum(value[actions]*p[actions], axis=1) + np.sum(likelihood*future_reward, axis=1)
    return actions, q


def independent_scores(p, value, future, p01, p11):
    pnext = p01 + (p11-p01)*p
    active = p*future[:, 1]*p11 + (1-p)*future[:, 0]*p01
    passive = future[:, 0]*pnext
    return value*p + active-passive


def select(policy, p, queues, t, k, p01, p11, due=None, current_truth=None, horizon=32):
    if policy in ('priced_horizon8','unpriced_horizon8'):
        from .pricing import priced_select
        return priced_select(p,queues,t,k,p01,p11,horizon,priced=policy=='priced_horizon8')
    value, slack, future = head_arrays(queues, t)
    eligible = value > 0
    if not eligible.any():
        return np.empty(0, dtype=int)
    if policy.startswith('joint_two_step') and t < horizon-1:
        actions, q = joint_values(p, value, future, p01, p11, k,
                                  observe=policy != 'joint_two_step_no_observation')
        # Stable ties: lexicographically first full-sized action, no outcome access.
        return actions[int(np.argmax(q))]
    if policy == 'independent_two_step' and t < horizon-1:
        scores = independent_scores(p, value, future, p01, p11)
    elif policy == 'urgency_value':
        scores = value*p/slack
    elif policy == 'current_state_oracle':
        if current_truth is None:
            raise ValueError('Oracle only: requires additional current state')
        scores = value*current_truth
    elif policy in ('edf', 'fixed_backoff_2', 'exponential_backoff_1_2_4'):
        if due is not None and policy != 'edf':
            eligible &= due <= t
        indices = np.flatnonzero(eligible)
        return np.asarray(sorted(indices, key=lambda i:(slack[i],-value[i]*p[i],i))[:k])
    elif policy in ('myopic_value','independent_two_step','joint_two_step',
                    'joint_two_step_absorbing','joint_two_step_no_observation'):
        scores = value*p
    else:
        raise ValueError('Unknown policy: '+policy)
    indices = np.flatnonzero(eligible)
    return np.asarray(sorted(indices, key=lambda i:(-scores[i],i))[:k], dtype=int)
