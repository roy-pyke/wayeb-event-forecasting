"""Outcome-free bounds on the excess Brier loss of cached-context forecasts."""
import numpy as np
from functools import lru_cache


def joint_bound(cached, full, feasible):
    p, f = np.asarray(cached), np.asarray(full)
    p, f = p.reshape(-1), f.reshape(-1)
    if p.shape != f.shape or feasible.shape[1] != len(p):
        raise ValueError('certificate dimensions differ')
    return float(np.max((np.sum(p*p-f*f) - 2*feasible@(p-f))/len(p)))


def bernoulli_bound(cached, full):
    p, f = np.asarray(cached), np.asarray(full)
    return float(np.mean(np.maximum(p*p-f*f, (1-p)**2-(1-f)**2)))


def cdf_bound(cached, full):
    p, f = np.asarray(cached), np.asarray(full)
    d = p-f
    tail = np.concatenate([np.cumsum(d[:,::-1], axis=1)[:,::-1], np.zeros((len(p),1))],axis=1)
    return float(np.max(np.sum(p*p-f*f, axis=1)[:,None]-2*tail,axis=1).mean()/p.shape[1])


@lru_cache(maxsize=16)
def static_nested_profiles(patterns=3,horizons=3):
    from .automata import PatternFamily
    assert patterns==3
    return PatternFamily().static_profiles(horizons)


def batch_bounds(cached,full,states,family,horizons):
    """Vectorized exact certificates for many queries with a fixed cache lag."""
    p=np.asarray(cached,dtype=float);f=np.asarray(full,dtype=float);d=p-f
    base=(p*p-f*f).sum((1,2))
    bern=np.maximum(p*p-f*f,(1-p)**2-(1-f)**2).mean((1,2))
    tail=np.concatenate([np.cumsum(d[:,:,::-1],2)[:,:,::-1],np.zeros((len(p),3,1))],2)
    cdf=((p*p-f*f).sum(2)-2*tail.min(2)).mean(1)/3
    nested=(base-2*(d.reshape(-1,9)@static_nested_profiles().T).min(1))/9
    joint=np.empty(len(p))
    for q in np.unique(states):
        mask=states==q;y=family.feasible(int(q),tuple(horizons))
        joint[mask]=(base[mask]-2*(d[mask].reshape(-1,9)@y.T).min(1))/9
    return {'bernoulli':bern,'cdf':cdf,'nested':nested,'joint':joint,
            'delta':np.max(np.abs(d),axis=(1,2))}
