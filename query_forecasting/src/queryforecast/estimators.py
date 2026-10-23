"""Coherent prefix strata and same-source inference baselines.

All adaptation precedes the independent Monte Carlo tails. A stochastic
compute-based stopping rule for the number of samples would bias an average;
we instead allocate with deterministic worst-case suffix costs.
"""
from dataclasses import dataclass
import math
import numpy as np


@dataclass
class Node:
    mass: float
    state: tuple
    hidden: np.ndarray
    last: int


def children(mon, node, h, p):
    return [Node(node.mass*p[a], mon.advance(*node.state, a), h, a) for a in range(5)]


def root(source, q):
    return Node(1., (0, int(q), 0, 0), source.initial, 5)


def exact(source, mon, q=0):
    frontier = [root(source, q)]
    answer = np.zeros(mon.d)
    while frontier:
        active = []
        for node in frontier:
            y = mon.fixed(node.state)
            if y is None: active.append(node)
            else: answer += node.mass*y
        frontier = []
        for begin in range(0, len(active), 4096):
            batch = active[begin:begin+4096]
            h, p = source.evaluate([n.hidden for n in batch], [n.last for n in batch])
            for i, node in enumerate(batch): frontier.extend(children(mon, node, h[i], p[i]))
    return answer


def tails(source, mon, nodes, rng):
    """Independent conditional paths; final decidable step is marginalized."""
    result = np.zeros((len(nodes), mon.d))
    pending = list(enumerate(nodes))
    while pending:
        active = []
        for i, node in pending:
            y = mon.fixed(node.state)
            if y is None: active.append((i, node))
            else: result[i] = y
        if not active: break
        hidden, prob = source.evaluate([n.hidden for _, n in active], [n.last for _, n in active])
        pending = []
        draws = rng.random(len(active))
        for j, (i, node) in enumerate(active):
            branch = children(mon, node, hidden[j], prob[j])
            fixed = [mon.fixed(n.state) for n in branch]
            if all(v is not None for v in fixed):
                result[i] = prob[j] @ np.array(fixed)
            else:
                a = min(int(np.searchsorted(np.cumsum(prob[j]), draws[j])), 4)
                pending.append((i, branch[a]))
    return result


def monte_carlo(source, mon, q, budget, rng):
    source.rows = 0
    node = root(source, q)
    fixed = mon.fixed(node.state)
    if fixed is not None: return fixed, {'rows': 0, 'samples': 0}
    n = budget//mon.H
    answer = tails(source, mon, [node]*n, rng).mean(0)
    return answer, {'rows': source.rows, 'samples': n}


def stratified(source, mon, q, budget, rng, semantic=True):
    source.rows = 0
    frontier = [root(source, q)]
    settled = np.zeros(mon.d)
    settled_mass = 0.
    expansions = 0
    while frontier and expansions < budget//4:
        next_frontier = []
        for n in frontier:
            fixed = mon.fixed(n.state)
            if fixed is None: next_frontier.append(n)
            else:
                settled += n.mass*fixed; settled_mass += n.mass
        frontier = next_frontier
        if not frontier: break
        base_cost = sum(mon.H-n.state[0] for n in frontier)
        # Geometry and mass policies share both constant folding and allocation.
        order = sorted(range(len(frontier)), key=lambda i:
            frontier[i].mass*(math.sqrt(mon.uncertainty(*frontier[i].state[:3]))
                              if semantic else 1.), reverse=True)
        chosen = None
        for i in order:
            n = frontier[i]
            costs = sum(mon.H-st[0] for a in range(5)
                        if mon.fixed(st := mon.advance(*n.state, a)) is None)
            if source.rows+1+base_cost-(mon.H-n.state[0])+costs <= budget:
                chosen = i; break
        if chosen is None: break
        node = frontier.pop(chosen)
        h, p = source.evaluate([node.hidden], [node.last])
        frontier.extend(children(mon, node, h[0], p[0]))
        expansions += 1
    active = []
    for node in frontier:
        fixed = mon.fixed(node.state)
        if fixed is None: active.append(node)
        else:
            settled += node.mass*fixed; settled_mass += node.mass
    masses = np.array([n.mass for n in active])
    if not np.isclose(masses.sum()+settled_mass, 1., atol=1e-12):
        raise AssertionError('prefix partition lost probability mass')
    if not active:
        return settled, {'rows': source.rows, 'expansions': expansions,
                         'strata': 0, 'variance_bound': 0., 'mass': settled_mass}
    costs = np.array([mon.H-n.state[0] for n in active])
    caps = np.array([mon.uncertainty(*n.state[:3]) for n in active])
    counts = np.ones(len(active), dtype=int)
    left = int(budget-source.rows-costs.sum())
    if left < 0: raise AssertionError('frontier violates reserve for tails')
    while np.any(costs <= left):
        gain = masses**2*caps/(counts*(counts+1)*costs)
        gain[costs > left] = -1
        i = int(np.argmax(gain)); counts[i] += 1; left -= int(costs[i])
    batch = [n for n, count in zip(active, counts) for _ in range(count)]
    sampled = tails(source, mon, batch, rng)
    offset = 0
    for node, count in zip(active, counts):
        settled += node.mass*sampled[offset:offset+count].mean(0)
        offset += count
    if source.rows > budget: raise AssertionError('model-row budget exceeded')
    return settled, {'rows': source.rows, 'expansions': expansions,
                     'strata': len(active), 'samples': int(counts.sum()),
                     'variance_bound': float(np.sum(masses**2*caps/counts)),
                     'mass': float(masses.sum()+settled_mass)}


