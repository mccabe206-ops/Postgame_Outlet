import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

from research.pgo_postseason_candidate import sources


class SourceTests(unittest.TestCase):
    def test_official_injury_empty_cells_and_status_are_preserved(self):
        page = ('<div class="d3-o-section-sub-title"><span>Patriots</span></div><table>'
                '<tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>'
                '<tr><td>Player &amp; Name</td><td>QB</td><td></td><td>Full Participation</td><td></td></tr>'
                '<tr><td>Other</td><td>RB</td><td>Ankle</td><td></td><td>Out</td></tr></table>')
        rows = sources.injury_tables(page)['Patriots']
        self.assertEqual(rows[0]['game_status'], '')
        self.assertEqual(rows[0]['player_name'], 'Player & Name')
        self.assertEqual(rows[1]['game_status'], 'Out')
        with self.assertRaises(ValueError):
            sources.injury_tables(page.replace('Out', 'Maybe'))
        with self.assertRaises(ValueError):
            sources.injury_tables(page + page)


class SnapshotTests(unittest.TestCase):
    def test_weekly_dispatch_uses_separate_strict_verifier(self):
        import json
        import pgo_forecast_postseason as candidate
        import pgo_forecast_weekly as weekly
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'manifest.json').write_text(json.dumps({'edition': candidate.EDITION}))
            with patch.object(candidate, 'load_snapshot', side_effect=ValueError('unreviewed run')):
                with self.assertRaisesRegex(ValueError, 'unreviewed run'):
                    weekly._verified_source(path)

    def test_derivation_preserves_scores_and_blocks_elapsed_games(self):
        import pgo_forecast_postseason as candidate
        from pgo_model import CURRENT_TEAMS
        teams = list(CURRENT_TEAMS)
        features = {t: {'pgo_v0': float(i), 'home_field': 0., 'rest_difference': 0.} for i, t in enumerate(teams)}
        fit = {'preprocessor': {'feature_names': ['pgo_v0', 'home_field', 'rest_difference'],
                               'medians': [0., 0., 0.], 'scales': [1., 1., 1.], 'missing_features': []},
               'coefficients': [0., 1., 1.5, .1]}
        game = dict(game_id='test', season=2026, week=1, kickoff='2026-09-10T00:20:00+00:00',
                    game_type='REG', location='Home', home=teams[0], away=teams[1], home_rest=7, away_rest=7)
        qualification = dict(selected_roster={t: {'full_name': t+' QB', 'gsis_id': t} for t in teams},
                             inputs_as_of='2026-09-09T21:00:00+00:00', games=[game],
                             coverage={t: {'status': 'UNKNOWN'} for t in teams})
        prior = dict(teams=[dict(team=t, rank=i+1, rating=0.) for i, t in enumerate(teams)],
                     games=[dict(**game, margin=1., total=44., pgo_v0_margin=0., legacy_margin=0.)])
        rates = {t: dict(pf=23., pa=21.) for t in teams}
        with patch.object(candidate.base, 'current_features', return_value=features):
            rows, games, skipped = candidate.derive(qualification, {}, fit, rates, 44., prior, '2026-09-09T22:00:00+00:00')
            self.assertEqual(len(rows), 32)
            self.assertAlmostEqual(sum(r['rating'] for r in rows), 0.)
            for row in rows:
                self.assertAlmostEqual(sum(row['contributions'].values()), row['rating'])
            self.assertAlmostEqual(games[0]['home_points'] - games[0]['away_points'], games[0]['margin'])
            self.assertAlmostEqual(games[0]['home_points'] + games[0]['away_points'], games[0]['total'])
            self.assertEqual(skipped, [])
            with self.assertRaisesRegex(ValueError, 'eligible'):
                candidate.derive(qualification, {}, fit, rates, 44., prior, '2026-09-09T23:20:00+00:00')


if __name__ == '__main__':
    unittest.main()
