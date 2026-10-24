from itertools import combinations, product
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
import pytest
from recurrent.control import joint_values, head_arrays, select
from recurrent.data import read_avt, fit_rates, transition
from recurrent.replay import simulate, arrivals_for, POLICIES
from recurrent.pricing import DestinationDP,advance_queue
from functools import lru_cache


def brute_q(p, queues, t, k, a, b):
    """Independent full current-state enumeration, then Bayes observations."""
    valid = [i for i,q in enumerate(queues) if q]
    acts = list(combinations(valid,min(k,len(valid))))
    answers=[]
    for act in acts:
        total=0.
        for truth in product((0,1),repeat=len(p)):
            pr=np.prod([p[i] if truth[i] else 1-p[i] for i in range(len(p))])
            reward=0.; nextq=[q.copy() for q in queues]; belief=np.asarray(p).copy()
            for i in act:
                belief[i]=truth[i]
                if truth[i]: reward+=nextq[i].pop(0)[0]
            nextq=[[x for x in q if x[1]>t+1] for q in nextq]
            belief=a+(b-a)*belief
            scores=[q[0][0]*belief[i] if q else 0 for i,q in enumerate(nextq)]
            total+=pr*(reward+sum(sorted(scores)[-k:]))
        answers.append(total)
    return np.asarray(acts),np.asarray(answers)


def test_joint_matches_independent_exhaustive_bayes_tree():
    rng=np.random.default_rng(5423)
    for _ in range(30):
        p=rng.uniform(.01,.99,4);a,b=.18,.73
        queues=[[(int(rng.integers(1,5)),int(rng.integers(1,5))) for j in range(2)] for i in range(4)]
        v,_,f=head_arrays(queues,0)
        act,q=joint_values(p,v,f,a,b,2)
        acts,exact=brute_q(p,queues,0,2,a,b)
        assert np.array_equal(act,acts)
        assert np.allclose(q,exact,atol=1e-12)


def test_full_capacity_always_attempts_all_nonempty():
    queues=[[(1,4)],[],[(2,3)]]
    for policy in ['myopic_value','independent_two_step','joint_two_step']:
        assert set(select(policy,np.array([.2,.6,.9]),queues,0,3,.2,.8))=={0,2}


def test_terminal_horizon_uses_immediate_reward():
    q=[[(1,40)],[(4,40)],[(2,40)]]
    p=np.ones(3)*.8
    assert select('joint_two_step',p,q,31,1,.1,.9).tolist()==[1]


def test_recurrence_never_absorbs_observed_success():
    states=np.array([[1,0],[0,1],[1,0]])
    arr=(np.ones((3,2),dtype=bool),np.ones((3,2),dtype=int),np.ones((3,2),dtype=int)*4)
    _,h=simulate(states,np.array([1,1]),arr,'joint_two_step',2,.2,.7,True)
    assert h[1]['belief']==pytest.approx([.7,.2])


def test_unattempted_future_is_not_observed():
    a=np.zeros((8,6),dtype=int);b=a.copy();b[4:]=1
    arr=arrivals_for('test',1,8)
    _,ha=simulate(a,np.ones(6),arr,'joint_two_step',2,.1,.9,True)
    _,hb=simulate(b,np.ones(6),arr,'joint_two_step',2,.1,.9,True)
    assert ha[:4]==hb[:4]
    assert ha[4]['selected']==hb[4]['selected']


def test_unknown_input_rejected_and_resources_conserved():
    rng=np.random.default_rng(23)
    states=rng.integers(0,2,(32,6))
    for policy in POLICIES:
        stats,_=simulate(states,np.ones(6),arrivals_for('test',3),policy,2,.2,.8)
        assert stats['max_buffer']<=12
        assert stats['attempts']<=64
    arr=(np.ones((1,1),dtype=bool),np.ones((1,1),dtype=int),np.ones((1,1),dtype=int))
    with pytest.raises(AssertionError):simulate(np.array([[-1]]),np.ones(1),arr,'myopic_value',1,.2,.8)


def test_interval_endpoints_are_censored_not_failures(tmp_path):
    f=tmp_path/'test.avt';f.write_text('a 2 10 20 30 40\nb 1 0 50\n')
    tr=read_avt(f,10)
    assert tr.states[0].tolist()==[-1,1,0,1,-1]
    rates=fit_rates(tr,50)
    assert rates['up_to_down_events']==1
    assert rates['down_to_up_events']==1


def test_transition_composes_in_physical_time():
    rates={'up_to_down_per_second':.01,'down_to_up_per_second':.02}
    a,b=transition(rates,10);c,d=transition(rates,20)
    mat=np.array([[1-a,a],[1-b,b]])
    assert (mat@mat)[:,1]==pytest.approx([c,d])


def test_no_current_capacity_gain_is_claimed_when_alternative_is_better():
    # Last slot: uncertain request never displaces certain higher-value service.
    chosen=select('joint_two_step',np.array([.99,.01]),[[(4,33)],[(1,33)]],31,1,.4,.8)
    assert chosen.tolist()==[0]


def test_price_relaxation_upper_bounds_exact_joint_pomdp():
    a,b=.18,.73
    single=DestinationDP(a,b)
    @lru_cache(None)
    def exact(p,queues,h):
        if h==0:return 0.
        eligible=[i for i,q in enumerate(queues) if q]
        if not eligible:return 0.
        values=[]
        for i in eligible: # K=1, observations arrive at end of slot
            value=0.
            for y in [0,1]:
                weight=p[i] if y else 1-p[i]
                nextp=[a+(b-a)*x for x in p];nextp[i]=b if y else a
                nextqueues=list(queues)
                nextqueues[i]=nextqueues[i][y:]
                reward=queues[i][0][0] if y else 0.
                value+=weight*(reward+exact(tuple(round(x,12) for x in nextp),
                                           tuple(advance_queue(q) for q in nextqueues),h-1))
            values.append(value)
        return max(values)
    for p in [(.2,.8),(.7,.6),(.4,.3)]:
        queues=(((3,3),(1,2)),((2,1),(4,3)))
        optimum=exact(p,queues,3)
        bound,price,_=single.evaluate(p,queues,3,1)
        assert bound+1e-10>=optimum


def test_single_destination_price_dp_matches_all_up_deadlines():
    dp=DestinationDP(1.,1.)
    value,_=dp.solve(1.,((3,3),(2,1),(4,3)),3,0.)
    assert value==7. # second record expires before it can become the head


def test_all_deadline_baselines_obey_feedback_and_capacity():
    states=np.random.default_rng(12).integers(0,2,(12,6))
    for policy in ['unpriced_horizon8','priced_horizon8']:
        stats,h=simulate(states,np.ones(6),arrivals_for('test',43,12),policy,2,.2,.8,True)
        assert stats['attempts']<=24 and stats['max_buffer']<=12
        assert len(h)==12


def test_same_first_recovery_distribution_reverses_joint_action():
    queues=[[(4,3)],[(3,3)]];p=np.array([.5,.5])
    observed=[]
    for p11 in [.55,.99]:
        acts,q=brute_q(p,queues,0,1,.5,p11)
        observed.append(int(acts[np.argmax(q),0]))
    assert observed==[0,1]


