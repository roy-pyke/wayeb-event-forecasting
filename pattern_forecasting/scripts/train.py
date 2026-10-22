"""Development-only baseline selection; no holdout access."""
import argparse,json,time
import joblib
import numpy as np
from patternforecast.common import PACKAGE,RUNS,protocol,write_json,sha256,experiment_cfg
from patternforecast.data import load
from patternforecast.models import Landmark,NeuralLandmark,score

parser=argparse.ArgumentParser();parser.add_argument('--datasets',nargs='+',default=['air','power','metro'])
parser.add_argument('--replicates',action='store_true')
parser.add_argument('--profile',choices=['long','short'],default='long')
parser.add_argument('--families',nargs='+',default=['hgb','extra_trees','gru','business','no_state']);args=parser.parse_args()
plan=json.loads((PACKAGE/'configs/TRAINING.json').read_text())
for name in args.datasets:
    cfg=experiment_cfg(name,args.profile)
    train,cal,dev=[load(name,split) for split in ('train','calibrate','development')]
    out=RUNS/name;out.mkdir(parents=True,exist_ok=True)
    suffix='' if args.profile=='long' else '-short'
    report_path=PACKAGE/'reports'/f'models-{name}{suffix}.json'
    report=json.loads(report_path.read_text()) if report_path.exists() else {'dataset':name,'runs':{},'selection':{}}
    families=args.families
    for family in families:
        settings=plan[family] if family in plan else [plan['hgb'][1]]
        seeds=[20261022]
        if args.replicates:
            if family in ('business','no_state'): continue
            seeds=plan['seed_replicates'][1:]
            settings=[report['selection'][family]['setting']]
        for setting in settings:
            for seed in seeds:
                key=('short-' if args.profile=='short' else '')+f'{family}-'+ '-'.join(map(str,setting))+f'-s{seed}'
                path=out/f'{key}.joblib'
                if key in report['runs'] and path.exists(): continue
                print('FIT',name,key,flush=True)
                cls=NeuralLandmark if family=='gru' else Landmark
                kind='extra_trees' if family=='extra_trees' else 'hgb'
                model=cls(cfg,kind,setting,seed,business_only=family=='business',no_state=family=='no_state')
                model.fit(train,cal)
                start=time.perf_counter();pred=model.predict(dev);predict_seconds=time.perf_counter()-start
                np.save(out/f'{key}-development.npy',pred.astype(np.float32))
                joblib.dump(model,path,compress=3)
                result=dict(family=family,setting=setting,seed=seed,**score(dev,pred,cfg['horizon_samples']),
                            fit_seconds=model.fit_seconds,fit_rows=model.fit_rows,predict_seconds=predict_seconds,
                            model_sha256=sha256(path))
                if hasattr(model,'history'): result['learning_curve']=model.history
                report['runs'][key]=result
                candidates={k:v for k,v in report['runs'].items() if v['family']==family and v['seed']==20261022}
                best=min(candidates,key=lambda k:candidates[k]['brier_complete'])
                report['selection'][family]={'key':best,**candidates[best]}
                write_json(report_path,report)
                print(name,key,{k:v for k,v in result.items() if k!='learning_curve'},flush=True)
    available={k:v for k,v in report['selection'].items() if k in ['hgb','extra_trees','gru']}
    best=min(available,key=lambda k:available[k]['brier_complete'])
    report['communication_backbone']=report['selection'][best]['key']
    write_json(report_path,report)
