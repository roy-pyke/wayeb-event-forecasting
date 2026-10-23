import json
import numpy as np
import pandas as pd
from queryforecast.common import ROOT,PACKAGE,CACHE
from queryforecast.data import load
from queryforecast.monitor import Monitor
from queryforecast.estimators import exact
from monitor import JointMonitor


def setup(domain):
    data=load(domain,'development')
    payload=json.loads((PACKAGE/'configs/heldout_structure/dfa.json').read_text())
    families=['nested','directional','multisignal','heldout_structure']
    parts=[Monitor(f,(2,4,8),payload if f=='heldout_structure' else None) for f in families]
    qs=np.c_[data['q'],np.zeros(48,int)]
    events=pd.read_csv(ROOT/'.cache/pattern_forecasting/multisignal'/domain/'development-business.csv')
    for (entity,segment),group in events.groupby(['entity','segment'],sort=False):
        ix=np.flatnonzero((data['entity']==entity)&(data['segment']==segment))
        if not len(ix):continue
        q=0;states=[]
        for a in group.symbol:q=int(parts[-1].next[q,ord(a)-65]);states.append(q)
        pos=np.searchsorted(group.timestamp.to_numpy(),data['t'][ix],side='right')-1
        qs[ix,-1]=np.where(pos>=0,np.array(states)[np.maximum(pos,0)],0)
    return data,qs.astype(int),JointMonitor(parts)


def reference(domain,index,mon,qs,source):
    path=CACHE/domain/'balanced'/f'origin-{index:03d}.npz'
    if path.exists():return np.load(path)['truth']
    path=CACHE/domain/'generalization'/f'origin-{index:03d}.npz'
    if path.exists():truth=np.load(path)['truth']
    else:truth=[exact(source,m,int(q)) for m,q in zip(mon.monitors,qs)]
    return np.concatenate([v.reshape(3,3) for v in truth],axis=1).ravel()
