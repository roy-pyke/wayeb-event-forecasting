"""Classical nullspace flight with local inverse refreshes.

Refreshing an r by r basis costs O(r^3); repeatedly decomposing all M active
columns costs O(M r^2). Full rank discovery is needed only when the active
basis degenerates. The randomized two-boundary move itself is unchanged.
"""
import numpy as np
from scipy.linalg import qr,svd


def rowspace(a):
    try:_,s,v=np.linalg.svd(a,full_matrices=False)
    except np.linalg.LinAlgError:
        _,s,v=svd(a,full_matrices=False,lapack_driver='gesvd')
    r=int(np.sum(s>max(s[0],1e-30)*1e-11))
    return v[:r],r


def recombine(weights, features, target, rng):
    w=np.asarray(weights,float).copy();original=w.copy()
    matrix=np.r_[np.ones((1,len(w))),np.asarray(features,float).T]
    if len(w)<=target:return w,{'moves':0,'moment_error':0.,'rank':0,'rebuilds':0}
    a,rank=rowspace(matrix)
    if target<rank:raise ValueError('particle budget below moment rank')
    moves=0;rebuilds=0;active_count=int(np.count_nonzero(w));scale=max(float(w.sum()),1e-30)
    while active_count>target:
        active=np.flatnonzero(w>0)
        local,r=rowspace(a[:,active]);rebuilds+=1
        _,_,pivots=qr(local,mode='economic',pivoting=True)
        basis=np.asarray(pivots[:r],int)
        inverse=np.linalg.inv(local[:,basis]);basis_set=set(basis)
        rest=[int(j) for j in np.argsort(w[active]) if j not in basis_set]
        progressed=False
        for j in rest:
            if active_count<=target:break
            if w[active[j]]<=0:continue
            indices=np.r_[active[basis],active[j]]
            coeff=inverse@local[:,j];u=np.r_[-coeff,1.]
            pos=np.flatnonzero(u>1e-13);neg=np.flatnonzero(u< -1e-13)
            if not len(pos) or not len(neg):break
            pr=w[indices[neg]]/(-u[neg]);mr=w[indices[pos]]/u[pos]
            ip=int(neg[np.argmin(pr)]);im=int(pos[np.argmin(mr)])
            plus=float(pr.min());minus=float(mr.min())
            if plus+minus<=0:break
            delta,killed=(plus,ip) if rng.random()<minus/(plus+minus) else (-minus,im)
            previous=int(np.count_nonzero(w[indices]))
            w[indices]+=delta*u;w[indices[killed]]=0.
            if w[indices].min()< -1e-11*scale:raise AssertionError('negative weight')
            w[indices]=np.maximum(w[indices],0.)
            active_count+=int(np.count_nonzero(w[indices]))-previous
            moves+=1;progressed=True
            if killed<r:
                if abs(coeff[killed])<1e-10:break
                correction=coeff.copy();correction[killed]-=1.
                inverse-=np.outer(correction,inverse[killed])/coeff[killed]
                basis[killed]=j
            if np.any(w[active[basis]]<=0):break
            if moves%32==0:
                try:inverse=np.linalg.inv(local[:,basis])
                except np.linalg.LinAlgError:break
                if np.max(np.abs(inverse@local[:,basis]-np.eye(r)))>1e-7:break
        if not progressed:raise AssertionError('no feasible nullspace move')
    error=float(np.max(np.abs(matrix@(w-original))))
    if error>2e-9:raise AssertionError(f'moment drift {error}')
    return w,{'moves':moves,'moment_error':error,'rank':rank,'rebuilds':rebuilds}
