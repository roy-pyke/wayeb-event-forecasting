"""Replay a real, held-out cycle through the executable two-stream sidecar."""
import argparse
import json
from pathlib import Path
import joblib
from stateforecast.data import PACKAGE,ROOT,read_raw,episodes
from stateforecast.online import StateSidecar
from stateforecast.stream import Event
import pandas as pd


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,default=ROOT/'runs/state-final');args=p.parse_args()
    model_date='2020-05-01'
    s=StateSidecar(json.loads((PACKAGE/'configs/dfa.json').read_text()),
                   joblib.load(args.run/f'{model_date}-M2.joblib'),joblib.load(args.run/f'{model_date}-M0.joblib'))
    t,c,z=read_raw();cut=pd.Timestamp(model_date).timestamp()
    output=[];selected=0
    for start,stop,observed in episodes(t,c,60):
        if t[start]<cut or not observed:continue
        if selected==3:break
        s.accept(Event('apu','LoadStart',t[start],t[start]));last=-float('inf')
        for i in range(start,stop):
            s.accept(Event('apu','Telemetry',t[i],t[i],tuple(z[i])))
            if t[i]-last>=20:
                output.append(s.predict('apu',t[i]));last=t[i]
        s.accept(Event('apu','LoadEnd',t[stop],t[stop]));selected+=1
    report=dict(scope='online sidecar demonstration on first three complete May cycles; history cold start',
                model_date=model_date,matches=s.monitor.matches,forecasts=output,feedback_updates=s.mixer.updates)
    out=args.run/'online-demo.json';out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
