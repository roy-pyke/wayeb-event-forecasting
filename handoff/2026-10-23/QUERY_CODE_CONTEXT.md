# 当前候选与强对照的完整代码摘录

按文件逐字拼接，供不能解压附件时审阅。完整项目的其余代码/测试在 ZIP。未执行任何实验。

## `query_forecasting/src/queryforecast/model.py`
SHA256 `b55f6321fa43448148a47c235d1e1290125cf9706d6845d8c66f166c5508eccb`

```python
import numpy as np
import torch
from torch import nn


class WorldModel(nn.Module):
    def __init__(self, inputs, hidden=48, embedding=8):
        super().__init__()
        self.initial = nn.Linear(inputs, hidden)
        self.embedding = nn.Embedding(6, embedding)
        self.gru = nn.GRU(embedding, hidden, batch_first=True)
        self.output = nn.Linear(hidden, 5)

    def forward(self, context, tokens):
        h = torch.tanh(self.initial(context)).unsqueeze(0)
        z, _ = self.gru(self.embedding(tokens), h)
        return self.output(z)


class Source:
    """One call row includes recurrent update AND next-symbol distribution."""
    def __init__(self, checkpoint, context):
        self.model = WorldModel(checkpoint['inputs'])
        self.model.load_state_dict(checkpoint['state'])
        self.model.eval()
        x = np.nan_to_num((context-checkpoint['mean'])/checkpoint['scale'], nan=0.0)
        x = np.clip(x, -10, 10).astype(np.float32)
        with torch.no_grad():
            self.initial = torch.tanh(self.model.initial(torch.tensor(x))).numpy()
        self.rows = 0

    def evaluate(self, h, last):
        self.rows += len(last)
        with torch.no_grad():
            h = torch.as_tensor(np.asarray(h), dtype=torch.float32).unsqueeze(0)
            a = torch.as_tensor(last, dtype=torch.long).reshape(-1, 1)
            z, _ = self.model.gru(self.model.embedding(a), h)
            p = torch.softmax(self.model.output(z[:, 0]).double(), dim=-1)
            return z[:, 0].numpy(), p.numpy()
```

## `query_forecasting/src/queryforecast/data.py`
SHA256 `91979cc23f4dba1039de9389bbd5f26bac582949a11f898fe55543b3e95ccab1`

```python
"""Only previously exposed train/calibration/development caches are accepted."""
import json
import numpy as np
import pandas as pd
from .common import ROOT, CACHE, PROTOCOL, digest, save
from .monitor import Monitor


def load(domain, split):
    if domain not in ('air', 'power') or split not in ('train', 'calibrate', 'development'):
        raise ValueError('confirmation and reserve are closed')
    folder = ROOT / '.cache/pattern_forecasting/multisignal' / domain
    cache = CACHE / domain / f'{split}.npz'
    source = folder / f'{split}.npz'
    business = folder / f'{split}-business.csv'
    identity = {'input': digest(source), 'events': digest(business),
                'data_source': digest(__file__), 'horizon': PROTOCOL['model_training_horizon']}
    if cache.exists() and json.loads(cache.with_suffix('.json').read_text()) == identity:
        return dict(np.load(cache, allow_pickle=False))
    old = dict(np.load(source, allow_pickle=False))
    H = PROTOCOL['model_training_horizon']
    keep = np.flatnonzero(old['coverage'] >= H)
    # Sampling never conditions on future outcomes or pattern progress.
    limit = {'train': PROTOCOL['model']['train_origins'],
             'calibrate': PROTOCOL['model']['calibration_origins'], 'development': 48}[split]
    rng = np.random.default_rng(PROTOCOL['seed'])
    idx = np.sort(rng.choice(keep, min(limit, len(keep)), replace=False))
    data = {k: old[k][idx] for k in ['t', 'segment', 'entity']}
    tele = old['telemetry'][idx].reshape(len(idx), -1)
    data['x'] = np.concatenate([old['business'][idx], tele,
                               np.isfinite(tele).astype(float)], axis=1).astype(np.float32)
    data['y'] = np.full((len(idx), H), 4, dtype=np.int64)
    events = pd.read_csv(business)
    native = 3600 if domain == 'air' else 60
    monitors = [Monitor(name) for name in PROTOCOL['families']]
    data['q'] = np.zeros((len(idx), len(monitors)), dtype=np.int64)
    groups = events.groupby(['entity', 'segment'], sort=False)
    pairs = set(zip(data['entity'], data['segment']))
    for entity, segment in pairs:
        rows = np.flatnonzero((data['entity'] == entity) & (data['segment'] == segment))
        try: group = groups.get_group((entity, segment))
        except KeyError: continue
        ts = group['timestamp'].to_numpy()
        symbols = np.array([ord(s)-65 for s in group['symbol']], dtype=np.int64)
        future = data['t'][rows, None] + native*np.arange(1, H+1)
        pos = np.searchsorted(ts, future)
        clipped = np.minimum(pos, len(ts)-1)
        valid = (pos < len(ts)) & (ts[clipped] == future)
        data['y'][rows] = np.where(valid, symbols[clipped], 4)
        current = np.searchsorted(ts, data['t'][rows], side='right')-1
        for j, mon in enumerate(monitors):
            q = 0; states = []
            for a in symbols:
                q = int(mon.next[q, a]); states.append(q)
            data['q'][rows, j] = np.where(current >= 0, np.asarray(states)[np.maximum(current, 0)], 0)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, **data)
    save(cache.with_suffix('.json'), identity)
    return data
```

## `query_forecasting/compositional/monitor.py`
SHA256 `c4be6b98b2af1e9f6ffcf6321b1e60ba09c111bca1664f3e21e3de686e39f253`

