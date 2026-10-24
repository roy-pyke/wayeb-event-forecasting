"""Fit/freeze on office train+development, then evaluate untouched site models."""
from pathlib import Path
import argparse,hashlib,json,pickle,sys
from datetime import datetime,timezone
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]; HERE=ROOT/'acn_research'
sys.path.insert(0,str(HERE/'src'))
from acnresearch.recovery import horizon_labels,complete_episode_mask
from acnresearch.learned import RecoveryCDF,MODELS,HORIZONS,scores,day_bootstrap
from acnresearch.discovery import run_discovery,perturb_cdf
PRIVATE=ROOT/'artifacts/acn/r1'; OUT=HERE/'reports/r1'
FIXED=['every_1','every_2','every_4','backoff']; WEIGHTS=[.25,1.,4.]
THRESHOLDS=[.05,.1,.2,.4,.6,.8]


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(g,probs,kind,weight,threshold=.2):
    rows=[]
    for (_,r),p in zip(g.iterrows(),probs):
        terminal=float(r.observed_min) if r.terminal else 60.
        rows.append(run_discovery(r.event_min,terminal,p,kind,weight,threshold))
    return pd.DataFrame(rows,index=g.index)


def choice_on_development(dev,predictions):
    known=complete_episode_mask(dev); g=dev.loc[known]
    choices={}; detail={}
    for w in WEIGHTS:
        fixed={s:float(simulate(g,predictions['empirical'][known],s,w).cost.mean()) for s in FIXED}
        thresholds={}; threshold_scores={}
        for name in MODELS:
            costs={str(t):float(simulate(g,predictions[name][known],'threshold',w,t).cost.mean()) for t in THRESHOLDS}
            thresholds[name]=float(min(costs,key=lambda x:(costs[x],float(x))))
            threshold_scores[name]=costs
        choices[str(w)]={'fixed':min(fixed,key=lambda x:(fixed[x],x)),'thresholds':thresholds}
        detail[str(w)]={'fixed_scores':fixed,'threshold_scores':threshold_scores}
    return choices,detail


