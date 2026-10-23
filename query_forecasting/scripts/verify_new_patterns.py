import json
import os
import re
import subprocess
import numpy as np
import pandas as pd
from queryforecast.common import ROOT, PACKAGE, REPORTS, digest, save
from queryforecast.monitor import Monitor

cfg=PACKAGE/'configs/heldout_structure';out=ROOT/'runs/query-recognition';out.mkdir(parents=True,exist_ok=True)
conf=out/'engine.conf';conf.write_text('include classpath("application.conf")\ndefault.showMatchesForecasts = true\n')
mon=Monitor('heldout_structure',payload=json.loads((cfg/'dfa.json').read_text()))
streams={'random':np.random.default_rng(20261023).choice(list('ABCD'),5000)}
for domain in ['air','power']:
 streams[domain]=pd.read_csv(ROOT/'.cache/pattern_forecasting/multisignal'/domain/'development-business.csv').symbol.to_numpy()[:10000]
report={'author_jar_sha256':digest(ROOT/'artifacts/wayeb.jar'),'export_sha256':digest(cfg/'dfa.json'),'patterns':{}}
for name,pattern in zip(['reentry','paired_loop','return'],(cfg/'patterns.sre').read_text().split('&')):
 p=mon.names.index(name);source=out/f'{name}.sre';source.write_text(pattern.strip()+'\n');fsm=out/f'{name}.fsm'
 with (out/f'{name}-compile.log').open('w') as log:
  subprocess.run([str(ROOT/'wayeb'),'compile',f'--patterns:{source}',f'--declarations:{cfg}/declarations.sre','--countPolicy:overlap',f'--outputFsm:{fsm}'],cwd=out,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 report['patterns'][name]={}
 for domain,symbols in streams.items():
  stream=out/f'{domain}.csv';stream.write_text(''.join(f'{a},{i+1}\n' for i,a in enumerate(symbols)))
  q=0;expected=[]
  for i,a in enumerate(symbols):
   q=int(mon.next[q,ord(a)-65])
   if (mon.final[q]>>p)&1:expected.append(i+1)
  logpath=out/f'{name}-{domain}.log'
  with logpath.open('w') as log:
   subprocess.run([str(ROOT/'wayeb'),'recognition',f'--fsm:{fsm}',f'--stream:{stream}',f'--statsFile:{out}/{name}-{domain}'],cwd=out,env=dict(os.environ,WAYEB_CONFIG_FILE=str(conf)),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  text=logpath.read_text()
  if 'Exception' in text or 'ERROR' in text:raise RuntimeError(text[-2000:])
  actual=list(map(int,re.findall(r'MATCH:\s+Timestamp->(\d+)',text)))
  assert actual==expected,(name,domain,len(actual),len(expected))
  report['patterns'][name][domain]={'events':len(symbols),'matches':len(expected),'mismatches':0,'input_sha256':digest(stream)}
  print(name,domain,len(expected),'passed',flush=True)
save(REPORTS/'new-pattern-recognition.json',report)
