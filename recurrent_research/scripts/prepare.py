"""Audit data and fit frozen primary-train model; no policy evaluation."""
import numpy as np
from common import DATA, REPORT, save
from recurrent.data import read_avt, fit_rates, audit, split_bounds, transition


def calibration(trace, rates, split):
    lo, hi = split_bounds(trace)[split]
    out = {}
    for lag in [1, 2, 4, 8]:
        current = trace.states[:, lo:hi-lag]
        future = trace.states[:, lo+lag:hi]
        mask = (current >= 0) & (future >= 0)
        x, y = current[mask], future[mask]
        a, b = transition(rates, lag * trace.step)
        p = a + (b-a)*x
        pi = rates['down_to_up_per_second'] / (rates['down_to_up_per_second'] + rates['up_to_down_per_second'])
        out[str(lag)] = {'n': len(y), 'up_rate': float(y.mean()), 'mean_prediction': float(p.mean()),
                         'markov_brier': float(np.mean((p-y)**2)),
                         'stationary_brier': float(np.mean((pi-y)**2)),
                         'last_observation_brier': float(np.mean((x.astype(float)-y)**2)),
                         'down_prefix_n': int((x == 0).sum()),
                         'down_prefix_recovery_rate': float(y[x == 0].mean()) if (x == 0).any() else None,
                         'predicted_down_prefix_recovery': a}
    return out


def main():
    web = read_avt(DATA/'web_sites.avt', 600)
    pl = read_avt(DATA/'pl-app.avt', 900)
    rates = fit_rates(web, float(web.times[split_bounds(web)['train'][1]]))
    save(REPORT/'model.json', rates)
    save(REPORT/'data_audit.json', {x.name: audit(x) for x in [web, pl]})
    save(REPORT/'calibration.json', {x.name: {s: calibration(x,rates,s) for s in ['dev','test']} for x in [web,pl]})
    print('Frozen rates', rates)
    print('Web p01,p11', transition(rates,600), 'PlanetLab', transition(rates,900))
    for x in [web, pl]:
        print(x.name, audit(x)['splits'])


if __name__ == '__main__':
    main()