def importance(source, mon, q, budget, rng):
    """Multiple-importance mixture of prefix-viable positive-query proposals.

    Extension of restricted-path sampling to the compiled monitor, not a claim
    of reproducing Boyd's exact code. The balance-mixture likelihood accounts
    for overlapping queries; sampling a selected component is not equivalent
    to pretending that component was the only proposal.
    """
    source.rows = 0
    initial = root(source, q)
    fixed = mon.fixed(initial.state)
    if fixed is not None: return fixed, {'rows': 0, 'samples': 0}
    codes = mon.codes(initial.state)
    union = int(np.bitwise_or.reduce(codes))
    targets = np.array([j for j in range(mon.d) if (union >> j) & 1])
    if not len(targets): return np.zeros(mon.d), {'rows': 0, 'samples': 0}
    n = budget//mon.H
    selected = rng.integers(len(targets), size=n)
    ratios = np.ones((n, len(targets)))  # q_component(prefix) / p(prefix)
    result = np.zeros((n, mon.d))
    pending = [(i, initial) for i in range(n)]
    while pending:
        active = []
        for i, node in pending:
            y = mon.fixed(node.state)
            if y is None: active.append((i, node))
            else: result[i] = y/ratios[i].mean()
        if not active: break
        hidden, prob = source.evaluate([v.hidden for _, v in active], [v.last for _, v in active])
        pending = []
        draws = rng.random(len(active))
        for j, (i, node) in enumerate(active):
            branch = children(mon, node, hidden[j], prob[j])
            unions = np.array([np.bitwise_or.reduce(mon.codes(v.state)) for v in branch])
            allowed = ((unions[:, None] >> targets) & 1).astype(float)
            normalizers = prob[j] @ allowed
            factors = np.divide(allowed, normalizers[None, :],
                                out=np.zeros_like(allowed), where=normalizers[None, :] > 0)
            branch_ratios = factors * ratios[i]
            proposal = prob[j] * factors[:, selected[i]]
            if not np.isclose(proposal.sum(), 1.): raise AssertionError('invalid proposal')
            fixed = [mon.fixed(v.state) for v in branch]
            if all(v is not None for v in fixed):
                denominator = branch_ratios.mean(1)
                weight = np.divide(proposal, denominator, out=np.zeros(5), where=denominator > 0)
                result[i] = weight @ np.array(fixed)
            else:
                a = min(int(np.searchsorted(np.cumsum(proposal), draws[j])), 4)
                ratios[i] = branch_ratios[a]
                pending.append((i, branch[a]))
    return result.mean(0), {'rows': source.rows, 'samples': n}
