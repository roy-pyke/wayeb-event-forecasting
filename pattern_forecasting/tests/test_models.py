import numpy as np
from sklearn.isotonic import isotonic_regression
from patternforecast.models import coherent,isotonic_axis,Features
from patternforecast.data import context_indices

def test_coherence_projection_is_feasible_and_nonexpansive_to_feasible_labels():
    rng=np.random.default_rng(73);x=rng.uniform(size=(200,3,3));p=coherent(x)
    from patternforecast.automata import PatternFamily
    for child,parent in PatternFamily().inclusion_pairs(): assert (p[:,child]<=p[:,parent]+1e-8).all()
    assert (np.diff(p,axis=2)>=-1e-8).all()
    from patternforecast.automata import PatternFamily
    y=PatternFamily().feasible(0,(3,6,12)).reshape(-1,3,3)
    for yy in y:
        assert (np.sum((p-yy)**2,(1,2))<=np.sum((x-yy)**2,(1,2))+1e-7).all()
    assert np.allclose(coherent(p),p,atol=1e-8)

def test_isotonic_primitive_matches_sklearn():
    x=np.random.default_rng(1).normal(size=(100,3,3))
    p=isotonic_axis(x,2)
    for i in range(100):
        for j in range(3): assert np.allclose(p[i,j],isotonic_regression(x[i,j]))

def test_cached_context_cannot_cross_segment_or_move_to_future():
    data={'t':np.arange(6),'segment':np.array([1,1,1,2,2,2])}
    ix,valid=context_indices(data,np.array([0,1,2,1,2,1]))
    assert np.array_equal(valid,[True,True,True,False,False,True])
    assert (ix<=np.arange(6)).all()
