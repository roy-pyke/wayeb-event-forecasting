"""Matched physical worlds at 1-minute feedback/dispatch; no new tuning."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]; HERE=ROOT/'acn_research'
sys.path.insert(0,str(HERE/'src'))
from acnresearch.value import make_world,refine_world,run_native,run_policy,SOLVER_DIAGNOSTICS
from analyze_value import paired_summary


def main():
    cfg=json.loads((HERE/'configs/VALUE_PROTOCOL_C2.json').read_text())
    selection=json.loads((HERE/'reports/c2/value_selection.json').read_text())
    baseline=selection['selected_causal_policy']; duration=selection['duration_slots']*5
    names=list(dict.fromkeys(['offline',baseline,'edf','current_mpc','resume_oracle_mpc']))
    directory=ROOT/'artifacts/acn/value/feedback_1min'; directory.mkdir(parents=True,exist_ok=True)
    rows=[]
    for cap in cfg['world']['feeder_amp']:
        for seed in cfg['evaluation_seeds']:
            world=refine_world(make_world(seed,cap))
            bound=None
            for name in names:
                result,trace=run_native(world) if name=='native' else run_policy(world,name,duration)
                if name=='offline': bound=result['delivered_kwh']
                assert result['delivered_kwh']<=bound+1e-6
                rows.append(dict(feeder_amp=cap,seed=seed,policy=name,**result))
                np.savez_compressed(directory/f'{cap}-{seed}-{name}.npz',**trace)
        print('fast feedback',cap,'complete',flush=True)
    df=pd.DataFrame(rows); df.to_csv(HERE/'reports/c2/feedback_1min.csv',index=False)
    slow=pd.read_csv(HERE/'reports/c2/value_evaluation.csv')
    result={'scope':'Matched synthetic worlds with 1-minute instead of 5-minute feedback and dispatch; finer action space changes too',
            'protocol_sha256':hashlib.sha256((HERE/'configs/FEEDBACK_PROTOCOL.json').read_bytes()).hexdigest(),
            'policy_world_runs':len(rows),'baseline':baseline,'groups':{}}
    (HERE/'reports/c2/solver_diagnostics_feedback.json').write_text(json.dumps(SOLVER_DIAGNOSTICS,indent=2)+'\n')
    for cap,g in df.groupby('feeder_amp'):
        p=g.pivot(index='seed',columns='policy',values='delivered_kwh')
        s=slow[slow.feeder_amp.eq(cap)&slow.condition.eq('pause')].pivot(index='seed',columns='policy',values='delivered_kwh')
        result['groups'][str(cap)]={
            'means_kwh':{k:float(v) for k,v in p.mean().items()},
            'current_minus_causal_1min':paired_summary(p.current_mpc-p[baseline]),
            'current_minus_causal_5min':paired_summary(s.current_mpc-s[baseline]),
            'oracle_minus_current_1min':paired_summary(p.resume_oracle_mpc-p.current_mpc),
            'offline_minus_current_1min':paired_summary(p.offline-p.current_mpc),
            'fast_minus_slow_causal':paired_summary(p[baseline]-s[baseline])}
    (HERE/'reports/c2/feedback_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__': main()
