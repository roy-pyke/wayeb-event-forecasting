"""One independent neural refit audit; does not modify any selected model."""
import argparse,hashlib,platform,time
import joblib
import numpy as np
from patternforecast.common import RUNS,REPORTS,FAMILY,write_json,sha256
from patternforecast.data import load
from patternforecast.models import NeuralLandmark,subset

p=argparse.ArgumentParser();p.add_argument('--dataset',default='air')
p.add_argument('--backbone',default='short-gru-32-0.01-s20261022');a=p.parse_args()
path=RUNS/a.dataset/f'{a.backbone}.joblib';original=joblib.load(path)
assert isinstance(original,NeuralLandmark)
train,cal,dev=[load(a.dataset,s) for s in ['train','calibrate','development']]
indices=np.linspace(0,len(dev['t'])-1,min(2000,len(dev['t'])),dtype=int);sample=subset(dev,indices)
reference=original.predict(sample).astype(np.float32)
start=time.perf_counter()
fresh=NeuralLandmark(original.cfg,original.kind,original.setting,original.seed)
fresh.fit(train,cal);prediction=fresh.predict(sample).astype(np.float32)
report=dict(family=FAMILY,dataset=a.dataset,backbone=a.backbone,model_sha256=sha256(path),
            test_queries=len(sample['t']),seconds=time.perf_counter()-start,
            max_absolute_prediction_difference=float(np.max(np.abs(reference-prediction))),
            bit_identical_predictions=bool(np.array_equal(reference,prediction)),
            original_prediction_sha256=hashlib.sha256(reference.tobytes()).hexdigest(),
            retrained_prediction_sha256=hashlib.sha256(prediction.tobytes()).hexdigest(),
            python=platform.python_version(),platform=platform.platform(),
            note='Same host, pinned CPU runtime and seed; does not assert bit identity across hardware or a publication reproduction.')
assert report['bit_identical_predictions'],report
write_json(REPORTS/f'reproducibility-{a.dataset}.json',report)
print(report,flush=True)