```python
"""Separate finite-state query potentials, without a joint-language powerset."""
from functools import lru_cache
import numpy as np


class JointMonitor:
    def __init__(self, monitors):
        self.monitors = monitors
        self.horizons = monitors[0].horizons
        assert all(m.horizons == self.horizons for m in monitors)
        self.H = max(self.horizons)
        self.offsets = np.cumsum([0]+[m.P for m in monitors])
        self.P = int(self.offsets[-1]); self.d = self.P*len(self.horizons)
        if self.d > 63: raise ValueError('bit-vector implementation currently supports <=63 outputs')
        self.sizes = [len(m.next) for m in monitors]
        self.possible = []
        for m in monitors:
            table = np.zeros((self.H+1, len(m.next), m.P), bool)
            terminal = ((m.final[:,None] >> np.arange(m.P)) & 1).astype(bool)
            for r in range(1, self.H+1):
                table[r] = np.any(terminal[m.next[:,:4]] | table[r-1,m.next[:,:4]], axis=1)
            self.possible.append(table)

    def encode(self, qs):
        code, mult = 0, 1
        for q, size in zip(qs, self.sizes):
            code += int(q)*mult; mult *= size
        return code

    @lru_cache(maxsize=None)
    def decode(self, code):
        qs = []
        for size in self.sizes:
            qs.append(code % size); code //= size
        return tuple(qs)

    @lru_cache(maxsize=None)
    def step(self, q, a):
        qs = self.decode(q)
        nexts = [int(m.next[s,a]) for m,s in zip(self.monitors,qs)]
        hits = sum(int(m.final[s]) << int(offset) for m,s,offset in
                   zip(self.monitors,nexts,self.offsets)) if a < 4 else 0
        return self.encode(nexts), hits

    def advance(self, depth, q, hits, code, a):
        nq, flags = self.step(q,a); hits |= flags
        if depth+1 in self.horizons:
            code |= hits << (self.horizons.index(depth+1)*self.P)
        return depth+1,nq,hits,code

    def vectors(self, codes):
        return ((np.asarray(codes,np.uint64)[:,None] >> np.arange(self.d,dtype=np.uint64)) & 1).astype(float)

    @lru_cache(maxsize=None)
    def bounds(self, state):
        depth,q,hits,code = state
        low = high = code
        qs = self.decode(q)
        for j,h in enumerate(self.horizons):
            if h <= depth: continue
            possible = hits
            for k,(s,m) in enumerate(zip(qs,self.monitors)):
                bits = self.possible[k][h-depth,s]
                possible |= sum(int(v) << int(self.offsets[k]+p) for p,v in enumerate(bits))
            low |= hits << (j*self.P); high |= possible << (j*self.P)
        return low,high

    def fixed(self, state):
        lo,hi = self.bounds(state)
        return self.vectors([lo])[0] if lo == hi else None

    def uncertainty(self, depth, q, hits):
        lo,hi = self.bounds((depth,q,hits,0))
        return (lo ^ hi).bit_count()/4.

    def targets(self, symbols, q=0):
        state = (0,q,0,0)
        for a in symbols: state = self.advance(*state,int(a))
        if state[0] != self.H: raise ValueError('wrong horizon')
        return self.vectors([state[3]])[0]


class HarmonicPotential:
    def __init__(self, mon, probabilities):
        self.mon = mon
        self.tables = []
        p = np.asarray(probabilities)
        for m in mon.monitors:
            table = np.zeros((mon.H+1,len(m.next),m.P))
            terminal = ((m.final[:,None] >> np.arange(m.P)) & 1).astype(bool)
            for r in range(1,mon.H+1):
                values = np.where(terminal[m.next[:,:4]], 1., table[r-1,m.next[:,:4]])
                table[r] = np.einsum('a,qap->qp',p[:4],values)+p[4]*table[r-1]
            self.tables.append(table)

    def __call__(self, states):
        mon = self.mon
        result = mon.vectors([s[3] for s in states])
        qs = np.array([mon.decode(s[1]) for s in states])
        depth = np.array([s[0] for s in states]); hits = np.array([s[2] for s in states])
        for j,h in enumerate(mon.horizons):
            ix = np.flatnonzero(depth < h)
            if not len(ix): continue
            for k,m in enumerate(mon.monitors):
                offset = int(mon.offsets[k]); cols = j*mon.P+offset+np.arange(m.P)
                value = self.tables[k][h-depth[ix],qs[ix,k]]
                done = ((hits[ix,None] >> (offset+np.arange(m.P))) & 1).astype(bool)
                result[np.ix_(ix,cols)] = np.where(done,1.,value)
        return result
```

## `query_forecasting/compositional/propagation.py`
SHA256 `647193e86a039156a44df0e6ab28f55a5eecee843ca06329a40a753957fc4e6f`

```python
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
```

## `query_forecasting/occupancy/features.py`
SHA256 `b3d7fb71b0b2acc355a9f4c6ee3251b6ef87b8e814638290ef88c6b627f23fad`

```python
"""Overlapping query occupancies, without factoring the path distribution.

Each pattern's hit-absorbing DFA is minimized independently. Constraints grow
with the sum of state counts, not their Cartesian product. The source history
stored on a particle is never replaced by these control features.
"""
import json
from functools import lru_cache
import numpy as np
from queryforecast.common import ROOT, PACKAGE


def family_components(monitor):
    family = monitor.family
    if family == 'heldout_structure':
        path = PACKAGE/'configs/heldout_structure/dfa.json'
    else:
        folder = ROOT/'pattern_forecasting/configs'
        if family != 'nested': folder = folder/family
        path = folder/'dfa.json'
    payload = json.loads(path.read_text())
    tables = list(payload['patterns'].values())
    states = [tuple(t['start'] for t in tables)]
    index = {states[0]: 0}
    for state in states:
        for a in payload['alphabet']:
            nxt = tuple(t['transitions'][str(s)][a] for t,s in zip(tables,state))
            if nxt not in index:
                index[nxt] = len(states); states.append(nxt)
    # Check that the independent reconstruction follows the frozen compiler.
    assert len(states) == len(monitor.next)
    for i,state in enumerate(states):
        for a,symbol in enumerate(payload['alphabet']):
            nxt = tuple(t['transitions'][str(s)][symbol] for t,s in zip(tables,state))
            assert index[nxt] == monitor.next[i,a]
    return np.array(states),tables,payload['alphabet']


def minimize_hitting(table, alphabet):
    raw = sorted(map(int,table['transitions']))
    ids = {q:i for i,q in enumerate(raw)}
    hit = len(raw); transitions = np.full((hit+1,5),hit,int)
    for q,i in ids.items():
        for a,symbol in enumerate(alphabet):
            nxt = table['transitions'][str(q)][symbol]
            transitions[i,a] = hit if nxt in table['finals'] else ids[nxt]
        transitions[i,4] = i
    classes = np.r_[np.zeros(hit,int),1]
    while True:
        labels = {}; new = []
        for q in range(hit+1):
            key = (q == hit, *map(int,classes[transitions[q]]))
            if key not in labels: labels[key] = len(labels)
            new.append(labels[key])
        new = np.array(new)
        if np.array_equal(new,classes): break
        classes = new
    absorbing = int(classes[hit])
    unhit = [c for c in sorted(set(classes)) if c != absorbing]
    remap = {c:i for i,c in enumerate(unhit)}; remap[absorbing] = len(unhit)
    return {q:remap[int(classes[i])] for q,i in ids.items()},len(unhit)


class OccupancyFeatures:
    def __init__(self, mon, order=0):
        if order not in (0,1): raise ValueError('only orders zero and one are registered')
        self.mon = mon; self.order = order
        self.components = []; self.sizes = []
        for m in mon.monitors:
            states,tables,alphabet = family_components(m)
            maps = []
            for j,t in enumerate(tables):
                mapping,unhit = minimize_hitting(t,alphabet)
                maps.append(np.array([mapping[int(q)] for q in states[:,j]]))
                self.sizes.append(unhit*(5 if order else 1)+1)
            self.components.append(np.array(maps).T)
        self.offsets = np.cumsum([0]+self.sizes)
        self.dimension = int(self.offsets[-1])+mon.d

    @lru_cache(maxsize=None)
    def cells(self, q, hits, last):
        result=[]; pattern=0
        for states,fq in zip(self.components,self.mon.decode(q)):
            for local in states[fq]:
                if (hits >> pattern) & 1:
                    cell = self.sizes[pattern]-1
                else:
                    if self.order and last not in range(5):
                        raise ValueError('source symbol required after a transition')
                    cell = int(local)*(5 if self.order else 1)+(last if self.order else 0)
                result.append(int(self.offsets[pattern])+cell); pattern += 1
        return tuple(result)

    def __call__(self, nodes):
        values = np.zeros((len(nodes),self.dimension))
        for i,node in enumerate(nodes):
            _,q,hits,_ = node.state
            values[i,list(self.cells(q,hits,node.last))] = 1.
        values[:,int(self.offsets[-1]):] = self.mon.vectors([n.state[3] for n in nodes])
        return values
```

