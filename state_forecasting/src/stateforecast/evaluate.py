import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score
from .data import instance_weights, targets


def metrics(data, prediction, horizons):
    y, known = targets(data, horizons)
    weight = instance_weights(data)
    out = {}
    for j, horizon in enumerate(horizons):
        mask = known[:, j]
        p, yy, w = prediction[mask, j], y[mask, j], weight[mask]
        p_log = np.clip(p, 1e-6, 1 - 1e-6)
        bins = np.minimum((p * 10).astype(int), 9)
        reliability = []
        ece = 0.0
        for b in range(10):
            inside = bins == b
            if inside.any():
                size = w[inside].sum()
                conf, obs = np.average(p[inside], weights=w[inside]), np.average(yy[inside], weights=w[inside])
                ece += size * abs(conf - obs) / w.sum()
                reliability.append(dict(bin=b, mean_probability=float(conf), frequency=float(obs), weight=float(size)))
        out[str(horizon)] = dict(brier=float(np.average((p - yy)**2, weights=w)),
                                 row_brier=float(np.mean((p - yy)**2)),
                                 log_loss=float(np.average(-yy*np.log(p_log)-(1-yy)*np.log(1-p_log), weights=w)),
                                 ece=float(ece), prevalence=float(np.average(yy, weights=w)),
                                 auroc=float(roc_auc_score(yy, p, sample_weight=w)) if len(np.unique(yy)) == 2 else None,
                                 average_precision=float(average_precision_score(yy, p, sample_weight=w)) if yy.any() else None,
                                 observed_queries=int(mask.sum()), reliability=reliability)
    out["mean_brier"] = float(np.mean([out[str(h)]["brier"] for h in horizons]))
    out["instances"] = int(len(np.unique(data["instance"])))
    out["queries"] = len(prediction)
    return out


def subset(data, mask):
    return {key: value[mask] for key, value in data.items()}


def paired_bootstrap(data, baseline, candidate, horizons, seed=20261022, repeats=1000):
    """Resample complete calendar days, retaining all dependent queries/cycles."""
    y, known = targets(data, horizons)
    w = instance_weights(data)
    days, inverse = np.unique((data["start"] // 86400).astype(int), return_inverse=True)
    totals, denominators = [], []
    for j in range(len(horizons)):
        diff = (baseline[:, j] - y[:, j])**2 - (candidate[:, j] - y[:, j])**2
        totals.append(np.bincount(inverse, weights=diff*w*known[:, j], minlength=len(days)))
        denominators.append(np.bincount(inverse, weights=w*known[:, j], minlength=len(days)))
    totals, denominators = np.asarray(totals), np.asarray(denominators)
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(repeats):
        sampled = rng.integers(0, len(days), len(days))
        boot.append(np.mean(totals[:, sampled].sum(axis=1)/denominators[:, sampled].sum(axis=1)))
    return dict(mean_improvement=float(np.mean(totals.sum(axis=1)/denominators.sum(axis=1))),
                ci95=np.quantile(boot, [.025, .975]).tolist(), days=len(days), replicates=repeats)
