from pathlib import Path
import sys
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from test_query import IID
sys.path.insert(0, str(PACKAGE/'experiments'))
from pooling import pooled, partition


def test_pooling_conserves_source_distribution_and_coherence():
    from patternforecast.polytope import FeasiblePolytope
    mon = Monitor('multisignal', (2, 4, 6)); source = IID()
    truth = exact(source, mon)
    poly = FeasiblePolytope(mon.vectors(mon.codes((0, 0, 0, 0))))
    for policy in ['single', 'depth', 'symbol', 'mass_buckets', 'semantic']:
        values = []
        for seed in range(200):
            v, meta = pooled(source, mon, 0, 32, np.random.default_rng(seed), policy)
            assert meta['rows']<=32
            assert poly.contains(v)[0]
            values.append(v)
        values = np.array(values)
        assert np.all(np.abs(values.mean(0)-truth) <= 5*values.std(0)/np.sqrt(200)+1e-12)


def test_distinct_source_histories_are_retained_in_pool():
    from queryforecast.estimators import Node
    mon = Monitor('multisignal', (2, 4, 6))
    a = Node(.2, (0,0,0,0), np.array([1.]), 0)
    b = Node(.8, (0,0,0,0), np.array([9.]), 3)
    group = partition(mon, [a,b], 'semantic')[0]
    assert group[0] is a and group[1] is b
    assert group[0].hidden[0] != group[1].hidden[0]
