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

    def test_full_slate_marks_late_row_and_keeps_accuracy_grades_separate(self):
        pool = self.fixture()
        pool['kind'] = 'full-slate-after-lock'
        pool['excluded'] = []
        pool['after_lock_game_ids'] = ['2026_01_NE_SEA']
        for game in pool['games']:
            game['added_after_lock'] = False
        game = dict(pool['games'][0], game_id='2026_01_NE_SEA', home='SEA', away='NE',
                    season=2026, week=1, selected_team='SEA', confidence_points=3,
                    win_probability=.6, expected_points=1.8, added_after_lock=True,
                    kickoff='2026-09-10T00:20:00Z', lock_at='2026-09-09T23:20:00Z',
                    probabilities={'home':.6,'away':.396,'tie':.004},
                    baselines={key:{'probabilities':{'home':.6,'away':.396,'tie':.004}}
                               for key in ('corrected','constant')})
        pool['games'].append(game)
        pool['expected_points_total'] = 3.75
        pool['max_points'] = 6
        result = dict(game_id=game['game_id'], home_team='SEA', away_team='NE',
                      kickoff=game['kickoff'], home_score=24, away_score=21,
                      finalized_at='2026-09-10T04:00:00Z')
        rendered = view.render_confidence_picks(pool, [result])
        for text in ('full slate', '3 games', 'Added after lock', '3.75',
                     'Full-slate points earned', '1 of 3', '0 eligible final results',
                     'not a pregame pool submission'):
            self.assertIn(text, rendered)
        self.assertNotIn('log loss 0.', rendered)
        self.assertIn('data-confidence-game-id="2026_01_NE_SEA"', rendered)
        self.assertNotIn('receives no new confidence allocation', rendered)
        archived = view.render_confidence_picks(self.fixture(), archive=True)
        self.assertIn('id="pgo-confidence-previous"', archived)
        self.assertNotIn('data-confidence-game-id=', archived)


if __name__ == '__main__':
    unittest.main()
