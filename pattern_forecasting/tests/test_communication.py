import numpy as np
from patternforecast.automata import PatternFamily
from patternforecast.oracle import MaxPlusOracle
from patternforecast.certificates import joint_bound,batch_bounds,cdf_bound,bernoulli_bound
from patternforecast.communication import replay_policy,evaluate

def test_max_plus_oracle_equals_explicit_profile_optimization():
    f=PatternFamily();oracle=MaxPlusOracle(f.next,f.final);rng=np.random.default_rng(31)
    for q in range(len(f.states)):
        for hs in [(1,2,3),(3,6,12),(5,15,30)]:
            p=rng.uniform(size=(3,3));full=rng.uniform(size=(3,3))
            assert abs(oracle.bound(q,hs,p,full)-joint_bound(p,full,f.feasible(q,hs)))<1e-12

def test_batch_certificates_match_scalar_formulas():
    f=PatternFamily();rng=np.random.default_rng(58)
    p=rng.uniform(size=(45,3,3));full=rng.uniform(size=(45,3,3));q=rng.integers(len(f.states),size=45)
    b=batch_bounds(p,full,q,f,(3,6,12))
    for i in range(45):
        assert abs(b['joint'][i]-joint_bound(p[i],full[i],f.feasible(int(q[i]),(3,6,12))))<1e-12
        assert abs(b['cdf'][i]-cdf_bound(p[i],full[i]))<1e-12
        assert abs(b['bernoulli'][i]-bernoulli_bound(p[i],full[i]))<1e-12
    assert (b['joint']<=b['nested']+1e-12).all()
    assert (b['nested']<=b['cdf']+1e-12).all()

def test_policy_refreshes_on_segment_boundary_and_obeys_pointwise_tolerance():
    f=PatternFamily();rng=np.random.default_rng(38);n=70
    predictions=rng.uniform(size=(17,n,3,3));q=np.full(n,f.start)
    bounds={k:[] for k in ['joint','nested','cdf','bernoulli','delta']}
    for lag in range(17):
        b=batch_bounds(predictions[lag],predictions[0],q,f,(3,6,12))
        for k in bounds:bounds[k].append(b[k])
    bounds={k:np.array(v) for k,v in bounds.items()}
    d={'t':np.arange(n)*3600,'segment':np.r_[np.ones(35),np.full(35,2)],
       'residual':np.full((n,3),20),'observed':np.ones((n,3),dtype=bool),'coverage':np.full(n,20)}
    for mode in ['joint','nested','cdf','bernoulli']:
        p,s,c,l=replay_policy(d,predictions,bounds,mode,.01)
        assert s[0] and s[35]
        assert (c<=.01+1e-12).all()
        assert evaluate(d,p,predictions[0],s,c,[3,6,12],.01)['bound_violations']==0
