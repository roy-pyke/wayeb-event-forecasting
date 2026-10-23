"""Isolate strict-comparison loss using the real author reallocator."""
from pathlib import Path
from types import SimpleNamespace
import inspect,json
import numpy as np
from acnportal.acnsim.interface import SessionInfo,InfrastructureInfo
import adacharge.postprocessing as post
ROOT=Path(__file__).resolve().parents[2]


def compare():
    # Normalize installed copy back to pinned comparison, then apply the proposed
    # local numerical tolerance. Neither source checkout is changed.
    source=inspect.getsource(post).replace('<= peak_limit + 1e-5','<= peak_limit').replace('<= ub[i] + 1e-5','<= ub[i]')
    fixed=source.replace('<= peak_limit','<= peak_limit + 1e-5').replace('<= ub[i]','<= ub[i] + 1e-5')
    infra=InfrastructureInfo(np.ones((1,6)),np.array([36.]),np.zeros(6),np.full(6,208.),
                            ['feeder'],[f's{i}' for i in range(6)],np.full(6,30.),np.zeros(6),
                            [np.arange(0,31,6) for _ in range(6)],np.zeros(6,bool))
    sessions=[SessionInfo(f's{i}',f'q{i}',10,0,0,2,2,0) for i in range(6)]
    for s in sessions: s.max_rates=np.full(2,30.)
    interface=SimpleNamespace(remaining_amp_periods=lambda _:100)
    rows=[]
    for tag,src in [('pinned_strict',source),('tolerance_1e-5',fixed)]:
        ns=dict(post.__dict__); exec(compile(src,'quantization_probe','exec'),ns)
        for delta in [0.,1e-8,1e-3]:
            rates=np.tile(np.array([7.,7.,7.,7.,4.,4.-delta])[:,None],(1,2))
            answer=ns['diff_based_reallocation'](rates,sessions,infra,interface)
            rows.append({'version':tag,'continuous_sum_amp':float(rates[:,0].sum()),
                         'underflow_amp':delta,'discrete_sum_amp':float(answer[:,0].sum())})
    assert [r['discrete_sum_amp'] for r in rows]==[36,30,30,36,36,30]
    return rows


if __name__=='__main__':
    report={'scope':'Deterministic real-reallocator diagnostic, not a full scheduling experiment',
            'cases':compare(),'physical_feeder_amp':36,'assertions':'passed'}
    (ROOT/'acn_research/reports/quantization_numerics.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
