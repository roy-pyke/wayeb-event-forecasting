import math
import numpy as np
from scipy.stats import qmc
from sklearn.cluster import KMeans
from queryforecast.estimators import root, children
from pooling import pooled, partition


def sampling(source, mon, q, budget, rng, policy):
    source.rows = 0
    initial = root(source, q)
    fixed = mon.fixed(initial.state)
    if fixed is not None: return fixed, {'rows': 0}
    n = budget//mon.H
    arithmetic = policy.startswith('arithmetic')
    if arithmetic:
        orders = [rng.permutation(5) if policy == 'arithmetic_permuted' else np.arange(5)
                  for _ in range(mon.H)]
        codes = (np.arange(n)/n + rng.random()) % 1
    elif policy == 'sobol':
        points = qmc.Sobol(mon.H, scramble=True, seed=int(rng.integers(2**31))).random_base2(
            math.ceil(math.log2(n)))[:n]
    elif policy == 'lhs':
        points = np.stack([(rng.permutation(n)+rng.random(n))/n for _ in range(mon.H)], 1)
    else: raise ValueError(policy)
    result = np.zeros((n, mon.d))
    pending = [(i, initial) for i in range(n)]
    while pending:
        active = []
        for i, node in pending:
            y = mon.fixed(node.state)
            if y is None: active.append((i, node))
            else: result[i] = y
        if not active: break
        hidden, prob = source.evaluate([v.hidden for _, v in active], [v.last for _, v in active])
        pending = []
        for j, (i, node) in enumerate(active):
            branch = children(mon, node, hidden[j], prob[j])
            fixed = [mon.fixed(v.state) for v in branch]
            if not arithmetic and all(v is not None for v in fixed):
                result[i] = prob[j] @ np.array(fixed)
                continue
            depth = node.state[0]
            if arithmetic:
                order = orders[depth]; cdf = np.r_[0., np.cumsum(prob[j, order])]
                pos = min(int(np.searchsorted(cdf[1:], codes[i], side='right')), 4)
                a = int(order[pos])
                codes[i] = np.clip((codes[i]-cdf[pos])/prob[j,a], 0., np.nextafter(1.,0.))
            else:
                a = min(int(np.searchsorted(np.cumsum(prob[j]), points[i,depth], side='right')), 4)
            pending.append((i, branch[a]))
    return result.mean(0), {'rows': source.rows}


def hidden_partition(mon, frontier):
    count = len({mon.codes(n.state) for n in frontier})
    hidden = np.array([n.hidden for n in frontier])
    hidden = (hidden-hidden.mean(0))/np.maximum(hidden.std(0), .01)
    last = np.eye(6)[[n.last for n in frontier]]
    q = np.eye(len(mon.next))[[n.state[1] for n in frontier]]
    bits = mon.vectors([n.state[3] for n in frontier])
    depth = np.array([n.state[0]/mon.H for n in frontier])[:,None]
    x = np.concatenate([v/math.sqrt(v.shape[1]) for v in [hidden,last,q,bits,depth]], 1)
    labels = KMeans(n_clusters=count, random_state=20261023, n_init=5, max_iter=100).fit_predict(x)
    return [[n for n,label in zip(frontier,labels) if label == k] for k in sorted(set(labels))]


def clustered(source, mon, q, budget, rng):
    # Inject only a partition function into the unchanged pooling estimator.
    # This module runs sequentially; restore even if a baseline call fails.
    import pooling
    previous = pooling.partition
    try:
        pooling.partition = lambda mon, frontier, policy: hidden_partition(mon, frontier)
        return pooled(source, mon, q, budget, rng, 'hidden_cluster')
    finally: pooling.partition = previous
