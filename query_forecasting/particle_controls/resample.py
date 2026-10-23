"""Conventional SMC and Fearnhead-Clifford discrete-particle resampling."""
import numpy as np


def tree_order(features,weights):
    def recurse(ids):
        if len(ids)<=2:return ids
        x=features[ids];w=weights[ids];w=w/w.sum()
        mean=w@x;var=w@((x-mean)**2)
        axis=int(np.argmax(var))
        if var[axis]<1e-25:return ids
        ids=ids[np.argsort(x[:,axis],kind='stable')];cut=len(ids)//2
        return np.r_[recurse(ids[:cut]),recurse(ids[cut:])]
    return recurse(np.arange(len(weights)))


def resample(weights,target,rng,policy='systematic',features=None):
    w=np.asarray(weights,float)
    if len(w)<=target:return w.copy()
    order=tree_order(features,w) if features is not None else np.arange(len(w))
    result=np.zeros(len(w));remaining=np.ones(len(w),bool);slots=target
    if policy.startswith('discrete'):
        while True:
            threshold=w[remaining].sum()/slots
            heavy=remaining&(w>=threshold)
            if not heavy.any():break
            result[heavy]=w[heavy];remaining[heavy]=False;slots-=int(heavy.sum())
            if slots==0:
                if w[remaining].sum()>1e-12:raise AssertionError('unallocated mass')
                return result
    ids=order[remaining[order]];total=float(w[ids].sum())
    u=(np.arange(slots)+(rng.random(slots) if policy=='stratified' else rng.random()))/slots
    cdf=np.cumsum(w[ids])/total
    selected=ids[np.minimum(np.searchsorted(cdf,u,side='right'),len(ids)-1)]
    np.add.at(result,selected,total/slots)
    if policy.startswith('discrete') and len(set(selected))!=slots:raise AssertionError('duplicate discrete particle')
    if np.count_nonzero(result)>target or abs(result.sum()-w.sum())>2e-12:raise AssertionError('resampling mass or count')
    return result
