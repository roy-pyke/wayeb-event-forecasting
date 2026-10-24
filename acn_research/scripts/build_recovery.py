"""Audit real recordings; private features stay ignored, aggregates are tracked."""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json, sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]; HERE=ROOT/'acn_research'
sys.path.insert(0,str(HERE/'src'))
from acnresearch.recovery import extract_episode, horizon_labels, complete_episode_mask
from acnresearch.requests import recording_filename


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--sites',nargs='+',default=['office','caltech','jpl'])
    args=ap.parse_args(); out=HERE/'reports/r1'; out.mkdir(exist_ok=True)
    private=ROOT/'artifacts/acn/r1'; private.mkdir(exist_ok=True)
    summary={}
    for site in args.sites:
        base=ROOT/'artifacts/acn'/site
        name='full_download_manifest.json' if site=='office' else 'r1_download_manifest.json'
        manifest=json.loads((base/name).read_text())
        sessions=json.loads((ROOT/'artifacts/acn/requests'/f'{site}.json').read_text())['_items']
        byfile={recording_filename(s['sessionID']):s for s in sessions}
        rows=[]; allrows=[]; counts=Counter()
        for n,m in enumerate(manifest):
            path=ROOT/m['path']; assert hashlib.sha256(path.read_bytes()).hexdigest()==m['sha256']
            df=pd.read_csv(path,index_col=0); df.index=pd.to_datetime(df.index,utc=True)
            start=df.index[0]; end=df.index[-1]
            key=hashlib.sha256((site+'/'+path.name).encode()).hexdigest()
            row,reason=extract_episode(df,byfile.get(path.name))
            counts[reason]+=1; counts['files']+=1; counts['rows']+=len(df)
            counts['metadata_matched']+=path.name in byfile
            allrows.append(dict(key=key,start=start,end=end))
            if row is not None:
                rows.append(dict(key=key,site=site,day=start.date().isoformat(),start=start.isoformat(),end=end.isoformat(),**row))
            if (n+1)%300==0: print(site,'extracted',n+1,flush=True)
        af=pd.DataFrame(allrows).sort_values(['start','key']); data=pd.DataFrame(rows)
        if site=='office':
            # Assign start days as indivisible units. Purge full recordings that
            # cross a later split boundary, even if their label window is short.
            a=af.iloc[int(.6*len(af))].start.normalize(); b=af.iloc[int(.8*len(af))].start.normalize()
            st=pd.to_datetime(data.start,utc=True); en=pd.to_datetime(data.end,utc=True)
            data['split']=np.where(st<a,'train',np.where(st<b,'development','office_test'))
            purge=((st<a)&(en>=a))|((st>=a)&(st<b)&(en>=b))
            data.loc[purge,'split']='purged'
            boundaries=[a.isoformat(),b.isoformat()]
        else: data['split']=site; boundaries=[]
        data.to_pickle(private/f'{site}_episodes.pkl')
        (private/f'{site}_all_sessions.json').write_text(af.to_json(orient='records',date_format='iso'))
        groups={}
        for split,g in data.groupby('split'):
            groups[split]={'alarms':len(g),'sustained_recoveries':int(g.event_min.notna().sum()),
                          'any_rebound':int(g.rebound_min.notna().sum()),
                          'complete_60min_outcomes':int(complete_episode_mask(g).sum()),
                          'known_requests':int(g.request_known.sum()),
                          'known_unmet_future_request':int(((g.remaining_kwh>=.1)&(g.slack_min>0)).sum()),
                          'eligible_sustained_recoveries':int(((g.remaining_kwh>=.1)&(g.slack_min>g.event_min)&g.event_min.notna()).sum()),
                          'outcomes':{str(k):int(v) for k,v in g.reason.value_counts().items()},
                          'horizons':{str(h):{'known':int(horizon_labels(g,h)[1].sum()),'positive':int(horizon_labels(g,h)[0].sum())} for h in [5,15,30,60]}}
        summary[site]={'counts':dict(counts),'split_boundaries_utc':boundaries,'groups':groups,
                       'private_table_sha256':hashlib.sha256((private/f'{site}_episodes.pkl').read_bytes()).hexdigest(),
                       'first_start':af.start.min().isoformat(),'last_start':af.start.max().isoformat()}
        (out/f'{site}_audit.json').write_text(json.dumps(summary[site],indent=2)+'\n')
        print(site,json.dumps(summary[site]),flush=True)


if __name__=='__main__': main()