## `query_forecasting/occupancy/recombine.py`
SHA256 `b1a397d4e53c580c2a13502850081e49291168581bac32dfa80901eaf20a9760`

```python
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
```

## `query_forecasting/occupancy/propagate.py`
SHA256 `558c4f13b93a473c913ddac453472c0ba8a642834107b0cc362d8a39ab29a248`

```python
"""Full-history moment-basis audit; no silent relaxation when rank exceeds budget."""
from dataclasses import replace
import numpy as np
from monitor import HarmonicPotential
from recombine import recombine as compress
from propagation import Particle,successors,combine_identical_histories
from features import OccupancyFeatures


class InfeasibleRank(ValueError):
    pass


def basis_propagate(source, mon, q, budget, rng, policy, certificate=False):
    source.rows=0
    initial=Particle(1.,(0,int(q),0,0),source.initial,5,())
    fixed=mon.fixed(initial.state)
    if fixed is not None:return fixed,{'rows':0,'mass_error':0.,'moment_error':0.,'max_rank':0}
    h0,p0=source.evaluate([source.initial],[5])
    if policy in ['harmonic','uniform']:
        phi=HarmonicPotential(mon,p0[0] if policy=='harmonic' else np.full(5,.2))
        feature=lambda nodes: phi([n.state for n in nodes])
    elif policy=='known_bits':feature=lambda nodes: mon.vectors([n.state[3] for n in nodes])
    elif policy in ['occupancy','occupancy_symbol']:
        feature=OccupancyFeatures(mon,int(policy=='occupancy_symbol'))
    else:raise ValueError(policy)
    nodes=[initial];answer=np.zeros(mon.d);settled=0.;error=0.;max_rank=0;witnesses=[]
    for depth in range(mon.H):
        nodes=combine_identical_histories(nodes)
        hidden,prob=(h0,p0) if depth==0 else source.evaluate([n.hidden for n in nodes],[n.last for n in nodes])
        live=[]
        for j,node in enumerate(nodes):
            for child in successors(mon,node,hidden[j],prob[j]):
                fixed=mon.fixed(child.state)
                if fixed is None:live.append(child)
                else:
                    answer+=child.mass*fixed;settled+=child.mass
                    if certificate:witnesses.append((child.mass,child.path+(4,)*(mon.H-len(child.path))))
        if not live:break
        target=int((budget-source.rows)//(mon.H-depth-1))
        if target<1:raise AssertionError('continuation budget')
        if len(live)>target:
            try:weights,meta=compress([n.mass for n in live],feature(live),target,rng)
            except ValueError as exc:
                if 'below moment rank' in str(exc):raise InfeasibleRank(str(exc)) from exc
                raise
            error=max(error,meta['moment_error']);max_rank=max(max_rank,meta['rank'])
            live=[replace(n,mass=float(w)) for n,w in zip(live,weights) if w>0]
        if abs(settled+sum(n.mass for n in live)-1.)>2e-9:raise AssertionError('mass')
        nodes=live
    if source.rows>budget or abs(settled-1.)>2e-9:raise AssertionError('budget or mass')
    meta={'rows':source.rows,'mass_error':abs(settled-1.),'moment_error':error,'max_rank':max_rank}
    if certificate:meta['witnesses']=witnesses
    return answer,meta
```

## `query_forecasting/engineering/constants.py`
SHA256 `15e887eb1e69121cb902c206e904256fec9e139bba1cb14fa67907311cb55fd7`

```python
"""Remove only exact constant controls, whose moments follow from total mass."""
import numpy as np
from recombine import recombine


def without_constants(weights,features,target,rng):
    features=np.asarray(features,float)
    variable=np.any(features!=features[0],axis=0)
    result,meta=recombine(weights,features[:,variable],target,rng)
    error=float(np.max(np.abs((result-np.asarray(weights))@features),initial=0.))
    if error>2e-9:raise AssertionError('original constraint drift after constant elimination')
    meta['moment_error']=max(meta['moment_error'],error)
    meta['removed_constant_columns']=int((~variable).sum())
    return result,meta
```

## `query_forecasting/finite_control/finite_features.py`
SHA256 `7c9d469f92e0ee0947ca649e1ef9be4b9c051bf387d3c58910a002dc8062494e`

```python
"""Finite suffix-function equivalence, not merely output-support equivalence."""
from functools import lru_cache
import numpy as np
from features import family_components


def finite_classes(table,alphabet,horizon):
    raw=sorted(map(int,table['transitions']));ids={q:i for i,q in enumerate(raw)}
    hit=len(raw);delta=np.full((hit+1,5),hit,int)
    for q,i in ids.items():
        for a,symbol in enumerate(alphabet):
            nxt=table['transitions'][str(q)][symbol]
            delta[i,a]=hit if nxt in table['finals'] else ids[nxt]
        delta[i,4]=i
    # A class is the complete Boolean function on suffixes of this length.
    classes=np.r_[np.zeros(hit,int),1];can_hit=classes.astype(bool)
    result=[({q:0 for q in raw},0)]
    for remaining in range(1,horizon+1):
        labels={};new=[]
        for q in range(hit+1):
            key=tuple(map(int,classes[delta[q]]))
            if key not in labels:labels[key]=len(labels)
            new.append(labels[key])
        classes=np.array(new);can_hit=can_hit[delta].any(1)
        # The absorbing hit and the everywhere-false function are constants.
        active=sorted(set(classes[:hit][can_hit[:hit]]))
        remap={c:i+1 for i,c in enumerate(active)}
        mapping={q:(remap[int(classes[i])] if can_hit[i] else 0) for q,i in ids.items()}
        result.append((mapping,len(active)))
    return result


class FiniteOccupancyFeatures:
    def __init__(self,mon,order=1):
        if order!=1:raise ValueError('registered finite-closure candidate is first order')
        self.mon=mon;families=[]
        for monitor in mon.monitors:
            states,tables,alphabet=family_components(monitor)
            families.append((states,[finite_classes(t,alphabet,mon.H) for t in tables]))
        self.components=[];self.sizes=[];self.offsets=[]
        for remaining in range(mon.H+1):
            components=[];sizes=[]
            for states,tables in families:
                maps=[]
                for j,series in enumerate(tables):
                    mapping,count=series[remaining]
                    maps.append(np.array([mapping[int(q)] for q in states[:,j]]))
                    sizes.append(2+5*count) # impossible cell, variable cells, hit cell
                components.append(np.array(maps).T)
            self.components.append(components);self.sizes.append(sizes)
            self.offsets.append(np.cumsum([0]+sizes))

    @lru_cache(maxsize=None)
    def cells(self,remaining,q,hits,last):
        result=[];pattern=0
        for states,fq in zip(self.components[remaining],self.mon.decode(q)):
            for local in states[fq]:
                if (hits>>pattern)&1:cell=self.sizes[remaining][pattern]-1
                elif local==0:cell=0
                else:cell=1+5*(int(local)-1)+last
                result.append(int(self.offsets[remaining][pattern])+cell);pattern+=1
        return tuple(result)

    def __call__(self,nodes):
        depths={n.state[0] for n in nodes}
        if len(depths)!=1:raise ValueError('one propagation depth required')
        remaining=self.mon.H-depths.pop();offset=int(self.offsets[remaining][-1])
        values=np.zeros((len(nodes),offset+self.mon.d))
        for i,n in enumerate(nodes):
            _,q,hits,_=n.state
            values[i,list(self.cells(remaining,q,hits,n.last))]=1.
        values[:,offset:]=self.mon.vectors([n.state[3] for n in nodes])
        return values
```

