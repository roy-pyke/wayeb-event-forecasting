"""Compare each exported monitor with the actual pinned Wayeb recognition CLI."""
import os
import re
import subprocess
import numpy as np
import pandas as pd
from patternforecast.common import REPORTS,CONFIG,FAMILY,ROOT, PACKAGE, CACHE, NAMES, sha256, write_json
from patternforecast.automata import PatternFamily

out=ROOT/'runs'/f'pattern-recognition-{FAMILY}'; out.mkdir(parents=True,exist_ok=True)
conf=out/'engine.conf'
conf.write_text('include classpath("application.conf")\ndefault.showMatchesForecasts = true\n')
family=PatternFamily()
patterns=(CONFIG/'patterns.sre').read_text().split('&')
streams={'random':np.random.default_rng(20261022).choice(list('ABCD'),10000)}
for name in ('air','power','metro'):
    frame=pd.read_csv(CACHE/name/'development-business.csv')
    # Concatenation intentionally creates a single stream for differential replay;
    # split resets in the labelled dataset are tested separately by replay tests.
    streams[name]=frame.symbol.to_numpy()[:20000]
report={'scope':'author CLI versus exported DFA; random and real business symbols',
        'author_jar_sha256':sha256(ROOT/'artifacts/wayeb.jar'),'patterns':{}}
for p,name in enumerate(NAMES):
    pattern=out/f'{name}.sre'; pattern.write_text(patterns[p].strip()+'\n')
    fsm=out/f'{name}.fsm'
    result=subprocess.run([str(ROOT/'wayeb'),'compile',f'--patterns:{pattern}',
          f'--declarations:{CONFIG}/declarations.sre',f'--countPolicy:{"nonoverlap" if FAMILY=="nested" else "overlap"}',f'--outputFsm:{fsm}'],
          cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
    if result.returncode or 'Exception' in result.stdout: raise RuntimeError(result.stdout[-2000:])
    report['patterns'][name]={}
    for dataset,symbols in streams.items():
        source=out/f'{dataset}.csv'
        source.write_text(''.join(f'{a},{i+1}\n' for i,a in enumerate(symbols)))
        q=family.start; expected=[]
        for i,a in enumerate(symbols):
            q,hit=family.step(q,a)
            if hit[p]: expected.append(i+1)
        log=out/f'{name}-{dataset}.log'
        with log.open('w') as stream:
            result=subprocess.run([str(ROOT/'wayeb'),'recognition',f'--fsm:{fsm}',
                     f'--stream:{source}',f'--statsFile:{out}/{name}-{dataset}'],cwd=out,
                     env=dict(os.environ,WAYEB_CONFIG_FILE=str(conf)),stdout=stream,
                     stderr=subprocess.STDOUT,timeout=180)
        text=log.read_text()
        if result.returncode or 'Exception' in text or 'ERROR' in text: raise RuntimeError(text[-2000:])
        observed=list(map(int,re.findall(r'MATCH:\s+Timestamp->(\d+)',text)))
        assert observed==expected,(name,dataset,len(observed),len(expected))
        report['patterns'][name][dataset]={'events':len(symbols),'matches':len(expected),
               'endpoint_mismatches':0,'input_sha256':sha256(source)}
        print(name,dataset,len(expected),'passed',flush=True)
write_json(REPORTS/'recognition.json',report)
