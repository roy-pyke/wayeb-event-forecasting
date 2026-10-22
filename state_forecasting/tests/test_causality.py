import json
import unittest
import numpy as np
from stateforecast.data import PACKAGE, episode_rows, episodes
from stateforecast.stream import ContextState, Event, Milestones, WayebMonitor
from stateforecast.rolling import asof


class CausalityTests(unittest.TestCase):
    def test_future_telemetry_cannot_change_prefix(self):
        times = np.arange(0, 101, 10, dtype=float)
        x = np.tile(np.arange(len(times))[:, None], (1, 7)).astype(float)
        a = episode_rows(times, x, 0, 10, True, [50, 70], 20)
        x[6:] = 10000
        b = episode_rows(times, x, 0, 10, True, [50, 70], 20)
        for one, two in zip(a[:3], b[:3]):
            np.testing.assert_equal(one[3], two[3])

    def test_terminal_time_does_not_normalize_progress(self):
        times = np.arange(0, 201, 10, dtype=float)
        x = np.tile(times[:, None], (1, 7))
        a = episode_rows(times, x, 0, 8, True, [50], 20)
        b = episode_rows(times, x, 0, 20, True, [50], 20)
        for one, two in zip(a, b):
            np.testing.assert_equal(one[3], two[3])

    def test_delayed_report_is_not_available_early(self):
        times = np.arange(0, 101, 10, dtype=float)
        x = np.tile(times[:, None], (1, 7))
        rows = episode_rows(times, x, 0, 10, True, [], 20, delay=30)
        self.assertTrue(np.isnan(rows[1][3][5]))  # t=20, no report yet
        self.assertEqual(rows[2][3][5], 10)  # t=40, only t<=10 available
        self.assertEqual(rows[2][3][-1], 30)

    def test_out_of_order_does_not_overwrite_new_report(self):
        c = ContextState(1)
        c.accept(Event("x", "Telemetry", 10, 10, (5,)))
        self.assertFalse(c.accept(Event("x", "Telemetry", 5, 12, (100,))))
        self.assertEqual(c.snapshot(13)[0][0], 5)
        with self.assertRaises(ValueError):
            c.snapshot(9)

    def test_event_time_cannot_be_in_future(self):
        with self.assertRaises(ValueError):
            ContextState(1).accept(Event("x", "Telemetry", 10, 9, (1,)))

    def test_gap_censors_and_prevents_phantom_completion(self):
        found = list(episodes(np.array([0, 10, 20, 200, 210, 220]), np.array([1, 0, 0, 0, 1, 0]), 60))
        self.assertEqual(found, [(1, 2, False), (5, 5, False)])

    def test_milestone_jump_and_rollback(self):
        m = Milestones()
        self.assertEqual(m.update(.8, 100), [(.25, 100), (.5, 100), (.75, 100)])
        self.assertEqual(m.update(.2, 110), [])
        self.assertEqual(m.update(.8, 120), [])
        m.reset()
        self.assertEqual(m.update(.3, 130), [(.25, 130)])

    def test_asof_masks_terminal_labels(self):
        d = dict(time=np.array([10., 20., 200.]), start=np.array([0., 0., 200.]),
                 residual=np.array([90., 80., 1.]), observed=np.array([True, True, True]),
                 instance=np.array([1, 1, 2]), X=np.ones((3, 2)))
        a = asof(d, 50, 0)
        np.testing.assert_array_equal(a["observed"], [False, False])
        np.testing.assert_array_equal(a["residual"], [40, 30])
        d["residual"][:2] = [900, 890]
        b = asof(d, 50, 0)
        for k in a:
            np.testing.assert_array_equal(a[k], b[k])

    def test_partition_and_telemetry_semantic_projection(self):
        table = json.loads((PACKAGE / "configs/dfa.json").read_text())
        coarse, fine = WayebMonitor(table), WayebMonitor(table)
        rng = np.random.default_rng(23)
        for t in range(10000):
            event = Event(str(rng.integers(0, 7)), rng.choice(table["alphabet"]), t, t)
            coarse.accept(event)
            fine.accept(Event(event.instance, "Telemetry", t, t, (.9,)))
            fine.accept(event)
        self.assertEqual(coarse.states, fine.states)
        self.assertEqual(coarse.matches, fine.matches)


if __name__ == "__main__":
    unittest.main()
