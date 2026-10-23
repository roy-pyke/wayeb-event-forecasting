"""Conventional sparse probing and an operational recovery-notice diagnostic."""
import time
import numpy as np
from acnresearch.value import recovery_notices,summarize


class ProbeEDF:
    def __init__(self,public,interval=1,backoff=False,fill_spare=False):
        self.public=public; self.interval=interval; self.backoff=backoff; self.fill_spare=fill_spare
        n=len(public.demand)
        self.active=np.ones(n,bool); self.last_attempt=np.full(n,-100000,int)
        self.wait=np.ones(n,int); self.eta=np.full(n,-1,int)

    def act(self,t,remaining,previous_pilot,previous_actual,notices=None):
        was_active=self.active.copy()
        if t:
            attempted=previous_pilot>0; failed=attempted&(previous_actual==0)
            succeeded=previous_actual>0
            self.last_attempt[attempted]=t-1
            self.active[failed]=False; self.active[succeeded]=True
            if self.backoff:
                self.wait[failed&~was_active]=np.minimum(4,self.wait[failed&~was_active]*2)
                self.wait[failed&was_active]=1
                self.wait[succeeded]=1
        if notices is not None:
            # Only already-observed inability unlocks a future notification.
            usable=(~self.active)&(notices>t)
            self.eta[usable]=notices[usable]
        p=self.public; cap=np.full(len(remaining),p.max_units,int)
        for i in range(len(remaining)):
            if self.active[i]: continue
            if self.eta[i]>=0:
                if t>=self.eta[i]:
                    self.active[i]=True; self.eta[i]=-1
                else: cap[i]=0
            else:
                interval=int(self.wait[i]) if self.backoff else self.interval
                cap[i]=1 if t-self.last_attempt[i]>=interval else 0
        cap=np.minimum(cap,remaining); cap[p.departure<=t]=0
        order=np.lexsort((np.arange(len(cap)),p.departure))
        action=np.zeros(len(cap),int); budget=p.feeder
        for i in order:
            action[i]=min(int(cap[i]),budget); budget-=action[i]
        if self.fill_spare:
            # Serving known-active cars has priority. Any remaining pilot budget
            # can test unknown acceptance at no displacement cost; never throttle
            # a paused car merely to conserve capacity that nobody else can use.
            for i in order:
                if p.departure[i]<=t: continue
                add=min(max(0,min(p.max_units,int(remaining[i]))-action[i]),budget)
                action[i]+=add; budget-=add
        return action


def run_probe(world,setting='every_1',lead=None,fill_spare=False):
    p=world.public; n=len(p.demand)
    controller=ProbeEDF(p,interval=int(setting[-1]) if setting.startswith('every_') else 1,
                        backoff=setting=='backoff',fill_spare=fill_spare)
    pilot=np.zeros((n,p.slots),int); actual=pilot.copy(); remaining=p.demand.copy()
    start=time.perf_counter()
    for t in range(p.slots):
        notices=recovery_notices(world,t,lead) if lead is not None else None
        pilot[:,t]=controller.act(t,remaining,pilot[:,t-1] if t else np.zeros(n),
                                  actual[:,t-1] if t else np.zeros(n),notices)
        actual[:,t]=np.minimum(pilot[:,t],remaining)*world.acceptance[:,t]
        remaining-=actual[:,t]
    return summarize(p,pilot,actual,time.perf_counter()-start),{'pilot':pilot,'actual':actual}
