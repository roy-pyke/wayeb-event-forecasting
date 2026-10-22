import numpy as np
from patternforecast.automata import PatternFamily
from patternforecast.polytope import FeasiblePolytope
from patternforecast.refresh import choose_patch


def test_joint_coherence_projection_and_sparse_patch_are_feasible():
    f=PatternFamily();rng=np.random.default_rng(333)
    for hs in [(1,2,3),(3,6,12),(5,15,30)]:
        for q in range(len(f.states)):
            y=f.feasible(q,hs);poly=FeasiblePolytope(y)
            assert poly.contains(y).all()
            raw=rng.uniform(size=(12,9));p=poly.project(raw)
            assert poly.contains(p).all()
            assert np.allclose(poly.project(p),p,atol=1e-7)
            for label in y:
                assert (np.sum((p-label)**2,1)<=np.sum((raw-label)**2,1)+1e-7).all()
            c,mask,b=choose_patch(p[0],p[1],y,'joint',.005,True,poly.contains)
            assert poly.contains(c)[0]
            assert b<=.005+1e-10


def test_short_horizon_exclusion_survives_coordinate_zeroing():
    f=PatternFamily();q,_=f.step(f.start,'A');y=f.feasible(q,(1,2,3)).reshape(-1,3,3)
    # A broad match on tick 1 consumes D and resets the shared stream. A branch
    # match would then need A,(B|C),D, so cannot also finish by tick 3.
    assert y[:,2,0].max()==1 and y[:,1,2].max()==1
    assert (y[:,2,0]+y[:,1,2]<=1).all()
