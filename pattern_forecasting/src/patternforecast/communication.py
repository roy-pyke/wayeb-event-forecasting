"""Causal cache replay, byte accounting, and paired calendar-week inference."""
import numpy as np
from .data import targets


def replay_policy(data,predictions,bounds,policy,threshold,max_lag=16):
    n=len(data['t']);lag_used=np.zeros(n,dtype=np.int16);sends=np.zeros(n,dtype=bool)
    certificate=np.zeros(n);last=-1
    for i in range(n):
        force=last<0 or data['segment'][i]!=data['segment'][last] or i-last>=max_lag
        lag=0 if force else i-last
        if policy=='all': send=True
        elif policy=='periodic': send=force or lag>=threshold
        else: send=force or bounds[policy][lag,i]>threshold
        if send: last=i;sends[i]=True;lag=0
        lag_used[i]=lag
        certificate[i]=bounds['joint'][lag,i]
    return predictions[lag_used,np.arange(n)],sends,certificate,lag_used


def weekly(data,values,valid=None):
    # Monday-aligned recorded-clock weeks; source timezone is not asserted.
    week=np.floor((data['t']+3*86400)/(7*86400)).astype(int)
    if valid is None: valid=np.ones(len(week),dtype=bool)
    labels=np.unique(week)
    sums=np.array([values[(week==w)&valid].sum() for w in labels])
    counts=np.array([np.sum((week==w)&valid) for w in labels])
    return labels,sums,counts


def block_interval(sums,counts,seed=20261022,replicates=1000):
    rng=np.random.default_rng(seed)
    take=rng.integers(len(sums),size=(replicates,len(sums)))
    totals=counts[take].sum(1);vals=sums[take].sum(1)/np.maximum(totals,1)
    return [float(x) for x in np.quantile(vals,[.025,.975])]


def evaluate(data,pred,full,sends,certificate,horizons,epsilon=None):
    y,known=targets(data,horizons);complete=known.all((1,2))
    error=np.mean((pred-y)**2,axis=(1,2));base=np.mean((full-y)**2,axis=(1,2));excess=error-base
    weeks,bs,counts=weekly(data,excess,complete)
    _,ps,pc=weekly(data,sends.astype(float))
    result={'queries':len(pred),'scored_queries':int(complete.sum()),'aux_packet_rate':float(sends.mean()),
            'brier':float(error[complete].mean()),'excess_brier':float(excess[complete].mean()),
            'excess_brier_ci':block_interval(bs,counts),'packet_rate_ci':block_interval(ps,pc),
            'max_observed_excess':float(excess[complete].max()),
            'max_joint_certificate':float(certificate.max()),
            'bound_violations':int(np.sum(excess[complete]>certificate[complete]+1e-7)),
            'epsilon_violations':None if epsilon is None else int(np.sum(excess[complete]>epsilon+1e-7)),
            'weeks':weeks,'week_excess_sums':bs,'week_scored_counts':counts,
            'week_packet_sums':ps,'week_query_counts':pc}
    assert result['bound_violations']==0
    if epsilon is not None: assert result['epsilon_violations']==0
    return result
