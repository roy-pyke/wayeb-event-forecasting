"""An exact mixture of neural histories; no predictive-state merging."""
from collections import defaultdict
import numpy as np
from queryforecast.estimators import root, children, tails


def build_frontier(source, mon, q, budget):
    source.rows = 0
    frontier = [root(source, q)]
    settled = np.zeros(mon.d)
    settled_mass = 0.
    expansions = 0
    while frontier and expansions < budget//4:
        active = []
        for node in frontier:
            fixed = mon.fixed(node.state)
            if fixed is None: active.append(node)
            else:
                settled += node.mass*fixed; settled_mass += node.mass
        frontier = active
        if not frontier: break
        i = max(range(len(frontier)), key=lambda i: frontier[i].mass)
        node = frontier.pop(i)
        hidden, prob = source.evaluate([node.hidden], [node.last])
        frontier.extend(children(mon, node, hidden[0], prob[0]))
        expansions += 1
    active = []
    for node in frontier:
        fixed = mon.fixed(node.state)
        if fixed is None: active.append(node)
        else:
            settled += node.mass*fixed; settled_mass += node.mass
    if not np.isclose(settled_mass+sum(n.mass for n in active), 1., atol=1e-12):
        raise AssertionError('lost mass')
    return active, settled, expansions


def partition(mon, frontier, policy):
    groups = defaultdict(list)
    signatures = {mon.codes(n.state) for n in frontier}
    if policy == 'mass_buckets':
        order = sorted(frontier, key=lambda n: n.mass, reverse=True)
        for ix in np.array_split(np.arange(len(order)), max(len(signatures), 1)):
            if len(ix): groups[int(ix[0])] = [order[i] for i in ix]
    else:
        for n in frontier:
            if policy == 'single': key = 0
            elif policy == 'depth': key = n.state[0]
            elif policy == 'symbol': key = n.last
            elif policy == 'semantic': key = mon.codes(n.state)
            else: raise ValueError(policy)
            groups[key].append(n)
    return list(groups.values())


def group_stats(mon, groups):
    masses, costs, caps = [], [], []
    for group in groups:
        masses.append(sum(n.mass for n in group))
        costs.append(max(mon.H-n.state[0] for n in group))
        codes = set()
        for n in group: codes.update(mon.codes(n.state))
        lower, upper = next(iter(codes)), next(iter(codes))
        for c in codes: lower &= c; upper |= c
        caps.append((lower ^ upper).bit_count()/4.)
    return np.array(masses), np.array(costs), np.array(caps)


def pooled(source, mon, q, budget, rng, policy='semantic'):
    frontier, answer, expanded = build_frontier(source, mon, q, budget)
    if not frontier:
        return answer, {'rows': source.rows, 'frontier': 0, 'groups': 0, 'expansions': expanded}
    groups = partition(mon, frontier, policy)
    masses, costs, caps = group_stats(mon, groups)
    # All policies use this same conservative coarsening if their group count
    # cannot fit a hard model-row budget. It retains the exact source mixture.
    while costs.sum()+source.rows > budget:
        order = np.argsort(masses)
        a, b = int(order[0]), int(order[1])
        merged = groups[a]+groups[b]
        groups = [g for i, g in enumerate(groups) if i not in (a, b)]+[merged]
        masses, costs, caps = group_stats(mon, groups)
    counts = np.ones(len(groups), dtype=int)
    left = int(budget-source.rows-costs.sum())
    while np.any(costs <= left):
        gain = masses**2*caps/(counts*(counts+1)*costs)
        gain[costs > left] = -1
        i = int(np.argmax(gain)); counts[i] += 1; left -= int(costs[i])
    selected = []
    for group, mass, count in zip(groups, masses, counts):
        weights = np.array([n.mass for n in group])/mass
        ids = rng.choice(len(group), size=count, p=weights)
        selected.extend(group[i] for i in ids)
    values = tails(source, mon, selected, rng)
    offset = 0
    for mass, count in zip(masses, counts):
        answer += mass*values[offset:offset+count].mean(0)
        offset += count
    if source.rows > budget: raise AssertionError('budget exceeded')
    return answer, {'rows': source.rows, 'frontier': len(frontier), 'groups': len(groups),
        'samples': int(counts.sum()), 'expansions': expanded,
        'variance_bound': float(np.sum(masses**2*caps/counts))}
