import unittest
import numpy as np
from stateforecast.fast_feedback import FastOutcomeExpert,adaptive_forecast


class FastFeedbackTests(unittest.TestCase):
    def test_executable_fast_sidecar_updates_after_observation(self):
        import json
        from stateforecast.data import PACKAGE
        from stateforecast.online_fast import FastStateSidecar
        from stateforecast.stream import Event
        class Model:
            calibrator=None
            def predict_cdf(self,x,h,calibrated=True):return np.tile([.2,.5,.8],(len(x),1))
        side=FastStateSidecar(json.loads((PACKAGE/'configs/dfa.json').read_text()),Model(),Model())
        side.accept(Event('x','LoadStart',0,0));side.accept(Event('x','Telemetry',0,0,(1,)*7))
        p=side.predict('x',0)
        self.assertEqual(side.mixer.updates,0)
        self.assertTrue(np.all(np.diff(p['completion_probability'])>=0))
        side.accept(Event('x','LoadEnd',20,20))
        self.assertEqual(side.mixer.updates,3)
        self.assertEqual(side.base_mixer.updates,3)
        self.assertEqual(side.state.monitor.matches,[('x',20)])

    def test_no_outcome_no_update(self):
        f=FastOutcomeExpert([30,60,120]);x=np.zeros(20)
        p,key=f.predict(x);np.testing.assert_equal(p,[.5]*3)
        self.assertEqual(f.cells,{})
        f.observe(key,1,1)
        p,_=f.predict(x);self.assertTrue(np.all(np.diff(p)>=0))

    def test_future_labels_do_not_change_prefix(self):
        d=dict(time=np.array([0.,5.,10.]),residual=np.array([100.,95.,90.]),observed=np.ones(3,dtype=bool),X=np.zeros((3,20)))
        experts=np.tile(np.array([[[.1,.3,.8],[.2,.4,.9]]]),(3,1,1))
        first,_,_=adaptive_forecast(d,experts,[30,60,120]);d['residual']+=200
        second,_,_=adaptive_forecast(d,experts,[30,60,120]);np.testing.assert_equal(first,second)

    def test_baseline_fast_expert_reads_no_sensors(self):
        f=FastOutcomeExpert([30,60,120]);a=np.zeros(20);b=a.copy();b[5:]=1e6
        self.assertEqual(f.key(a),f.key(b))


if __name__=='__main__':unittest.main()
