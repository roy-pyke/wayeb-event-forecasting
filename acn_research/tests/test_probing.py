import numpy as np
from acnresearch.value import make_world,World,run_policy
from acnresearch.probing import ProbeEDF,run_probe


def test_every_slot_probe_reproduces_existing_edf():
    world=make_world(100,36)
    _,a=run_probe(world,'every_1'); _,b=run_policy(world,'edf')
    assert np.array_equal(a['pilot'],b['pilot'])


def test_notice_ignored_before_observed_inability():
    w=make_world(100,36); p=ProbeEDF(w.public)
    p.act(0,w.public.demand,np.zeros(6),np.zeros(6),notices=np.full(6,6))
    assert np.all(p.eta==-1)


def test_sparse_probes_do_not_read_future_acceptance():
    w=make_world(100,36); a=w.acceptance.copy(); b=a.copy(); b[:,10:]=True
    for setting in ['every_1','every_2','every_4','backoff']:
        _,x=run_probe(World(w.public,a),setting)
        _,y=run_probe(World(w.public,b),setting)
        assert np.array_equal(x['pilot'][:,:10],y['pilot'][:,:10])


def test_spare_capacity_avoids_unnecessary_recovery_throttling():
    w=make_world(100,180)
    optimum,_=run_policy(w,'offline')
    for setting in ['every_1','every_2','every_4','backoff']:
        result,_=run_probe(w,setting,fill_spare=True)
        assert abs(result['delivered_kwh']-optimum['delivered_kwh'])<1e-8
