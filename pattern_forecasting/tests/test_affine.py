import numpy as np
import pytest
from patternforecast.automata import PatternFamily
from patternforecast.affine import CoordinateMap,encode_frame,decode_frame,select_message,loss_bound
from patternforecast.polytope import FeasiblePolytope
from patternforecast.common import FAMILY


def test_structural_reconstruction_is_exact_and_rank_minimal():
    f=PatternFamily();rng=np.random.default_rng(53)
    for q in range(len(f.states)):
        y=f.feasible(q,(1,2,3)).astype(float)
        weights=rng.dirichlet(np.ones(len(y)),size=30);p=weights@y
        for mode in ['all','zero','basis']:
            mapping=CoordinateMap.compile(y,mode)
            assert np.allclose(mapping.expand(p[:,mapping.indices]),p,atol=1e-10)
            if mode=='basis':
                assert mapping.dimension==np.linalg.matrix_rank(y)
                if FAMILY=='directional':assert mapping.dimension==int(y.max(0).sum())


def test_serialized_candidates_bound_every_outcome_and_reject_bad_headers():
    f=PatternFamily();rng=np.random.default_rng(57)
    for q in range(len(f.states)):
        y=f.feasible(q,(1,2,3)).astype(float);poly=FeasiblePolytope(y)
        p,full=rng.dirichlet(np.ones(len(y)),size=2)@y
        for mode in ['all','zero','basis']:
            mapping=CoordinateMap.compile(y,mode);meta=(123,0,1,7,q)
            prediction,b,packet,bits=select_message(p,full,y,mapping,poly,.0005,meta)
            assert b<=.0005+1e-10
            assert poly.contains(prediction)[0]
            assert np.max(np.mean((prediction-y)**2-(full-y)**2,axis=1))<=b+1e-10
            if packet:
                decoded=decode_frame(packet,7,q,mapping,p,poly)[-1]
                assert np.array_equal(decoded,prediction)
                with pytest.raises(ValueError,match='version'):decode_frame(packet,8,q,mapping,p,poly)
                with pytest.raises(ValueError,match='state'):decode_frame(packet,7,q+1,mapping,p,poly)
                with pytest.raises(ValueError,match='length'):decode_frame(packet[:-1],7,q,mapping,p,poly)


def test_wire_lengths_and_quantization_are_real_bytes():
    y=np.vstack([np.zeros(9),np.eye(9)]);poly=FeasiblePolytope(y)
    mapping=CoordinateMap.compile(y,'all');values=np.arange(9)/100
    for bits in [8,16,32,64]:
        packet=encode_frame(1,2,3,7,0,values,bits)
        assert len(packet)==27+9*bits//8
        p=decode_frame(packet,7,0,mapping,np.zeros(9),poly)[-1]
        assert np.max(np.abs(p-values))<=1/(255 if bits==8 else 65535) if bits<32 else np.allclose(p,values)
        mask=np.arange(9)%2==0
        packet=encode_frame(1,2,3,7,0,values,bits,mask)
        assert len(packet)==29+5*bits//8


def test_certified_greedy_refresh_also_covers_feasible_labels():
    from patternforecast.refresh import choose_patch
    f=PatternFamily();rng=np.random.default_rng(61)
    for q in range(len(f.states)):
        y=f.feasible(q,(1,2,3)).astype(float);poly=FeasiblePolytope(y)
        p,full=rng.dirichlet(np.ones(len(y)),size=2)@y
        for strategy in ['greedy_delta','greedy_loss']:
            pred,mask,b=choose_patch(p,full,y,'joint',.005,validator=poly.contains,strategy=strategy)
            assert poly.contains(pred)[0]
            assert loss_bound(pred,full,y)<=.005+1e-10