def evaluate_group(g,preds,selection,label):
    model_scores={name:scores(g,p) for name,p in preds.items()}
    selected=selection['forecast']; known=complete_episode_mask(g); complete=g.loc[known]
    comparisons={}; metrics={}; traces=[]
    for w in WEIGHTS:
        setting=selection['policy'][str(w)]; policies={s:(s,preds['empirical'][known],.2) for s in FIXED}
        for model in MODELS:
            policies[model+'_dp']=('dp',preds[model][known],.2)
            policies[model+'_threshold']=('threshold',preds[model][known],setting['thresholds'][model])
        for change in ['early_10min','late_10min','inflate_0p2']:
            policies[selected+'_dp_'+change]=('dp',np.array([perturb_cdf(p,change) for p in preds[selected][known]]),.2)
        runs={}
        for name,(kind,prob,threshold) in policies.items():
            r=simulate(complete,prob,kind,w,threshold); runs[name]=r
            recovered=complete.event_min.notna().to_numpy()
            metrics[f'{w}:{name}']={'n':len(r),'cost':float(r.cost.mean()),'failed_probes':float(r.failed_probes.mean()),
                                    'delay_minutes_per_recovered':float(r.delay_slots.to_numpy()[recovered].mean()*5) if recovered.any() else None,
                                    'missed':int(r.missed.sum()),'recoveries':int(recovered.sum())}
            saved=r.drop(columns='probe_slots').copy(); saved['key']=complete.key; saved['day']=complete.day
            saved['policy']=name; saved['weight']=w; saved['group']=label; traces.append(saved)
        for name in policies:
            comparisons[f'{w}:{name}_minus_fixed']=day_bootstrap(runs[name].cost-runs[setting['fixed']].cost,complete.day)
        for baseline in ['empirical_dp',selected+'_threshold','full_gbdt_dp','full_logistic_dp']:
            comparisons[f'{w}:selected_dp_minus_{baseline}']=day_bootstrap(runs[selected+'_dp'].cost-runs[baseline].cost,complete.day)
    brier_pairs={}
    for h in [15,60]:
        y,m=horizon_labels(g,h); j=int(h/5)-1
        for model in MODELS:
            differences=(preds[model][m,j]-y[m])**2-(preds['empirical'][m,j]-y[m])**2
            brier_pairs[f'{h}:{model}_minus_empirical']=day_bootstrap(differences,g.day.to_numpy()[m])
    return {'alarms':len(g),'complete_discovery_outcomes':len(complete),
            'prediction':model_scores,'brier_comparisons':brier_pairs,
            'discovery_metrics':metrics,'discovery_comparisons':comparisons},pd.concat(traces,ignore_index=True)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--phase',choices=['development','evaluation'],required=True)
    args=ap.parse_args(); office=pd.read_pickle(PRIVATE/'office_episodes.pkl')
    protocol=HERE/'configs/LEARNED_PROTOCOL_R1.json'
    if args.phase=='development':
        train=office.loc[office.split.eq('train')]; dev=office.loc[office.split.eq('development')]
        models={name:RecoveryCDF(name).fit(train) for name in MODELS}
        preds={name:model.predict(dev) for name,model in models.items()}
        performance={name:scores(dev,p) for name,p in preds.items()}
        objective={name:float(np.mean([v['brier'] for v in s.values() if v['n']])) for name,s in performance.items()}
        selection={'protocol_sha256':digest(protocol),'created_utc':datetime.now(timezone.utc).isoformat(),
                   'forecast':min(objective,key=lambda x:(objective[x],x)),
                   'forecast_selection_mean_brier':objective,'training_alarms':len(train),'development_alarms':len(dev)}
        selection['policy'],selection['policy_selection_scores']=choice_on_development(dev,preds)
        with (PRIVATE/'models.pkl').open('wb') as f: pickle.dump(models,f)
        selection['models_sha256']=digest(PRIVATE/'models.pkl')
        selection['source_sha256']={p.name:digest(p) for p in (HERE/'src/acnresearch').glob('*.py')}
        (OUT/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
        result,traces=evaluate_group(dev,preds,selection,'development')
        (OUT/'development.json').write_text(json.dumps(result,indent=2)+'\n')
        traces.to_pickle(PRIVATE/'development_discovery.pkl')
        print(json.dumps({k:v for k,v in selection.items() if k not in ['source_sha256','policy_selection_scores']},indent=2),flush=True)
    else:
        selection=json.loads((OUT/'selection.json').read_text())
        assert digest(protocol)==selection['protocol_sha256']
        assert digest(PRIVATE/'models.pkl')==selection['models_sha256']
        with (PRIVATE/'models.pkl').open('rb') as f: models=pickle.load(f)
        external=[pd.read_pickle(PRIVATE/f'{site}_episodes.pkl') for site in ['caltech','jpl']]
        data=pd.concat([office.loc[office.split.eq('office_test')],*external],ignore_index=True)
        allpred={name:model.predict(data) for name,model in models.items()}
        # Private CDFs are also the only learned input to optional coupled control.
        with (PRIVATE/'evaluation_predictions.pkl').open('wb') as f: pickle.dump({'frame':data,'cdf':allpred},f)
        groups={}; traces=[]
        for label,g in data.groupby('split'):
            preds={name:p[g.index] for name,p in allpred.items()}
            groups[label],detail=evaluate_group(g,preds,selection,label); traces.append(detail)
            print(label,'evaluation complete',len(g),'alarms',flush=True)
        (OUT/'evaluation.json').write_text(json.dumps({'scope':'R1 observational prediction + absorbing-recovery discovery diagnostic; not production causal effect',
             'selection':{k:v for k,v in selection.items() if k!='policy_selection_scores'},'groups':groups},indent=2)+'\n')
        pd.concat(traces,ignore_index=True).to_pickle(PRIVATE/'evaluation_discovery.pkl')
        print('saved',OUT/'evaluation.json',flush=True)


if __name__=='__main__': main()
