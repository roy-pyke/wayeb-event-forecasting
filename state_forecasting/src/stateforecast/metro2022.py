"""Separate, checksum-verified 2022 confirmation cohort; original 2020 preserved."""
from collections import deque
import hashlib
import json
import urllib.request
import numpy as np
import pandas as pd
from .data import PACKAGE,CACHE,SENSORS,FEATURES,sha256,episodes,episode_rows


def prepare_2022():
    config=json.loads((PACKAGE/'configs/CONFIRMATION_2022.json').read_text())
    destination=CACHE/'metropt2022';destination.mkdir(exist_ok=True,parents=True)
    manifest=destination/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old['source_code_sha256']==sha256(__file__):return destination
    csv=destination/'dataset_train.csv'
    if not csv.exists():
        urllib.request.urlretrieve(config['source_url'],csv)
    if csv.stat().st_size!=config['source_bytes']:raise ValueError('2022 download incomplete')
    md5=hashlib.md5()
    with csv.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):md5.update(b)
    if md5.hexdigest()!=config['source_md5']:raise ValueError('2022 published MD5 mismatch')
    chunks=[]
    for frame in pd.read_csv(csv,usecols=['timestamp','COMP',*SENSORS],chunksize=200000):
        chunks.append((pd.to_datetime(frame.timestamp).astype('int64').to_numpy()/1e9,
                       frame.COMP.to_numpy(dtype=np.int8),frame[SENSORS].to_numpy()))
    t=np.concatenate([p[0] for p in chunks]);c=np.concatenate([p[1] for p in chunks]);z=np.concatenate([p[2] for p in chunks]);del chunks
    if np.any(np.diff(t)<=0):raise ValueError('2022 timestamps are not strictly increasing')
    cut=pd.Timestamp(config['confirmation'][0]).timestamp();end=pd.Timestamp(config['confirmation'][1]).timestamp()
    records={'warmup':[],'confirmation':[]};history=deque(maxlen=3);omitted=0;business=[]
    for eid,(start,stop,observed) in enumerate(episodes(t,c,config['gap_censor_seconds'])):
        if t[stop]<cut:split='warmup'
        elif t[start]>=cut and t[stop]<end:split='confirmation'
        else:split=None;omitted+=1
        if split:
            business.extend([('LoadStart',t[start]),('LoadEnd' if observed else 'Gap',t[stop])])
            for now,r,obs,x in episode_rows(t,z,start,stop,observed,history,config['landmark_min_spacing_seconds']):
                records[split].append((eid,now,r,obs,t[start],x))
        if observed:history.append(t[stop]-t[start])
    summary={}
    for name,rows in records.items():
        eid,now,r,obs,start,x=zip(*rows)
        path=destination/f'{name}.npz'
        np.savez_compressed(path,instance=np.asarray(eid),time=np.asarray(now),residual=np.asarray(r),
                            observed=np.asarray(obs),start=np.asarray(start),X=np.asarray(x))
        summary[name]=dict(queries=len(rows),instances=len(set(eid)),sha256=sha256(path))
    with (destination/'business.csv').open('w') as f:
        for kind,stamp in business:f.write(f'{kind},{int(stamp)}\n')
    info=dict(source=config,source_sha256=sha256(csv),source_md5=md5.hexdigest(),raw_rows=len(t),
              first_timestamp=str(pd.Timestamp(t[0],unit='s')),last_timestamp=str(pd.Timestamp(t[-1],unit='s')),
              median_interval_seconds=float(np.median(np.diff(t))),gap_count=int((np.diff(t)>60).sum()),
              excluded_boundary_or_outside_period_instances=omitted,splits=summary,features=FEATURES,
              source_code_sha256=sha256(__file__))
    manifest.write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps({k:v for k,v in info.items() if k not in ['source','features']},indent=2),flush=True)
    return destination
