"""Landmark discrete hazard with a monotone, temporally separate calibration."""
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from .data import BASE, CONTEXT, instance_weights, targets


class StateSurvival:
    def __init__(self, mode, edges, bins=8, seed=20261022, max_iter=180,
                 max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=10.0):
        self.mode, self.edges, self.bins = mode, np.asarray(edges), bins
        self.params = dict(max_iter=max_iter, max_leaf_nodes=max_leaf_nodes,
                           min_samples_leaf=min_samples_leaf, l2_regularization=l2_regularization,
                           learning_rate=0.07, early_stopping=False, random_state=seed)
        self.cuts = None
        self.calibrator = None

    def _features(self, x, fit=False):
        x = np.array(x, copy=True)
        # Freshness is a reliability signal used by the sidecar gate, not a
        # sensor-cadence shortcut for an otherwise unchanged semantic target.
        if self.mode == "M0":
            return x[:, :len(BASE)]
        x = x[:, :len(BASE) + len(CONTEXT)]
        if self.mode == "M1":
            if fit:
                self.cuts = [np.unique(np.nanquantile(x[:, j], np.linspace(0, 1, self.bins + 1)[1:-1]))
                             for j in range(len(BASE), x.shape[1])]
            for j, cuts in enumerate(self.cuts, len(BASE)):
                valid = np.isfinite(x[:, j])
                x[valid, j] = np.searchsorted(cuts, x[valid, j], side="right")
        return x

    def fit(self, data):
        x = self._features(data["X"], fit=True)
        r, event = data["residual"], data["observed"]
        indices, bins, labels = [], [], []
        for k, boundary in enumerate(self.edges):
            lower = 0 if k == 0 else self.edges[k - 1]
            valid = (r > lower) & (event | (r >= boundary))
            ii = np.flatnonzero(valid)
            indices.extend(ii)
            bins.extend([k] * len(ii))
            labels.extend((event[ii] & (r[ii] <= boundary)).astype(int))
        ii, kk, yy = np.asarray(indices), np.asarray(bins), np.asarray(labels)
        if len(np.unique(yy)) < 2:
            raise ValueError("hazard training requires failures and survivors")
        w = instance_weights(data)[ii]
        w = w / np.mean(w)
        self.estimator = HistGradientBoostingClassifier(**self.params)
        self.estimator.fit(np.c_[x[ii], self.edges[kk]], yy, sample_weight=w)
        self.fit_rows = len(yy)
        return self

    def predict_cdf(self, x, horizons, calibrated=True):
        transformed = self._features(x)
        hazards = np.column_stack([self.estimator.predict_proba(
            np.c_[transformed, np.full(len(x), edge)])[:, 1] for edge in self.edges])
        cdf = 1 - np.cumprod(1 - hazards, axis=1)
        columns = []
        for h in horizons:
            found = np.flatnonzero(self.edges == h)
            if len(found) != 1:
                raise ValueError("query horizon must be an explicit hazard edge")
            columns.append(int(found[0]))
        result = cdf[:, columns]
        if calibrated and self.calibrator is not None:
            result = self.calibrator.predict(result.ravel()).reshape(result.shape)
        return result

    def calibrate(self, data, horizons):
        if len(data["X"]) == 0:
            self.calibrator = None
            return self
        raw = self.predict_cdf(data["X"], horizons, calibrated=False)
        y, known = targets(data, horizons)
        w = np.broadcast_to(instance_weights(data)[:, None], raw.shape)
        if not known.any():
            self.calibrator = None
            return self
        self.calibrator = IsotonicRegression(y_min=1e-6, y_max=1-1e-6, out_of_bounds="clip")
        self.calibrator.fit(raw[known], y[known], sample_weight=w[known])
        return self


class ReliableForecaster:
    """A conservative, explicit fallback when telemetry is stale or absent."""
    def __init__(self, context_model, baseline, stale_after=30.0):
        self.context_model, self.baseline, self.stale_after = context_model, baseline, stale_after

    def predict_cdf(self, x, horizons):
        result = self.context_model.predict_cdf(x, horizons)
        fallback = (~np.isfinite(x[:, len(BASE) + 1])) | (x[:, -1] > self.stale_after)
        if np.any(fallback):
            result[fallback] = self.baseline.predict_cdf(x[fallback], horizons)
        return result, fallback
