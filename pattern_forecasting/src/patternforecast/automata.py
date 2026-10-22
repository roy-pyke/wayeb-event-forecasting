"""Finite product of the pinned author's exported deterministic automata."""
from collections import deque
from functools import lru_cache
import itertools
import json
import numpy as np
from .common import CONFIG, NAMES


class PatternFamily:
    def __init__(self, payload=None):
        if payload is None:
            payload = json.loads((CONFIG/'dfa.json').read_text())
        self.alphabet = tuple(payload['alphabet'])
        self.tables = [payload['patterns'][n] for n in NAMES]
        start = tuple(t['start'] for t in self.tables)
        states, seen, queue = [], {start}, deque([start])
        while queue:
            q = queue.popleft()
            states.append(q)
            for a in self.alphabet:
                nxt = tuple(t['transitions'][str(s)][a] for t, s in zip(self.tables, q))
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        self.states = states
        self.index = {q:i for i, q in enumerate(states)}
        self.start = self.index[start]
        self.next = np.array([[self.index[tuple(t['transitions'][str(s)][a]
                    for t, s in zip(self.tables, q))] for a in self.alphabet] for q in states])
        self.final = np.array([[s in t['finals'] for s,t in zip(q,self.tables)] for q in states])
        self.final_mask = self.final.astype(int) @ (2**np.arange(len(NAMES)))
        self.onehot = np.eye(len(states), dtype=np.float32)

    def step(self, state, symbol):
        if symbol is None:
            return state, np.zeros(len(NAMES), dtype=bool)
        nxt = self.next[state, self.alphabet.index(symbol)]
        return int(nxt), self.final[nxt].copy()

    def verify_inclusion(self):
        return bool(np.all(~self.final[:,0] | self.final[:,1]) and
                    np.all(~self.final[:,1] | self.final[:,2]))

    def inclusion_pairs(self):
        return [(i,j) for i in range(len(self.tables)) for j in range(len(self.tables))
                if i!=j and np.all(~self.final[:,i]|self.final[:,j])]

    @lru_cache(maxsize=8)
    def static_profiles(self,horizon_count=3):
        """Exact time-unbounded joint outcome relations, union over current states.

        Each interval reaches its closure in the augmented (state,hit-mask)
        graph. This includes Boolean/union constraints, not only inclusions.
        """
        nodes={(q,0,0) for q in range(len(self.states))}
        p=len(self.tables)
        for position in range(horizon_count):
            queue=deque(nodes)
            while queue:
                q,hits,profile=queue.popleft()
                for nxt in self.next[q]:
                    item=(int(nxt),hits|int(self.final_mask[nxt]),profile)
                    if item not in nodes:nodes.add(item);queue.append(item)
            nodes={(q,hits,profile|(hits<<(position*p))) for q,hits,profile in nodes}
        codes=sorted({v for _,_,v in nodes})
        return np.array([[(c>>(h*p+j))&1 for j in range(p) for h in range(horizon_count)] for c in codes],dtype=float)

    @lru_cache(maxsize=256)
    def feasible(self, state, horizons):
        """Exact reachability with at most one alphabet event per native tick.

        Silence preserves the monitor, but never creates a new match even when
        the current monitor is accepting. Repeated identical symbols are allowed
        here: this is a conservative superset of change-only regime streams.
        """
        horizons = tuple(int(x) for x in horizons)
        assert all(x>0 for x in horizons) and list(horizons)==sorted(set(horizons))
        nodes = {(int(state), 0, 0)}
        p, position = len(NAMES), 0
        for step in range(1, max(horizons)+1):
            following = set(nodes)
            for q, hits, profile in nodes:
                for nxt in self.next[q]:
                    following.add((int(nxt), hits | int(self.final_mask[nxt]), profile))
            nodes = following
            if step in horizons:
                nodes = {(q, hits, profile | (hits << (position*p))) for q,hits,profile in nodes}
                position += 1
        codes = sorted({profile for _,_,profile in nodes})
        return np.array([[(code >> (h*p+j)) & 1 for j in range(p)
                         for h in range(len(horizons))] for code in codes], dtype=np.float64)


def independent_profiles(patterns, horizons):
    """Per-pattern first arrival, without any cross-pattern constraints."""
    single = [np.r_[np.zeros(k), np.ones(horizons-k)] for k in range(horizons+1)]
    return np.array([np.concatenate(parts) for parts in itertools.product(single, repeat=patterns)])
