"""Conditional coupling of real learned CDFs with explicit response assumptions."""
from dataclasses import dataclass
import time
import numpy as np
from acnresearch.value import PublicWorld,flow_plan,summarize
from acnresearch.discovery import conditional_probability,next_probe,perturb_cdf


@dataclass
class ServiceWorld:
    public: PublicWorld
    response_caps: np.ndarray
    disconnect: np.ndarray
    recovery: np.ndarray
    cdf: np.ndarray
    empirical_cdf: np.ndarray


def make_service_world(seed,feeder_amp,recovery_amp,episodes,cdf,empirical_cdf):
    rng=np.random.default_rng(seed); chosen=rng.integers(0,len(episodes),3)
    sample=episodes.iloc[chosen]; T=12
    demand=np.r_[rng.integers(20,46,3),rng.integers(8,31,3)]
    departure=rng.integers(6,13,6)
    pub=PublicWorld(demand,departure,feeder_amp//6,T)
    recovery=np.r_[np.zeros(3,int),[int(np.ceil(e/5)) if np.isfinite(e) else T+1 for e in sample.event_min]]
    disconnect=np.r_[np.full(3,T),[int(np.ceil(r.observed_min/5)) if r.terminal else T for _,r in sample.iterrows()]]
    caps=np.zeros((6,T),int)
    for i in range(6):
        caps[i,recovery[i]:min(departure[i],disconnect[i])]=5 if i<3 else recovery_amp//6
    return ServiceWorld(pub,caps,disconnect,recovery,
                         np.vstack([np.zeros((3,T)),cdf[chosen]]),
                         np.vstack([np.zeros((3,T)),empirical_cdf[chosen]]))


class LearnedProbeEDF:
    def __init__(self,public,cdf,kind='dp',threshold=.2,restore=False):
        self.p=public; self.cdf=np.asarray(cdf).copy(); self.kind=kind
        self.threshold=threshold; self.restore=restore
        n=len(public.demand); self.active=np.r_[np.ones(3,bool),np.zeros(n-3,bool)]
        self.last=np.zeros(n,int); self.attempt=np.zeros(n,int); self.upper=np.full(n,public.max_units,int)

    def act(self,t,remaining,previous_pilot,previous_actual,connected,oracle_recovery=None):
        p=self.p; n=len(remaining)
        if t:
            observed=previous_pilot>0; positive=previous_actual>0
            failed=observed&~positive
            self.active[failed]=False; self.active[positive]=True
            self.last[observed]=t-1
            self.attempt[failed]+=int(t>1); self.attempt[positive]=0
            # Ordinary causal cap reclamation. A one-unit successful probe does
            # not imply a one-unit maximum: only actual strictly below pilot does.
            limited=positive&(previous_actual<previous_pilot)
            self.upper[limited]=previous_actual[limited]
        cap=np.zeros(n,int)
        for i in range(n):
            if self.active[i]: cap[i]=self.upper[i]; continue
            if oracle_recovery is not None:
                cap[i]=p.max_units if t>=oracle_recovery[i] else 0
                continue
            due=next_probe(self.kind,int(self.last[i]),int(self.attempt[i]),self.cdf[i],threshold=self.threshold)
            if t>=due:
                prob=conditional_probability(self.cdf[i],int(self.last[i]),t)
                cap[i]=p.max_units if self.restore and prob>=.5 else 1
        cap=np.minimum(cap,remaining); cap[(p.departure<=t)|~connected]=0
        action=np.zeros(n,int); budget=p.feeder
        order=np.lexsort((np.arange(n),p.departure))
        for i in order:
            action[i]=min(int(cap[i]),budget); budget-=action[i]
        for i in order:
            if p.departure[i]<=t or not connected[i]: continue
            add=min(max(0,min(int(remaining[i]),int(self.upper[i]))-action[i]),budget)
            action[i]+=add; budget-=add
        return action


def run_service(world,kind='dp',empirical=False,threshold=.2,restore=False,perturb='natural',oracle=False):
    p=world.public; n=len(p.demand); pilot=np.zeros((n,p.slots),int); actual=pilot.copy()
    remaining=p.demand.copy(); start=time.perf_counter()
    cdf=world.empirical_cdf if empirical else world.cdf
    cdf=np.array([perturb_cdf(x,perturb) for x in cdf])
    controller=LearnedProbeEDF(p,cdf,kind,threshold,restore)
    for t in range(p.slots):
        connected=t<world.disconnect
        pilot[:,t]=controller.act(t,remaining,pilot[:,t-1] if t else np.zeros(n,int),
                                   actual[:,t-1] if t else np.zeros(n,int),connected,
                                   world.recovery if oracle else None)
        actual[:,t]=np.minimum.reduce([pilot[:,t],world.response_caps[:,t],remaining])
        remaining-=actual[:,t]
        assert np.all(actual[~connected,t]==0)
        assert np.all(pilot[p.departure<=t,t]==0)
    result=summarize(p,pilot,actual,time.perf_counter()-start)
    return result,{'pilot':pilot,'actual':actual}


def offline_service(world):
    p=world.public
    plan=flow_plan(p.demand,world.response_caps,p.feeder,p.departure)
    return float(plan.sum()*p.quantum_kwh)
