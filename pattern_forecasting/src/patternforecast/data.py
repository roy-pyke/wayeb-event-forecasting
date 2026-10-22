"""Causal, split-local stream replay. Holdout preparation requires a freeze file."""
from collections import deque
from io import BytesIO
import json
from pathlib import Path
import urllib.request
import zipfile
import numpy as np
import pandas as pd
from .common import CACHE, ROOT, PACKAGE, NAMES, protocol, sha256, write_json
from .automata import PatternFamily

SOURCES = {
    'air': ('https://archive.ics.uci.edu/static/public/501/beijing+multi+site+air+quality+data.zip',
            'b04da438b2f331ac0ffd45aebdfec0d20d2367feb5f6948c4b1f7ce1191e33c4'),
    'power': ('https://archive.ics.uci.edu/static/public/235/individual+household+electric+power+consumption.zip',
              '9f84b46ade8a2d8e1286ec4b2b6c2987a45a755c59f263be3b3b3d10dfbda3ff'),
    'metro': ('https://archive.ics.uci.edu/static/public/791/metropt%2B3%2Bdataset.zip',
              'aab991a970e58210de853bb8078ce0e63abb4d9412fdc5c79792dae3d8e1721a')}


def download(name):
    path = CACHE/'raw'/f'{name}.zip'
    path.parent.mkdir(parents=True, exist_ok=True)
    if name == 'metro' and not path.exists():
        old = ROOT/'.cache/state_forecasting/metropt3.zip'
        if old.exists():
            path.symlink_to(old)
    if not path.exists():
        temp = path.with_suffix('.tmp')
        urllib.request.urlretrieve(SOURCES[name][0], temp)
        if sha256(temp) != SOURCES[name][1]:
            raise ValueError('source checksum mismatch')
        temp.rename(path)
    if sha256(path) != SOURCES[name][1]:
        raise ValueError('source checksum mismatch')
    return path


def raw_streams(name, cutoff):
    """Read raw records, then restrict dates before any feature/label analysis."""
    cfg = protocol()['datasets'][name]
    cutoff = pd.Timestamp(cutoff)
    with zipfile.ZipFile(download(name)) as archive:
        if name == 'air':
            with zipfile.ZipFile(BytesIO(archive.read('PRSA2017_Data_20130301-20170228.zip'))) as inner:
                for member in sorted(inner.namelist()):
                    if not member.endswith('.csv'):
                        continue
                    frame = pd.read_csv(inner.open(member))
                    stamps = pd.to_datetime(frame[['year','month','day','hour']])
                    entity = str(frame['station'].iloc[0])
                    columns = ['PM2.5','PM10','SO2','NO2','CO','O3','TEMP','PRES','DEWP','RAIN','WSPM']
                    frame = frame[columns].set_axis(stamps)
                    yield entity, frame.loc[frame.index < cutoff]
        elif name == 'power':
            frame = pd.read_csv(archive.open('household_power_consumption.txt'), sep=';', na_values=['?'])
            stamps = pd.to_datetime(frame['Date']+' '+frame['Time'], format='%d/%m/%Y %H:%M:%S')
            frame = frame.drop(columns=['Date','Time']).set_axis(stamps)
            yield 'household', frame.loc[frame.index < cutoff]
        else:
            columns = ['Reservoirs','TP2','TP3','H1','DV_pressure','Oil_temperature','Motor_current']
            frame = pd.read_csv(archive.open('MetroPT3(AirCompressor).csv'), usecols=['timestamp',*columns])
            frame.index = pd.to_datetime(frame.pop('timestamp'))
            frame = frame.loc[frame.index < cutoff, columns]
            # Right-labelled bins contain observations no later than their label.
            frame = frame.resample('10s', label='right', closed='right').last()
            yield 'compressor', frame.loc[frame.index < cutoff]


