import itertools
import sys
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from test_query import IID
sys.path.insert(0,str(PACKAGE/'compositional'))
from monitor import JointMonitor,HarmonicPotential
from compress import compress
from propagation import propagate,sample


def test_compositional_targets_and_surrogate_dp():
    parts = [Monitor(f,(1,2,3)) for f in ['nested','directional','multisignal']]
    joint = JointMonitor(parts); p = IID().p
    q = joint.encode([1,2,0]); value = np.zeros(joint.d)
    for path in itertools.product(range(5),repeat=3):
        y = joint.targets(path,q)
        expected = np.concatenate([m.targets(path,s).reshape(3,3) for m,s in zip(parts,[1,2,0])],axis=1).ravel()
        np.testing.assert_array_equal(y,expected)
        value += np.prod(p[list(path)])*y
    phi = HarmonicPotential(joint,p)
    np.testing.assert_allclose(phi([(0,q,0,0)])[0],value,atol=1e-13)
    for a in range(5):
        state = joint.advance(0,q,0,0,a)
        children = [joint.advance(*state,b) for b in range(5)]
        np.testing.assert_allclose(phi([state])[0],p@phi(children),atol=1e-13)


def test_compression_preserves_moments_and_original_weights_in_expectation():
    rng = np.random.default_rng(51)
    w = rng.random(50); w /= w.sum()
    features = rng.normal(size=(50,4))
    samples = []
    for seed in range(500):
        v,meta = compress(w,features,12,np.random.default_rng(seed))
        assert np.count_nonzero(v)<=12 and np.all(v>=0)
        np.testing.assert_allclose(v.sum(),w.sum(),atol=1e-10)
        np.testing.assert_allclose(v@features,w@features,atol=1e-10)
        samples.append(v)
    samples = np.array(samples)
    assert np.all(np.abs(samples.mean(0)-w) < 5*samples.std(0)/np.sqrt(len(samples))+1e-12)


def test_redundant_moment_rows_are_safe():
    w = np.ones(20)/20
    x = np.arange(20)[:,None].astype(float)
    f = np.c_[x,x,x*2,np.ones(20)]
    v,_ = compress(w,f,3,np.random.default_rng(0))
    np.testing.assert_allclose(v@f,w@f,atol=1e-10)


def test_positive_propagation_is_exact_for_surrogate_and_has_path_certificate():
    parts = [Monitor(f,(2,3,5)) for f in ['nested','directional','multisignal']]
    mon = JointMonitor(parts); source = IID(); phi = HarmonicPotential(mon,source.p)
    truth = phi([(0,0,0,0)])[0]
    for seed in range(12):
        value,meta = propagate(source,mon,0,160,np.random.default_rng(seed),certificate=True)
        np.testing.assert_allclose(value,truth,atol=3e-10)
        weights,paths = zip(*meta['witnesses'])
        np.testing.assert_allclose(np.array(weights) @ np.array([mon.targets(p) for p in paths]),value,atol=1e-12)
        assert min(weights) >= 0 and meta['rows'] <= 160


def test_neural_history_is_not_collapsed_and_all_estimators_are_unbiased():
    class NonMarkovSource(IID):
        def evaluate(self,hidden,last):
            self.rows += len(last)
            h = (np.asarray(hidden).ravel()+np.asarray(last)+1)%7
            p = np.stack([.2+.1*np.sin(h),.25+.1*np.cos(h),.15+.05*np.sin(2*h),.15+.05*np.cos(2*h),np.full(len(h),.25)],1)
            p /= p.sum(1,keepdims=True)
            return h[:,None],p
    mon = JointMonitor([Monitor('multisignal',(2,3,4))]); source = NonMarkovSource()
    truth = exact(source,mon)
    for policy in ['harmonic','mass','monitor_we','mc','potential','potential_lhs']:
        method = propagate if policy in ['harmonic','mass','monitor_we'] else sample
        values = []
        for seed in range(150):
            v,meta = method(source,mon,0,64,np.random.default_rng(seed),policy)
            assert meta['rows']<=64; values.append(v)
        values = np.array(values)
        assert np.all(np.abs(values.mean(0)-truth) < 5*values.std(0)/np.sqrt(len(values))+1e-10)
