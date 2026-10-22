"""Equal-information, censored landmark baselines. No confirmation-data fitting."""
import copy
import time
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, ExtraTreesClassifier
from sklearn.isotonic import IsotonicRegression
from .data import design, targets
from .automata import PatternFamily
from .common import FAMILY


def subset(data,indices):
    return {k:v[indices] for k,v in data.items()}


def isotonic_axis(x,axis):
    """Exact equal-weight one-dimensional isotonic projection, length three."""
    a=np.moveaxis(x,axis,-1)
    out=np.empty_like(a)
    for i in range(3):
        out[...,i]=np.maximum.reduce([np.minimum.reduce(
            [a[...,start:end+1].mean(-1) for end in range(i,3)]) for start in range(i+1)])
    return np.moveaxis(out,-1,axis)


def coherent(x):
    """Dykstra projection onto nested-pattern and monotone-horizon order cones.

    Standard coherence repair, not claimed as a novel contribution.
    """
    if FAMILY!='nested':
        from .certificates import static_nested_profiles
        from .polytope import FeasiblePolytope
        return FeasiblePolytope(static_nested_profiles()).project(x)
    z=np.asarray(x,dtype=float).copy(); u=np.zeros_like(z); v=np.zeros_like(z)
    for _ in range(200):
        y=isotonic_axis(z+u,1); u=z+u-y
        nxt=isotonic_axis(y+v,2); v=y+v-nxt
        error=np.max(np.abs(nxt-z)); z=nxt
        feasible=(np.diff(z,axis=1)>=-1e-11).all() and (np.diff(z,axis=2)>=-1e-11).all()
        if error<1e-11 and feasible: break
    if not feasible: raise ArithmeticError('Coherence projection did not converge')
    return np.clip(z,0,1)


class Features:
    def __init__(self,native,business_only=False,no_state=False):
        self.native=native; self.business_only=business_only; self.no_state=no_state

    def arrays(self,data,lag=0):
        biz,raw,age=design(data,lag,self.native,self.business_only,self.no_state)
        return np.c_[biz,np.log1p(age)],raw

    def fit(self,data):
        biz,raw=self.arrays(data)
        if self.business_only:
            self.center=np.zeros(raw.shape[-1]);self.scale=np.ones(raw.shape[-1])
        else:
            with np.errstate(invalid='ignore'):
                self.center=np.nanmedian(raw,axis=(0,1))
                self.scale=np.nanstd(raw,axis=(0,1))
        self.center=np.nan_to_num(self.center)
        self.scale=np.where(np.isfinite(self.scale)&(self.scale>1e-6),self.scale,1)
        self.biz_center=np.nanmean(biz,axis=0)
        self.biz_scale=np.nanstd(biz,axis=0)
        self.biz_scale=np.where(self.biz_scale>1e-6,self.biz_scale,1)
        return self

    def transform(self,data,lag=0):
        biz,raw=self.arrays(data,lag)
        missing=~np.isfinite(raw)
        raw=np.clip(np.nan_to_num((raw-self.center)/self.scale),-20,20)
        biz=np.clip(np.nan_to_num((biz-self.biz_center)/self.biz_scale),-30,30)
        seq=np.concatenate([raw,missing],axis=2).astype(np.float32)
        return biz.astype(np.float32),seq


def training_views(data,features,seed,cap=20000):
    """Identical query sample and cache-age augmentation for every baseline."""
    rng=np.random.default_rng(seed)
    ids=np.sort(rng.choice(len(data['t']),min(cap,len(data['t'])),replace=False))
    lag=rng.integers(1,17,size=len(data['t']))
    b0,s0=features.transform(data,0); b1,s1=features.transform(data,lag)
    return np.r_[b0[ids],b1[ids]],np.r_[s0[ids],s1[ids]],np.r_[ids,ids]


