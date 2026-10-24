"""Check committed aggregates and causal deterministic replays, without refitting."""
import csv
import hashlib
import json
import platform
import subprocess
import sys
import numpy as np
from common import DATA,REPORT,HERE,save
from recurrent.replay import arrivals_for,simulate,POLICIES
from recurrent.data import transition


def main():
    result={'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,
            'aggregate_checks':{},'deterministic_policies':[],'source_hashes':{}}
    for name in ['dev_windows.csv','test_windows.csv','baseline_audit_windows.csv','independent_r2c_windows.csv']:
        with (REPORT/name).open() as f:rows=list(csv.DictReader(f))
        for r in rows:
            for unit in ['value','records']:
                assert int(r['arrived_'+unit])==sum(int(r[k+'_'+unit]) for k in ['completed','expired','rejected','pending'])
            cap=int(r.get('capacity',2));slots=int(r['observed_slots'])
            assert int(r['attempts'])<=cap*slots
            assert int(r['failed_attempts'])<=int(r['attempts'])
            assert int(r['max_buffer'])<=12
        result['aggregate_checks'][name]={'rows':len(rows),'all_resource_and_conservation_checks':True}
    rates=json.loads((REPORT/'model.json').read_text());a,b=transition(rates,600)
    states=np.random.default_rng(23032).integers(0,2,(32,6));arr=arrivals_for('verification',23032)
    for p in POLICIES+['priced_horizon8','unpriced_horizon8']:
        first,h1=simulate(states,np.ones(6),arr,p,2,a,b,True)
        second,h2=simulate(states,np.ones(6),arr,p,2,a,b,True)
        first.pop('runtime_seconds');second.pop('runtime_seconds')
        assert first==second and h1==h2
        result['deterministic_policies'].append(p)
    for f in sorted(list((HERE/'src').rglob('*.py'))+list((HERE/'scripts').glob('*.py'))+list((HERE/'configs').glob('*.json'))):
        result['source_hashes'][str(f.relative_to(HERE))]=hashlib.sha256(f.read_bytes()).hexdigest()
    tests=subprocess.run([sys.executable,'-m','pytest','-q',str(HERE/'tests')],capture_output=True,text=True)
    result['tests']={'exit_code':tests.returncode,'output':tests.stdout.strip()}
    if tests.returncode:raise RuntimeError(tests.stdout+tests.stderr)
    # At K=6, all non-backoff work-conserving policies share the same completions.
    summary=json.loads((REPORT/'test_summary.json').read_text())
    for dataset,s in summary.items():
        values=[s['6']['aggregates'][p]['completed_value'] for p in POLICIES if 'backoff' not in p]
        assert len(set(values))==1
    ms=json.loads((REPORT/'independent_r2c.json').read_text())
    values=[v['completed_value'] for p,v in ms['capacities']['6']['aggregates'].items() if 'backoff' not in p]
    assert len(set(values))==1
    result['full_capacity_neutrality']=True
    save(REPORT/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='source_hashes'},indent=2))


if __name__=='__main__':main()
