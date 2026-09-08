import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_challenger as ch


class CorrectedTrainerTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(Path('research/pgo_week1_corrected/train.py').exists(),
                        'The combined trainer has not been implemented')
        self.train = importlib.import_module('research.pgo_week1_corrected.train')

    def test_portable_context_uses_decayed_history_and_preserves_original(self):
        context = {'season': 2025, 'ratings': {'NE': 2.0},
                   'ratios': {'NE': {'passing_epa_per_play_for': ch._RatioState(3, 10)}},
                   'qb_history': {'old': {'dropbacks': 999}},
                   'current_strength': {'last_kickoff': '2026-01-05T01:20:00+00:00',
                                        'qb_history': {'new': {'dropbacks': 200.5}},
                                        'qb_population': {'dropbacks': 900.0},
                                        'inputs': {'do_not_export': 'large'}},
                   'evaluation_metadata': {'do_not_export': 'large'}}
        exported = self.train.portable_context(context, {'colliding_gsis': {'id'}})
        self.assertEqual(exported['ratios']['NE']['passing_epa_per_play_for'], .3)
        self.assertEqual(exported['current_strength']['qb_history'], {'new': {'dropbacks': 200.5}})
        self.assertEqual(exported['inputs'], {'colliding_gsis': ['id']})
        self.assertNotIn('evaluation_metadata', exported)
        self.assertNotIn('inputs', exported['current_strength'])
        exported['current_strength']['qb_history']['new']['dropbacks'] = 0
        self.assertEqual(context['current_strength']['qb_history']['new']['dropbacks'], 200.5)
        context['season'] = 2026
        with self.assertRaises(ValueError):
            self.train.portable_context(context, {})

    def test_training_contract_rejects_dropped_games_removed_fields_and_nonfinite(self):
        row = ch.FeatureRow('2018_g', 2018, 1, '2018-09-01T00:00:00+00:00',
                            3.0, {'home_field': 1.0, 'qb_epa_per_dropback': None}, {})
        saved = {'2018_g': {'season': '2018', 'week': '1', 'kickoff': row.kickoff,
                           'actual_margin': '3.0'}}
        args = (saved, ['2018_g'], set(row.features))
        self.train.validate_rows([row], *args)
        with self.assertRaises(ValueError):
            self.train.validate_rows([], *args)
        with self.assertRaises(ValueError):
            self.train.validate_rows([row, row], *args)
        row.features['head_coach_continuity'] = 1.0
        with self.assertRaises(ValueError):
            self.train.validate_rows([row], *args)
        del row.features['head_coach_continuity']
        row.features['home_field'] = float('nan')
        with self.assertRaises(ValueError):
            self.train.validate_rows([row], *args)

    def test_run_start_is_exclusive_and_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'run'
            self.train.start_run(path, {'status': 'STARTED'})
            original = (path / 'run-start.json').read_bytes()
            with self.assertRaises((FileExistsError, ValueError)):
                self.train.start_run(path, {'status': 'REPLACED'})
            self.assertEqual((path / 'run-start.json').read_bytes(), original)

    def test_combined_fit_delegates_only_to_declared_symmetric_fit(self):
        rows = [object()]
        with patch.object(self.train.audit, '_fit_arm', return_value=('pp', 'coef', 'mirrored')) as fit:
            self.assertEqual(self.train.fit_combined(rows), ('pp', 'coef', 'mirrored'))
        fit.assert_called_once_with('active4_symmetric', rows)

    def test_saved_fit_replay_handles_missing_and_standardization(self):
        fit = {'preprocessor': {'feature_names': ['a'], 'medians': [2.0],
                               'scales': [4.0], 'missing_features': ['a']},
               'coefficients': [1.0, 3.0, -5.0]}
        rows = [ch.FeatureRow('a', 2025, 1, '', 0, {'a': 6.0}, {}),
                ch.FeatureRow('b', 2025, 1, '', 0, {'a': None}, {})]
        self.assertEqual(self.train.replay(rows, json.loads(json.dumps(fit))), [4.0, -4.0])


if __name__ == '__main__':
    unittest.main()
