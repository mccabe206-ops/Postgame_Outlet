"""No-fit regression check for the independent verifier's decision/symmetry guards."""
import copy
import importlib.util
import unittest


class VerifierTests(unittest.TestCase):
    def test_screen_and_corrupt_saved_arithmetic(self):
        self.assertIsNotNone(importlib.util.find_spec(
            'research.pgo_corrected_roster_candidate.verify'), 'Independent verifier is missing')
        from research.pgo_corrected_roster_candidate import verify as v

        metrics = {key: {'overall': {'mae': pooled}, 'weeks_1_4': {'mae': early},
                        'seasons': [{'season': s, 'mae': 9 if key == 'candidate' and s < 2023 else 10}
                                    for s in range(2018, 2026)]}
                   for key, pooled, early in [('candidate', 9, 99), ('corrected', 10, 1)]}
        result = v.screen(metrics, {'lower': 0.01})
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(len(result['checks']), 3)
        self.assertEqual(result['season_wins'], 5)
        self.assertEqual(v.screen(metrics, {'lower': 0})['status'], 'FAIL')
        bad = copy.deepcopy(metrics)
        bad['candidate']['overall']['mae'] = 10
        self.assertEqual(v.screen(bad, {'lower': 0.01})['status'], 'FAIL')
        bad = copy.deepcopy(metrics)
        bad['candidate']['seasons'][0]['mae'] = 10
        self.assertEqual(v.screen(bad, {'lower': 0.01})['status'], 'FAIL')
        with self.assertRaises(AssertionError):
            v.compare({**result, 'fourth_gate': True}, result)

        fit = {'preprocessor': {'feature_names': ['age', 'home_field', 'rest_difference'],
                                'missing_features': ['age'], 'medians': [0, 0, 0], 'scales': [1, 1, 1]},
               'coefficients': [0, 2, 3, 4, 0]}
        probes = [{'age': 2, 'home_field': 1, 'rest_difference': -3},
                  {'age': None, 'home_field': -1, 'rest_difference': 2}]
        self.assertEqual(v.symmetry(fit, probes)['maximum_error'], 0)
        for index in (0, 4):
            bad = copy.deepcopy(fit)
            bad['coefficients'][index] = 0.01
            with self.assertRaises(AssertionError):
                v.symmetry(bad, probes)
        bad = copy.deepcopy(fit)
        bad['coefficients'][1] = float('nan')
        with self.assertRaises(AssertionError):
            v.symmetry(bad, probes)
        with self.assertRaises(ValueError):
            v.verify(v.DIRECTORY / 'missing-run', v.DIRECTORY / 'charter.md')


if __name__ == '__main__':
    unittest.main()
