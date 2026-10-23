"""Retrain in a new directory; never overwrite the selected research sources."""
import argparse
import json
import runpy
import sys
import tempfile
from pathlib import Path
import numpy as np
import torch
import queryforecast.common as common
# Bind the original data cache before redirecting model/report destinations.
import queryforecast.data

parser=argparse.ArgumentParser();parser.add_argument('domain',choices=['air','power'])
args=parser.parse_args();domain=args.domain
cache,reports=common.CACHE,common.REPORTS
selected=cache/domain/'world.pt';before=common.digest(selected)
folder=Path(tempfile.mkdtemp(prefix=f'retrain-{domain}-',dir=cache))
(folder/domain).mkdir();(folder/'reports').mkdir()
common.CACHE=folder;common.REPORTS=folder/'reports'
sys.argv=['train.py',domain]
runpy.run_path(str(common.PACKAGE/'scripts/train.py'),run_name='__main__')
new=torch.load(folder/domain/'world.pt',weights_only=False)
old=torch.load(selected,weights_only=False)
maximum=max(float(torch.max(torch.abs(old['state'][k]-new['state'][k]))) for k in old['state'])
oldreport=json.loads((reports/f'model-{domain}.json').read_text())
newreport=json.loads((folder/'reports'/f'model-{domain}.json').read_text())
result={'domain':domain,'selected_sha256_before':before,'selected_sha256_after':common.digest(selected),
 'retrained_sha256':common.digest(folder/domain/'world.pt'),'max_parameter_difference':maximum,
 'normalization_equal':bool(np.array_equal(new['mean'],old['mean']) and np.array_equal(new['scale'],old['scale'])),
 'epoch_loss_records_identical':oldreport['history']==newreport['history'],
 'source_sha256':common.digest(common.PACKAGE/'scripts/train.py'),
 'torch':torch.__version__,'scope':'Same-machine deterministic retraining, not cross-platform bitwise equivalence'}
result['passed']=bool(before==result['selected_sha256_after'] and maximum==0 and
                      result['normalization_equal'] and result['epoch_loss_records_identical'])
common.save(reports/f'retraining-{domain}.json',result)
print(result,flush=True)
if not result['passed']:raise SystemExit('retraining differed; original source retained')
