import argparse
import time
import numpy as np
import torch
from torch import nn
from queryforecast.common import CACHE, REPORTS, PROTOCOL, digest, save
from queryforecast.data import load
from queryforecast.model import WorldModel

parser = argparse.ArgumentParser()
parser.add_argument('domain', choices=['air', 'power'])
args = parser.parse_args()
start = time.perf_counter()
cfg = PROTOCOL['model']
torch.set_num_threads(3)
torch.manual_seed(cfg['seed'])
torch.use_deterministic_algorithms(True)
train, val = load(args.domain, 'train'), load(args.domain, 'calibrate')
mean = np.nanmean(train['x'], axis=0)
scale = np.nanstd(train['x'], axis=0)
mean = np.nan_to_num(mean); scale = np.maximum(np.nan_to_num(scale), .01)
def tensors(data):
    x = np.clip(np.nan_to_num((data['x']-mean)/scale), -10, 10).astype(np.float32)
    y = torch.tensor(data['y'], dtype=torch.long)
    prev = torch.cat([torch.full((len(y), 1), 5), y[:, :-1]], 1)
    return torch.tensor(x), y, prev
x, y, prev = tensors(train); vx, vy, vp = tensors(val)
model = WorldModel(x.shape[1], cfg['hidden'], cfg['embedding'])
opt = torch.optim.Adam(model.parameters(), lr=cfg['learning_rate'])
loss = nn.CrossEntropyLoss()
history, best, best_state = [], float('inf'), None
generator = torch.Generator().manual_seed(cfg['seed'])
for epoch in range(cfg['epochs']):
    model.train(); total = 0
    for ix in torch.randperm(len(x), generator=generator).split(cfg['batch']):
        opt.zero_grad()
        value = loss(model(x[ix], prev[ix]).reshape(-1, 5), y[ix].reshape(-1))
        value.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5); opt.step()
        total += value.item()*len(ix)
    model.eval()
    with torch.no_grad():
        vloss = sum(loss(model(vx[ix], vp[ix]).reshape(-1, 5), vy[ix].reshape(-1)).item()*len(ix)
                    for ix in torch.arange(len(vx)).split(cfg['batch']))/len(vx)
    history.append({'epoch': epoch+1, 'train_nll': total/len(x), 'calibration_nll': vloss})
    if vloss < best:
        best = vloss
        best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    print(args.domain, history[-1], flush=True)
path = CACHE / args.domain / 'world.pt'
torch.save({'state': best_state, 'inputs': x.shape[1], 'mean': mean, 'scale': scale}, path)
save(REPORTS / f'model-{args.domain}.json', {'config': cfg, 'history': history,
     'selected_calibration_nll': best, 'sha256': digest(path),
     'train_origins': len(x), 'calibration_origins': len(vx),
     'seconds': time.perf_counter()-start, 'torch': torch.__version__})
