import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import pgo_season as season
from tests import test_pgo_season as fixtures


class PenaltyIntegrationTests(unittest.TestCase):
    def test_penalty_view_explains_paired_errors_and_keeps_main_picks_separate(self):
        import pgo_season_view as view
        self.assertTrue(hasattr(view, '_penalty_shadow'), 'Penalty comparison view missing')
        shadow = dict(status='READY', checked_at='2026-09-10T10:00:00Z', games=[], excluded=[],
            historical=dict(games=2127, baseline_mae=10.1, candidate_mae=10.2, mae_improvement=-.1,
                            interval={'lower':-.2,'upper':.03}, season_wins=3, status='FAIL'),
            metrics=dict(paired_games=1, paired_weeks=1,
                         control=dict(wins=1,losses=0,ties=0,mae=2.,rmse=2.,bias=2.),
                         candidate=dict(wins=1,losses=0,ties=0,mae=4.,rmse=4.,bias=4.),mae_improvement=-2.))
        rendered = view._penalty_shadow(shadow)
        self.assertIn('separate from the main picks', rendered)
        self.assertIn('Lower error is better', rendered)
        self.assertIn('10.100', rendered)
        self.assertIn('10.200', rendered)
        self.assertIn('did not meet', rendered)
        self.assertIn('Weights stay fixed', rendered)
        shadow.update(status='BLOCKED', blocked_reason='<script>bad source</script>')
        self.assertNotIn('<script>', view._penalty_shadow(shadow))

    def state(self):
        game = dict(fixtures.SeasonTests().game(), margin=3, total=45, home_points=24,
                    away_points=21, issued_at='2026-09-09T18:00:00Z')
        return dict(schema_version=1, season=2026, current_week=1, status='READY',
                    checked_at='2026-09-09T18:00:00Z', weeks=[dict(week=1, games=[game])],
                    rankings={'completed_week':0}, results=[], sources=[])

    def test_shadow_durable_failure_does_not_publish_a_new_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); before = self.state(); season.save_state(before, root)
            pointer = (root/'current.json').read_bytes()
            changed = copy.deepcopy(before)
            changed.update(checked_at='2026-09-09T19:00:01Z', penalty_shadow={'games':[{'new':True}]})
            module = SimpleNamespace(check_durable_shadow=Mock(side_effect=ValueError('Shadow cutoff passed')))
            with patch.dict(sys.modules, {'pgo_penalty_monitor':module}):
                with self.assertRaisesRegex(ValueError, 'Shadow cutoff passed'):
                    season.save_state(changed, root)
            self.assertEqual((root/'current.json').read_bytes(), pointer)
            self.assertEqual(season.load_current(root), before)

    def test_refresh_saves_shadow_after_primary_grading_without_changing_pick(self):
        before = self.state(); game = before['weeks'][0]['games'][0]
        future = dict(game, game_id='2026_01_NYJ_BUF', home='BUF', away='NYJ', kickoff='2026-09-13T17:00:00Z')
        before['weeks'][0]['games'].append(future)
        finals = season.parse_scoreboard(fixtures.SeasonTests().board(), [game], '2026-09-09T23:00:00Z')['results']
        def shadow(state, previous, root, checked_at):
            self.assertEqual(state['weeks'][0]['games'][0]['grade'], 'W')
            self.assertEqual(state['weeks'][0]['games'][0]['margin'], game['margin'])
            return {'status':'READY', 'games':[], 'verified_primary_finals':len(state['results'])}
        module = SimpleNamespace(refresh_shadow=shadow, check_durable_shadow=Mock())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); season.save_state(before, root)
            with patch.dict(sys.modules, {'pgo_penalty_monitor':module}), patch.object(season,'fetch_inputs',return_value=([game,future],finals,[],{})), patch.object(season,'legacy_models',return_value=[]), patch.object(season,'refresh_availability',return_value=[]):
                after = season.refresh(root)
            self.assertEqual(after.get('penalty_shadow',{}).get('verified_primary_finals'), 1)
            self.assertEqual(season.load_current(root), after)
            module.check_durable_shadow.assert_called_once()


if __name__ == '__main__': unittest.main()
