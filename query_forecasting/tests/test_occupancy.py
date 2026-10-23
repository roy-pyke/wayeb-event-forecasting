import sys
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from test_query import IID
sys.path.insert(0,str(PACKAGE/'compositional'))
sys.path.insert(0,str(PACKAGE/'occupancy'))
from monitor import JointMonitor
from propagate import basis_propagate
from features import OccupancyFeatures
from recombine import recombine


def test_local_basis_refresh_conserves_mass_moments_and_expectation():
    rng=np.random.default_rng(102);w=np.full(180,1/180);f=rng.normal(size=(180,9))
    f=np.c_[f,f[:,2],np.ones(len(w))]
    values=[]
    for seed in range(240):
        v,meta=recombine(w,f,40,np.random.default_rng(seed))
        assert np.count_nonzero(v)<=40 and np.all(v>=0)
        np.testing.assert_allclose(v@f,w@f,atol=2e-9)
        values.append(v)
    values=np.array(values)
    assert np.all(np.abs(values.mean(0)-w)<5*values.std(0)/np.sqrt(len(values))+1e-12)


class TimeVaryingMarkov(IID):
    def __init__(self, order):
        super().__init__();self.order=order
        self.kernel=np.random.default_rng(62).dirichlet(np.ones(5),size=(8,6))
    def evaluate(self, hidden, last):
        self.rows+=len(last)
        depth=np.asarray(hidden).ravel().astype(int)
        previous=np.asarray(last) if self.order else np.zeros(len(last),int)
        return (depth+1)[:,None],self.kernel[depth,previous]


def test_transition_closed_occupancies_exact_for_whole_markov_class():
    mon=JointMonitor([Monitor(f,(2,3,5)) for f in ['nested','directional','multisignal']])
    for order,policy in [(0,'occupancy'),(1,'occupancy_symbol')]:
        source=TimeVaryingMarkov(order);truth=exact(source,mon)
        for seed in range(5):
            value,meta=basis_propagate(source,mon,0,512,np.random.default_rng(seed),policy,True)
            assert meta['max_rank']>0 and meta['rows']<=512
            np.testing.assert_allclose(value,truth,atol=2e-10)
            weights,paths=zip(*meta['witnesses'])
            assert min(weights)>=0
            np.testing.assert_allclose(np.array(weights)@np.array([mon.targets(p) for p in paths]),value,atol=1e-12)


def test_overlapping_features_are_not_product_state_bins():
    mon=JointMonitor([Monitor(f,(2,3,5)) for f in ['nested','directional','multisignal']])
    f=OccupancyFeatures(mon,1)
    assert f.dimension==sum(f.sizes)+mon.d
    assert sum(f.sizes)<np.prod(f.sizes)


def test_full_history_uniform_and_bits_remain_unbiased_for_nonmarkov_source():
    class HistorySource(IID):
        def evaluate(self,hidden,last):
            self.rows+=len(last)
            h=(np.asarray(hidden).ravel()*3+np.asarray(last)+1)%11
            p=np.exp(np.sin(h[:,None]+np.arange(5)[None,:]))
            return h[:,None],p/p.sum(1,keepdims=True)
    mon=JointMonitor([Monitor('multisignal',(1,3,4))]);source=HistorySource()
    truth=exact(source,mon)
    for policy in ['uniform','known_bits','occupancy','occupancy_symbol']:
        values=[]
        for seed in range(160):
            v,meta=basis_propagate(source,mon,0,160,np.random.default_rng(seed),policy)
            values.append(v);assert meta['rows']<=160
        values=np.array(values)
        assert np.all(np.abs(values.mean(0)-truth)<5*values.std(0)/np.sqrt(len(values))+1e-10)
