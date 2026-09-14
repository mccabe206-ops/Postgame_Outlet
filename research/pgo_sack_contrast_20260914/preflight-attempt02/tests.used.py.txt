"""Algebra and boundary tests only: never fit a candidate during tests."""
import copy
import math
import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np

from research.pgo_sack_contrast_20260914 import candidate as c


class ContrastTests(unittest.TestCase):
    def setUp(self):
        self.meta = dict(feature_names=['other', c.Q, c.T], medians=[0., 0., 0.],
                         scales=[1., 2., 4.], missing_features=[c.Q, c.T])
        self.row = c.ch.FeatureRow('x', 2017, 1, '2017-09-01T00:00:00+00:00',
                                  7., dict(other=3., **{c.Q: 2., c.T: -4.}), {})

    def test_transform_inverse_and_penalty_are_independent_identities(self):
        matrix = np.array([[3., 1., -1., 0., 0.]])
        transformed = c.transform(matrix, self.meta, c.transformation(self.meta))
        self.assertAlmostEqual(transformed[0, 1], 0.)
        self.assertAlmostEqual(transformed[0, 2], 1 / math.sqrt(2))
        self.assertTrue(np.array_equal(transformed[:, [0, 3, 4]], matrix[:, [0, 3, 4]]))
        self.assertTrue(np.array_equal(matrix, [[3., 1., -1., 0., 0.]]))
        a, b = .4, -.8
        bq, bt = (a + b / 2) / math.sqrt(2), (a - b / 2) / math.sqrt(2)
        self.assertAlmostEqual(a * a + b * b, (bq + bt) ** 2 / 2 + 4 * (bq - bt) ** 2 / 2)
        self.assertAlmostEqual(a * transformed[0, 1] + b * transformed[0, 2], bq - bt)
        self.assertAlmostEqual((transformed[0, 1] + 2 * transformed[0, 2]) / math.sqrt(2), 1.)
        self.assertAlmostEqual((transformed[0, 1] - 2 * transformed[0, 2]) / math.sqrt(2), -1.)
        # Factor-one rotation is algebra only, never another fitted arm.
        q, t = 1.7, -.2
        self.assertAlmostEqual(((q + t) / math.sqrt(2)) ** 2 + ((q - t) / math.sqrt(2)) ** 2, q*q+t*t)

    def test_observed_zero_and_one_or_both_missing_keep_flags(self):
        pp = c.preprocessor(self.meta)
        rows = [replace(self.row, features=dict(other=3., **{c.Q:q, c.T:t}))
                for q, t in ((0., 0.), (None, 0.), (0., None), (None, None), (None, 4.))]
        matrix = c.transform(pp.transform(rows), self.meta, c.transformation(self.meta))
        self.assertTrue(np.array_equal(matrix[:, 3:], [[0,0], [1,0], [0,1], [1,1], [1,0]]))
        self.assertTrue(np.array_equal(matrix[:4, 1:3], np.zeros((4,2))))
        self.assertAlmostEqual(matrix[4, 1], 1 / math.sqrt(2))
        self.assertAlmostEqual(matrix[4, 2], -1 / (2*math.sqrt(2)))

    def test_permuted_feature_inventory_rejected(self):
        declaration = c.transformation(self.meta)
        altered = copy.deepcopy(self.meta)
        altered['feature_names'][1:] = reversed(altered['feature_names'][1:])
        with self.assertRaisesRegex(ValueError, 'inventory'):
            c.transform(np.zeros((1,5)), altered, declaration)

    def test_no_rescaling_and_no_extra_columns(self):
        x = np.array([[1., 2., 3., 0., 1.], [4., 7., -5., 1., 0.]])
        out = c.transform(x, self.meta, c.transformation(self.meta))
        self.assertEqual(x.shape, out.shape)
        np.testing.assert_allclose(out[:, 1], (x[:,1]+x[:,2])/math.sqrt(2), rtol=0, atol=1e-14)
        np.testing.assert_allclose(out[:, 2], (x[:,1]-x[:,2])/(2*math.sqrt(2)), rtol=0, atol=1e-14)

    def test_bad_numbers_and_invalid_saved_scales_stop(self):
        for value in (True, float('nan'), float('inf'), '1'):
            bad = replace(self.row, features={**self.row.features, c.Q:value})
            with self.subTest(value=value), self.assertRaises(ValueError):
                c.validate_rows([bad], self.meta['feature_names'])
        for value in (0., -1., float('nan'), True):
            bad = copy.deepcopy(self.meta); bad['scales'][0] = value
            with self.subTest(scale=value), self.assertRaises(ValueError): c.preprocessor(bad)

    def test_unobserved_feature_stops_and_zero_variance_falls_back(self):
        row = replace(self.row, features={**self.row.features, c.Q:None})
        with self.assertRaises(ValueError): c.ch.fit_preprocessor([row], self.meta['feature_names'])
        pp = c.ch.fit_preprocessor([self.row, self.row], self.meta['feature_names'])
        self.assertTrue(np.array_equal(pp.scales, [1.,1.,1.]))

    def test_future_changes_do_not_enter_selected_training_preprocessor(self):
        source = [self.row, replace(self.row, game_id='future', season=2018)]
        first = c.reconstructed(source, ['x'], self.meta['feature_names'])
        source[1] = replace(source[1], features={key:99999. for key in self.meta['feature_names']})
        after = c.reconstructed(source, ['x'], self.meta['feature_names'])
        self.assertEqual(first, after)

    def test_serialized_replay_matches_independent_raw_basis(self):
        fit = dict(preprocessor=self.meta, transformation=c.transformation(self.meta),
                   coefficients=[0., .3, .4, -.8, 0., 0.])
        bq = (.4 - .8/2)/math.sqrt(2)
        bt = (.4 + .8/2)/math.sqrt(2)
        self.assertAlmostEqual(c.replay([self.row], fit)[0], .3*3 + bq*1 + bt*(-1))
        self.assertTrue(c.symmetry(fit, self.row)['passed'])

    def test_gate_requires_all_locked_conditions(self):
        seasons = [{'season':s, 'mae':10.} for s in range(2018,2026)]
        metrics = {'control':{'overall':{'mae':10.},'seasons':seasons},
                   'sack_contrast4':{'overall':{'mae':9.9},'seasons':[{**s, 'mae':9.9} for s in seasons]}}
        passed = c.screen(metrics, {'lower':.01}, {'candidate_drift':.1,'control_drift':.1})
        self.assertEqual(passed['status'], 'PASS')
        failed = c.screen(metrics, {'lower':-.01}, {'candidate_drift':.1,'control_drift':.1})
        self.assertEqual(failed['status'], 'FAIL')
        failed = c.screen(metrics, {'lower':.01}, {'candidate_drift':.2,'control_drift':.1})
        self.assertTrue(failed['primary_screen_passed'])
        self.assertFalse(failed['stability_screen_passed'])

    def test_fit_fence_rejects_duplicate_or_unplanned_call_before_optimizer(self):
        with patch.object(c.ch, 'fit_huber_ridge', side_effect=AssertionError('must not fit')):
            with self.assertRaises(ValueError): c.fit_once('other', [], [], set())
            with self.assertRaises(ValueError): c.fit_once('2018', [], [], {'2018'})


if __name__ == '__main__': unittest.main()
