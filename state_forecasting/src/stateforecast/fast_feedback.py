"""Fast causal fallback for joint expert failures during abrupt operating changes."""
import heapq
import numpy as np
from .mixer import DelayedExpertMixer


class FastOutcomeExpert:
    """Discounted Beta counts by business age/history, without sensor inputs.

    Both baseline and context systems receive this exact same expert.
    Counts are updated only by matured horizon outcomes.
    """
    def __init__(self, horizons, decay=.98):
        self.horizons=np.asarray(horizons)
        self.decay=decay
        self.cells={}

    def key(self, x):
        age=int(np.searchsorted([30,60,120,300],x[0],side='right'))
        previous=int(np.searchsorted([30,60,120,300],x[1],side='right')) if np.isfinite(x[1]) else 5
        return age,previous

    def predict(self, x):
        key=self.key(x)
        success,total=self.cells.get(key,(np.zeros(len(self.horizons)),np.zeros(len(self.horizons))))
        p=(success+1)/(total+2)
        # One monotone CDF is required; per-horizon counts can mature at different times.
        return np.maximum.accumulate(p),key

    def observe(self,key,horizon_index,outcome):
        success,total=self.cells.setdefault(key,(np.zeros(len(self.horizons)),np.zeros(len(self.horizons))))
        success[horizon_index]=self.decay*success[horizon_index]+outcome
        total[horizon_index]=self.decay*total[horizon_index]+1


def adaptive_forecast(data, fixed_experts, horizons, eta=2.0, share=.02, decay=.98):
    fixed_experts=np.asarray(fixed_experts)
    count=len(fixed_experts);nh=len(horizons)
    mixer=DelayedExpertMixer(fixed_experts.shape[1]+1,eta,share)
    fast=FastOutcomeExpert(horizons,decay)
    queue=[];serial=0
    predictions=np.zeros((count,nh));weights=np.zeros((count,len(mixer.weights)))
    for i in np.argsort(data['time'],kind='stable'):
        now=data['time'][i]
        while queue and queue[0][0]<=now:
            available,_,p,y,key,k=heapq.heappop(queue)
            mixer.observe(p,y,available,now)
            fast.observe(key,k,y)
        dynamic,key=fast.predict(data['X'][i])
        experts=np.vstack([fixed_experts[i],dynamic])
        weights[i]=mixer.weights;predictions[i]=mixer.predict(experts)
        for k,h in enumerate(horizons):
            r,seen=data['residual'][i],data['observed'][i]
            if seen and r<=h:available,y=now+r,1
            elif r>=h:available,y=now+h,0
            else:continue
            serial+=1;heapq.heappush(queue,(available,serial,experts[:,k],y,key,k))
    return predictions,weights,dict(updates=mixer.updates,fast_cells=len(fast.cells),decay=decay,
                                   eta=eta,share=share,mean_weights=weights.mean(axis=0).tolist())
