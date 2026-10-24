"""Run development once, freeze comparator, then evaluate held-out traces."""
import argparse
import csv
import hashlib
import json
import time
import numpy as np
from common import DATA, REPORT, HERE, save, protocol
from recurrent.data import read_avt, windows, transition
from recurrent.replay import POLICIES, arrivals_for, simulate

COMPARATORS = ['edf','fixed_backoff_2','exponential_backoff_1_2_4',
               'myopic_value','urgency_value','independent_two_step']


def run_trace(trace, split, rates):
    p01,p11=transition(rates,trace.step)
    rows=[]
    for number,(start,chosen,states,initial,status) in enumerate(windows(trace,split,240 if split=='dev' else 480)):
        if len(states)==0:
            continue
        arrivals=arrivals_for(trace.name,start)
        for k in protocol()['workload']['capacities']:
            for policy in POLICIES:
                stats,_=simulate(states,initial,arrivals,policy,k,p01,p11)
                rows.append({'dataset':trace.name,'split':split,'window_start':start,'capacity':k,
                             'policy':policy,'measurement_status':status,**stats})
        if number%40==0:
            print(trace.name,split,'selected window',number,'rows',len(rows),flush=True)
    return rows


def write_rows(path,rows):
    with path.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def paired(rows, dataset, k, baseline):
    use=[x for x in rows if x['dataset']==dataset and x['capacity']==k]
    candidate={x['window_start']:x for x in use if x['policy']=='joint_two_step'}
    base={x['window_start']:x for x in use if x['policy']==baseline}
    if set(candidate)!=set(base):raise AssertionError('Unpaired windows')
    keys=sorted(candidate)
    d=np.asarray([candidate[t]['completed_value']-base[t]['completed_value'] for t in keys],dtype=float)
    rng=np.random.default_rng(23028)
    boot=d[rng.integers(0,len(d),(2000,len(d)))].mean(axis=1)
    failures=np.asarray([candidate[t]['failed_attempts']-base[t]['failed_attempts'] for t in keys],dtype=float)
    return {'n_windows':len(d),'mean_completed_value_difference':float(d.mean()),
            'total_completed_value_difference':float(d.sum()),
            'paired_bootstrap_95':np.percentile(boot,[2.5,97.5]).tolist(),
            'wins':int((d>0).sum()),'ties':int((d==0).sum()),'losses':int((d<0).sum()),
            'mean_failed_attempt_difference':float(failures.mean()),
            'relative_completed_value_gain':float(d.sum()/sum(base[t]['completed_value'] for t in keys))}


def summarize(rows, comparator):
    summary={}
    for dataset in sorted({x['dataset'] for x in rows}):
        summary[dataset]={}
        for k in [1,2,4,6]:
            use=[x for x in rows if x['dataset']==dataset and x['capacity']==k]
            aggregates={}
            for policy in POLICIES:
                sample=[x for x in use if x['policy']==policy]
                numeric=['completed_value','completed_records','failed_attempts','attempts','expired_value',
                         'rejected_value','pending_value','arrived_value','runtime_seconds']
                aggregates[policy]={key:float(sum(x[key] for x in sample)) for key in numeric}
                aggregates[policy]['n_windows']=len(sample)
                aggregates[policy]['microseconds_per_slot']=1e6*aggregates[policy]['runtime_seconds']/sum(x['observed_slots'] for x in sample)
            summary[dataset][str(k)]={'aggregates':aggregates,
                                      'candidate_minus':{p:paired(rows,dataset,k,p) for p in POLICIES if p!='joint_two_step'},
                                      'selected_comparator':comparator}
    return summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['dev','test']);args=parser.parse_args()
    rates=json.loads((REPORT/'model.json').read_text())
    web=read_avt(DATA/'web_sites.avt',600)
    if args.phase=='dev':
        rows=run_trace(web,'dev',rates)
        scores={p:sum(x['completed_value'] for x in rows if x['policy']==p and x['capacity']==2) for p in COMPARATORS}
        selected=max(COMPARATORS,key=lambda p:scores[p])
        selection={'comparator':selected,'development_K2_total_value':scores,
                   'model_sha256':hashlib.sha256((REPORT/'model.json').read_bytes()).hexdigest(),
                   'protocol_sha256':hashlib.sha256((HERE/'configs/PROTOCOL_R2.json').read_bytes()).hexdigest(),
                   'algorithm':'exact two-slot joint recourse; no parameter selection',
                   'frozen_before_controller_test':True}
        save(REPORT/'selection.json',selection)
    else:
        selection=json.loads((REPORT/'selection.json').read_text())
        assert selection['model_sha256']==hashlib.sha256((REPORT/'model.json').read_bytes()).hexdigest()
        assert selection['protocol_sha256']==hashlib.sha256((HERE/'configs/PROTOCOL_R2.json').read_bytes()).hexdigest()
        selected=selection['comparator']
        rows=run_trace(web,'test',rates)+run_trace(read_avt(DATA/'pl-app.avt',900),'test',rates)
    write_rows(REPORT/f'{args.phase}_windows.csv',rows)
    summary=summarize(rows,selected)
    save(REPORT/f'{args.phase}_summary.json',summary)
    for dataset,result in summary.items():
        print(dataset,'K2 versus',selected,result['2']['candidate_minus'][selected],flush=True)
        print(dataset,'K2 versus additive',result['2']['candidate_minus']['independent_two_step'],flush=True)


if __name__=='__main__':main()
