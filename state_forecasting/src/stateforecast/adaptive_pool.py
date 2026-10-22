"""Second research generation: calibration is a competing expert, not a mandate.

This module is separate so the original frozen, failed experiment remains runnable.
"""
import heapq
import numpy as np
from .mixer import DelayedExpertMixer


def causal_pool(data, experts, horizons, eta=2.0, share=0.02):
    """experts shape: (rows, number_of_experts, number_of_horizons)."""
    experts=np.asarray(experts)
    if experts.ndim!=3 or len(experts)!=len(data['time']):
        raise ValueError('expert tensor shape mismatch')
    mixer=DelayedExpertMixer(experts.shape[1],eta,share)
    queue=[];counter=0
    predictions=np.zeros((len(experts),experts.shape[2]))
    weights=np.zeros(experts.shape[:2])
    for i in np.argsort(data['time'],kind='stable'):
        now=data['time'][i]
        while queue and queue[0][0]<=now:
            available,_,p,y=heapq.heappop(queue)
            mixer.observe(p,y,available,now)
        weights[i]=mixer.weights;predictions[i]=mixer.predict(experts[i])
        for k,h in enumerate(horizons):
            remaining,observed=data['residual'][i],data['observed'][i]
            if observed and remaining<=h:available,y=now+remaining,1
            elif remaining>=h:available,y=now+h,0
            else:continue
            counter+=1;heapq.heappush(queue,(available,counter,experts[i,:,k],y))
    return predictions,weights,dict(updates=mixer.updates,experts=experts.shape[1],eta=eta,share=share,
                                   mean_weights=np.mean(weights,axis=0).tolist())
