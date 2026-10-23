"""All completed development controls, paired origins, no silent failed-run deletion."""
import json
import numpy as np
from queryforecast.common import CACHE,REPORTS,PROTOCOL,save

MODES=['balanced','overflow','moment-basis-v2','markov-control','particle-control']
CANDIDATES={'Q3':'balanced/harmonic','Q4':'overflow/harmonic','Q5':'moment-basis-v2/occupancy_symbol'}
result={'scope':'development only, same frozen source/query/input/budget; no unopened years',
        'bootstrap':'5000 paired-origin bootstrap resamples, fixed selected comparator and reselected best comparator both reported',
        'runtime':'Concurrent experiment times are descriptive; serial timing is required separately.',
        'domains':{}}
for domain in ['air','power']:
    summary={};errors={};missing=[];reference_truth=None
    for mode in MODES:
        report=REPORTS/f'{domain}-{mode}.json'
        if not report.exists():missing.append(mode);continue
        report=json.loads(report.read_text())
        paths=sorted((CACHE/domain/mode).glob('origin-*.npz'))
        if len(paths)!=48 or report['origins']!=48 or report['replicates']!=32:
            raise AssertionError('incomplete/full report mismatch')
        values=[dict(np.load(p)) for p in paths]
        truth=np.array([v['truth'] for v in values])
        if reference_truth is None:reference_truth=truth
        else:np.testing.assert_allclose(truth,reference_truth,rtol=0,atol=1e-13)
        for k,method in enumerate(report['methods']):
            name=mode+'/'+method
            finite=all(np.isfinite(v['estimates'][1,k]).all() for v in values)
            e=np.array([np.mean((v['estimates'][1,k]-v['truth'])**2) for v in values])
            summary[name]={'mse':float(e.mean()) if finite else None,
              'seconds_concurrent':float(np.mean([v['seconds'][1,k] for v in values])),
              'rows':float(np.mean([v['rows'][1,k] for v in values])),
              'infeasible_runs':int(sum((~v.get('feasible',np.ones(v['rows'].shape,bool))[1,k]).sum() for v in values))}
            if finite:errors[name]=e
    names=list(errors);matrix=np.array([errors[n] for n in names]).T
    ids=np.random.default_rng(PROTOCOL['seed']).integers(48,size=(5000,48))
    means=matrix[ids].mean(1);gates={}
    for stage,name in CANDIDATES.items():
        if name not in names:
            gates[stage]={'status':'missing or infeasible'};continue
        k=names.index(name);others=[i for i in range(len(names)) if i!=k]
        best=min(others,key=lambda i:matrix[:,i].mean())
        base=matrix[:,best].mean();candidate=matrix[:,k].mean()
        if base<=1e-30:
            gain=0. if candidate<=1e-30 else None
            fixed_ci=reselected_ci=None;passes=candidate<=1e-30
        else:
            gain=1-candidate/base
            fixed_ci=np.quantile(1-means[:,k]/np.maximum(means[:,best],1e-30),[.025,.975]).tolist()
            reselected_ci=np.quantile(1-means[:,k]/np.maximum(means[:,others].min(1),1e-30),[.025,.975]).tolist()
            passes=bool(gain>=.2 and reselected_ci[0]>0)
        gates[stage]={'candidate':name,'best_comparator':names[best],
          'relative_mse_reduction':gain,'paired_origin_95_fixed':fixed_ci,'paired_origin_95_reselected_best':reselected_ci,
          'mse_gate':passes,'inference_status':'complete development comparison' if not missing else 'provisional; stronger runs pending',
          'concurrent_time_ratio':summary[name]['seconds_concurrent']/summary[names[best]]['seconds_concurrent']}
    result['domains'][domain]={'missing':missing,'methods':summary,'gates':gates}
result['independent_confirmation']='NOT RUN; remaining years closed'
save(REPORTS/'evidence-summary.json',result)
for domain,d in result['domains'].items():print(domain,'pending',d['missing'],'gates',d['gates'])
