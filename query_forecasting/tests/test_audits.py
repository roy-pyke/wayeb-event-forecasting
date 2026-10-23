import sys
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact, root
from test_query import IID
sys.path.insert(0, str(PACKAGE/'experiments'))
sys.path.insert(0, str(PACKAGE/'audits'))
from hybrid import hybrid
from moments import conditional_moments, allocation, decomposition
from pooling import pooled, build_frontier, partition


def test_hybrid_balances_prefix_and_overlapping_query_proposals():
    mon = Monitor('multisignal', (2, 3, 4)); source = IID()
    truth = exact(source, mon)
    values = []
    for seed in range(500):
        v, meta = hybrid(source, mon, 0, 48, np.random.default_rng(seed))
        assert meta['rows'] <= 48
        values.append(v)
    values = np.array(values)
    assert np.all(np.abs(values.mean(0)-truth) < 5*values.std(0)/np.sqrt(len(values))+1e-12)


def test_exact_continuation_moments_and_pooled_variance():
    mon = Monitor('multisignal', (2, 3, 4)); source = IID()
    truth = exact(source, mon)
    means, _ = conditional_moments(source, mon, [root(source, 0)])
    np.testing.assert_allclose(means[0], truth, atol=1e-12)
    frontier, settled, expanded = build_frontier(source, mon, 0, 48)
    means, seconds = conditional_moments(source, mon, frontier)
    np.testing.assert_allclose(settled+np.array([n.mass for n in frontier])@means, truth, atol=1e-12)
    groups, masses, counts, costs, caps = allocation(mon, partition(mon, frontier, 'semantic'), expanded, 48)
    terms = decomposition(mon, frontier, groups, masses, counts, means, seconds)
    values = np.array([pooled(source, mon, 0, 48, np.random.default_rng(seed))[0] for seed in range(1000)])
    losses = np.mean((values-truth)**2, axis=1)
    assert abs(losses.mean()-terms['exact_mse']) < 5*losses.std()/np.sqrt(len(losses))
    _, meta = pooled(source, mon, 0, 48, np.random.default_rng(0))
    assert meta['groups'] == len(groups) and meta['samples'] == counts.sum()
    assert abs(meta['variance_bound']-np.sum(masses**2*caps/counts)) < 1e-12
