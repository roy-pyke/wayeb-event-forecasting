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
