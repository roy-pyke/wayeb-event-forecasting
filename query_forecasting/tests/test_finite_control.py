import sys
import itertools
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from test_occupancy import TimeVaryingMarkov
from test_query import IID
for folder in ['compositional','occupancy','engineering','finite_control']:
    sys.path.insert(0,str(PACKAGE/folder))
from monitor import JointMonitor
from features import family_components
from finite_features import finite_classes
from finite_method import finite_estimate


def test_finite_classes_preserve_suffix_functions_and_all_earlier_deadlines():
    _,tables,alphabet=family_components(Monitor('directional',(1,2,3)))
    for table in tables:
        levels=finite_classes(table,alphabet,3)
        for remaining in [1,2,3]:
            mapping,_=levels[remaining];by_class={}
            for q,cell in mapping.items():
                behavior=[]
                for path in itertools.product(range(5),repeat=remaining):
                    current=q;hit=False;outputs=[]
                    for a in path:
                        if a<4:
                            current=table['transitions'][str(current)][alphabet[a]]
                            hit=hit or current in table['finals']
                        outputs.append(hit)
                    behavior.extend(outputs)
                if cell==0:assert not any(behavior)
                if cell in by_class:assert behavior==by_class[cell]
                else:by_class[cell]=behavior


def test_finite_closure_exact_markov_and_positive_path_measure():
    mon=JointMonitor([Monitor(f,(1,3,5)) for f in ['nested','directional','multisignal']])
    source=TimeVaryingMarkov(1);truth=exact(source,mon)
    for seed in range(8):
        value,meta=finite_estimate(source,mon,0,300,np.random.default_rng(seed),True)
        np.testing.assert_allclose(value,truth,atol=2e-10)
        assert meta['max_rank']>0 and meta['rows']<=300
        weights,paths=zip(*meta['witnesses'])
        np.testing.assert_allclose(np.array(weights)@np.array([mon.targets(p) for p in paths]),value,atol=1e-12)


def test_finite_closure_unbiased_nonmarkov_history():
    class HistorySource(IID):
        def evaluate(self,hidden,last):
            self.rows+=len(last);h=(np.asarray(hidden).ravel()*3+np.asarray(last)+1)%11
            p=np.exp(np.sin(h[:,None]+np.arange(5)[None,:]))
            return h[:,None],p/p.sum(1,keepdims=True)
    mon=JointMonitor([Monitor('multisignal',(1,3,4))]);source=HistorySource();truth=exact(source,mon)
    values=[]
    for seed in range(180):
        v,_=finite_estimate(source,mon,0,100,np.random.default_rng(seed));values.append(v)
    values=np.array(values)
    assert np.all(np.abs(values.mean(0)-truth)<5*values.std(0)/np.sqrt(len(values))+1e-10)