## `query_forecasting/finite_control/finite_method.py`
SHA256 `616aa6b45526291a367d16d5e12ab96ed78dff3e1e371529758a41e6db862e76`

```python
"""Isolated compiler substitution; unchanged source propagation and mass flight."""
import propagate as occupancy_module
from constants import without_constants
from finite_features import FiniteOccupancyFeatures


def finite_estimate(source,mon,q,budget,rng,certificate=False):
    original_features=occupancy_module.OccupancyFeatures
    original_compression=occupancy_module.compress
    try:
        occupancy_module.OccupancyFeatures=FiniteOccupancyFeatures
        occupancy_module.compress=without_constants
        return occupancy_module.basis_propagate(source,mon,q,budget,rng,'occupancy_symbol',certificate)
    finally:
        occupancy_module.OccupancyFeatures=original_features
        occupancy_module.compress=original_compression
```

## `query_forecasting/markov_control/potential.py`
SHA256 `7b4918489abbec0b5b05c3fead5196bb2906948de0cc56b33a9a28bd6e52a1cd`

```python
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
```

## `query_forecasting/markov_control/methods.py`
SHA256 `0aa5ec399d1da0196d26ab140c45affb8ecb58de0cdd4e36e9395a8a8c834f24`

```python
from dataclasses import replace
import numpy as np
from propagation import Particle,successors,combine_identical_histories,sample_count
from recombine import recombine
from potential import proxy,MarkovPotential


def markov_estimate(source,mon,q,budget,rng,policy,certificate=False):
    source.rows=0
    initial=Particle(1.,(0,int(q),0,0),source.initial,5,())
    fixed=mon.fixed(initial.state)
    if fixed is not None:return fixed,{'rows':0,'proxy_rows':0,'mass_error':0.,'moment_error':0.}
    h0,p0,kernels=proxy(source,mon.H);proxy_rows=source.rows
    if proxy_rows>=budget:raise ValueError('insufficient budget for proxy')
    phi=MarkovPotential(mon,kernels)
    if policy=='balanced':
        nodes=[initial];answer=np.zeros(mon.d);settled=0.;error=0.;witnesses=[]
        for depth in range(mon.H):
            nodes=combine_identical_histories(nodes)
            hidden,prob=(h0,p0) if depth==0 else source.evaluate([n.hidden for n in nodes],[n.last for n in nodes])
            live=[]
            for j,node in enumerate(nodes):
                for child in successors(mon,node,hidden[j],prob[j]):
                    fixed=mon.fixed(child.state)
                    if fixed is None:live.append(child)
                    else:
                        answer+=child.mass*fixed;settled+=child.mass
                        if certificate:witnesses.append((child.mass,child.path+(4,)*(mon.H-len(child.path))))
            if not live:break
            target=int((budget-source.rows)//(mon.H-depth-1))
            if len(live)>target:
                weights,meta=recombine([n.mass for n in live],phi(live),target,rng)
                error=max(error,meta['moment_error'])
                live=[replace(n,mass=float(w)) for n,w in zip(live,weights) if w>0]
            nodes=live
        if abs(settled-1.)>2e-9:raise AssertionError('positive mass')
        meta={'mass_error':abs(settled-1.),'moment_error':error}
        if certificate:meta['witnesses']=witnesses
    else:
        if policy not in ['cv','lhs']:raise ValueError(policy)
        n=sample_count(budget-(proxy_rows-1),mon.H)
        values=np.repeat(phi([initial]),n,axis=0);pending=[(i,initial) for i in range(n)]
        for depth in range(mon.H):
            active=[];unique={}
            for i,node in pending:
                if mon.fixed(node.state) is None:active.append((i,node));unique[node.path]=node
            if not active:break
            nodes=list(unique.values())
            hidden,prob=(h0,p0) if depth==0 else source.evaluate([v.hidden for v in nodes],[v.last for v in nodes])
            cache={}
            for j,node in enumerate(nodes):
                children=successors(mon,node,hidden[j],prob[j])
                correction=prob[j]@phi(children)-phi([node])[0]
                cache[node.path]=(children,prob[j],correction,all(mon.fixed(c.state) is not None for c in children))
            draws=(rng.permutation(n)+rng.random(n))/n if policy=='lhs' else rng.random(n)
            pending=[]
            for i,node in active:
                children,p,correction,done=cache[node.path];values[i]+=correction
                if not done:
                    a=min(int(np.searchsorted(np.cumsum(p),draws[i])),4);pending.append((i,children[a]))
        answer=values.mean(0);meta={}
    if source.rows>budget:raise AssertionError('proxy and estimation exceeded total budget')
    return answer,dict(meta,rows=source.rows,proxy_rows=proxy_rows)
```

## `query_forecasting/particle_controls/resample.py`
SHA256 `69dd38e69c3156f3e895596d344862f2c07329b7e6272c06aed487531c7b6dfe`

```python
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
```

## `query_forecasting/particle_controls/method.py`
SHA256 `3329b79db3a92dc8c9c4dccbd1dfd621bb8a2a3ffb3c8cdadaa9fc6c28743825`