class Landmark:
    def __init__(self,cfg,kind,setting,seed,business_only=False,no_state=False):
        self.cfg=cfg; self.kind=kind; self.setting=setting; self.seed=seed
        self.features=Features(cfg['native_seconds'],business_only,no_state)
        self.h=np.array(cfg['horizon_samples']); self.calibrators=None

    def fit(self,train,calibrate):
        start=time.perf_counter(); self.features.fit(train)
        biz,seq,ids=training_views(train,self.features,self.seed)
        flat=np.c_[biz,seq.reshape(len(biz),-1)]
        rows=[]; labels=[]
        for p in range(3):
            residual=train['residual'][ids,p]; observed=train['observed'][ids,p]
            coverage=train['coverage'][ids]
            for k,upper in enumerate(self.h):
                lower=0 if k==0 else self.h[k-1]
                hit=observed&(residual<=upper)&(residual>lower)
                valid=(residual>lower)&(hit|(coverage>=upper))
                extra=np.zeros((valid.sum(),6),dtype=np.float32); extra[:,p]=1;extra[:,3+k]=1
                rows.append(np.c_[flat[valid],extra]);labels.append(hit[valid])
        X=np.concatenate(rows); y=np.concatenate(labels)
        if self.kind=='hgb':
            leaves,iterations=self.setting
            self.estimator=HistGradientBoostingClassifier(max_iter=iterations,max_leaf_nodes=leaves,
                max_bins=64,min_samples_leaf=40,l2_regularization=2,learning_rate=.06,
                early_stopping=False,random_state=self.seed)
        else:
            self.estimator=ExtraTreesClassifier(n_estimators=120,min_samples_leaf=self.setting[0],
                max_depth=20,max_features=.8,n_jobs=3,random_state=self.seed)
        self.estimator.fit(X,y)
        self.fit_seconds=time.perf_counter()-start; self.fit_rows=len(y)
        self.calibrate(calibrate)
        return self

    def raw_predict(self,data,lag=0):
        biz,seq=self.features.transform(data,lag)
        flat=np.c_[biz,seq.reshape(len(biz),-1)]
        output=np.empty((len(flat),3,3))
        for p in range(3):
            for k in range(3):
                extra=np.zeros((len(flat),6),dtype=np.float32);extra[:,p]=1;extra[:,3+k]=1
                output[:,p,k]=self.estimator.predict_proba(np.c_[flat,extra])[:,1]
        return 1-np.cumprod(1-output,axis=2)

    def calibrate(self,data):
        rng=np.random.default_rng(self.seed+100)
        lag=rng.integers(0,17,size=len(data['t']));lag[::2]=0
        pred=self.raw_predict(data,lag)
        y,known=targets(data,self.h)
        self.calibrators=[]
        for p in range(3):
            row=[]
            for k in range(3):
                mask=known[:,p,k]
                row.append(IsotonicRegression(y_min=0,y_max=1,out_of_bounds='clip').fit(pred[mask,p,k],y[mask,p,k]))
            self.calibrators.append(row)

    def predict(self,data,lag=0,repair=True):
        if self.cfg.get('pattern_family','nested')!=FAMILY: raise ValueError('model/family mismatch')
        pred=self.raw_predict(data,lag)
        if self.calibrators is not None:
            for p in range(3):
                for k in range(3): pred[:,p,k]=self.calibrators[p][k].predict(pred[:,p,k])
        return coherent(pred) if repair else pred


