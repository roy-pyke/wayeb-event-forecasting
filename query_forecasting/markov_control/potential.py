"""Stronger conventional proxy controls; every neural proxy call is charged."""
import numpy as np


def proxy(source, horizon):
    hidden,p0=source.evaluate([source.initial],[5])
    kernels=np.repeat(p0[:,None,:],horizon*6,axis=0).reshape(horizon,6,5)
    backbone=hidden[0];choice=int(np.argmax(p0[0]))
    for depth in range(1,horizon):
        h,p=source.evaluate([backbone]*5,list(range(5)))
        kernels[depth,:5]=p
        backbone=h[choice];choice=int(np.argmax(p[choice]))
    return hidden,p0,kernels


class MarkovPotential:
    def __init__(self, mon, kernels):
        self.mon=mon;self.tables=[]
        for m in mon.monitors:
            terminal=((m.final[:,None]>>np.arange(m.P))&1).astype(bool)
            hit=terminal[m.next].copy();hit[:,4]=False
            family=[]
            for horizon in mon.horizons:
                table=np.zeros((horizon+1,len(m.next),6,m.P))
                for depth in reversed(range(horizon)):
                    following=np.stack([table[depth+1,m.next[:,a],a] for a in range(5)],axis=1)
                    outcomes=np.where(hit,1.,following)
                    table[depth]=np.einsum('la,qaj->qlj',kernels[depth],outcomes)
                family.append(table)
            self.tables.append(family)

    def __call__(self, nodes):
        mon=self.mon;states=[n.state for n in nodes]
        result=mon.vectors([s[3] for s in states])
        qs=np.array([mon.decode(s[1]) for s in states]);depth=np.array([s[0] for s in states])
        hits=np.array([s[2] for s in states]);last=np.array([n.last for n in nodes])
        for j,horizon in enumerate(mon.horizons):
            ix=np.flatnonzero(depth<horizon)
            if not len(ix):continue
            for k,m in enumerate(mon.monitors):
                offset=int(mon.offsets[k]);cols=j*mon.P+offset+np.arange(m.P)
                values=self.tables[k][j][depth[ix],qs[ix,k],last[ix]]
                done=((hits[ix,None]>>(offset+np.arange(m.P)))&1).astype(bool)
                result[np.ix_(ix,cols)]=np.where(done,1.,values)
        return result
