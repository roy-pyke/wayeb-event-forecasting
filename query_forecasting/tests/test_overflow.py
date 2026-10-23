import sys
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from test_query import IID
sys.path.insert(0,str(PACKAGE/'compositional'))
sys.path.insert(0,str(PACKAGE/'overflow'))
from monitor import JointMonitor,HarmonicPotential
from propagation import propagate
from guarded import guarded


def test_identity_without_overflow_and_iid_exactness_with_overflow():
    mon=JointMonitor([Monitor(f,(2,4,6)) for f in ['nested','directional','multisignal']])
    source=IID();truth=HarmonicPotential(mon,source.p)([(0,0,0,0)])[0]
    overflow_cases=identity_cases=0
    for budget in [192,512,2048]:
        for seed in range(8):
            v,meta=guarded(source,mon,0,budget,np.random.default_rng(seed),certificate=True)
            assert meta['rows']<=budget
            np.testing.assert_allclose(v,truth,atol=3e-9)
            weights,paths=zip(*meta['witnesses'])
            np.testing.assert_allclose(np.array(weights)@np.array([mon.targets(p) for p in paths]),v,atol=1e-12)
            if meta['overflows']:
                overflow_cases+=1
            else:
                previous,_=propagate(source,mon,0,budget,np.random.default_rng(seed),'monitor_we')
                np.testing.assert_array_equal(v,previous);identity_cases+=1
    assert overflow_cases and identity_cases


def test_guarded_sampling_is_unbiased_for_nonmarkov_source():
    class History(IID):
        def evaluate(self,hidden,last):
            self.rows+=len(last)
            h=(np.asarray(hidden).ravel()+np.asarray(last)+1)%7
            p=np.stack([.2+.1*np.sin(h),.25+.1*np.cos(h),.15+.05*np.sin(2*h),.15+.05*np.cos(2*h),np.full(len(h),.25)],1)
            p/=p.sum(1,keepdims=True)
            return h[:,None],p
    mon=JointMonitor([Monitor('multisignal',(2,3,4))]);source=History();truth=exact(source,mon)
    for policy in ['harmonic','uniform','known_bits','mass']:
        values=[]
        for seed in range(150):
            v,meta=guarded(source,mon,0,48,np.random.default_rng(seed),policy)
            assert meta['rows']<=48;values.append(v)
        values=np.array(values)
        assert np.all(np.abs(values.mean(0)-truth)<5*values.std(0)/np.sqrt(len(values))+1e-10)
