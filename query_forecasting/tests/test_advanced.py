import sys
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from test_query import IID
sys.path.insert(0,str(PACKAGE/'experiments'))
from advanced import sampling,clustered


def test_low_discrepancy_estimators_are_coherent_and_unbiased_empirically():
 from patternforecast.polytope import FeasiblePolytope
 mon=Monitor('multisignal',(2,3,4));source=IID();truth=exact(source,mon)
 poly=FeasiblePolytope(mon.vectors(mon.codes((0,0,0,0))))
 for policy in ['arithmetic','arithmetic_permuted','sobol','lhs']:
  values=[]
  for seed in range(250):
   v,meta=sampling(source,mon,0,64,np.random.default_rng(seed),policy)
   assert meta['rows']<=64 and poly.contains(v)[0];values.append(v)
  values=np.array(values)
  assert np.all(np.abs(values.mean(0)-truth)<5*values.std(0)/np.sqrt(len(values))+1e-12)


def test_pooling_with_a_history_dependent_source():
 class HistorySource(IID):
  def evaluate(self,hidden,last):
   self.rows+=len(last)
   h=(np.asarray(hidden).ravel()+np.asarray(last)+1)%7
   p=np.stack([.2+.1*np.sin(h),.25+.1*np.cos(h),.15+.05*np.sin(2*h),.15+.05*np.cos(2*h),np.full(len(h),.25)],1)
   p/=p.sum(1,keepdims=True)
   return h[:,None],p
 from pooling import pooled
 mon=Monitor('multisignal',(2,3,4));source=HistorySource();truth=exact(source,mon)
 for method in [clustered,pooled]:
  values=np.array([method(source,mon,0,48,np.random.default_rng(seed))[0] for seed in range(250)])
  assert np.all(np.abs(values.mean(0)-truth)<5*values.std(0)/np.sqrt(len(values))+1e-12)
