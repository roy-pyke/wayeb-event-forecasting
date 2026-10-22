import numpy as np
from patternforecast.automata import PatternFamily
from patternforecast.models import coherent
from patternforecast.refresh import choose_patch,masks_by_size,candidate_bound,refresh_replay


def test_sparse_patch_is_minimum_cardinality_and_obeys_all_feasible_outcomes():
    rng=np.random.default_rng(101);family=PatternFamily()
    for _ in range(60):
        q=int(rng.integers(len(family.states)));y=family.feasible(q,(3,6,12))
        p,f=coherent(rng.uniform(size=(2,3,3)))
        p=p.ravel()*y.max(0);f=f.ravel()*y.max(0)
        for mode in ['cdf','joint']:
            candidate,patch,b=choose_patch(p,f,y,mode,.02)
            assert np.max(np.mean((candidate-y)**2-(f-y)**2,1))<=.02+1e-10
            assert b<=.02+1e-10
            assert np.array_equal(candidate[patch],f[patch])
            assert np.array_equal(candidate[~patch],p[~patch])
            for smaller in masks_by_size(9)[:patch.sum()]:
                trial=np.where(smaller,f,p).reshape(-1,3,3)
                valid=(np.diff(trial,axis=2)>=-1e-7).all((1,2))
                for child,parent in family.inclusion_pairs():valid&=(trial[:,child]<=trial[:,parent]+1e-7).all(1)
                if valid.any(): assert (candidate_bound(trial[valid],f,y,mode)>.02-1e-10).all()


def test_forced_zero_projection_preserves_static_order_constraints():
    family=PatternFamily();rng=np.random.default_rng(131)
    p=coherent(rng.uniform(size=(50,3,3)))
    for hs in [(1,2,3),(3,6,12),(5,15,30)]:
        for q in range(len(family.states)):
            possible=family.feasible(q,hs).max(0).reshape(3,3);out=p*possible
            for child,parent in family.inclusion_pairs(): assert (out[:,child]<=out[:,parent]+1e-8).all()
            assert (np.diff(out,axis=2)>=-1e-8).all()


def test_real_sparse_wire_roundtrip_lengths_and_version_guard():
    from patternforecast.wire import encode,decode,Receiver
    import pytest
    receiver=Receiver(7);full=np.linspace(.01,.9,9).astype(np.float32)
    frame=encode(123,2,0,7,full,np.ones(9,dtype=bool))
    assert len(frame)==62
    assert np.array_equal(receiver.accept(frame)[1],full)
    patch=np.zeros(9,dtype=bool);patch[[0,4,8]]=True
    fresh=full/2;frame2=encode(124,2,1,7,fresh,patch)
    assert len(frame2)==38
    expected=full.copy();expected[patch]=fresh[patch]
    assert np.array_equal(receiver.accept(frame2)[1],expected)
    with pytest.raises(ValueError,match='version'):decode(frame2,8)
    with pytest.raises(ValueError,match='out-of-order'):receiver.accept(frame2)
    with pytest.raises(ValueError,match='length'):decode(frame2[:-1],7)
