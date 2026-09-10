import copy
import unittest

import pgo_model_updates as view


class ConfidenceViewTests(unittest.TestCase):
    def fixture(self):
        return {'status': 'EXPERIMENTAL / HOLD', 'generated_at': '2026-09-10T00:30:00Z',
                'expected_points_total': 1.95, 'max_points': 3,
                'calibration': {'slope': .15, 'tie_probability': .004},
                'excluded': [{'game_id': '2026_01_NE_SEA', 'home': 'SEA', 'away': 'NE',
                              'reason': 'EXISTING_CUTOFF_ELAPSED'}],
                'games': [
                    {'game_id': '2026_01_BUF_NYJ', 'away': 'BUF', 'home': 'NYJ',
                     'selected_team': 'BUF', 'win_probability': .7, 'confidence_points': 2,
                     'expected_points': 1.4, 'kickoff': '2026-09-13T17:00:00Z',
                     'lock_at': '2026-09-13T16:00:00Z'},
                    {'game_id': '2026_01_LA_ARI', 'away': 'LA', 'home': 'ARI',
                     'selected_team': 'ARI', 'win_probability': .55, 'confidence_points': 1,
                     'expected_points': .55, 'kickoff': '2026-09-13T17:00:00Z',
                     'lock_at': '2026-09-13T16:00:00Z'}]}

    def test_model_picks_expected_points_and_late_opener_are_clear(self):
        pool = self.fixture()
        before = copy.deepcopy(pool)
        rendered = view.render_confidence_picks(pool)
        for text in ('PGO confidence picks', '70.0%', '55.0%', '1.40', '1.95',
                     'Expected pool points', 'EXPERIMENTAL / HOLD', '2 remaining games',
                     'NE @ SEA', 'already locked', 'not NFL scoreboard points',
                     'Non-QB injuries', '0 of 2'):
            self.assertIn(text, rendered)
        self.assertEqual(rendered.count('data-confidence-game-id='), 2)
        self.assertNotIn('data-confidence-game-id="2026_01_NE_SEA"', rendered)
        self.assertIn('href="#postseason-why-2026_01_BUF_NYJ"', rendered)
        self.assertEqual(pool, before)


if __name__ == '__main__':
    unittest.main()
