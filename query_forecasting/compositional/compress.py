"""Positive, unbiased finite-population compression with preserved moments.

Nullspace flight is a classical balanced-sampling/recombination construction.
The incremental basis update avoids a fresh SVD for every discarded history.
"""
import numpy as np
from scipy.linalg import qr


def compress(weights, features, target, rng):
    weights = np.asarray(weights,float).copy()
    original = weights.copy()
    features = np.asarray(features,float)
    matrix = np.r_[np.ones((1,len(weights))), features.T]
    if len(weights) <= target:
        return weights, {'moves':0,'moment_error':0.,'rank':0}
    _, singular, vh = np.linalg.svd(matrix,full_matrices=False)
    rank = int(np.sum(singular > singular[0]*1e-11))
    if target < rank: raise ValueError('particle budget below moment rank')
    a = vh[:rank]
    moves = 0
    while np.count_nonzero(weights) > target:
        active = np.flatnonzero(weights > 0)
        # Rebuild on the active columns, since the active rank can decrease.
        _, s, v = np.linalg.svd(a[:,active],full_matrices=False)
        r = int(np.sum(s > max(s[0],1e-30)*1e-11))
        local = v[:r]
        _,_,pivots = qr(local,mode='economic',pivoting=True)
        basis = list(map(int,pivots[:r]))
        inverse = np.linalg.inv(local[:,basis])
        rest = [int(j) for j in np.argsort(weights[active]) if int(j) not in set(basis)]
        progressed = False
        for j in rest:
            if np.count_nonzero(weights) <= target: break
            indices = active[basis+[j]]
            coeff = inverse @ local[:,j]
            u = np.r_[-coeff,1.]
            positive, negative = np.flatnonzero(u>1e-13),np.flatnonzero(u < -1e-13)
            if not len(positive) or not len(negative): break
            plus_ratios = weights[indices[negative]]/(-u[negative])
            minus_ratios = weights[indices[positive]]/u[positive]
            ip = int(negative[np.argmin(plus_ratios)])
            im = int(positive[np.argmin(minus_ratios)])
            plus,minus = float(plus_ratios.min()),float(minus_ratios.min())
            if plus+minus <= 0: break
            use_plus = rng.random() < minus/(plus+minus)
            delta, killed = (plus,ip) if use_plus else (-minus,im)
            weights[indices] += delta*u
            weights[indices[killed]] = 0.
            if weights.min() < -1e-11: raise AssertionError('negative mass')
            weights[weights < 0] = 0.
            moves += 1; progressed = True
            if killed < r:
                if abs(coeff[killed]) < 1e-10: break
                correction = coeff.copy(); correction[killed] -= 1.
                inverse -= np.outer(correction,inverse[killed])/coeff[killed]
                basis[killed] = j
            if np.any(weights[active[basis]] <= 0) or moves % 32 == 0:
                break  # safely refresh the numerical basis
        if not progressed: raise AssertionError('no feasible compression move')
    error = float(np.max(np.abs(matrix @ (weights-original))))
    if error > 2e-9: raise AssertionError(f'moment drift {error}')
    return weights, {'moves':moves,'moment_error':error,'rank':rank}
