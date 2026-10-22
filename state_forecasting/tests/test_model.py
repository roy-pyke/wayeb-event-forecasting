import json
import unittest
import numpy as np
from stateforecast.data import PACKAGE, episode_rows, BASE, SENSORS, targets
from stateforecast.model import StateSurvival, ReliableForecaster
from stateforecast.mixer import DelayedExpertMixer, causal_mix
from stateforecast.online import StateSidecar
from stateforecast.stream import Event


class ConstantModel:
    def __init__(self, p):
        self.p = np.asarray(p)
    def predict_cdf(self, x, h):
        return np.tile(self.p, (len(x), 1))


class ModelTests(unittest.TestCase):
    def test_empty_calibration_preserves_uncalibrated_model(self):
        m=StateSurvival('M0',[30,60,120])
        m.calibrate({'X':np.empty((0,20))},[30,60,120])
        self.assertIsNone(m.calibrator)

    def test_censored_horizon_never_becomes_false_negative(self):
        d = dict(residual=np.array([20,20,80]), observed=np.array([False,True,False]))
        y, known = targets(d,[10,30,60,120])
        np.testing.assert_array_equal(known[0],[True,False,False,False])
        np.testing.assert_array_equal(y[1],[0,1,1,1])
        np.testing.assert_array_equal(known[2],[True,True,True,False])

    def test_survival_probability_preserves_mass_and_order(self):
        class Estimator:
            def predict_proba(self, x):
                return np.tile([.8,.2], (len(x),1))
        model=StateSurvival('M0',[10,20,30]);model.estimator=Estimator()
        p=model.predict_cdf(np.ones((2,20)),[10,20,30])
        np.testing.assert_allclose(p[0],[.2,.36,.488])
        self.assertTrue((np.diff(p,axis=1)>=0).all())
        self.assertTrue((p[:,-1]<1).all())

    def test_shared_calibration_retains_cdf_order(self):
        from sklearn.isotonic import IsotonicRegression
        model=StateSurvival('M0',[10,20,30])
        model.calibrator=IsotonicRegression(out_of_bounds='clip').fit([.1,.3,.7,.9],[0,0,1,1])
        q=model.calibrator.predict([.2,.4,.8])
        self.assertTrue((np.diff(q)>=0).all())

    def test_quantization_fitted_only_on_training(self):
        m=StateSurvival('M1',[30,60,120],bins=4)
        train=np.tile(np.arange(100.)[:,None],(1,20))
        m._features(train,fit=True)
        cuts=[c.copy() for c in m.cuts]
        m._features(np.full((10,20),100000.))
        for a,b in zip(cuts,m.cuts):np.testing.assert_equal(a,b)

    def test_mixer_rejects_future_feedback(self):
        mixer=DelayedExpertMixer()
        with self.assertRaises(ValueError):mixer.observe([.2,.9],1,100,99)
        np.testing.assert_equal(mixer.weights,[.5,.5])

    def test_future_outcome_cannot_change_earlier_mixture(self):
        d=dict(time=np.array([0.,5.,10.,20.]), residual=np.array([100.,95.,90.,80.]), observed=np.ones(4,dtype=bool))
        a=np.tile([.1,.3,.9],(4,1));b=np.tile([.2,.4,.8],(4,1))
        p1,_,_=causal_mix(d,a,b,[30,60,120])
        d['residual']=np.array([200.,195.,190.,180.])
        p2,_,_=causal_mix(d,a,b,[30,60,120])
        np.testing.assert_equal(p1,p2)

    def test_mixture_is_cdf(self):
        m=DelayedExpertMixer()
        m.observe([.1,.8],1,1,1)
        p=m.predict(np.array([[.1,.4,.7],[.2,.6,.9]]))
        self.assertTrue(np.all(np.diff(p)>=0))
        self.assertTrue(np.all((p>=0)&(p<=1)))

    def test_missing_context_falls_back_exactly(self):
        f=ReliableForecaster(ConstantModel([.8,.9,.99]),ConstantModel([.1,.2,.3]))
        x=np.zeros((3,20));x[0,-1]=31;x[1,len(BASE)+1]=np.nan
        p,used=f.predict_cdf(x,[30,60,120])
        np.testing.assert_allclose(p[:2],[[.1,.2,.3],[.1,.2,.3]])
        np.testing.assert_array_equal(used,[True,True,False])

    def test_online_features_equal_training_features(self):
        table=json.loads((PACKAGE/'configs/dfa.json').read_text())
        sidecar=StateSidecar(table,ConstantModel([.1,.2,.3]),ConstantModel([.1,.2,.3]))
        times=np.arange(0.,101.,10.)
        sensor=np.tile(times[:,None],(1,7))
        expected=episode_rows(times,sensor,0,10,True,[],20)
        sidecar.accept(Event('job','LoadStart',0,0))
        at={r[0]:r[3] for r in expected}
        for i,t in enumerate(times[:-1]):
            sidecar.accept(Event('job','Telemetry',t,t,tuple(sensor[i])))
            if t in at:np.testing.assert_equal(sidecar.features('job',t)[0],at[t])
        self.assertEqual(len(sidecar.monitor.matches),0)
        self.assertTrue(sidecar.accept(Event('job','LoadEnd',100,100)))
        self.assertIsNone(sidecar.predict('job',100))

    def test_online_feedback_only_when_finish_or_deadline_arrives(self):
        table=json.loads((PACKAGE/'configs/dfa.json').read_text())
        sidecar=StateSidecar(table,ConstantModel([.9,.9,.9]),ConstantModel([.1,.1,.1]))
        sidecar.accept(Event('x','LoadStart',0,0))
        sidecar.accept(Event('x','Telemetry',0,0,(1.,)*7))
        sidecar.predict('x',0)
        np.testing.assert_equal(sidecar.mixer.weights,[.5,.5])
        sidecar.accept(Event('x','Telemetry',10,10,(1.,)*7))
        self.assertEqual(sidecar.mixer.updates,0)
        sidecar.accept(Event('x','LoadEnd',20,20))
        self.assertEqual(sidecar.mixer.updates,3)
        self.assertGreater(sidecar.mixer.weights[1],.9)

    def test_online_gap_censors_feedback(self):
        table=json.loads((PACKAGE/'configs/dfa.json').read_text())
        s=StateSidecar(table,ConstantModel([.9]*3),ConstantModel([.1]*3))
        s.accept(Event('x','LoadStart',0,0));s.predict('x',0)
        s.accept(Event('x','Gap',10,10))
        self.assertEqual(s.mixer.updates,0)
        self.assertEqual(s.pending,[])


if __name__=='__main__':unittest.main()
