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
