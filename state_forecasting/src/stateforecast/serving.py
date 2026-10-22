"""Equivalent execution adapter for the frozen survival model.

All hazard bins share one fitted tree ensemble. Batch their input rows to avoid
calling that ensemble once per bin. No training, thresholds, or outputs change.
"""
import numpy as np


class BatchedSurvival:
    def __init__(self, model):
        self.model = model

    @property
    def calibrator(self):
        return self.model.calibrator

    def predict_cdf(self, x, horizons, calibrated=True):
        edges = self.model.edges
        columns = []
        for horizon in horizons:
            found = np.flatnonzero(edges == horizon)
            if len(found) != 1:
                raise ValueError("query horizon must be an explicit hazard edge")
            columns.append(int(found[0]))
        features = self.model._features(x)
        # Row-major: all bins of query 0, then all bins of query 1, etc.
        inputs = np.column_stack((np.repeat(features, len(edges), axis=0),
                                  np.tile(edges, len(features))))
        hazards = self.model.estimator.predict_proba(inputs)[:, 1].reshape(len(features), len(edges))
        result = (1 - np.cumprod(1 - hazards, axis=1))[:, columns]
        if calibrated and self.calibrator is not None:
            result = self.calibrator.predict(result.ravel()).reshape(result.shape)
        return result
