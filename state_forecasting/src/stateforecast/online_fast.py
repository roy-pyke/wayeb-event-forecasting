"""Final executable sidecar, including the fast business-outcome fallback."""
import numpy as np
from .online import StateSidecar
from .mixer import DelayedExpertMixer
from .fast_feedback import FastOutcomeExpert
from .data import BASE


def raw_and_calibrated(model,x,horizons):
    raw=model.predict_cdf(x,horizons,calibrated=False)[0]
    calibrated=model.calibrator.predict(raw) if model.calibrator is not None else raw.copy()
    return raw,calibrated


class FastStateSidecar:
    def __init__(self,table,context_model,baseline,horizons=(30,60,120)):
        self.state=StateSidecar(table,context_model,baseline,horizons,adaptive=False)
        self.baseline,self.context=baseline,context_model
        self.horizons=list(horizons)
        self.fast=FastOutcomeExpert(horizons)
        self.mixer=DelayedExpertMixer(5)
        self.base_mixer=DelayedExpertMixer(3)
        self.pending=[]
        self.clock=-float('inf')

    def _feedback(self,p,y,available,now):
        self.mixer.observe(p['full'],y,available,now)
        self.base_mixer.observe(p['base'],y,available,now)
        self.fast.observe(p['key'],p['horizon'],y)
        p['done']=True

    def _advance(self,now,inclusive=True):
        if now<self.clock:raise ValueError('arrival clock cannot go backwards')
        self.clock=now
        ready=[p for p in self.pending if p['deadline']<now or (inclusive and p['deadline']==now)]
        for p in sorted(ready,key=lambda p:p['deadline']):self._feedback(p,0,p['deadline'],now)
        self.pending=[p for p in self.pending if not p['done']]

    def accept(self,event):
        self._advance(event.arrival_time,inclusive=False)
        matched=self.state.accept(event)
        if event.kind in {'LoadEnd','Gap'}:
            for p in self.pending:
                if p['instance']==event.instance:
                    if matched:self._feedback(p,1,event.arrival_time,event.arrival_time)
                    p['done']=True
            self.pending=[p for p in self.pending if not p['done']]
        self._advance(event.arrival_time)
        return matched

    def predict(self,instance,now):
        self._advance(now)
        x=self.state.features(instance,now)
        if x is None:return None
        raw0,cal0=raw_and_calibrated(self.baseline,x,self.horizons)
        dynamic,key=self.fast.predict(x[0])
        base=np.stack([raw0,cal0,dynamic])
        stale=(x[0,-1]>30) or not np.isfinite(x[0,len(BASE)+1])
        raw2,cal2=(raw0,cal0) if stale else raw_and_calibrated(self.context,x,self.horizons)
        full=np.stack([raw0,cal0,raw2,cal2,dynamic])
        p=self.base_mixer.predict(base) if stale else self.mixer.predict(full)
        for j,h in enumerate(self.horizons):
            self.pending.append(dict(instance=instance,deadline=now+h,full=full[:,j],base=base[:,j],
                                     key=key,horizon=j,done=False))
        return dict(instance=instance,as_of=now,pattern_state=self.state.monitor.states[instance],
                    horizons_seconds=self.horizons,completion_probability=p.tolist(),
                    weights=self.mixer.weights.tolist(),source='business_fallback' if stale else 'full_context_pool')
