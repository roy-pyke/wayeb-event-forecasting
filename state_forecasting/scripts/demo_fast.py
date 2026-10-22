import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from stateforecast.data import PACKAGE,ROOT,CACHE,SENSORS,episodes
from stateforecast.online_fast import FastStateSidecar
from stateforecast.serving import BatchedSurvival
from stateforecast.stream import Event


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,default=ROOT/'runs/state-confirmation-2022');args=ap.parse_args()
    report=json.loads((args.run/'report.json').read_text());date=report['updates'][0]['date']
    m0=joblib.load(args.run/f'{date}-M0.joblib');m2=joblib.load(args.run/f'{date}-M2.joblib')
    side=FastStateSidecar(json.loads((PACKAGE/'configs/dfa.json').read_text()),BatchedSurvival(m2),BatchedSurvival(m0))
    collected=[];lower=pd.Timestamp(date);upper=lower+pd.Timedelta(days=1)
    for chunk in pd.read_csv(CACHE/'metropt2022/dataset_train.csv',usecols=['timestamp','COMP',*SENSORS],chunksize=200000):
        times=pd.to_datetime(chunk.timestamp);mask=(times>=lower)&(times<upper)
        if mask.any():collected.append(chunk[mask])
        if times.iloc[-1]>=upper:break
    frame=pd.concat(collected);t=pd.to_datetime(frame.timestamp).astype('int64').to_numpy()/1e9;c=frame.COMP.to_numpy();z=frame[SENSORS].to_numpy()
    forecasts=[];count=0
    for start,stop,seen in episodes(t,c,60):
        if not seen:continue
        side.accept(Event('apu','LoadStart',t[start],t[start]));last=-float('inf')
        for i in range(start,stop):
            side.accept(Event('apu','Telemetry',t[i],t[i],tuple(z[i])))
            if t[i]-last>=20:forecasts.append(side.predict('apu',t[i]));last=t[i]
        side.accept(Event('apu','LoadEnd',t[stop],t[stop]));count+=1
        if count==3:break
    result=dict(scope='final live sidecar on three actual 2022 cycles, business-history cold start',date=date,
                matches=side.state.monitor.matches,forecasts=forecasts,feedback_updates=side.mixer.updates)
    (args.run/'online-fast-demo.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
