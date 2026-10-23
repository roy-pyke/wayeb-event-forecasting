"""Join first alarms to as-of requests; do not infer counterfactual benefit."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]; HERE=ROOT/'acn_research'
sys.path.insert(0,str(HERE/'src'))
from acnresearch.alarms import first_alarm
from acnresearch.requests import recording_filename,request_asof,timestamp


def main():
    raw=ROOT/'artifacts/acn/office'
    manifest=json.loads((raw/'full_download_manifest.json').read_text())
    sessions=json.loads((ROOT/'artifacts/acn/requests/office.json').read_text())['_items']
    byfile={recording_filename(s['sessionID']):s for s in sessions}
    assert len(byfile)==len(sessions)
    old=json.loads((HERE/'reference/acn_probe/protocol.json').read_text())
    development={Path(e['path']).name for e in old['selection_manifest']}
    oldalarms=pd.read_csv(HERE/'reference/acn_probe/inactivity_alarms.csv')
    oldfirst=oldalarms.loc[oldalarms.threshold_amp.eq(.5)].sort_values('alarm_time').drop_duplicates('file').set_index('file')
    groups={'development_128':Counter(),'new_1346_same_site':Counter()}
    private=[]
    for n,m in enumerate(manifest):
        path=ROOT/m['path']; data=path.read_bytes()
        assert hashlib.sha256(data).hexdigest()==m['sha256']
        df=pd.read_csv(path,index_col=0); df.index=pd.to_datetime(df.index,utc=True)
        g='development_128' if path.name in development else 'new_1346_same_site'
        c=groups[g]; c['sessions']+=1; c['rows']+=len(df)
        s=byfile.get(path.name); c['metadata_matches']+=s is not None
        alarm=first_alarm(df)
        if path.name in development:
            assert (alarm is not None)==(path.name in oldfirst.index)
            if alarm:
                ref=oldfirst.loc[path.name]
                assert alarm['outcome']==ref.outcome
                assert df.index[alarm['alarm_index']]==pd.Timestamp(ref.alarm_time)
        if alarm is None: continue
        c['first_alarm_sessions']+=1; c['outcome_'+alarm['outcome']]+=1
        i,j=alarm['alarm_index'],alarm['outcome_index']; at=df.index[i]
        req=request_asof(s,at) if s else None
        c['request_known_at_alarm']+=req is not None
        record={'file':path.name,'group':g,'alarm_time':at.isoformat(),**alarm,
                'request_known':req is not None}
        if req:
            counter=df['Energy Delivered (kWh)'].to_numpy(float)
            valid=bool(np.isfinite(counter[:i+1]).all() and (np.diff(counter[:i+1])>=-1e-6).all() and counter[i]>=0)
            remaining=req['kwh_requested']-counter[i] if valid else None
            record.update(requested_kwh=req['kwh_requested'],remaining_declared_kwh=remaining,
                          declared_departure=req['requested_departure'].isoformat())
            c['known_request_valid_counter']+=valid
            c['known_request_remaining_ge_0p1']+=bool(valid and remaining>=.1)
            c['known_request_already_satisfied']+=bool(valid and remaining<=0)
            eligible=bool(valid and remaining>=.1 and req['requested_departure']>at)
            c['known_unmet_request_and_future_declared_departure']+=eligible
            if alarm['outcome']=='resumed':
                c['resumed_with_request_known']+=1
                c['resumed_with_known_unmet_request']+=bool(valid and remaining>=.1)
                c['resumed_eligible_at_alarm']+=eligible
                c['resumed_eligible_before_declared_departure']+=bool(eligible and df.index[j]<req['requested_departure'])
                c['resumed_eligible_and_pilot_ge_6']+=bool(eligible and alarm['pilot_ge_6_through_prefix'])
                # Counter increase only over uninterrupted non-reset observation,
                # before declared departure; no final-energy imputation.
                end=j
                for k in range(j+1,len(df)):
                    dt=(df.index[k]-df.index[k-1]).total_seconds()
                    if dt<=0 or dt>15 or df.iloc[k]['Charging State']=='UNPLUGGED' or df.index[k]>=req['requested_departure'] or not np.isfinite(counter[k]) or counter[k]<counter[k-1]-1e-6: break
                    end=k
                extra=max(0.,float(counter[end]-counter[j])) if np.isfinite(counter[j]) and df.index[j]<req['requested_departure'] else 0.
                record['observed_energy_after_resume_before_declared_departure_kwh']=extra
                c['resumed_eligible_with_observed_extra_ge_0p1']+=bool(eligible and extra>=.1)
        private.append(record)
        if (n+1)%200==0: print('audited',n+1,flush=True)
    (raw/'full_alarm_request_linkage.private.json').write_text(json.dumps(private,indent=2)+'\n')
    out={'scope':'Descriptive extension over all 1474 static office recordings. New files are same site, not an independent deployment.',
         'groups':{k:dict(v) for k,v in groups.items()},'original_128_alarm_parity':'passed',
         'source':json.loads((HERE/'reports/full_office_sources.json').read_text()),
         'limitations':['User request is declared intent, not verified physical battery demand','Current resume after a positive pilot is observational; no causal benefit inferred','Counter validity checked only through alarm; future counter used only for descriptive outcomes','No receive timestamps; modifiedAt is earliest documented submission availability','New 1346 are a file-disjoint same-site audit, not model performance confirmation']}
    (HERE/'reports/full_office_request_audit.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2),flush=True)


if __name__=='__main__': main()
