import sys
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from test_query import IID
from test_occupancy import TimeVaryingMarkov
for folder in ['compositional','occupancy','markov_control']:sys.path.insert(0,str(PACKAGE/folder))
from monitor import JointMonitor
from potential import proxy,MarkovPotential
from methods import markov_estimate
from propagation import Particle


def test_proxy_matches_arbitrary_time_varying_first_order_kernel():
    mon=JointMonitor([Monitor(f,(1,3,5)) for f in ['nested','directional','multisignal']])
    source=TimeVaryingMarkov(1);truth=exact(source,mon)
    for policy in ['balanced','cv','lhs']:
        for seed in range(4):
            value,meta=markov_estimate(source,mon,0,200,np.random.default_rng(seed),policy)
            np.testing.assert_allclose(value,truth,atol=3e-10)
            assert meta['proxy_rows']==21 and meta['rows']<=200


def test_markov_controls_are_unbiased_with_nonmarkov_hidden_history():
    class HistorySource(IID):
        def evaluate(self,hidden,last):
            self.rows+=len(last)
            h=(np.asarray(hidden).ravel()*3+np.asarray(last)+1)%11
            p=np.exp(np.sin(h[:,None]+np.arange(5)[None,:]))
            return h[:,None],p/p.sum(1,keepdims=True)
    mon=JointMonitor([Monitor('multisignal',(1,3,4))]);source=HistorySource();truth=exact(source,mon)
    for policy in ['balanced','cv','lhs']:
        values=[]
        for seed in range(200):
            v,meta=markov_estimate(source,mon,0,160,np.random.default_rng(seed),policy,True)
            values.append(v);assert meta['rows']<=160
            if policy=='balanced':
                weights,paths=zip(*meta['witnesses'])
                np.testing.assert_allclose(np.array(weights)@np.array([mon.targets(p) for p in paths]),v,atol=1e-12)
        values=np.array(values)
        assert np.all(np.abs(values.mean(0)-truth)<5*values.std(0)/np.sqrt(len(values))+1e-10)
