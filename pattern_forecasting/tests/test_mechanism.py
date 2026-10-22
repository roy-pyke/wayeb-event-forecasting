import itertools
import re
import numpy as np
from patternforecast.automata import PatternFamily,independent_profiles
from patternforecast.certificates import joint_bound,cdf_bound,bernoulli_bound
from patternforecast.data import replay,targets


def test_author_automata_against_independent_regex():
    family=PatternFamily()
    regexes=['ABCD','A[BC]+D','A[ABC]*D']
    assert family.verify_inclusion()
    rng=np.random.default_rng(7)
    for letters in [list('AABCBABCDAD'),*rng.choice(list('ABCD'),(20,500))]:
        word=''; q=family.start
        for letter in letters:
            word+=letter
            q,hit=family.step(q,letter)
            expected=[any(re.fullmatch(pattern,word[start:]) for start in range(len(word))) for pattern in regexes]
            assert expected==hit.tolist()


def test_no_new_match_during_silence():
    family=PatternFamily(); q=family.start
    for a in 'ABCD': q,_=family.step(q,a)
    assert family.final[q].all()
    q2,hit=family.step(q,None)
    assert q2==q and not hit.any()


def test_reachable_profiles_equal_exhaustive_short_futures():
    family=PatternFamily(); horizons=(1,2,3)
    for q in range(len(family.states)):
        expected=set()
        for word in itertools.product([None,*family.alphabet],repeat=3):
            q2=q; hits=np.zeros(3,dtype=bool); profile=[]
            for a in word:
                q2,hit=family.step(q2,a); hits|=hit; profile.append(hits.copy())
            expected.add(tuple(np.array(profile).T.ravel()))
        assert expected==set(map(tuple,family.feasible(q,horizons)))


def test_certificates_bound_every_feasible_outcome_and_are_nested():
    family=PatternFamily(); rng=np.random.default_rng(19)
    strict=0
    for q in range(len(family.states)):
        yy=family.feasible(q,(1,2,3))
        for _ in range(20):
            p=np.sort(rng.uniform(size=(3,3)),axis=1)
            f=np.sort(rng.uniform(size=(3,3)),axis=1)
            bound=joint_bound(p,f,yy)
            losses=np.mean((p.ravel()-yy)**2-(f.ravel()-yy)**2,axis=1)
            assert np.max(losses)<=bound+1e-12
            assert bound<=cdf_bound(p,f)+1e-12
            assert cdf_bound(p,f)<=bernoulli_bound(p,f)+1e-12
            assert abs(cdf_bound(p,f)-joint_bound(p,f,independent_profiles(3,3)))<1e-12
            strict+=bound<cdf_bound(p,f)-1e-6
    assert strict>0


def test_causal_prefix_and_gaps_in_preprocessing():
    family=PatternFamily(); cfg=dict(native_seconds=1,query_every_samples=1)
    stamps=np.arange(70,dtype=float)
    values=np.column_stack([np.tile([0.,1.,2.,3.,2.,1.,0.],10),np.arange(70)])
    first,_,_,_=replay(stamps,values,[.5,1.5,2.5],cfg,family,'test')
    changed=values.copy(); changed[40:]*=100
    second,_,_,_=replay(stamps,changed,[.5,1.5,2.5],cfg,family,'test')
    past=first['t']<40
    for key in ['business','telemetry','q']:
        np.testing.assert_array_equal(first[key][past],second[key][past])
    values[40,0]=np.nan
    gapped,_,_,_=replay(stamps,values,[.5,1.5,2.5],cfg,family,'test')
    pre=gapped['t']<40
    assert np.all(gapped['coverage'][pre]<=39-gapped['t'][pre])
    y,known=targets(gapped,[3,6,12])
    # Unobserved intervals ending after the coverage cutoff remain unknown.
    assert not known[(~gapped['observed'])[:,:,None] & (gapped['coverage'][:,None,None]<np.array([3,6,12]))].any()


def test_true_profiles_are_automaton_feasible():
    family=PatternFamily(); cfg=dict(native_seconds=1,query_every_samples=1)
    rng=np.random.default_rng(41)
    values=rng.uniform(0,4,(200,2))
    data,_,_,_=replay(np.arange(200,dtype=float),values,[1,2,3],cfg,family,'test')
    yy,known=targets(data,[1,2,3])
    for i in np.flatnonzero(known.all(axis=(1,2))):
        feasible=family.feasible(int(data['q'][i]),(1,2,3))
        assert np.any(np.all(feasible==yy[i].ravel(),axis=1))
