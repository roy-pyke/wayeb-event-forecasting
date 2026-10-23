import sys
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from test_occupancy import TimeVaryingMarkov
for folder in ['compositional','particle_controls']:sys.path.insert(0,str(PACKAGE/folder))
from monitor import JointMonitor
from resample import resample
from method import particle_estimate


def test_discrete_weights_and_conditional_expectations():
    w=np.r_[.3,.2,np.full(50,.01)];features=np.arange(len(w))[:,None]
    for policy in ['systematic','stratified','discrete','discrete_ordered']:
        values=[]
        for seed in range(800):
            v=resample(w,12,np.random.default_rng(seed),policy,features if policy.endswith('ordered') else None)
            np.testing.assert_allclose(v.sum(),1.,atol=1e-12)
            if policy.startswith('discrete'):np.testing.assert_array_equal(v[:2],w[:2])
            values.append(v)
        values=np.array(values)
        assert np.all(np.abs(values.mean(0)-w)<5*values.std(0)/np.sqrt(len(values))+1e-11)


def test_complete_particle_queries_unbiased_and_path_coherent():
    mon=JointMonitor([Monitor('multisignal',(1,3,4))]);source=TimeVaryingMarkov(1)
    truth=exact(source,mon)
    for policy in ['systematic','stratified','discrete','discrete_ordered']:
        values=[]
        for seed in range(160):
            v,meta=particle_estimate(source,mon,0,90,np.random.default_rng(seed),policy,True)
            assert meta['rows']<=90
            weights,paths=zip(*meta['witnesses'])
            np.testing.assert_allclose(np.array(weights)@np.array([mon.targets(p) for p in paths]),v,atol=1e-12)
            values.append(v)
        values=np.array(values)
        assert np.all(np.abs(values.mean(0)-truth)<5*values.std(0)/np.sqrt(len(values))+1e-10)
