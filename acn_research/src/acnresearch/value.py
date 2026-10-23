"""Finite-action recovery-information experiment with an exact flow bound.

One unit is 6 A for one control period. Integral requests, station limits and
feeder limits make the time/session transportation polytope integral. LP vertices
therefore implement allowed actions, rather than a continuous relaxation.
"""
from dataclasses import dataclass
import time
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import eye, hstack, kron, vstack


@dataclass
class PublicWorld:
    demand: np.ndarray
    departure: np.ndarray
    feeder: int
    slots: int
    period: int = 5
    voltage: int = 208
    max_units: int = 5

    @property
    def quantum_kwh(self): return 6*self.voltage*self.period/60000


@dataclass
class World:
    public: PublicWorld
    acceptance: np.ndarray


def make_world(seed, feeder_amp, pause=True):
    r=np.random.default_rng(seed); n=6; horizon=24
    departure=r.integers(12,25,n)
    demand=r.integers(20,76,n)
    acceptance=np.arange(horizon)[None,:]<departure[:,None]
    chosen=r.choice(n,3,replace=False)
    for i in chosen:
        start=int(r.integers(3,8)); length=int(r.integers(2,9))
        end=min(start+length,int(departure[i])-2)
        if pause: acceptance[i,start:end]=False
    return World(PublicWorld(demand,departure,feeder_amp//6,horizon),acceptance)


def flow_plan(remaining, caps, feeder, departure=None, early=True):
    """Integer network-flow LP. Secondary reward is < 0.25 total unit."""
    remaining=np.asarray(remaining,dtype=float); caps=np.asarray(caps,dtype=float)
    n,h=caps.shape
    assert np.allclose(remaining,np.rint(remaining),atol=1e-6)
    assert np.allclose(caps,np.rint(caps),atol=1e-6)
    if h==0 or remaining.sum()<1e-7: return np.zeros_like(caps,dtype=int)
    mat=vstack([kron(eye(n),np.ones((1,h))),hstack([eye(h)]*n)],format='csr')
    rhs=np.r_[np.rint(remaining),np.full(h,feeder)]
    reward=np.ones((n,h))
    if early:
        urgency=np.zeros(n) if departure is None else 1-np.asarray(departure)/max(1,max(departure))
        secondary=(1-np.arange(h)/h)[None,:]+.01*urgency[:,None]+.0001*(1-np.arange(n)/n)[:,None]
        reward+=secondary*.24/(1.011*max(1,caps.sum()))
    opt=linprog(-reward.ravel(),A_ub=mat,b_ub=rhs,
                bounds=np.column_stack([np.zeros(n*h),caps.ravel()]),method='highs')
    if not opt.success: raise RuntimeError(opt.message)
    plan=opt.x.reshape(n,h)
    assert np.max(np.abs(plan-np.rint(plan)))<1e-6, 'Non-integral solution'
    plan=np.rint(plan).astype(int)
    assert np.all(plan.sum(axis=1)<=remaining+1e-6)
    assert np.all(plan.sum(axis=0)<=feeder) and np.all(plan<=caps) and np.all(plan>=0)
    return plan


def recovery_notices(world,t,lead):
    """Only the environment sees future acceptance. No future pause notices."""
    eta=np.full(len(world.public.demand),-1,dtype=int)
    if lead==0: return eta
    for i in range(len(eta)):
        if world.acceptance[i,t] or t>=world.public.departure[i]: continue
        future=np.flatnonzero(world.acceptance[i,t+1:])
        if len(future):
            end=t+1+int(future[0])
            if lead<0 or end-t<=lead: eta[i]=end
    return eta


class MPC:
    def __init__(self,public,duration=4,current_oracle=False,lead=0):
        self.public=public; self.duration=duration; self.current_oracle=current_oracle
        self.lead=lead; self.known_active=np.ones(len(public.demand),dtype=bool)
        self.pause_since=np.full(len(public.demand),-1,dtype=int)

    def act(self,t,remaining,previous_pilot,previous_actual,current=None,notices=None):
        p=self.public; n=len(remaining)
        previous=self.known_active.copy()
        if self.current_oracle:
            assert current is not None
            self.known_active=np.asarray(current).copy()
        elif t:
            # No pilot is not evidence of inability to draw. Positive response
            # restores the nominal cap immediately (strong feedback baseline).
            self.known_active[previous_actual>0]=True
            self.known_active[(previous_pilot>0)&(previous_actual==0)]=False
        onset=previous&~self.known_active
        self.pause_since[onset]=t
        caps=np.full((n,p.slots-t),p.max_units,dtype=int)
        for i in range(n):
            if not self.known_active[i]:
                end=max(t+1,int(self.pause_since[i])+self.duration)
                if notices is not None and notices[i]>=0: end=int(notices[i])
                elif self.current_oracle and self.lead>0:
                    # Absence of a guaranteed oracle notice is itself information.
                    end=max(end,t+self.lead+1)
                caps[i,:min(caps.shape[1],end-t)]=0
                if not self.current_oracle: caps[i,0]=1 # conventional probe
            caps[i,max(0,int(p.departure[i])-t):]=0
        return flow_plan(remaining,caps,p.feeder,p.departure)[:,0]


class Greedy:
    def __init__(self,public,kind='edf'):
        self.public=public; self.kind=kind
        self.known_active=np.ones(len(public.demand),dtype=bool)

    def act(self,t,remaining,previous_pilot,previous_actual,**kwargs):
        if t:
            self.known_active[previous_actual>0]=True
            self.known_active[(previous_pilot>0)&(previous_actual==0)]=False
        p=self.public; cap=np.where(self.known_active,p.max_units,1)
        cap=np.minimum(cap,remaining); cap[p.departure<=t]=0
        priorities=p.departure if self.kind=='edf' else p.departure-t-remaining/p.max_units
        order=np.lexsort((np.arange(len(cap)),priorities))
        action=np.zeros(len(cap),dtype=int); budget=p.feeder
        for i in order:
            action[i]=min(int(cap[i]),budget); budget-=action[i]
        return action


def summarize(public,pilot,actual,runtime):
    delivered=actual.sum(axis=1); q=public.quantum_kwh
    assert np.all(pilot>=0) and np.all(pilot<=public.max_units)
    assert np.all(pilot.sum(axis=0)<=public.feeder)
    assert np.all(actual<=pilot) and np.all(delivered<=public.demand)
    assert np.allclose(pilot,np.rint(pilot)) and np.allclose(actual,np.rint(actual))
    return {'delivered_kwh':float(delivered.sum()*q),
            'shortfall_kwh':float((public.demand-delivered).sum()*q),
            'fully_served':int(np.sum(delivered>=public.demand)),
            'wasted_reserved_kwh':float((pilot-actual).sum()*q),
            'runtime_seconds':runtime,'constraint_violations':0}


def run_policy(world,name,duration=4):
    p=world.public; n=len(p.demand); pilot=np.zeros((n,p.slots),dtype=int)
    actual=pilot.copy(); remaining=p.demand.copy(); start=time.perf_counter()
    if name=='offline':
        pilot=flow_plan(p.demand,world.acceptance*p.max_units,p.feeder,p.departure)
        actual=pilot.copy()
    else:
        lead={'current_mpc':0,'lead1_mpc':1,'lead3_mpc':3,'resume_oracle_mpc':-1}.get(name,0)
        oracle=name in ('current_mpc','lead1_mpc','lead3_mpc','resume_oracle_mpc')
        policy=Greedy(p,name) if name in ('edf','llf') else MPC(p,duration,oracle,lead)
        for t in range(p.slots):
            kwargs={}
            if oracle:
                kwargs={'current':world.acceptance[:,t], 'notices':recovery_notices(world,t,lead)}
            cmd=policy.act(t,remaining,pilot[:,t-1] if t else np.zeros(n),
                           actual[:,t-1] if t else np.zeros(n),**kwargs)
            cmd[p.departure<=t]=0
            pilot[:,t]=cmd
            actual[:,t]=np.minimum(cmd,remaining)*world.acceptance[:,t]
            remaining-=actual[:,t]
    return summarize(p,pilot,actual,time.perf_counter()-start),{'pilot':pilot,'actual':actual}


def run_native(world):
    """Same requests, exogenous acceptance and physical constraints, author solver."""
    from datetime import datetime,timezone
    import warnings
    from acnportal import acnsim
    from adacharge.adaptive_charging_optimization import ObjectiveComponent,total_energy,quick_charge
    from acnresearch.native import AvailabilityBattery,DeclaredRequestInterface,AuditedRampdown,AuditedASA
    p=world.public; stations=[f'station-{i}' for i in range(len(p.demand))]
    network=acnsim.ChargingNetwork()
    for s in stations: network.register_evse(acnsim.FiniteRatesEVSE(s,[0,6,12,18,24,30]),p.voltage,0)
    network.add_constraint(acnsim.Current(stations),p.feeder*6,name='shared-feeder')
    events=[]
    for i,s in enumerate(stations):
        energy=float(p.demand[i]*p.quantum_kwh)
        ev=acnsim.EV(0,int(p.departure[i]),energy,s,f'session-{i}',
                    AvailabilityBattery(energy,world.acceptance[i]*30,p.voltage),
                    estimated_departure=int(p.departure[i]))
        events.append(acnsim.PluginEvent(0,ev))
    scheduler=AuditedASA([ObjectiveComponent(total_energy,1),ObjectiveComponent(quick_charge,1e-5)],
                        solver='CLARABEL',constraint_type='LINEAR',estimate_max_rate=True,
                        max_rate_estimator=AuditedRampdown(6,6),max_recompute=1,
                        quantize=True,reallocate=True,uninterrupted_charging=False)
    sim=acnsim.Simulator(network,scheduler,acnsim.EventQueue(events),datetime(2020,1,1,tzinfo=timezone.utc),
                        period=p.period,verbose=False,interface_type=DeclaredRequestInterface)
    start=time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always'); sim.run()
    elapsed=time.perf_counter()-start
    assert not any('Invalid schedule' in str(w.message) for w in caught)
    pilot=np.zeros((len(p.demand),p.slots)); actual=pilot.copy()
    length=min(sim.charging_rates.shape[1],p.slots)
    pilot[:,:length]=sim.pilot_signals[:,:length]/6
    actual[:,:length]=sim.charging_rates[:,:length]/6
    assert np.max(np.abs(pilot-np.rint(pilot)))<1e-6
    assert np.max(np.abs(actual-np.rint(actual)))<1e-6
    assert np.max(np.abs(actual[~world.acceptance]),initial=0)<1e-6
    result=summarize(p,np.rint(pilot).astype(int),np.rint(actual).astype(int),elapsed)
    result['native_solver_calls']=scheduler.solve_calls
    return result,{'pilot':np.rint(pilot).astype(int),'actual':np.rint(actual).astype(int)}
