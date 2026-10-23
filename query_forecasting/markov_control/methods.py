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
