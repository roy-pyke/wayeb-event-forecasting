"""Search plus restricted multiple-importance sampling; same frontier as Q2.

This is a monitor adapter of the search/residual-IS principle in Boyd et al.
(NeurIPS 2022), not their original tail-splitting beam-search implementation.
"""
import numpy as np
from queryforecast.estimators import children
from pooling import build_frontier


def hybrid(source, mon, q, budget, rng):
    frontier, answer, expanded = build_frontier(source, mon, q, budget)
    if not frontier:
        return answer, {'rows': source.rows, 'expansions': expanded, 'samples': 0}
    unions = np.array([np.bitwise_or.reduce(mon.codes(n.state)) for n in frontier])
    union = int(np.bitwise_or.reduce(unions))
    targets = np.array([j for j in range(mon.d) if (union >> j) & 1])
    masses = np.array([n.mass for n in frontier])
    allowed = ((unions[:, None] >> targets) & 1).astype(float)
    normalizers = masses @ allowed
    factors = allowed / normalizers[None, :]
    worst_cost = max(mon.H-n.state[0] for n in frontier)
    n = (budget-source.rows)//worst_cost
    if n < 1:
        raise AssertionError('no budget for residual sampling')
    selected = rng.integers(len(targets), size=n)
    pending, ratios = [], np.empty((n, len(targets)))
    for i, component in enumerate(selected):
        idx = rng.choice(len(frontier), p=masses*factors[:, component])
        pending.append((i, frontier[idx]))
        # Absolute q/p, including the prefix-mixture selection probability.
        ratios[i] = factors[idx]
    result = np.zeros((n, mon.d))
    while pending:
        active = []
        for i, node in pending:
            fixed = mon.fixed(node.state)
            if fixed is None:
                active.append((i, node))
            else:
                result[i] = fixed/ratios[i].mean()
        if not active:
            break
        hidden, prob = source.evaluate([v.hidden for _, v in active], [v.last for _, v in active])
        pending = []
        draws = rng.random(len(active))
        for j, (i, node) in enumerate(active):
            branch = children(mon, node, hidden[j], prob[j])
            unions = np.array([np.bitwise_or.reduce(mon.codes(v.state)) for v in branch])
            allowed = ((unions[:, None] >> targets) & 1).astype(float)
            z = prob[j] @ allowed
            factors = np.divide(allowed, z[None, :], out=np.zeros_like(allowed), where=z[None, :] > 0)
            branch_ratios = factors*ratios[i]
            proposal = prob[j]*factors[:, selected[i]]
            if not np.isclose(proposal.sum(), 1.):
                raise AssertionError('invalid component distribution')
            fixed = [mon.fixed(v.state) for v in branch]
            if all(v is not None for v in fixed):
                denominator = branch_ratios.mean(1)
                w = np.divide(proposal, denominator, out=np.zeros(5), where=denominator > 0)
                result[i] = w @ np.array(fixed)
            else:
                a = min(int(np.searchsorted(np.cumsum(proposal), draws[j])), 4)
                ratios[i] = branch_ratios[a]
                pending.append((i, branch[a]))
    if source.rows > budget:
        raise AssertionError('budget exceeded')
    return answer+result.mean(0), {'rows': source.rows, 'expansions': expanded, 'samples': n}
