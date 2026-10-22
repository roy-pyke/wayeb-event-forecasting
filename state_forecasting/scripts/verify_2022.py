"""Verify every confirmation cohort business endpoint with the original engine."""
import csv
import json
import os
import re
import subprocess
from stateforecast.data import PACKAGE,ROOT,CACHE,sha256
from stateforecast.stream import WayebMonitor,Event


def main():
    path=CACHE/'metropt2022/business.csv';out=ROOT/'runs/state-recognition-2022';out.mkdir(exist_ok=True,parents=True)
    table=json.loads((PACKAGE/'configs/dfa.json').read_text());m=WayebMonitor(table);fine=WayebMonitor(table)
    expected=[];previous=None
    with path.open() as f:
        for kind,t in csv.reader(f):
            t=int(t)
            if previous=='LoadStart' and kind=='LoadEnd':expected.append(t)
            previous=kind;event=Event('apu',kind,t,t)
            m.accept(event);fine.accept(Event('apu','Telemetry',t,t,(.9,)));fine.accept(event)
    assert expected==[t for _,t in m.matches];assert fine.matches==m.matches
    conf=out/'engine.conf';conf.write_text('include classpath("application.conf")\ndefault.showMatchesForecasts = true\n')
    log=out/'recognition.log'
    with log.open('w') as f:
        result=subprocess.run([str(ROOT/'wayeb'),'recognition',f'--fsm:{ROOT / "runs/state-bridge/pattern.fsm"}',
                               f'--stream:{path}',f'--statsFile:{out / "recognition"}'],cwd=out,
                              env=dict(os.environ,WAYEB_CONFIG_FILE=str(conf)),stdout=f,stderr=subprocess.STDOUT,timeout=180)
    content=log.read_text()
    if result.returncode or 'Exception' in content or 'ERROR' in content:raise RuntimeError(content[-2000:])
    actual=list(map(int,re.findall(r'MATCH:\s+Timestamp->(\d+)',content)));assert actual==expected
    r=dict(status='passed',matches=len(actual),endpoint_mismatches=0,inserted_telemetry_mismatches=0,
           input_sha256=sha256(path),table_sha256=sha256(PACKAGE/'configs/dfa.json'),author_jar_sha256=sha256(ROOT/'artifacts/wayeb.jar'))
    (PACKAGE/'reports/recognition-2022.json').write_text(json.dumps(r,indent=2)+'\n');print(r)


if __name__=='__main__':main()