```python
from dataclasses import replace
import numpy as np
from monitor import HarmonicPotential
from propagation import Particle,successors,combine_identical_histories
from resample import resample


def particle_estimate(source,mon,q,budget,rng,policy,certificate=False):
    source.rows=0
    initial=Particle(1.,(0,int(q),0,0),source.initial,5,())
    fixed=mon.fixed(initial.state)
    if fixed is not None:return fixed,{'rows':0,'mass_error':0.}
    h0,p0=source.evaluate([source.initial],[5])
    phi=HarmonicPotential(mon,p0[0]) if policy=='discrete_ordered' else None
    nodes=[initial];answer=np.zeros(mon.d);settled=0.;witnesses=[]
    for depth in range(mon.H):
        nodes=combine_identical_histories(nodes)
        hidden,prob=(h0,p0) if depth==0 else source.evaluate([n.hidden for n in nodes],[n.last for n in nodes])
        live=[]
        for j,node in enumerate(nodes):
            for child in successors(mon,node,hidden[j],prob[j]):
                fixed=mon.fixed(child.state)
                if fixed is None:live.append(child)
                else:
                    answer+=child.mass*fixed;settled+=child.mass
                    if certificate:witnesses.append((child.mass,child.path+(4,)*(mon.H-len(child.path))))
        if not live:break
        target=int((budget-source.rows)//(mon.H-depth-1))
        if len(live)>target:
            f=phi([n.state for n in live]) if phi is not None else None
            weights=resample([n.mass for n in live],target,rng,policy,f)
            live=[replace(n,mass=float(w)) for n,w in zip(live,weights) if w>0]
        nodes=live
    if source.rows>budget or abs(settled-1.)>2e-9:raise AssertionError('budget or mass')
    meta={'rows':source.rows,'mass_error':abs(settled-1.)}
    if certificate:meta['witnesses']=witnesses
    return answer,meta
```

## `query_forecasting/tests/test_occupancy.py`
SHA256 `043a53672098da5c117fe10d589b070e11f43e2619ab9a516322328faff267b7`

```python
import sys
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from test_query import IID
sys.path.insert(0,str(PACKAGE/'compositional'))
sys.path.insert(0,str(PACKAGE/'occupancy'))
from monitor import JointMonitor
from propagate import basis_propagate
from features import OccupancyFeatures
from recombine import recombine


def test_local_basis_refresh_conserves_mass_moments_and_expectation():
    rng=np.random.default_rng(102);w=np.full(180,1/180);f=rng.normal(size=(180,9))
    f=np.c_[f,f[:,2],np.ones(len(w))]
    values=[]
    for seed in range(240):
        v,meta=recombine(w,f,40,np.random.default_rng(seed))
        assert np.count_nonzero(v)<=40 and np.all(v>=0)
        np.testing.assert_allclose(v@f,w@f,atol=2e-9)
        values.append(v)
    values=np.array(values)
    assert np.all(np.abs(values.mean(0)-w)<5*values.std(0)/np.sqrt(len(values))+1e-12)


class TimeVaryingMarkov(IID):
    def __init__(self, order):
        super().__init__();self.order=order
        self.kernel=np.random.default_rng(62).dirichlet(np.ones(5),size=(8,6))
    def evaluate(self, hidden, last):
        self.rows+=len(last)
        depth=np.asarray(hidden).ravel().astype(int)
        previous=np.asarray(last) if self.order else np.zeros(len(last),int)
        return (depth+1)[:,None],self.kernel[depth,previous]


def test_transition_closed_occupancies_exact_for_whole_markov_class():
    mon=JointMonitor([Monitor(f,(2,3,5)) for f in ['nested','directional','multisignal']])
    for order,policy in [(0,'occupancy'),(1,'occupancy_symbol')]:
        source=TimeVaryingMarkov(order);truth=exact(source,mon)
        for seed in range(5):
            value,meta=basis_propagate(source,mon,0,512,np.random.default_rng(seed),policy,True)
            assert meta['max_rank']>0 and meta['rows']<=512
            np.testing.assert_allclose(value,truth,atol=2e-10)
            weights,paths=zip(*meta['witnesses'])
            assert min(weights)>=0
            np.testing.assert_allclose(np.array(weights)@np.array([mon.targets(p) for p in paths]),value,atol=1e-12)


def test_overlapping_features_are_not_product_state_bins():
    mon=JointMonitor([Monitor(f,(2,3,5)) for f in ['nested','directional','multisignal']])
    f=OccupancyFeatures(mon,1)
    assert f.dimension==sum(f.sizes)+mon.d
    assert sum(f.sizes)<np.prod(f.sizes)


def test_full_history_uniform_and_bits_remain_unbiased_for_nonmarkov_source():
    class HistorySource(IID):
        def evaluate(self,hidden,last):
            self.rows+=len(last)
            h=(np.asarray(hidden).ravel()*3+np.asarray(last)+1)%11
            p=np.exp(np.sin(h[:,None]+np.arange(5)[None,:]))
            return h[:,None],p/p.sum(1,keepdims=True)
    mon=JointMonitor([Monitor('multisignal',(1,3,4))]);source=HistorySource()
    truth=exact(source,mon)
    for policy in ['uniform','known_bits','occupancy','occupancy_symbol']:
        values=[]
        for seed in range(160):
            v,meta=basis_propagate(source,mon,0,160,np.random.default_rng(seed),policy)
            values.append(v);assert meta['rows']<=160
        values=np.array(values)
        assert np.all(np.abs(values.mean(0)-truth)<5*values.std(0)/np.sqrt(len(values))+1e-10)
```

## `query_forecasting/tests/test_finite_control.py`
SHA256 `2962ff61a237df906df9a777242a90d62c894d2b1b6d1c2658868f74b8acdff1`

```python
import sys
import itertools
import numpy as np
from queryforecast.common import PACKAGE
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from test_occupancy import TimeVaryingMarkov
from test_query import IID
for folder in ['compositional','occupancy','engineering','finite_control']:
    sys.path.insert(0,str(PACKAGE/folder))
from monitor import JointMonitor
from features import family_components
from finite_features import finite_classes
from finite_method import finite_estimate


def test_finite_classes_preserve_suffix_functions_and_all_earlier_deadlines():
    _,tables,alphabet=family_components(Monitor('directional',(1,2,3)))
    for table in tables:
        levels=finite_classes(table,alphabet,3)
        for remaining in [1,2,3]:
            mapping,_=levels[remaining];by_class={}
            for q,cell in mapping.items():
                behavior=[]
                for path in itertools.product(range(5),repeat=remaining):
                    current=q;hit=False;outputs=[]
                    for a in path:
                        if a<4:
                            current=table['transitions'][str(current)][alphabet[a]]
                            hit=hit or current in table['finals']
                        outputs.append(hit)
                    behavior.extend(outputs)
                if cell==0:assert not any(behavior)
                if cell in by_class:assert behavior==by_class[cell]
                else:by_class[cell]=behavior


def test_finite_closure_exact_markov_and_positive_path_measure():
    mon=JointMonitor([Monitor(f,(1,3,5)) for f in ['nested','directional','multisignal']])
    source=TimeVaryingMarkov(1);truth=exact(source,mon)
    for seed in range(8):
        value,meta=finite_estimate(source,mon,0,300,np.random.default_rng(seed),True)
        np.testing.assert_allclose(value,truth,atol=2e-10)
        assert meta['max_rank']>0 and meta['rows']<=300
        weights,paths=zip(*meta['witnesses'])
        np.testing.assert_allclose(np.array(weights)@np.array([mon.targets(p) for p in paths]),value,atol=1e-12)


def test_finite_closure_unbiased_nonmarkov_history():
    class HistorySource(IID):
        def evaluate(self,hidden,last):
            self.rows+=len(last);h=(np.asarray(hidden).ravel()*3+np.asarray(last)+1)%11
            p=np.exp(np.sin(h[:,None]+np.arange(5)[None,:]))
            return h[:,None],p/p.sum(1,keepdims=True)
    mon=JointMonitor([Monitor('multisignal',(1,3,4))]);source=HistorySource();truth=exact(source,mon)
    values=[]
    for seed in range(180):
        v,_=finite_estimate(source,mon,0,100,np.random.default_rng(seed));values.append(v)
    values=np.array(values)
    assert np.all(np.abs(values.mean(0)-truth)<5*values.std(0)/np.sqrt(len(values))+1e-10)
```

