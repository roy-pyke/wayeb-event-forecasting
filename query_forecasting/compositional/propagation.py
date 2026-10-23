from collections import defaultdict
from dataclasses import dataclass, replace
import numpy as np
from monitor import HarmonicPotential
from compress import compress


@dataclass
class Particle:
    mass: float
    state: tuple
    hidden: np.ndarray
    last: int
    path: tuple


def successors(mon, node, hidden, prob):
    return [Particle(node.mass*prob[a],mon.advance(*node.state,a),hidden,a,node.path+(a,))
            for a in range(5)]


def combine_identical_histories(nodes):
    combined = {}
    for n in nodes:
        if n.path in combined:
            old = combined[n.path]; combined[n.path] = replace(old,mass=old.mass+n.mass)
        else: combined[n.path] = n
    return list(combined.values())


def weighted_ensemble(mon, nodes, target, rng):
    grouped = defaultdict(list)
    for n in nodes: grouped[n.state].append(n)
    groups = list(grouped.values())
    if len(groups) > target:
        groups.sort(key=lambda g: sum(n.mass for n in g),reverse=True)
        groups = groups[:target-1]+[sum(groups[target-1:],[])]
    mass = np.array([sum(n.mass for n in g) for g in groups])
    cap = np.array([max(mon.uncertainty(*n.state[:3]) for n in g) for g in groups])
    counts = np.ones(len(groups),int)
    for _ in range(target-len(groups)):
        i = int(np.argmax(mass**2*cap/(counts*(counts+1)))); counts[i] += 1
    result = []
    for group,total,count in zip(groups,mass,counts):
        cdf = np.cumsum([n.mass for n in group])/total
        u = (np.arange(count)+rng.random())/count
        indices = np.minimum(np.searchsorted(cdf,u,side='right'),len(group)-1)
        result.extend(replace(group[i],mass=total/count) for i in indices)
    return combine_identical_histories(result)


def propagate(source, mon, q, budget, rng, policy='harmonic', certificate=False):
    source.rows = 0
    initial = Particle(1.,(0,int(q),0,0),source.initial,5,())
    fixed = mon.fixed(initial.state)
    if fixed is not None:
        return fixed, {'rows':0,'mass_error':0.,'moment_error':0.,'moves':0,'support':1}
    h0,p0 = source.evaluate([initial.hidden],[5])
    phi = HarmonicPotential(mon,p0[0]) if policy == 'harmonic' else None
    nodes = [initial]; answer = np.zeros(mon.d); settled_mass = 0.
    moment_error = 0.; moves = 0; witnesses = []
    for depth in range(mon.H):
        nodes = combine_identical_histories(nodes)
        hidden,prob = (h0,p0) if depth == 0 else source.evaluate([n.hidden for n in nodes],[n.last for n in nodes])
        live = []
        for j,node in enumerate(nodes):
            for child in successors(mon,node,hidden[j],prob[j]):
                fixed = mon.fixed(child.state)
                if fixed is None: live.append(child)
                else:
                    answer += child.mass*fixed; settled_mass += child.mass
                    if certificate: witnesses.append((child.mass,child.path+(4,)*(mon.H-len(child.path))))
        if not live: break
        remaining = mon.H-depth-1
        target = int((budget-source.rows)//remaining)
        if target < 1: raise AssertionError('insufficient continuation budget')
        if len(live) > target:
            if policy == 'monitor_we':
                live = weighted_ensemble(mon,live,target,rng)
            else:
                f = phi([n.state for n in live]) if policy == 'harmonic' else np.empty((len(live),0))
                weights,meta = compress([n.mass for n in live],f,target,rng)
                live = [replace(n,mass=float(w)) for n,w in zip(live,weights) if w > 0]
                moves += meta['moves']; moment_error = max(moment_error,meta['moment_error'])
        if abs(settled_mass+sum(n.mass for n in live)-1.) > 2e-9:
            raise AssertionError('lost positive probability mass')
        nodes = live
    if source.rows > budget or abs(settled_mass-1.) > 2e-9:
        raise AssertionError('budget or probability conservation violation')
    result = {'rows':source.rows,'mass_error':abs(settled_mass-1.),'moment_error':moment_error,
              'moves':moves,'support':len(witnesses)}
    if certificate: result['witnesses'] = witnesses
    return answer,result


def sample_count(budget, horizon):
    # Deterministic worst-case cost with exact within-call shared-prefix caching.
    n = 1
    while sum(min(5**d,n+1) for d in range(horizon)) <= budget: n += 1
    return n


def sample(source, mon, q, budget, rng, policy='mc'):
    source.rows = 0
    initial = Particle(1.,(0,int(q),0,0),source.initial,5,())
    fixed = mon.fixed(initial.state)
    if fixed is not None: return fixed,{'rows':0,'samples':0}
    n = sample_count(budget,mon.H)
    use_control = policy != 'mc'; lhs = policy == 'potential_lhs'
    h0,p0 = source.evaluate([initial.hidden],[5])
    phi = HarmonicPotential(mon,p0[0]) if use_control else None
    values = np.repeat(phi([initial.state]),n,axis=0) if use_control else np.zeros((n,mon.d))
    pending = [(i,initial) for i in range(n)]
    for depth in range(mon.H):
        unique = {}; active = []
        for i,node in pending:
            y = mon.fixed(node.state)
            if y is not None:
                if not use_control: values[i] = y
            else:
                active.append((i,node)); unique[node.path] = node
        if not active: break
        nodes = list(unique.values())
        hidden,prob = (h0,p0) if depth == 0 else source.evaluate([v.hidden for v in nodes],[v.last for v in nodes])
        cache = {}
        for j,node in enumerate(nodes):
            branches = successors(mon,node,hidden[j],prob[j])
            fixed = [mon.fixed(c.state) for c in branches]
            done = all(v is not None for v in fixed)
            if use_control:
                correction = prob[j] @ phi([c.state for c in branches])-phi([node.state])[0]
            elif done: correction = prob[j] @ np.array(fixed)
            else: correction = None
            cache[node.path] = (branches,prob[j],correction,done)
        # Stratify all n trajectory uniforms; use indices of surviving paths.
        draws = (rng.permutation(n)+rng.random(n))/n if lhs else rng.random(n)
        pending = []
        for i,node in active:
            branches,p,correction,done = cache[node.path]
            if use_control: values[i] += correction
            elif done: values[i] = correction
            if done: continue
            a = min(int(np.searchsorted(np.cumsum(p),draws[i])),4)
            pending.append((i,branches[a]))
    if source.rows > budget: raise AssertionError('prefix-cached sampling exceeded hard budget')
    return values.mean(0),{'rows':source.rows,'samples':n}
