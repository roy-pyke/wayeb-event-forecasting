"""Offline exact moments of the deployed Rao-Blackwell tail estimator.

These oracle computations are diagnostic only, never available to an estimator.
"""
import numpy as np
from queryforecast.estimators import children
from pooling import group_stats


def conditional_moments(source, mon, roots):
    records = [None]*len(roots)
    pending = list(enumerate(roots))
    while pending:
        active = []
        for i, node in pending:
            y = mon.fixed(node.state)
            if y is None:
                active.append((i, node))
            else:
                records[i] = (y, float(y@y))
        pending = []
        for begin in range(0, len(active), 4096):
            batch = active[begin:begin+4096]
            hidden, prob = source.evaluate([n.hidden for _, n in batch], [n.last for _, n in batch])
            for j, (i, node) in enumerate(batch):
                branch = children(mon, node, hidden[j], prob[j])
                fixed = [mon.fixed(n.state) for n in branch]
                if all(y is not None for y in fixed):
                    value = prob[j] @ np.array(fixed)
                    # This step is analytically averaged in tails(), not sampled.
                    records[i] = (value, float(value@value))
                else:
                    ids = np.arange(len(records), len(records)+5)
                    records.extend([None]*5)
                    records[i] = (prob[j], ids, 'branch')
                    pending.extend(zip(ids, branch))
    for i in range(len(records)-1, -1, -1):
        record = records[i]
        if len(record) == 3:
            p, ids, _ = record
            mean = p @ np.array([records[j][0] for j in ids])
            second = float(p @ np.array([records[j][1] for j in ids]))
            records[i] = (mean, second)
    return (np.array([r[0] for r in records[:len(roots)]]),
            np.array([r[1] for r in records[:len(roots)]]))


def allocation(mon, groups, expanded, budget):
    """Replay the registered deterministic allocation, with no sampled outcomes."""
    masses, costs, caps = group_stats(mon, groups)
    while costs.sum()+expanded > budget:
        a, b = map(int, np.argsort(masses)[:2])
        groups = [g for i, g in enumerate(groups) if i not in (a, b)]+[groups[a]+groups[b]]
        masses, costs, caps = group_stats(mon, groups)
    counts = np.ones(len(groups), int)
    left = int(budget-expanded-costs.sum())
    while np.any(costs <= left):
        gain = masses**2*caps/(counts*(counts+1)*costs)
        gain[costs > left] = -1
        i = int(np.argmax(gain))
        counts[i] += 1
        left -= int(costs[i])
    return groups, masses, counts, costs, caps


def decomposition(mon, frontier, groups, masses, counts, means, seconds):
    index = {id(n): i for i, n in enumerate(frontier)}
    within_total = between_total = 0.
    for group, mass, count in zip(groups, masses, counts):
        ix = [index[id(n)] for n in group]
        w = np.array([n.mass for n in group])/mass
        mu = means[ix]
        squared = np.sum(mu*mu, axis=1)
        center = w@mu
        within = float(w @ (seconds[ix]-squared))
        between = float(w @ squared-center@center)
        if min(within, between) < -1e-10:
            raise AssertionError('negative oracle variance')
        within_total += mass**2*max(within, 0.)/count/mon.d
        between_total += mass**2*max(between, 0.)/count/mon.d
    return {'within_history_mse': within_total, 'between_history_mse': between_total,
            'exact_mse': within_total+between_total}
