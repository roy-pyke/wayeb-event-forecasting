import itertools
import numpy as np
import pytest
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact, monte_carlo, stratified, importance


class IID:
    def __init__(self, p=(.1, .2, .3, .15, .25)):
        self.initial = np.zeros(1); self.p = np.array(p); self.rows = 0
    def evaluate(self, hidden, last):
        self.rows += len(last)
        return np.zeros((len(last), 1)), np.broadcast_to(self.p, (len(last), 5)).copy()


@pytest.mark.parametrize('family', ['nested', 'directional', 'multisignal'])
def test_languages_against_enumerated_streams(family):
    m = Monitor(family, (1, 2, 3))
    for q in range(len(m.next)):
        observed = {tuple(m.targets(path, q)) for path in itertools.product(range(5), repeat=3)}
        assert observed == {tuple(v) for v in m.vectors(m.codes((0, q, 0, 0)))}


def test_silence_does_not_repeat_an_endpoint():
    m = Monitor('multisignal', (1, 2, 3))
    q = 0
    for a in [0, 1, 2]: q = int(m.next[q, a])
    assert m.final[q] != 0
    assert not m.targets([4, 4, 4], q).any()


@pytest.mark.parametrize('family', ['nested', 'directional', 'multisignal'])
def test_exact_probability_and_budget(family):
    m = Monitor(family, (1, 2, 3)); source = IID()
    brute = sum(np.prod(source.p[list(path)])*m.targets(path)
                for path in itertools.product(range(5), repeat=3))
    assert np.allclose(exact(source, m), brute)
    for method in [monte_carlo, stratified, importance]:
        value, meta = method(source, m, 0, 128, np.random.default_rng(11))
        assert meta['rows'] <= 128
        assert np.isfinite(value).all()
    # Full frontier should integrate this small path space exactly.
    value, meta = stratified(source, m, 0, 1024, np.random.default_rng(21))
    assert np.allclose(value, brute, atol=1e-13)
    assert meta['variance_bound'] == 0


def test_seeded_estimator_means_and_coherence():
    from patternforecast.polytope import FeasiblePolytope
    m = Monitor('multisignal', (2, 3, 4)); source = IID()
    truth = exact(source, m)
    poly = FeasiblePolytope(m.vectors(m.codes((0, 0, 0, 0))))
    for method in [monte_carlo, stratified, importance]:
        values = []
        for seed in range(200):
            v, _ = method(source, m, 0, 32, np.random.default_rng(seed))
            values.append(v)
            if method != importance: assert poly.contains(v)
        values = np.array(values)
        assert np.all(np.abs(values.mean(0)-truth) <= 5*values.std(0)/np.sqrt(len(values))+1e-12)


def test_closed_reserves():
    from queryforecast.data import load
    for split in ['confirmation', 'reserve', '2017']:
        with pytest.raises(ValueError): load('air', split)


def test_zero_uncertainty_uses_no_model():
    m = Monitor('multisignal', (1, 2))
    for method in [monte_carlo, stratified, importance]:
        value, meta = method(IID(), m, 0, 20, np.random.default_rng(1))
        assert meta['rows'] == 0
        assert np.all(value == 0)
