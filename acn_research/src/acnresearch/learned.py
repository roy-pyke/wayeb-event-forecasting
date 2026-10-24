"""Fixed train-only survival-CDF baselines, intentionally small-data models."""
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, log_loss
from acnresearch.recovery import FEATURES, horizon_labels
from acnresearch.discovery import monotone_cdf

HORIZONS=np.arange(5,61,5)
MODELS=['empirical','elapsed_logistic','full_logistic','full_gbdt']


class RecoveryCDF:
    def __init__(self,kind):
        self.kind=kind
        self.features=['elapsed_min'] if kind=='elapsed_logistic' else FEATURES

    def matrix(self,frame,h):
        x=frame[self.features].to_numpy(float)
        return np.column_stack([x,np.full(len(frame),h/60)])

    def fit(self,frame):
        arrays=[]; ys=[]; weights=[]; self.base=[]
        masks=[horizon_labels(frame,h)[1] for h in HORIZONS]
        per_record=np.maximum(1,np.asarray(masks).sum(axis=0))
        for h,known in zip(HORIZONS,masks):
            y,_=horizon_labels(frame,h)
            self.base.append(float(y[known].mean()) if known.any() else 0.)
            arrays.append(self.matrix(frame,h)[known]); ys.append(y[known]); weights.append(1/per_record[known])
        self.base=monotone_cdf(self.base)
        if self.kind=='empirical': return self
        x=np.concatenate(arrays); y=np.concatenate(ys); w=np.concatenate(weights)
        self.single_class=len(np.unique(y))<2
        if self.single_class: return self
        if self.kind.endswith('logistic'):
            self.estimator=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),
                                         StandardScaler(),LogisticRegression(C=1,max_iter=3000,random_state=724))
            self.estimator.fit(x,y,logisticregression__sample_weight=w)
        elif self.kind=='full_gbdt':
            self.estimator=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=7,min_samples_leaf=20,
                l2_regularization=1,learning_rate=.05,random_state=724,early_stopping=False)
            self.estimator.fit(x,y,sample_weight=w)
        else: raise ValueError(self.kind)
        return self

    def predict(self,frame):
        if self.kind=='empirical' or self.single_class:
            return np.tile(self.base,(len(frame),1))
        return monotone_cdf(np.column_stack([self.estimator.predict_proba(self.matrix(frame,h))[:,1] for h in HORIZONS]))


def scores(frame,prob):
    result={}
    for j,h in enumerate(HORIZONS):
        y,known=horizon_labels(frame,h); y=y[known]; p=prob[known,j]
        if not len(y): result[str(h)]={'n':0}; continue
        bins=np.minimum(9,(p*10).astype(int)); ece=0.
        for b in range(10):
            m=bins==b
            if m.any(): ece+=m.mean()*abs(p[m].mean()-y[m].mean())
        positive=p>=.5
        tp=int(((y==1)&positive).sum()); fp=int(((y==0)&positive).sum())
        fn=int(((y==1)&~positive).sum()); tn=int(((y==0)&~positive).sum())
        result[str(h)]={'n':len(y),'positives':int(y.sum()),'prevalence':float(y.mean()),
                       'mean_probability':float(p.mean()),'brier':float(np.mean((p-y)**2)),
                       'log_loss':float(log_loss(y,p,labels=[0,1])),
                       'average_precision':float(average_precision_score(y,p)) if y.sum() else None,
                       'ece_10bins':float(ece),'tp':tp,'fp':fp,'fn':fn,'tn':tn}
    return result


def day_bootstrap(values,days,seed=724):
    """Ratio of cluster sums: retains all episodes within each sampled day."""
    values=np.asarray(values,float); days=np.asarray(days)
    unique,inverse=np.unique(days,return_inverse=True)
    if not len(values): return {'n':0,'days':0,'mean':None,'ci95':None}
    sums=np.bincount(inverse,weights=values); counts=np.bincount(inverse)
    rng=np.random.default_rng(seed); draw=rng.integers(0,len(unique),(2000,len(unique)))
    means=sums[draw].sum(axis=1)/counts[draw].sum(axis=1)
    return {'n':len(values),'days':len(unique),'mean':float(values.mean()),
            'ci95':[float(x) for x in np.quantile(means,[.025,.975])],
            'positive':int((values>1e-10).sum()),'negative':int((values< -1e-10).sum()),'ties':int((abs(values)<=1e-10).sum())}
