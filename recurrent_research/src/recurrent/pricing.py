"""Established finite-horizon Lagrangian relaxation as a stronger comparator.

No indexability or Whittle-index claim: only a valid finite-horizon dual bound
under the independent fitted model, and a heuristic using the resulting bids.
"""
from functools import lru_cache
import numpy as np

PRICES=(0.,.5,1.,1.5,2.,3.,4.)


def advance_queue(queue):
    return tuple((v,d-1) for v,d in queue if d>1)


class DestinationDP:
    def __init__(self,p01,p11):
        self.p01=float(p01);self.p11=float(p11)
        # Instance-local caches make the transition model part of the cache key.
        self.solve=lru_cache(maxsize=350000)(self._solve)

    def _solve(self,p,queue,h,price):
        if h==0 or not queue:return (0.,0.)
        a,b=self.p01,self.p11
        no_completion=advance_queue(queue)
        completion=advance_queue(queue[1:])
        passive=self.solve(round(a+(b-a)*p,12),no_completion,h-1,price)[0]
        active=(queue[0][0]*p-price
                +p*self.solve(round(b,12),completion,h-1,price)[0]
                +(1-p)*self.solve(round(a,12),no_completion,h-1,price)[0])
        return max(passive,active),active-passive

    def evaluate(self,p,queues,h,k,priced=True):
        best=None
        for price in PRICES if priced else (0.,):
            solved=[self.solve(round(float(pi),12),tuple(q),h,price) for pi,q in zip(p,queues)]
            bound=price*k*h+sum(x[0] for x in solved)
            if best is None or bound<best[0]-1e-12:
                best=(bound,price,np.asarray([x[1] for x in solved]))
        return best


@lru_cache(maxsize=8)
def solver(p01,p11):return DestinationDP(p01,p11)


def priced_select(p,queues,t,k,p01,p11,horizon=32,priced=True):
    relative=[tuple((v,d-t) for v,d in q) for q in queues]
    h=min(horizon-t,max((d for q in relative for _,d in q),default=0),8)
    _,_,bids=solver(p01,p11).evaluate(p,relative,h,k,priced)
    eligible=[i for i,q in enumerate(queues) if q]
    return np.asarray(sorted(eligible,key=lambda i:(-bids[i],i))[:k],dtype=int)