def make_network(bizdim,channels,hidden):
    import torch
    from torch import nn
    class AttentionNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.gru=nn.GRU(channels,hidden,batch_first=True)
            self.attn=nn.Sequential(nn.Linear(hidden+channels,hidden),nn.Tanh(),nn.Linear(hidden,1))
            self.head=nn.Sequential(nn.Linear(hidden+channels+bizdim,64),nn.ReLU(),nn.Linear(64,12))
            self.next=nn.Linear(hidden,channels//2)
        def forward(self,biz,seq):
            states,_=self.gru(seq[:,:-1])
            current=seq[:,-1:,:].expand(-1,states.shape[1],-1)
            weights=self.attn(torch.cat([states,current],2)).softmax(1)
            context=(weights*states).sum(1)
            pmf=self.head(torch.cat([context,seq[:,-1],biz],1)).reshape(-1,3,4).softmax(2)
            return pmf,self.next(states)
    return AttentionNet()


class NeuralLandmark(Landmark):
    def fit(self,train,calibrate):
        import torch
        torch.set_num_threads(3);torch.manual_seed(self.seed);torch.use_deterministic_algorithms(True)
        self.features.fit(train)
        biz,seq,ids=training_views(train,self.features,self.seed)
        hidden,rank_weight=self.setting
        net=make_network(biz.shape[1],seq.shape[2],hidden)
        optimizer=torch.optim.Adam(net.parameters(),lr=.001,weight_decay=1e-4)
        b=torch.from_numpy(biz);s=torch.from_numpy(seq)
        residual=train['residual'][ids];observed=train['observed'][ids]
        bins=np.searchsorted(self.h,residual,side='left').clip(0,3)
        event=observed&(residual<=self.h[-1])
        # Unknown partial bins contribute only survival through the last fully observed edge.
        completed=np.sum(residual[:,:,None]>=self.h,axis=2)
        allowed=np.arange(4)[None,None,:]>=completed[:,:,None]
        event_index=torch.from_numpy(bins.astype(np.int64));is_event=torch.from_numpy(event)
        survival_mask=torch.from_numpy(allowed);r=torch.from_numpy(residual)
        val_ids=np.arange(0,len(calibrate['t']),max(1,len(calibrate['t'])//10000))
        val=subset(calibrate,val_ids);vy,vk=targets(val,self.h)
        vb,vs=self.features.transform(val)
        vb=torch.from_numpy(vb);vs=torch.from_numpy(vs)
        rng=np.random.default_rng(self.seed);best=np.inf;best_state=None;stale=0;history=[]
        start=time.perf_counter()
        for epoch in range(35):
            net.train();losses=[]
            order=rng.permutation(len(b))
            for first in range(0,len(order),512):
                j=order[first:first+512];pmf,aux=net(b[j],s[j])
                event_prob=pmf.gather(2,event_index[j,:,None]).squeeze(2)
                survival=(pmf*survival_mask[j]).sum(2)
                nll=-torch.log(torch.where(is_event[j],event_prob,survival).clamp_min(1e-7)).mean()
                partner=torch.roll(torch.arange(len(j)),1)
                cdf=pmf.cumsum(2)
                own=cdf.gather(2,event_index[j,:,None]).squeeze(2)
                rival=cdf[partner].gather(2,event_index[j,:,None]).squeeze(2)
                comparable=is_event[j]&(r[j]<r[j][partner])
                ranking=torch.exp(torch.clamp((rival-own)/.1,max=10))[comparable].mean() if comparable.any() else nll*0
                channels=seq.shape[2]//2
                observed_next=1-s[j,1:,channels:]
                auxloss=(((aux-s[j,1:,:channels])**2)*observed_next).sum()/observed_next.sum().clamp_min(1)
                loss=nll+rank_weight*ranking+.01*auxloss
                optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),5);optimizer.step()
                losses.append(float(loss.detach()))
            net.eval()
            with torch.no_grad(): vp=net(vb,vs)[0][:,:,:3].cumsum(2).numpy()
            score=float(((vp-vy)**2)[vk].mean());history.append({'epoch':epoch+1,'loss':float(np.mean(losses)),'calibration_brier':score})
            if score<best-1e-5: best=score;best_state=copy.deepcopy(net.state_dict());stale=0
            else: stale+=1
            if stale>=6: break
        self.weights=best_state;self.bizdim=biz.shape[1];self.channels=seq.shape[2]
        self.fit_rows=len(b);self.fit_seconds=time.perf_counter()-start;self.history=history
        self.calibrate(calibrate)
        return self

    def raw_predict(self,data,lag=0):
        import torch
        torch.set_num_threads(3)
        net=make_network(self.bizdim,self.channels,self.setting[0]);net.load_state_dict(self.weights);net.eval()
        b,s=self.features.transform(data,lag);out=[]
        with torch.no_grad():
            for i in range(0,len(b),2048):
                prob=net(torch.from_numpy(b[i:i+2048]),torch.from_numpy(s[i:i+2048]))[0]
                out.append(prob[:,:,:3].cumsum(2).numpy())
        return np.concatenate(out)


def score(data,pred,horizons):
    y,known=targets(data,horizons)
    sq=(pred-y)**2
    complete=known.all(axis=(1,2))
    return {'brier_known':float(sq[known].mean()),'brier_complete':float(sq[complete].mean()),
            'complete_queries':int(complete.sum()),'by_pattern':[float(sq[:,p,:][known[:,p,:]].mean()) for p in range(3)]}
