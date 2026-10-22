import unittest
import numpy as np
from sklearn.isotonic import IsotonicRegression
from stateforecast.data import FEATURES
from stateforecast.model import StateSurvival
from stateforecast.serving import BatchedSurvival


class ServingTests(unittest.TestCase):
    def test_fitted_models_preserve_each_query_and_calibration(self):
        rng = np.random.default_rng(20261022)
        x = rng.normal(size=(120, len(FEATURES)))
        x[::7, 6] = np.nan
        data = dict(X=x, instance=np.arange(len(x)),
                    residual=rng.uniform(1, 200, len(x)),
                    observed=rng.random(len(x)) > .1)
        for mode in ['M0', 'M1', 'M2']:
            with self.subTest(mode=mode):
                original = StateSurvival(mode, [10, 30, 60, 120, 300],
                                         max_iter=8, max_leaf_nodes=7, min_samples_leaf=5).fit(data)
                original.calibrator = IsotonicRegression(out_of_bounds='clip').fit(
                    [0, .1, .4, .7, 1], [0, .2, .3, .8, 1])
                batched = BatchedSurvival(original)
                for query in [x[:1], x[:11], x[::13]]:
                    for calibrated in [False, True]:
                        np.testing.assert_array_equal(
                            batched.predict_cdf(query, [120, 30, 60], calibrated),
                            original.predict_cdf(query, [120, 30, 60], calibrated))

    def test_invalid_horizon_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'explicit hazard edge'):
            BatchedSurvival(StateSurvival('M0', [30, 60, 120])).predict_cdf(
                np.zeros((1, len(FEATURES))), [45])


if __name__ == '__main__':
    unittest.main()
