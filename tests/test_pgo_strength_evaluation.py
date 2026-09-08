from dataclasses import replace
import tempfile
from pathlib import Path
import unittest

import pgo_strength_evaluation as evaluation
from test_pgo_opponent_evaluation import Row


class StrengthEvaluationTests(unittest.TestCase):
    def row(self, game='a'):
        features = {name: 1.0 for names in evaluation.GROUPS.values() for name in names}
        features.update(home_field=1.0, rest_difference=0.0)
        return Row(game, 2018, 1, '2018-09-01T00:00:00+00:00', 3.0, features, {})

    def test_ablations_remove_whole_group_preserve_controls_and_original(self):
        row = self.row()
        for group, fields in evaluation.GROUPS.items():
            reduced = evaluation.ablate([row], group)[0]
            self.assertEqual(set(reduced.features), set(row.features) - set(fields))
            self.assertEqual(reduced.features['home_field'], 1.0)
            self.assertEqual(reduced.actual_margin, row.actual_margin)
            self.assertTrue(set(fields) <= set(row.features))
        with self.assertRaises(ValueError):
            evaluation.ablate([replace(row, features={'home_field': 1.0})], 'qb')

    def test_matching_games_rejects_target_or_order_changes(self):
        rows = [self.row('a'), self.row('b')]
        evaluation.validate_matching_arms({'raw': rows, 'candidate': rows})
        for changed in ([rows[1], rows[0]], [replace(rows[0], actual_margin=4.0), rows[1]]):
            with self.assertRaises(ValueError):
                evaluation.validate_matching_arms({'raw': rows, 'candidate': changed})

    def test_screen_requires_every_predeclared_condition(self):
        def metrics(mae, early, wins):
            return {'overall': {'mae': mae}, 'weeks_1_4': {'mae': early},
                    'seasons': [{'season': 2018+i, 'mae': 9 if i < wins else 11} for i in range(8)]}
        raw = metrics(10, 10, 0)
        raw['seasons'] = [{'season': 2018+i, 'mae': 10} for i in range(8)]
        good = metrics(9, 10, 5)
        self.assertTrue(evaluation.screen(good, raw, {'lower': .01})['merits_further_prospective_study'])
        for candidate, interval in ((metrics(9, 10, 4), .01), (metrics(9, 11, 5), .01), (good, 0)):
            self.assertFalse(evaluation.screen(candidate, raw, {'lower': interval})['merits_further_prospective_study'])

    def test_run_rejects_existing_output_before_loading_or_fitting(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'new'):
                evaluation.run_experiment(Path(directory))


if __name__ == '__main__':
    unittest.main()
