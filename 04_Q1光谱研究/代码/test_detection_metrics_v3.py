"""Targeted synthetic checks; never reads workbooks or writes historical output."""
import unittest
import subprocess
import sys
import types
import numpy as np
from detection_metrics_v3 import detection_metrics_v3 as metrics


class ThreeStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fixed reviewed objects, loaded in memory; the older checkout is untouched.
        ref = '346c64ebe864e7f09fa2de227e7b72709fbb8670'
        def load(name, filename):
            source = subprocess.check_output(['git', 'show',
                ref + ':04_Q1光谱研究/代码/' + filename])
            module = types.ModuleType(name)
            sys.modules[name] = module
            exec(compile(source, filename, 'exec'), module.__dict__)
            return module
        cls.old = load('validation_modules', 'validation_modules.py')
        cls.v2 = load('validation_modules_v2_reviewed', 'validation_modules_v2.py')

    def test_actual_detector_unknown_and_single_axis(self):
        x = np.ones((5, 5)); x[2, 2] = 20
        x[1, 2] = np.nan; x[3, 2] = np.nan
        p, d = self.v2.detect_v2(x)
        y = np.zeros(x.shape, dtype=bool); y[2, 2] = True
        out = metrics(p, y, d['eligible'])
        self.assertEqual(d['state'][2, 2], 'Evaluable Triggered')
        self.assertEqual(out['TP'], 1)
        self.assertEqual(out['unknown'], 8)
        with self.assertRaises(TypeError): self.old.detection_metrics(p, y)
        p, d = self.v2.detect_v2(x, time_radius=1, wave_radius=1)
        self.assertEqual(d['state'][2, 2], 'Fallback Required')
        self.assertEqual(metrics(p, y, d['eligible'])['unknown_positive'], 1)

    def test_actual_detector_pollution_and_unit_scaling(self):
        x = np.ones((5, 5)); x[2, 2] = 20; x[1, 2] = 65535
        p, d = self.v2.detect_v2(x)
        self.assertTrue(np.isnan(p[2, 2]))
        self.assertTrue(d['time_polluted'][2, 2])
        p2, d2 = self.v2.detect_v2(x * 10, floor=10, upper=655350)
        np.testing.assert_equal(p, p2)
        y = np.zeros(x.shape, dtype=bool)
        self.assertEqual(metrics(p, y, d['eligible']), metrics(p2, y, d2['eligible']))

    def test_r0_existing_support_and_surface(self):
        t = np.array([0., .5, 2.]); w = np.array([400., 401., 405.])
        plane = 2 * t[:, None] + 3 * w[None, :] + 7
        masked = plane.copy(); masked[1, 1] = np.nan
        for order in ('time-wave', 'wave-time'):
            restored, info = self.v2.r0_with_support_v2(masked, t, w, order)
            np.testing.assert_allclose(restored, plane)
            self.assertGreater(info['provenance'][1, 1], 0)
        surface = self.old.GridSurface(t, w, plane)
        np.testing.assert_allclose(surface.evaluate([.25], [402.]), [[1213.5]])
        with self.assertRaises(ValueError): surface.evaluate([-1.], [402.])
        edge = plane.copy(); edge[0] = np.nan
        restored, info = self.v2.r0_with_support_v2(edge, t, w)
        self.assertTrue(info['unresolved'][0].all())

    def test_confusion_and_abstentions(self):
        out = metrics([1, 1, 0, 0, np.nan, np.nan],
                      np.array([1, 0, 1, 0, 1, 0], dtype=bool))
        self.assertEqual([out[k] for k in ('TP','FP','FN','TN','unknown_positive','unknown_negative')], [1]*6)
        self.assertEqual(out['Recall_conditional'], .5)
        self.assertEqual(out['positive_recovery_all'], 1/3)
        self.assertEqual(out['coverage'], 2/3)

    def test_all_unknown(self):
        out = metrics([np.nan, np.nan], np.array([True, False]))
        self.assertIsNone(out['Recall_conditional'])
        self.assertIsNone(out['F1_conditional'])
        self.assertEqual(out['positive_recovery_all'], 0)
        self.assertEqual(out['unknown_positive_fraction'], 1)
        self.assertEqual(out['coverage'], 0)

    def test_empty(self):
        out = metrics([], np.array([], dtype=bool))
        self.assertEqual(out['total'], 0)
        self.assertIsNone(out['coverage'])
        self.assertIsNone(out['positive_recovery_all'])

    def test_no_positives(self):
        out = metrics([0, np.nan], np.array([False, False]))
        self.assertIsNone(out['Recall_conditional'])
        self.assertIsNone(out['positive_recovery_all'])

    def test_qualification_is_not_population_filter(self):
        out = metrics([1, np.nan], np.array([True, True]), np.array([True, False]))
        self.assertEqual(out['positive_recovery_all'], .5)
        self.assertEqual(out['total'], 2)
        with self.assertRaises(ValueError):
            metrics([1, 0], np.array([True, False]), np.array([True, False]))

    def test_protected_peaks(self):
        out = metrics([1, 0, np.nan], np.zeros(3, dtype=bool),
                      protected_peaks=np.ones(3, dtype=bool))
        self.assertEqual(out['protected_peak_flag_rate_conditional'], .5)
        self.assertEqual(out['protected_peak_flag_rate_all'], 1/3)
        self.assertEqual(out['protected_peak_unknown'], 1)

    def test_invalid_inputs(self):
        for p in ([2], [-1], [np.inf]):
            with self.assertRaises(ValueError): metrics(p, np.array([True]))
        for y in (np.array([1]), np.array([np.nan]), np.array([[True]])):
            with self.assertRaises(ValueError): metrics([1], y)
        with self.assertRaises(ValueError):
            metrics([1], np.array([True]), np.array([1]))


if __name__ == '__main__':
    unittest.main()
