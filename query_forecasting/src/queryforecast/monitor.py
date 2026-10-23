"""Compile residual output languages from pinned Wayeb transition exports."""
from functools import lru_cache
import json
import numpy as np
from .common import ROOT


class Monitor:
    def __init__(self, family='multisignal', horizons=(2, 4, 6), payload=None):
        self.family = family
        self.horizons = tuple(horizons)
        if list(horizons) != sorted(set(horizons)) or min(horizons) <= 0:
            raise ValueError('positive increasing horizons required')
        folder = ROOT / 'pattern_forecasting/configs'
        if family != 'nested': folder = folder / family
        if payload is None: payload = json.loads((folder / 'dfa.json').read_text())
        self.names = tuple(payload['patterns'])
        tables = list(payload['patterns'].values())
        start = tuple(t['start'] for t in tables)
        states, index = [start], {start: 0}
        transitions = []
        for state in states:
            row = []
            for a in payload['alphabet']:
                nxt = tuple(t['transitions'][str(s)][a] for t, s in zip(tables, state))
                if nxt not in index:
                    index[nxt] = len(states); states.append(nxt)
                row.append(index[nxt])
            row.append(index[state])  # no event, no new endpoint
            transitions.append(row)
        self.next = np.array(transitions, dtype=np.int64)
        self.final = np.array([sum((s in t['finals']) << j for j, (s, t) in
                                  enumerate(zip(state, tables))) for state in states])
        self.P = len(tables)
        self.d = self.P * len(horizons)
        self.H = max(horizons)
        self.horizon_shift = {h: i*self.P for i, h in enumerate(horizons)}

    def advance(self, depth, q, hits, code, a):
        nq = int(self.next[q, a])
        nh = int(hits | (self.final[nq] if a < 4 else 0))
        nc = int(code)
        if depth+1 in self.horizon_shift:
            nc |= nh << self.horizon_shift[depth+1]
        return depth+1, nq, nh, nc

    @lru_cache(maxsize=None)
    def future_codes(self, depth, q, hits):
        if depth == self.H: return (0,)
        codes = set()
        for a in range(5):
            nd, nq, nh, code = self.advance(depth, q, hits, 0, a)
            codes.update(code | c for c in self.future_codes(nd, nq, nh))
        return tuple(sorted(codes))

    def codes(self, state):
        depth, q, hits, code = state
        return tuple(code | v for v in self.future_codes(depth, q, hits))

    def vectors(self, codes):
        return ((np.asarray(codes, dtype=np.int64)[:, None] >>
                 np.arange(self.d)) & 1).astype(float)

    @lru_cache(maxsize=None)
    def uncertainty(self, depth, q, hits):
        codes = self.future_codes(depth, q, hits)
        lower, upper = codes[0], codes[0]
        for c in codes[1:]: lower &= c; upper |= c
        return (lower ^ upper).bit_count() / 4.0

    def fixed(self, state):
        codes = self.codes(state)
        return self.vectors(codes)[0] if len(codes) == 1 else None

    def targets(self, symbols, q=0):
        state = (0, q, 0, 0)
        for a in symbols: state = self.advance(*state, int(a))
        if state[0] != self.H: raise ValueError('wrong target length')
        return self.vectors([state[3]])[0]