## `query_forecasting/scripts/moment_basis_experiment.py`
SHA256 `c37462b67a1ea96fe71c58a764515ec74a8160cc2e6108b1b078d139ace6d7a5`

```python
import argparse
import json
import sys
import time
import numpy as np
import torch
from patternforecast.polytope import FeasiblePolytope
from queryforecast.common import PACKAGE,CACHE,REPORTS,PROTOCOL,digest,save
from queryforecast.model import Source
for folder in ['compositional','overflow','occupancy']:
    sys.path.insert(0,str(PACKAGE/folder))
from context import setup,reference
from propagate import basis_propagate,InfeasibleRank

parser=argparse.ArgumentParser();parser.add_argument('domain',choices=['air','power'])
parser.add_argument('--limit',type=int);parser.add_argument('--repetitions',type=int)
args=parser.parse_args();torch.set_num_threads(1)
data,qs,mon=setup(args.domain)
checkpoint=torch.load(CACHE/args.domain/'world.pt',weights_only=False)
count=args.limit or 48;reps=args.repetitions or 32
mode='moment-basis-v2' if args.limit is None and args.repetitions is None else f'moment-basis-v2-pilot-{count}-{reps}'
folder=CACHE/args.domain/mode;folder.mkdir(parents=True,exist_ok=True)
files=sorted((PACKAGE/'src').rglob('*.py'))
for name in ['compositional','overflow','occupancy']:files+=sorted((PACKAGE/name).glob('*.py'))
identity={'model':digest(CACHE/args.domain/'world.pt'),'count':count,'replicates':reps,'script':digest(__file__),
 'protocol':digest(PACKAGE/'configs/MOMENT_BASIS_AUDIT.json'),
 'sources':{str(p.relative_to(PACKAGE)):digest(p) for p in files}}
manifest=folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text())!=identity:raise RuntimeError('run changed')
save(manifest,identity)
methods=['harmonic','uniform','known_bits','occupancy','occupancy_symbol'];budgets=[512,2048]
records=[];started=time.perf_counter()
for i in range(count):
    path=folder/f'origin-{i:03d}.npz'
    if path.exists():records.append(dict(np.load(path)));continue
    source=Source(checkpoint,data['x'][i]);q=mon.encode(qs[i]);truth=reference(args.domain,i,mon,qs[i],source)
    polys=[FeasiblePolytope(m.vectors(m.codes((0,int(s),0,0)))) for m,s in zip(mon.monitors,qs[i])]
    shape=(2,len(methods),reps)
    est=np.full((*shape,36),np.nan);rows=np.zeros(shape);timing=np.zeros(shape)
    feasible=np.zeros(shape,bool);coherent=np.zeros(shape,bool);ranks=np.zeros(shape,int)
    mass_error=np.zeros(shape);moment_error=np.zeros(shape)
    for b,budget in enumerate(budgets):
        for r in range(reps):
            for k,name in enumerate(methods):
                rng=np.random.default_rng(PROTOCOL['seed']+100000*i+10*r+b);begin=time.perf_counter()
                try:
                    v,meta=basis_propagate(source,mon,q,budget,rng,name)
                    est[b,k,r]=v;feasible[b,k,r]=True;ranks[b,k,r]=meta['max_rank']
                    mass_error[b,k,r]=meta['mass_error'];moment_error[b,k,r]=meta['moment_error']
                    matrix=v.reshape(3,12)
                    coherent[b,k,r]=all(poly.contains(matrix[:,j*3:j*3+3].ravel())[0] for j,poly in enumerate(polys))
                except InfeasibleRank:pass
                rows[b,k,r]=source.rows;timing[b,k,r]=time.perf_counter()-begin
        print(args.domain,mode,i,budget,'done',round(time.perf_counter()-started,1),flush=True)
    rec={'estimates':est,'truth':truth,'rows':rows,'seconds':timing,'feasible':feasible,
         'family_coherent':coherent,'ranks':ranks,'mass_error':mass_error,'moment_error':moment_error}
    np.savez_compressed(path,**rec);records.append(rec)
result={'domain':args.domain,'mode':mode,'origins':count,'replicates':reps,'methods':methods,
        'status':'mechanism audit; final comparison requires completed Q3/Q4 and serial timings','results':[]}
for b,budget in enumerate(budgets):
    for k,name in enumerate(methods):
        good=np.array([v['feasible'][b,k] for v in records]);fail=int((~good).sum())
        e=np.array([np.mean((v['estimates'][b,k]-v['truth'])**2,axis=-1) for v in records])
        result['results'].append({'budget':budget,'method':name,
          'mse':float(e.mean()) if not fail else None,
          'infeasible_runs':fail,'family_incoherent_feasible_runs':int(sum((v['feasible'][b,k]&~v['family_coherent'][b,k]).sum() for v in records)),
          'max_rank':int(max(v['ranks'][b,k].max() for v in records)),
          'rows':float(np.mean([v['rows'][b,k] for v in records])),
          'seconds':float(np.mean([v['seconds'][b,k] for v in records]))})
result['max_mass_error']=float(max(v['mass_error'].max() for v in records))
result['max_moment_error']=float(max(v['moment_error'].max() for v in records))
save(REPORTS/f'{args.domain}-{mode}.json',result);print(result['results'][len(methods):],flush=True)
```

## `query_forecasting/scripts/finite_closure_experiment.py`
SHA256 `4e24a8478180aa43f89dd074f1f1e720f0908084d082dd0972fedb781bb912a6`

