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
