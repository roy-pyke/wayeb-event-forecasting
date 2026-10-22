"""Generic max-plus automaton oracle; no enumeration of joint label profiles."""
import numpy as np


class MaxPlusOracle:
    def __init__(self,transitions,finals):
        self.transitions=np.asarray(transitions,dtype=int)
        self.finals=np.asarray(finals,dtype=bool)
        self.patterns=self.finals.shape[1]
        self.masks=np.arange(2**self.patterns)
        self.bits=((self.masks[:,None]>>np.arange(self.patterns))&1).astype(float)
        self.final_masks=self.finals.astype(int)@(2**np.arange(self.patterns))
        self.state_count=len(self.transitions)
        src=[];dest=[]
        for q in range(self.state_count):
            for mask in self.masks:
                origin=q*len(self.masks)+mask
                src.append(origin);dest.append(origin)  # silence never rematches
                for nxt in self.transitions[q]:
                    src.append(origin);dest.append(nxt*len(self.masks)+(mask|self.final_masks[nxt]))
        self.src=np.asarray(src);self.dest=np.asarray(dest)

    def bound(self,state,horizons,cached,full,weights=None):
        p=np.asarray(cached,dtype=float);f=np.asarray(full,dtype=float)
        assert p.shape==f.shape==(self.patterns,len(horizons))
        if weights is None: weights=np.full(p.shape,1/p.size)
        weights=np.asarray(weights);assert weights.shape==p.shape and (weights>=0).all()
        constants=np.sum(weights*(p*p-f*f));coef=-2*weights*(p-f)
        return float(constants+self.maximize(state,horizons,coef))

    def maximize(self,state,horizons,coefficients,witness=False):
        """Maximize a linear reward over feasible labels, optionally with witness.

        The witness is a label profile reached by a real future event path.
        It permits exact span discovery without enumerating all profiles.
        """
        coef=np.asarray(coefficients,dtype=float)
        assert coef.shape==(self.patterns,len(horizons))
        assert tuple(sorted(set(horizons)))==tuple(horizons) and min(horizons)>0
        value=np.full(self.state_count*len(self.masks),-np.inf)
        value[int(state)*len(self.masks)]=0
        at={h:i for i,h in enumerate(horizons)}
        parents=[]
        for tick in range(1,max(horizons)+1):
            nxt=np.full_like(value,-np.inf)
            scores=value[self.src]
            np.maximum.at(nxt,self.dest,scores)
            if witness:
                best=np.full(len(value),len(self.src),dtype=int)
                valid=np.isfinite(scores)&(scores==nxt[self.dest])
                edges=np.flatnonzero(valid)
                np.minimum.at(best,self.dest[edges],edges)
                parent=np.full(len(value),-1,dtype=int)
                reachable=best<len(self.src);parent[reachable]=self.src[best[reachable]]
                parents.append(parent)
            value=nxt
            if tick in at:
                reward=self.bits@coef[:,at[tick]]
                value+=np.tile(reward,self.state_count)
        result=float(np.max(value))
        if not witness:return result
        end=int(np.argmax(value));profile=np.zeros_like(coef)
        for tick in range(max(horizons),0,-1):
            if tick in at:profile[:,at[tick]]=self.bits[end%len(self.masks)]
            end=int(parents[tick-1][end]);assert end>=0
        assert end==int(state)*len(self.masks)
        assert np.isclose(np.sum(profile*coef),result,atol=1e-10)
        return result,profile
