"""Balance query moments only when monitor bins exceed particle capacity."""
from collections import defaultdict
from dataclasses import replace
import numpy as np
from monitor import HarmonicPotential
from compress import compress
from propagation import Particle,successors,combine_identical_histories,weighted_ensemble


def guarded(source, mon, q, budget, rng, policy='harmonic', certificate=False):
    source.rows = 0
    initial = Particle(1.,(0,int(q),0,0),source.initial,5,())
    fixed = mon.fixed(initial.state)
    if fixed is not None:
        return fixed,{'rows':0,'mass_error':0.,'moment_error':0.,'overflows':0,'stages':[]}
    h0,p0 = source.evaluate([initial.hidden],[5])
    phi = None
    nodes = [initial];answer = np.zeros(mon.d);settled_mass = 0.
    stages=[];witnesses=[];moment_error=0.;overflows=0
    for depth in range(mon.H):
        nodes = combine_identical_histories(nodes)
        hidden,prob = (h0,p0) if depth == 0 else source.evaluate([n.hidden for n in nodes],[n.last for n in nodes])
        live=[]
        for j,node in enumerate(nodes):
            for child in successors(mon,node,hidden[j],prob[j]):
                fixed=mon.fixed(child.state)
                if fixed is None:live.append(child)
                else:
                    answer+=child.mass*fixed;settled_mass+=child.mass
                    if certificate:witnesses.append((child.mass,child.path+(4,)*(mon.H-len(child.path))))
        if not live:break
        remaining=mon.H-depth-1;target=int((budget-source.rows)//remaining)
        groups=defaultdict(list)
        for n in live:groups[n.state].append(n)
        groups=list(groups.values())
        stage={'depth':depth+1,'histories':len(live),'bins':len(groups),'capacity':target,
               'overflow':len(groups)>target,'live_mass':float(sum(n.mass for n in live))}
        if len(live)>target:
            if len(groups)<=target:
                live=weighted_ensemble(mon,live,target,rng)
            else:
                overflows+=1
                masses=np.array([sum(n.mass for n in g) for g in groups])
                states=[g[0].state for g in groups]
                if policy in ['harmonic','uniform']:
                    if phi is None:
                        phi=HarmonicPotential(mon,p0[0] if policy=='harmonic' else np.full(5,.2))
                    features=phi(states)
                elif policy=='known_bits':features=mon.vectors([s[3] for s in states])
                elif policy=='mass':features=np.empty((len(groups),0))
                else:raise ValueError(policy)
                weights,meta=compress(masses,features,target,rng)
                moment_error=max(moment_error,meta['moment_error'])
                stage['rank']=meta['rank'];stage['moves']=meta['moves']
                live=[]
                for group,total,newweight in zip(groups,masses,weights):
                    if newweight<=0:continue
                    i=rng.choice(len(group),p=np.array([n.mass for n in group])/total)
                    live.append(replace(group[i],mass=float(newweight)))
        stages.append(stage)
        if abs(settled_mass+sum(n.mass for n in live)-1.)>2e-9:
            raise AssertionError('positive mass not conserved')
        nodes=live
    if source.rows>budget or abs(settled_mass-1.)>2e-9:
        raise AssertionError('budget or conservation violation')
    meta={'rows':source.rows,'mass_error':abs(settled_mass-1.),'moment_error':moment_error,
          'overflows':overflows,'stages':stages}
    if certificate:meta['witnesses']=witnesses
    return answer,meta
