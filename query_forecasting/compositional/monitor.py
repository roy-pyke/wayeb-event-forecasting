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