def replay(stamps, values, cuts, cfg, family, entity, segment_offset=0):
    native, spacing = cfg['native_seconds'], cfg['query_every_samples']
    history_length = protocol()['telemetry_history_samples']
    regime = np.searchsorted(cuts, values[:,0], side='right')
    regime[~np.isfinite(values[:,0])] = -1
    breaks = np.r_[True, (np.diff(stamps) != native) | (regime[:-1] < 0) | (regime[1:] < 0)]
    segments = np.cumsum(breaks) + segment_offset
    output = {k:[] for k in ['t','business','telemetry','residual','observed','coverage','q','segment','entity']}
    business_events, match_counts = [], np.zeros(len(NAMES), dtype=int)
    boundaries = np.r_[0,np.flatnonzero(np.diff(segments))+1,len(segments)]
    for begin,end in zip(boundaries[:-1],boundaries[1:]):
        seg = segments[begin]
        ix = np.arange(begin,end)
        if regime[ix[0]] < 0 or len(ix) < history_length+1:
            continue
        q = family.start
        last_regime = -1
        last_event = stamps[ix[0]]
        q_changed = np.full(len(NAMES), stamps[ix[0]])
        past_events = deque(maxlen=4)
        endpoints = [[] for _ in NAMES]
        rows = []
        for local_i, i in enumerate(ix):
            now = stamps[i]
            if regime[i] != last_regime:
                old = family.states[q]
                q, matched = family.step(q, family.alphabet[regime[i]])
                q_changed[np.array(old) != np.array(family.states[q])] = now
                past_events.append((int(regime[i]), now))
                last_event, last_regime = now, int(regime[i])
                business_events.append((entity, int(seg), int(now), family.alphabet[regime[i]], q))
                for p in np.flatnonzero(matched):
                    endpoints[p].append(now)
                    match_counts[p] += 1
            if local_i < history_length-1 or local_i % spacing:
                continue
            phase = 2*np.pi*(now%86400)/86400
            season = 2*np.pi*(now%(365.25*86400))/(365.25*86400)
            temporal = np.r_[(now-q_changed)/native, (now-last_event)/native,
                             np.sin(phase), np.cos(phase), np.sin(season), np.cos(season)]
            historical = np.zeros((4,5), dtype=float)
            for j,(symbol,time) in enumerate(reversed(past_events)):
                historical[j,symbol] = 1
                historical[j,4] = (now-time)/native
            biz = np.r_[family.onehot[q], temporal, historical.ravel()]
            raw = values[ix[local_i-history_length+1:local_i+1]]
            rows.append((now,biz,raw.copy(),q))
        if not rows:
            continue
        times = np.array([r[0] for r in rows])
        coverage = (stamps[ix[-1]]-times)/native
        residual = np.broadcast_to(coverage[:,None], (len(times),len(NAMES))).copy()
        observed = np.zeros(residual.shape, dtype=bool)
        for p, event_times in enumerate(endpoints):
            events = np.asarray(event_times)
            next_index = np.searchsorted(events, times, side='right')
            valid = next_index < len(events)
            residual[valid,p] = (events[next_index[valid]]-times[valid])/native
            observed[valid,p] = True
        for j,row in enumerate(rows):
            for k,v in zip(['t','business','telemetry','q'],row):
                output[k].append(v)
            output['residual'].append(residual[j])
            output['observed'].append(observed[j])
            output['coverage'].append(coverage[j])
            output['segment'].append(int(seg))
            output['entity'].append(entity)
    for k in output:
        output[k] = np.asarray(output[k], dtype=None if k in ('entity','segment','q','observed') else np.float32 if k not in ('t',) else np.float64)
    return output, business_events, match_counts, int(segments.max())+1 if len(segments) else segment_offset


