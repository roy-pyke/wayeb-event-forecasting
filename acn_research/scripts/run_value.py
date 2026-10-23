"""Separate development selection from fixed held-out synthetic evaluation."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from datetime import datetime,timezone
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]; HERE=ROOT/'acn_research'
sys.path.insert(0,str(HERE/'src'))
from acnresearch.value import make_world,run_policy,run_native


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--phase',choices=['development','evaluation'],required=True)
    parser.add_argument('--revision',choices=['c1','c2'],default='c1')
    args=parser.parse_args()
    protocol=HERE/('configs/VALUE_PROTOCOL_C2.json' if args.revision=='c2' else 'configs/VALUE_PROTOCOL.json'); cfg=json.loads(protocol.read_text())
    report_dir=HERE/'reports'/('c2' if args.revision=='c2' else '')
    report_dir.mkdir(parents=True,exist_ok=True)
    protohash=hashlib.sha256(protocol.read_bytes()).hexdigest()
    trace_dir=ROOT/'artifacts/acn/value'/('c2' if args.revision=='c2' else '')/args.phase; trace_dir.mkdir(parents=True,exist_ok=True)
    freeze=report_dir/'value_selection.json'
    if args.revision=='c2':
        import inspect,adacharge.postprocessing
        assert '<= peak_limit + 1e-5' in inspect.getsource(adacharge.postprocessing)
    from types import SimpleNamespace
    from acnportal.acnsim.interface import SessionInfo
    from acnportal.algorithms.preprocessing import apply_upper_bound_estimate
    test_session=SessionInfo('station','session',5,0,0,10,10,0)
    assert np.all(apply_upper_bound_estimate(SimpleNamespace(get_maximum_rates=lambda _:{'session':11}),[test_session])[0].max_rates==11)
    if args.phase=='development':
        seeds=cfg['development_seeds']; conditions=['pause']
        # One duration is selected on current-state MPC, then used by all MPCs.
        policies=[('native',None),('edf',None),('llf',None)]
        for duration in cfg['baseline_duration_candidates_slots']:
            policies.extend([('causal_mpc',duration),('current_mpc',duration)])
    else:
        selection=json.loads(freeze.read_text()); assert selection['protocol_sha256']==protohash
        seeds=cfg['evaluation_seeds']; conditions=['pause','no_pause']
        duration=selection['duration_slots']
        policies=[(x,duration) for x in ['native','edf','llf','causal_mpc','current_mpc','lead1_mpc','lead3_mpc','resume_oracle_mpc']]
    results=[]
    for condition in conditions:
        for cap in cfg['world']['feeder_amp']:
            for seed in seeds:
                world=make_world(seed,cap,pause=condition=='pause')
                offline,trace=run_policy(world,'offline')
                np.savez_compressed(trace_dir/f'{condition}-{cap}-{seed}-world.npz',
                                    demand=world.public.demand,departure=world.public.departure,
                                    acceptance=world.acceptance,offline=trace['actual'])
                rows=[dict(policy='offline',duration_slots=0,**offline)]
                for name,duration in policies:
                    result,trace=run_native(world) if name=='native' else run_policy(world,name,duration or 4)
                    assert result['delivered_kwh']<=offline['delivered_kwh']+1e-6
                    rows.append(dict(policy=name,duration_slots=duration or 0,**result))
                    np.savez_compressed(trace_dir/f'{condition}-{cap}-{seed}-{name}-{duration}.npz',**trace)
                for row in rows:
                    row.update(condition=condition,feeder_amp=cap,seed=seed,
                               requested_kwh=float(world.public.demand.sum()*world.public.quantum_kwh))
                results.extend(rows)
            print(args.phase,condition,cap,'complete',flush=True)
    table=pd.DataFrame(results)
    table.to_csv(report_dir/f'value_{args.phase}.csv',index=False)
    if args.phase=='development':
        current=table[table.policy.eq('current_mpc')].groupby('duration_slots').delivered_kwh.mean()
        duration=int(current.idxmax())
        eligible=table[table.policy.isin(['native','edf','llf']) | (table.policy.eq('causal_mpc') & table.duration_slots.eq(duration))]
        scores=eligible.groupby('policy').delivered_kwh.mean()
        out={'created_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':protohash,
             'development_seeds':seeds,'duration_slots':duration,'selected_causal_policy':str(scores.idxmax()),
             'current_mpc_duration_mean_kwh':{str(k):float(v) for k,v in current.items()},
             'causal_policy_mean_kwh':{str(k):float(v) for k,v in scores.items()},
             'scope':'Global development selection only. Same duration in every held-out MPC. No per-test-world best choice.'}
        freeze.write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))
    else:
        print('evaluation rows',len(table),flush=True)


if __name__=='__main__': main()
