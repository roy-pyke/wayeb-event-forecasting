"""Bounded probing under a forecast CDF. Conventional finite-horizon DP."""
import numpy as np


def monotone_cdf(p):
    return np.maximum.accumulate(np.clip(np.asarray(p,float),1e-6,1-1e-6),axis=-1)


def conditional_probability(cdf,last_failure,t):
    f=np.r_[0.,monotone_cdf(cdf)]
    return float(np.clip((f[t]-f[last_failure])/(1-f[last_failure]),0,1))


def dp_schedule(cdf,delay_weight=1.,max_gap=4):
    """Optimal schedule for this single absorbing recovery/failed-probe model.

    V[s] conditional on recovery R>s after a failed probe at s. For next probe
    j, sum delay of recoveries in (s,j], plus P(R>j)*(1+V[j]). Horizon T is
    probed. No recovery/remaining mass pays failed probes, not fictitious delay.
    This is not an optimality claim for coupled charging or transient recovery.
    """
    f=np.r_[0.,monotone_cdf(cdf)]; mass=np.diff(f); T=len(cdf)
    v=np.zeros(T+1); nxt=np.full(T+1,T,int)
    for s in range(T-1,-1,-1):
        choices=[]
        for j in range(s+1,min(s+max_gap,T)+1):
            delays=np.arange(j-s-1,-1,-1)
            cost=(delay_weight*np.dot(mass[s:j],delays)+(1-f[j])*(1+v[j]))/(1-f[s])
            choices.append((cost,j))
        v[s],nxt[s]=min(choices)
    return nxt,v


def next_probe(kind,last,attempt,cdf,delay_weight=1.,threshold=.2):
    T=len(cdf)
    if kind.startswith('every_'): return min(T,last+int(kind[-1]))
    if kind=='backoff': return min(T,last+min(4,2**attempt))
    if kind=='dp': return int(dp_schedule(cdf,delay_weight)[0][last])
    if kind=='threshold':
        return next((t for t in range(last+1,min(T,last+4)+1)
                     if conditional_probability(cdf,last,t)>=threshold or t==min(T,last+4)),T)
    raise ValueError(kind)


def run_discovery(event_min,terminal_min,cdf,kind,delay_weight=1.,threshold=.2):
    """Conditional absorbing-state discovery diagnostic, not a log-policy OPE."""
    T=len(cdf); recovery=int(np.ceil(event_min/5)) if np.isfinite(event_min) else T+1
    last=0; attempt=0; failed=0; detected=None; probes=[]
    while last<T:
        t=next_probe(kind,last,attempt,cdf,delay_weight,threshold)
        if t*5>=terminal_min and terminal_min<5*T: break
        probes.append(t)
        if t>=recovery: detected=t; break
        failed+=1; last=t; attempt+=1
    delay=(detected if detected is not None else T)-recovery if recovery<=T else 0
    return dict(cost=float(failed+delay_weight*delay),failed_probes=failed,
                delay_slots=delay,detected=detected is not None,
                missed=bool(recovery<=T and detected is None),probe_slots=probes)


def perturb_cdf(cdf,kind):
    p=monotone_cdf(cdf)
    if kind=='early_10min': return np.r_[p[2:],p[-1],p[-1]]
    if kind=='late_10min': return np.r_[0.,0.,p[:-2]]
    if kind=='inflate_0p2': return np.minimum(1-1e-6,p+.2)
    if kind=='natural': return p
    raise ValueError(kind)
