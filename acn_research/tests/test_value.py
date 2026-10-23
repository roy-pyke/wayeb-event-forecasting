from itertools import product
import numpy as np
from acnresearch.value import PublicWorld,World,flow_plan,MPC,run_policy


def test_flow_bound_matches_exhaustive_discrete_actions():
    for mask in range(16):
        caps=np.array([(mask>>i)&1 for i in range(4)]).reshape(2,2)
        p=PublicWorld(np.array([1,2]),np.array([2,2]),1,2,max_units=1)
        best=0
        for flat in product(range(2),repeat=4):
            a=np.array(flat).reshape(2,2)
            if np.all(a<=caps) and np.all(a.sum(axis=0)<=1) and np.all(a.sum(axis=1)<=p.demand):
                best=max(best,int(a.sum()))
        assert flow_plan(p.demand,caps,1).sum()==best


def test_causal_policies_cannot_read_future_acceptance():
    p=PublicWorld(np.array([15,15]),np.array([8,8]),5,8)
    a=np.ones((2,8),bool); b=a.copy(); b[0,4:6]=False
    for name in ['edf','llf','causal_mpc','current_mpc']:
        _,ta=run_policy(World(p,a),name)
        _,tb=run_policy(World(p,b),name)
        assert np.array_equal(ta['pilot'][:,:4],tb['pilot'][:,:4])


def test_response_depends_on_action_and_capacity_control_reaches_bound():
    p=PublicWorld(np.array([15,15]),np.array([8,8]),10,8)
    accept=np.ones((2,8),bool); accept[0,2:4]=False
    w=World(p,accept)
    best,_=run_policy(w,'offline')
    for name in ['edf','llf','current_mpc','resume_oracle_mpc']:
        result,trace=run_policy(w,name)
        assert abs(result['delivered_kwh']-best['delivered_kwh'])<1e-8
        assert not trace['actual'][0,2:4].any()


def test_no_command_is_not_evidence_of_no_acceptance():
    p=PublicWorld(np.array([15]),np.array([8]),5,8)
    m=MPC(p)
    m.act(1,np.array([15]),np.array([0]),np.array([0]))
    assert m.known_active[0]
