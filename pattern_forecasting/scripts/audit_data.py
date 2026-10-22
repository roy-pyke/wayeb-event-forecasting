import numpy as np
from patternforecast.automata import PatternFamily
from patternforecast.common import REPORTS,CONFIG,FAMILY,PACKAGE,protocol,write_json
from patternforecast.data import load,targets
family=PatternFamily();report={'joint_states':len(family.states),'verified_inclusion_pairs':family.inclusion_pairs(),'datasets':{}}
for name,cfg in protocol()['datasets'].items():
    report['datasets'][name]={}
    for split in ('train','calibrate','development'):
        data=load(name,split);y,known=targets(data,cfg['horizon_samples'])
        complete=known.all((1,2));bad=0
        codes=(y.reshape(-1,9).astype(int)@(2**np.arange(9)))
        for q in np.unique(data['q']):
            feasible=family.feasible(int(q),tuple(cfg['horizon_samples']))
            options=feasible.astype(int)@(2**np.arange(9))
            mask=complete&(data['q']==q);bad+=int((~np.isin(codes[mask],options)).sum())
        assert bad==0
        report['datasets'][name][split]={'queries':len(y),'fully_observed_queries':int(complete.sum()),
                'infeasible_labels':bad,'states_observed':len(np.unique(data['q']))}
write_json(REPORTS/'data-audit.json',report);print(report)
