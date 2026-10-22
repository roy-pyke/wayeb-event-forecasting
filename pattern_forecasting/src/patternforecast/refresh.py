"""Exact myopic sparse refresh under shared feasible-outcome certificates."""
from functools import lru_cache
import itertools
import numpy as np
from .certificates import static_nested_profiles


@lru_cache(maxsize=12)
def masks_by_size(dimension):
    result=[]
    for size in range(dimension+1):
        rows=[]
        for selected in itertools.combinations(range(dimension),size):
            row=np.zeros(dimension,dtype=bool);row[list(selected)]=True;rows.append(row)
        result.append(np.array(rows))
    return result


def candidate_bound(candidate,full,profiles,mode):
    p=np.asarray(candidate,dtype=float).reshape(-1,3,3)
    f=np.asarray(full,dtype=float).reshape(3,3)
    d=p-f;constant=(p*p-f*f).sum((1,2))
    if mode=='cdf':
        tail=np.concatenate([np.cumsum(d[:,:,::-1],2)[:,:,::-1],np.zeros((len(p),3,1))],2)
        return (constant-2*tail.min(2).sum(1))/9
    return (constant-2*(d.reshape(-1,9)@profiles.T).min(1))/9


def valid_candidates(candidates,validator=None):
    cube=np.asarray(candidates).reshape(-1,3,3)
    valid=(np.diff(cube,axis=2)>=-1e-7).all((1,2))
    for child,parent in inclusion_pairs():valid&=(cube[:,child]<=cube[:,parent]+1e-7).all(1)
    if validator is not None:valid&=validator(candidates)
    return valid


def choose_patch(cached,full,profiles,mode,epsilon,sparse=True,validator=None,strategy='exact'):
    """Minimum coordinates in the declared action space, not trajectory optimality."""
    p=np.asarray(cached,dtype=float).ravel();f=np.asarray(full,dtype=float).ravel()
    if candidate_bound(p,f,profiles,mode)[0]<=epsilon+1e-12:
        return p.copy(),np.zeros(9,dtype=bool),float(candidate_bound(p,f,profiles,mode)[0])
    if not sparse: return f.copy(),np.ones(9,dtype=bool),0.0
    if strategy.startswith('greedy'):
        mask=np.zeros(9,dtype=bool)
        order=np.argsort(-np.abs(f-p),kind='stable')
        for size in range(9):
            if strategy=='greedy_delta':mask[order[size]]=True
            else:
                available=np.flatnonzero(~mask)
                trials=np.repeat(mask[None,:],len(available),axis=0)
                trials[np.arange(len(available)),available]=True
                costs=candidate_bound(np.where(trials,f,p),f,profiles,mode)
                mask=trials[int(np.argmin(costs))]
            candidate=np.where(mask,f,p)
            b=float(candidate_bound(candidate,f,profiles,mode)[0])
            if b<=epsilon+1e-12 and valid_candidates(candidate,validator)[0]:return candidate,mask,b
        raise ArithmeticError('Greedy full replacement invalid')
    for masks in masks_by_size(9)[1:]:
        candidates=np.where(masks,f,p)
        # Projection/float32 wire rounding has a common 1e-7 feasibility tolerance.
        # The loss certificate is still evaluated on the actual rounded vector.
        valid=valid_candidates(candidates,validator)
        candidates=candidates[valid];active=masks[valid]
        if not len(candidates): continue
        b=candidate_bound(candidates,f,profiles,mode)
        index=int(np.argmin(b))
        if b[index]<=epsilon+1e-12: return candidates[index],active[index],float(b[index])
    raise ArithmeticError(f'Full refresh invalid: full={f}, polytope={None if validator is None else validator(f)}')


@lru_cache(maxsize=1)
def inclusion_pairs():
    from .automata import PatternFamily
    return PatternFamily().inclusion_pairs()


def refresh_replay(data,full,family,horizons,mode,epsilon,sparse,full_coherence=False,strategy='exact'):
    n=len(full);out=np.empty_like(full);packets=np.zeros(n,dtype=bool)
    certificates=np.zeros(n);coords=np.zeros(n,dtype=int);ages=np.zeros((n,9),dtype=int)
    sets=[family.feasible(q,tuple(horizons)) for q in range(len(family.states))]
    possible=np.array([y.max(0) for y in sets])
    reference=np.asarray(full).reshape(-1,9).copy()*possible[data['q']]
    fixed=static_nested_profiles()
    polytopes=None
    if full_coherence:
        from .polytope import FeasiblePolytope
        polytopes=[FeasiblePolytope(y) for y in sets]
        for q in np.unique(data['q']):
            ix=data['q']==q;reference[ix]=polytopes[q].project(reference[ix])
        reference=reference.astype(np.float32).astype(float)
    cached=np.zeros(9);last_update=np.zeros(9,dtype=int)
    for i in range(n):
        q=int(data['q'][i]);cached=cached*possible[q]
        if polytopes is not None: cached=polytopes[q].project(cached).astype(np.float32).astype(float)
        profiles=fixed if mode=='nested' else sets[q]
        if i==0 or data['segment'][i]!=data['segment'][i-1]:
            cached=reference[i].copy();patch=np.ones(9,dtype=bool);certificate=0.0
        else:
            cached,patch,certificate=choose_patch(cached,reference[i],profiles,mode,epsilon,sparse,
                               validator=None if polytopes is None else polytopes[q].contains,strategy=strategy)
        packets[i]=patch.any();coords[i]=patch.sum();certificates[i]=certificate
        last_update[patch]=i;ages[i]=i-last_update;out[i]=cached.reshape(3,3)
    bytecost=packets.astype(int)*(26 if sparse else 24)+coords*4
    return {'pred':out,'full':reference.reshape(-1,3,3),'sends':packets,'certificate':certificates,
            'coordinates':coords,'bytes':bytecost,'coordinate_age':ages}
