"""Freeze a conventional probing baseline, then test operational notices."""
from pathlib import Path
import argparse,hashlib,json,sys
from datetime import datetime,timezone
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]; HERE=ROOT/'acn_research'
sys.path.insert(0,str(HERE/'src'))
from acnresearch.probing import run_probe
from acnresearch.value import make_world,run_policy,SOLVER_DIAGNOSTICS
from analyze_value import paired_summary


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--phase',choices=['development','evaluation'],required=True)
    ap.add_argument('--revision',choices=['p1','p2'],default='p1')
    args=ap.parse_args(); path=HERE/('configs/PROBING_PROTOCOL_P2.json' if args.revision=='p2' else 'configs/PROBING_PROTOCOL.json'); cfg=json.loads(path.read_text())
    protohash=hashlib.sha256(path.read_bytes()).hexdigest()
    subdir='probing_p2' if args.revision=='p2' else 'probing'
    out=HERE/'reports'/subdir; out.mkdir(exist_ok=True)
    traces=ROOT/'artifacts/acn'/subdir/args.phase; traces.mkdir(parents=True,exist_ok=True)
    if args.phase=='development':
        policies={s:(s,None) for s in ['every_1','every_2','every_4','backoff']}
        seeds=cfg['development_seeds']; conditions=['pause']
    else:
        sel=json.loads((out/'selection.json').read_text()); assert sel['protocol_sha256']==protohash
        policies={'selected_causal':(sel['setting'],None),'every_slot':('every_1',None),
                  'notice_15min':(sel['setting'],3),'notice_full':(sel['setting'],-1)}
        seeds=cfg['evaluation_seeds']; conditions=['pause','no_pause']
    rows=[]
    for condition in conditions:
        for cap in cfg['feeder_amp']:
            for seed in seeds:
                w=make_world(seed,cap,condition=='pause')
                bound,trace=run_policy(w,'offline'); local=[]
                if args.phase=='evaluation':
                    local.append(dict(policy='offline',**bound))
                    current,_=run_policy(w,'current_mpc',duration=2)
                    local.append(dict(policy='current_mpc',**current))
                for name,(setting,lead) in policies.items():
                    result,trace=run_probe(w,setting,lead,fill_spare=args.revision=='p2')
                    assert result['delivered_kwh']<=bound['delivered_kwh']+1e-6
                    if args.revision=='p2' and cap==180:
                        assert abs(result['delivered_kwh']-bound['delivered_kwh'])<1e-6
                    local.append(dict(policy=name,**result))
                    np.savez_compressed(traces/f'{condition}-{cap}-{seed}-{name}.npz',**trace)
                rows.extend(dict(condition=condition,feeder_amp=cap,seed=seed,**r) for r in local)
            print(args.phase,condition,cap,'complete',flush=True)
    df=pd.DataFrame(rows); df.to_csv(out/f'{args.phase}.csv',index=False)
    (out/f'solver_diagnostics_{args.phase}.json').write_text(json.dumps(SOLVER_DIAGNOSTICS,indent=2)+'\n')
    if args.phase=='development':
        scores=df.groupby('policy',sort=False).delivered_kwh.mean()
        selection={'protocol_sha256':protohash,'created_utc':datetime.now(timezone.utc).isoformat(),
                   'setting':str(scores.idxmax()),'development_mean_kwh':{k:float(v) for k,v in scores.items()}}
        (out/'selection.json').write_text(json.dumps(selection,indent=2)+'\n'); print(json.dumps(selection,indent=2))
    else:
        result={'scope':'Operational perfect recovery-notice diagnostic, not a trained predictor or production causal estimate',
                'policy_world_runs':len(df),'selection':sel,'groups':{}}
        for (cond,cap),g in df.groupby(['condition','feeder_amp']):
            p=g.pivot(index='seed',columns='policy',values='delivered_kwh')
            result['groups'][f'{cond}_{cap}A']={'means_kwh':{k:float(v) for k,v in p.mean().items()},
                'mean_wasted_reservation_kwh':{k:float(v) for k,v in g.groupby('policy').wasted_reserved_kwh.mean().items()},
                'selected_minus_every_slot':paired_summary(p.selected_causal-p.every_slot),
                'notice15_minus_selected':paired_summary(p.notice_15min-p.selected_causal),
                'noticefull_minus_selected':paired_summary(p.notice_full-p.selected_causal),
                'offline_minus_selected':paired_summary(p.offline-p.selected_causal)}
        (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))


if __name__=='__main__': main()