```python
import argparse
import json
import sys
import time
import numpy as np
import torch
from patternforecast.polytope import FeasiblePolytope
from queryforecast.common import PACKAGE,CACHE,REPORTS,PROTOCOL,digest,save
from queryforecast.model import Source
for folder in ['compositional','overflow','occupancy','engineering','finite_control']:
    sys.path.insert(0,str(PACKAGE/folder))
from context import setup,reference
from propagate import InfeasibleRank
from finite_method import finite_estimate

parser=argparse.ArgumentParser();parser.add_argument('domain',choices=['air','power'])
parser.add_argument('--limit',type=int);parser.add_argument('--repetitions',type=int)
args=parser.parse_args();torch.set_num_threads(1)
data,qs,mon=setup(args.domain)
checkpoint=torch.load(CACHE/args.domain/'world.pt',weights_only=False)
count=args.limit or 48;reps=args.repetitions or 32
mode='finite-closure' if args.limit is None and args.repetitions is None else f'finite-closure-pilot-{count}-{reps}'
folder=CACHE/args.domain/mode;folder.mkdir(parents=True,exist_ok=True)
files=sorted((PACKAGE/'src').rglob('*.py'))
for name in ['compositional','overflow','occupancy','engineering','finite_control']:files+=sorted((PACKAGE/name).glob('*.py'))
identity={'model':digest(CACHE/args.domain/'world.pt'),'count':count,'replicates':reps,'script':digest(__file__),
 'protocol':digest(PACKAGE/'configs/FINITE_CLOSURE.json'),
 'sources':{str(p.relative_to(PACKAGE)):digest(p) for p in files}}
manifest=folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text())!=identity:raise RuntimeError('run changed')
save(manifest,identity)
methods=['finite_occupancy'];budgets=[512,2048]
records=[];started=time.perf_counter()
for i in range(count):
    path=folder/f'origin-{i:03d}.npz'
    if path.exists():records.append(dict(np.load(path)));continue
    source=Source(checkpoint,data['x'][i]);q=mon.encode(qs[i]);truth=reference(args.domain,i,mon,qs[i],source)
    polys=[FeasiblePolytope(m.vectors(m.codes((0,int(s),0,0)))) for m,s in zip(mon.monitors,qs[i])]
    shape=(2,len(methods),reps)
    est=np.full((*shape,36),np.nan);rows=np.zeros(shape);timing=np.zeros(shape)
    feasible=np.zeros(shape,bool);coherent=np.zeros(shape,bool);ranks=np.zeros(shape,int)
    mass_error=np.zeros(shape);moment_error=np.zeros(shape)
    for b,budget in enumerate(budgets):
        for r in range(reps):
            for k,name in enumerate(methods):
                rng=np.random.default_rng(PROTOCOL['seed']+100000*i+10*r+b);begin=time.perf_counter()
                try:
                    v,meta=finite_estimate(source,mon,q,budget,rng)
                    est[b,k,r]=v;feasible[b,k,r]=True;ranks[b,k,r]=meta['max_rank']
                    mass_error[b,k,r]=meta['mass_error'];moment_error[b,k,r]=meta['moment_error']
                    matrix=v.reshape(3,12)
                    coherent[b,k,r]=all(poly.contains(matrix[:,j*3:j*3+3].ravel())[0] for j,poly in enumerate(polys))
                except InfeasibleRank:pass
                rows[b,k,r]=source.rows;timing[b,k,r]=time.perf_counter()-begin
        print(args.domain,mode,i,budget,'done',round(time.perf_counter()-started,1),flush=True)
    rec={'estimates':est,'truth':truth,'rows':rows,'seconds':timing,'feasible':feasible,
         'family_coherent':coherent,'ranks':ranks,'mass_error':mass_error,'moment_error':moment_error}
    np.savez_compressed(path,**rec);records.append(rec)
result={'domain':args.domain,'mode':mode,'origins':count,'replicates':reps,'methods':methods,
        'status':'mechanism audit; final comparison requires completed Q3/Q4 and serial timings','results':[]}
for b,budget in enumerate(budgets):
    for k,name in enumerate(methods):
        good=np.array([v['feasible'][b,k] for v in records]);fail=int((~good).sum())
        e=np.array([np.mean((v['estimates'][b,k]-v['truth'])**2,axis=-1) for v in records])
        result['results'].append({'budget':budget,'method':name,
          'mse':float(e.mean()) if not fail else None,
          'infeasible_runs':fail,'family_incoherent_feasible_runs':int(sum((v['feasible'][b,k]&~v['family_coherent'][b,k]).sum() for v in records)),
          'max_rank':int(max(v['ranks'][b,k].max() for v in records)),
          'rows':float(np.mean([v['rows'][b,k] for v in records])),
          'seconds':float(np.mean([v['seconds'][b,k] for v in records]))})
result['max_mass_error']=float(max(v['mass_error'].max() for v in records))
result['max_moment_error']=float(max(v['moment_error'].max() for v in records))
save(REPORTS/f'{args.domain}-{mode}.json',result);print(result['results'][len(methods):],flush=True)
```

## `query_forecasting/scripts/markov_control_experiment.py`
SHA256 `bc94aa03dc3ac615850bd7b234ff8eced18e1691d3f04054ce5785d2e3b5c7bf`