def prepare(name, confirmation=False, force=False):
    cfg = protocol()['datasets'][name]
    if confirmation and not (PACKAGE/'configs/FROZEN.json').exists():
        raise RuntimeError('Freeze the development selection before preparing confirmation labels')
    stage = 'confirmation' if confirmation else 'development'
    path = CACHE/name
    path.mkdir(parents=True, exist_ok=True)
    splits = ['confirmation'] if confirmation else ['train','calibrate','development']
    manifest_path = path/f'manifest-{stage}.json'
    identity = {p.name:sha256(p) for p in [Path(__file__), PACKAGE/'configs/PROTOCOL.json', PACKAGE/'configs/dfa.json']}
    if not force and manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        if old['source_identity']==identity and all((path/f'{s}.npz').exists() for s in splits):
            return old
    cutoff = cfg['confirmation'][1] if confirmation else cfg['development'][1]
    streams = list(raw_streams(name, cutoff))
    allowed = cfg.get('training_entities',[entity for entity,_ in streams])
    cutfile = path/'cuts.json'
    if confirmation:
        cuts = np.asarray(json.loads(cutfile.read_text())['cuts'])
    else:
        measurements = []
        for entity,frame in streams:
            if entity in allowed:
                train = frame.loc[(frame.index>=cfg['train'][0]) & (frame.index<cfg['train'][1])]
                measurements.append(train[cfg['regime_signal']].to_numpy())
        cuts = np.nanquantile(np.concatenate(measurements),protocol()['regime_quantiles'])
        if len(np.unique(cuts)) != 3:
            raise ValueError('Training quantiles do not define four distinct regimes')
        write_json(cutfile,dict(cuts=cuts,fit_split='train',entities=allowed))
    family = PatternFamily()
    manifest = dict(dataset=name,stage=stage,source_identity=identity,raw_sha256=sha256(download(name)),
                    cuts=cuts,features=list(streams[0][1].columns),splits={})
    for split in splits:
        pieces, event_rows, totals, offset = [], [], np.zeros(3,dtype=int), 0
        for entity,frame in streams:
            if split!='confirmation' and entity not in allowed:
                continue
            sub = frame.loc[(frame.index>=cfg[split][0]) & (frame.index<cfg[split][1])]
            if sub.index.has_duplicates or not sub.index.is_monotonic_increasing:
                raise ValueError(f'Non-monotone or duplicate timestamps: {name}/{entity}')
            columns = [cfg['regime_signal']] + [c for c in sub if c!=cfg['regime_signal']]
            values = sub[columns].to_numpy(dtype=np.float32)
            stamps = sub.index.astype('int64').to_numpy()/1e9
            if not len(stamps):
                continue
            data, events, counts, offset = replay(stamps,values,cuts,cfg,family,entity,offset)
            if len(data['t']):
                pieces.append(data)
            event_rows.extend(events)
            totals += counts
        merged = {k:np.concatenate([p[k] for p in pieces]) for k in pieces[0]}
        np.savez_compressed(path/f'{split}.npz',**merged)
        pd.DataFrame(event_rows,columns=['entity','segment','timestamp','symbol','q']).to_csv(path/f'{split}-business.csv',index=False)
        y,known = targets(merged,cfg['horizon_samples'])
        manifest['splits'][split] = dict(rows=len(merged['t']),matches=dict(zip(NAMES,totals.tolist())),
                 entities=np.unique(merged['entity']).tolist(),q_counts={str(q):int(np.sum(merged['q']==q)) for q in np.unique(merged['q'])},
                 known_fraction=float(known.mean()),positive_fraction=[float(y[:,p,:][known[:,p,:]].mean()) for p in range(3)],
                 npz_sha256=sha256(path/f'{split}.npz'))
        print(name,split,manifest['splits'][split],flush=True)
    write_json(manifest_path,manifest)
    return manifest


def load(name,split):
    with np.load(CACHE/name/f'{split}.npz',allow_pickle=False) as archive:
        return dict(archive)


def targets(data,horizons):
    horizons = np.asarray(horizons)
    y = data['observed'][:,:,None] & (data['residual'][:,:,None]<=horizons)
    known = data['observed'][:,:,None] | (data['coverage'][:,None,None]>=horizons)
    return y.astype(float),known


def context_indices(data,lag):
    indices = np.maximum(np.arange(len(data['t']))-lag,0)
    valid = data['segment'][indices] == data['segment']
    return indices, valid


def design(data,lag=0,native=1,business_only=False,no_state=False):
    indices,valid = context_indices(data,lag)
    raw = data['telemetry'][indices].copy()
    raw[~valid] = np.nan
    business = data['business'].copy()
    if no_state:
        business[:,:len(PatternFamily().states)] = 0
    if business_only:
        raw[:] = np.nan
    ages = (data['t']-data['t'][indices])/native
    ages[~valid] = np.nan
    return business,raw,ages.astype(np.float32)