```python
import argparse
import json
import sys
import time
import numpy as np
import torch
from patternforecast.polytope import FeasiblePolytope
from queryforecast.common import PACKAGE,CACHE,REPORTS,PROTOCOL,digest,save
from queryforecast.model import Source
for folder in ['compositional','overflow','occupancy','markov_control']:
    sys.path.insert(0,str(PACKAGE/folder))
from context import setup,reference
from methods import markov_estimate

parser=argparse.ArgumentParser();parser.add_argument('domain',choices=['air','power'])
parser.add_argument('--limit',type=int);parser.add_argument('--repetitions',type=int)
args=parser.parse_args();torch.set_num_threads(1)
data,qs,mon=setup(args.domain)
checkpoint=torch.load(CACHE/args.domain/'world.pt',weights_only=False)
count=args.limit or 48;reps=args.repetitions or 32
mode='markov-control' if args.limit is None and args.repetitions is None else f'markov-control-pilot-{count}-{reps}'
folder=CACHE/args.domain/mode;folder.mkdir(parents=True,exist_ok=True)
files=sorted((PACKAGE/'src').rglob('*.py'))
for name in ['compositional','overflow','occupancy','markov_control']:files+=sorted((PACKAGE/name).glob('*.py'))
identity={'model':digest(CACHE/args.domain/'world.pt'),'count':count,'replicates':reps,'script':digest(__file__),
 'protocol':digest(PACKAGE/'configs/MARKOV_CONTROL_AUDIT.json'),
 'sources':{str(p.relative_to(PACKAGE)):digest(p) for p in files}}
manifest=folder/'identity.json'
if manifest.exists() and json.loads(manifest.read_text())!=identity:raise RuntimeError('run changed')
save(manifest,identity)
methods=['balanced','cv','lhs','cv_family_projected','lhs_family_projected'];budgets=[512,2048]
records=[];started=time.perf_counter()
for i in range(count):
    path=folder/f'origin-{i:03d}.npz'
    if path.exists():records.append(dict(np.load(path)));continue
    source=Source(checkpoint,data['x'][i]);q=mon.encode(qs[i]);truth=reference(args.domain,i,mon,qs[i],source)
    polys=[FeasiblePolytope(m.vectors(m.codes((0,int(s),0,0)))) for m,s in zip(mon.monitors,qs[i])]
    shape=(2,len(methods),reps)
    est=np.zeros((*shape,36));rows=np.zeros(shape);timing=np.zeros(shape)
    coherent=np.zeros(shape,bool);proxy_rows=np.zeros(shape,int)
    mass_error=np.zeros(shape);moment_error=np.zeros(shape)
    for b,budget in enumerate(budgets):
        for r in range(reps):
            for k,name in enumerate(methods):
                rng=np.random.default_rng(PROTOCOL['seed']+100000*i+10*r+b);begin=time.perf_counter()
                v,meta=markov_estimate(source,mon,q,budget,rng,name.replace('_family_projected',''))
                if name.endswith('_family_projected'):
                    matrix=v.reshape(3,12).copy()
                    for j,poly in enumerate(polys):matrix[:,j*3:j*3+3]=poly.project(matrix[:,j*3:j*3+3].ravel()).reshape(3,3)
                    v=matrix.ravel()
                est[b,k,r]=v;proxy_rows[b,k,r]=meta['proxy_rows']
                mass_error[b,k,r]=meta.get('mass_error',0.);moment_error[b,k,r]=meta.get('moment_error',0.)
                rows[b,k,r]=meta['rows'];timing[b,k,r]=time.perf_counter()-begin
                matrix=v.reshape(3,12)
                coherent[b,k,r]=all(poly.contains(matrix[:,j*3:j*3+3].ravel())[0] for j,poly in enumerate(polys))
        print(args.domain,mode,i,budget,'done',round(time.perf_counter()-started,1),flush=True)
    rec={'estimates':est,'truth':truth,'rows':rows,'seconds':timing,'proxy_rows':proxy_rows,
         'family_coherent':coherent,'mass_error':mass_error,'moment_error':moment_error}
    np.savez_compressed(path,**rec);records.append(rec)
result={'domain':args.domain,'mode':mode,'origins':count,'replicates':reps,'methods':methods,
        'status':'strong conventional controls, not a proposed novel contribution','results':[]}
for b,budget in enumerate(budgets):
    for k,name in enumerate(methods):
        e=np.array([np.mean((v['estimates'][b,k]-v['truth'])**2) for v in records])
        result['results'].append({'budget':budget,'method':name,'mse':float(e.mean()),
          'family_incoherent_runs':int(sum((~v['family_coherent'][b,k]).sum() for v in records)),
          'rows':float(np.mean([v['rows'][b,k] for v in records])),
          'proxy_rows':float(np.mean([v['proxy_rows'][b,k] for v in records])),
          'seconds':float(np.mean([v['seconds'][b,k] for v in records]))})
result['max_mass_error']=float(max(v['mass_error'].max() for v in records))
result['max_moment_error']=float(max(v['moment_error'].max() for v in records))
save(REPORTS/f'{args.domain}-{mode}.json',result);print(result['results'][len(methods):],flush=True)
```

## `query_forecasting/scripts/summarize_evidence.py`
SHA256 `5700b30869b74296d451c3e2aaa6b2971c38c1ab18bc23e6370b244fc4563321`

```python
"""All completed development controls, paired origins, no silent failed-run deletion."""
import json
import numpy as np
from queryforecast.common import CACHE,REPORTS,PROTOCOL,save

MODES=['balanced','overflow','moment-basis-v2','markov-control','particle-control']
CANDIDATES={'Q3':'balanced/harmonic','Q4':'overflow/harmonic','Q5':'moment-basis-v2/occupancy_symbol'}
result={'scope':'development only, same frozen source/query/input/budget; no unopened years',
        'bootstrap':'5000 paired-origin bootstrap resamples, fixed selected comparator and reselected best comparator both reported',
        'runtime':'Concurrent experiment times are descriptive; serial timing is required separately.',
        'domains':{}}
for domain in ['air','power']:
    summary={};errors={};missing=[];reference_truth=None
    for mode in MODES:
        report=REPORTS/f'{domain}-{mode}.json'
        if not report.exists():missing.append(mode);continue
        report=json.loads(report.read_text())
        paths=sorted((CACHE/domain/mode).glob('origin-*.npz'))
        if len(paths)!=48 or report['origins']!=48 or report['replicates']!=32:
            raise AssertionError('incomplete/full report mismatch')
        values=[dict(np.load(p)) for p in paths]
        truth=np.array([v['truth'] for v in values])
        if reference_truth is None:reference_truth=truth
        else:np.testing.assert_allclose(truth,reference_truth,rtol=0,atol=1e-13)
        for k,method in enumerate(report['methods']):
            name=mode+'/'+method
            finite=all(np.isfinite(v['estimates'][1,k]).all() for v in values)
            e=np.array([np.mean((v['estimates'][1,k]-v['truth'])**2) for v in values])
            summary[name]={'mse':float(e.mean()) if finite else None,
              'seconds_concurrent':float(np.mean([v['seconds'][1,k] for v in values])),
              'rows':float(np.mean([v['rows'][1,k] for v in values])),
              'infeasible_runs':int(sum((~v.get('feasible',np.ones(v['rows'].shape,bool))[1,k]).sum() for v in values))}
            if finite:errors[name]=e
    names=list(errors);matrix=np.array([errors[n] for n in names]).T
    ids=np.random.default_rng(PROTOCOL['seed']).integers(48,size=(5000,48))
    means=matrix[ids].mean(1);gates={}
    for stage,name in CANDIDATES.items():
        if name not in names:
            gates[stage]={'status':'missing or infeasible'};continue
        k=names.index(name);others=[i for i in range(len(names)) if i!=k]
        best=min(others,key=lambda i:matrix[:,i].mean())
        base=matrix[:,best].mean();candidate=matrix[:,k].mean()
        if base<=1e-30:
            gain=0. if candidate<=1e-30 else None
            fixed_ci=reselected_ci=None;passes=candidate<=1e-30
        else:
            gain=1-candidate/base
            fixed_ci=np.quantile(1-means[:,k]/np.maximum(means[:,best],1e-30),[.025,.975]).tolist()
            reselected_ci=np.quantile(1-means[:,k]/np.maximum(means[:,others].min(1),1e-30),[.025,.975]).tolist()
            passes=bool(gain>=.2 and reselected_ci[0]>0)
        gates[stage]={'candidate':name,'best_comparator':names[best],
          'relative_mse_reduction':gain,'paired_origin_95_fixed':fixed_ci,'paired_origin_95_reselected_best':reselected_ci,
          'mse_gate':passes,'inference_status':'complete development comparison' if not missing else 'provisional; stronger runs pending',
          'concurrent_time_ratio':summary[name]['seconds_concurrent']/summary[names[best]]['seconds_concurrent']}
    result['domains'][domain]={'missing':missing,'methods':summary,'gates':gates}
result['independent_confirmation']='NOT RUN; remaining years closed'
save(REPORTS/'evidence-summary.json',result)
for domain,d in result['domains'].items():print(domain,'pending',d['missing'],'gates',d['gates'])
```
