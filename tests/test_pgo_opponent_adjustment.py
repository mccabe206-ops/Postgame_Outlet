"""Independent arithmetic and chronology checks; no model fits or real-source reads."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_challenger as ch
import pgo_opponent_adjustment as candidate
from tests.test_pgo_challenger import _synthetic_paths


def raw_context():
    rates = {
        'NE': (0.2, 0.3, 0.1, 0.2),
        'LAR': (0.6, -0.1, 0.5, -0.2),
    }
    return {
        'season': 2025,
        'ratios': {team: {name: ch._RatioState(value * 100, 100)
                          for name, value in zip(candidate.EPA_PAIRS, values)}
                   for team, values in rates.items()},
    }


def game_inputs():
    game = {'season': 2025, 'week': 2, 'home': 'NE', 'away': 'LAR'}
    home = {'gsis_ids': {}}
    away = {'gsis_ids': {}}
    rows = {
        'NE': {'attempts': 8, 'sacks_suffered': 2, 'passing_epa': 10,
               'carries': 4, 'rushing_epa': 6},
        'LAR': {'attempts': 18, 'sacks_suffered': 2, 'passing_epa': 20,
                'carries': 4, 'rushing_epa': 8},
    }
    players = {
        (2025, 2, team): [{**row, 'position': 'QB', 'player_id': team + '-QB',
                           'passing_cpoe': 1, 'passing_interceptions': 0,
                           'sack_fumbles_lost': 0}]
        for team, row in rows.items()
    }
    inputs = {'team_rows': {(2025, 2, team): row for team, row in rows.items()},
              'players': players}
    return game, home, away, inputs


class OpponentCorrectionTests(unittest.TestCase):
    def test_week_reference_is_denominator_weighted_and_cold_start_is_zero(self):
        context = raw_context()
        context['ratios']['LAR']['passing_epa_per_play_for'] = ch._RatioState(180, 300)
        original = copy.deepcopy(context['ratios'])
        corrections = candidate._freeze_week(context, 2025, 1)
        means = context['opponent_epa']['weeks'][0]['league_means']
        self.assertAlmostEqual(means['passing_epa_per_play_for'], 0.5)
        self.assertAlmostEqual(corrections['NE']['passing_epa_per_play_for'], -0.3)
        self.assertAlmostEqual(corrections['LAR']['passing_epa_per_play_for'], 0.1)
        self.assertEqual(corrections['BUF'], dict.fromkeys(candidate.EPA_PAIRS, 0.0))
        self.assertEqual(context['ratios'], original)
        self.assertEqual(context['opponent_epa']['weeks'][0]['fallback_team_features'], 30 * 4)
        empty = {'ratios': {}}
        values = candidate._freeze_week(empty, 2013, 1)
        self.assertTrue(all(v == 0 for row in values.values() for v in row.values()))
        self.assertEqual(empty['opponent_epa']['weeks'][0]['fallback_team_features'], 128)

    def test_corrections_stay_frozen_for_whole_week_and_refresh_next_week(self):
        context = raw_context()
        before = copy.deepcopy(candidate._freeze_week(context, 2025, 1))
        context['ratios']['NE']['passing_epa_per_play_for'] = ch._RatioState(9999, 100)
        self.assertEqual(candidate._freeze_week(context, 2025, 1), before)
        self.assertEqual(len(context['opponent_epa']['weeks']), 1)
        self.assertNotEqual(candidate._freeze_week(context, 2025, 2), before)
        self.assertEqual(len(context['opponent_epa']['weeks']), 2)
        with self.assertRaisesRegex(ValueError, 'increasing'):
            candidate._freeze_week(context, 2025, 1)

    def test_pass_rush_offense_defense_signs_and_adjusted_qb_population(self):
        context = raw_context()
        original = copy.deepcopy(context)
        game, home, away, inputs = game_inputs()
        input_copy = copy.deepcopy(inputs)
        candidate._update_adjusted(game, home, away, context, inputs, 0.5 ** 0.25)
        state = context['opponent_epa']
        expected = {
            'NE': (0.8, -0.8, 1.3, -1.8),
            'LAR': (1.2, -1.2, 2.2, -1.7),
        }
        for team, values in expected.items():
            for name, value in zip(candidate.EPA_PAIRS, values):
                self.assertAlmostEqual(state['ratios'][team][name].value, value)
        self.assertEqual(context['ratios'], original['ratios'])
        self.assertEqual(inputs, input_copy)
        self.assertAlmostEqual(state['qb_history']['NE-QB']['passing_epa'], 8)
        self.assertAlmostEqual(state['qb_history']['LAR-QB']['passing_epa'], 24)
        self.assertAlmostEqual(state['qb_population']['passing_epa'], 32)
        self.assertEqual(state['qb_population']['passing_epa_plays'], 30)
        self.assertAlmostEqual(state['qb_population']['rushing_epa'], 14)
        adjusted = ch._qb_features('NE-QB', 0, None, state)
        self.assertAlmostEqual(adjusted['qb_epa_per_dropback'],
                               (10 / 210) * 0.8 + (200 / 210) * (32 / 30))
        self.assertAlmostEqual(adjusted['qb_rushing_epa_per_carry'],
                               (10 / 210) * 1.3 + (200 / 210) * (14 / 8))

    def test_missing_observations_stay_missing_and_only_decay_prior_state(self):
        context = raw_context()
        game, home, away, inputs = game_inputs()
        inputs['team_rows'][(2025, 2, 'NE')]['passing_epa'] = None
        inputs['players'][(2025, 2, 'NE')][0]['passing_epa'] = None
        prior = candidate._state(context)
        prior['ratios']['NE']['passing_epa_per_play_for'] = ch._RatioState(5, 10)
        candidate._update_adjusted(game, home, away, context, inputs, 0.5)
        ratio = prior['ratios']['NE']['passing_epa_per_play_for']
        self.assertEqual((ratio.numerator, ratio.denominator), (2.5, 5))
        self.assertEqual(prior['qb_history']['NE-QB'].get('passing_epa_plays', 0), 0)
        self.assertEqual(prior['qb_history']['NE-QB']['dropbacks'], 10)

    def test_adjusted_views_preserve_raw_qb_selection_and_other_features(self):
        players = {}
        for name, epa, probability in [('starter', 0.2, 0.5), ('backup', 0.1, 1.0)]:
            players[name] = {key: 1.0 for key in ch.QB_FEATURES}
            players[name].update(position='QB', qb_epa_per_dropback=epa,
                                 qb_value=epa, probability=probability,
                                 offense_snap_share=1.0, defense_snap_share=0.0)
        base = {name: 0.0 for name in candidate.EPA_PAIRS}
        base.update(pgo_v0=3.0, unrelated=42.0)
        full, current = ch.lineup_views('NE', {'NE': players}, base)
        metadata = {'roster': players, 'starter': 'starter'}
        raw = (full, current, metadata)
        original = copy.deepcopy(raw)
        context = raw_context()
        state = candidate._state(context)
        for name, total in [('starter', -100), ('backup', 100)]:
            state['qb_history'][name].update(passing_epa=total, passing_epa_plays=100,
                                              dropbacks=100, rushing_epa=0, carries=10)
        state['qb_population'].update(passing_epa=0, passing_epa_plays=200,
                                      dropbacks=200, rushing_epa=0, carries=20)
        result = candidate._adjusted_views(raw, 'NE', context, 'team_qb_epa')
        self.assertIs(result[2], metadata)
        self.assertEqual(raw, original)
        self.assertAlmostEqual(result[0]['qb_epa_per_dropback'], -1 / 3)
        self.assertAlmostEqual(result[1]['qb_epa_per_dropback'], 0)
        self.assertAlmostEqual(result[1]['qb_current_minus_full'], 1 / 3)
        changed = set(candidate.EPA_PAIRS) | set(candidate.QB_EPA) | {'qb_current_minus_full'}
        for before, after in zip(raw[:2], result[:2]):
            self.assertEqual({k: v for k, v in before.items() if k not in changed},
                             {k: v for k, v in after.items() if k not in changed})

    def test_snapshot_uses_fixed_gsis_and_offseason_is_applied_once_without_mutation(self):
        context = raw_context()
        game, home, away, inputs = game_inputs()
        candidate._update_adjusted(game, home, away, context, inputs, 0.5)
        features = dict.fromkeys(candidate.EPA_PAIRS, 0.0)
        features.update(pgo_v0=8.0, qb_epa_per_dropback=99,
                        qb_rushing_epa_per_carry=99, qb_cpoe=7, qb_current_minus_full=0)
        snapshot = {'edition': 'pgo-active-roster-2026-09-07',
                    'teams': [{'team': 'NE', 'qb_gsis_id': 'NE-QB', 'features': features}]}
        original = copy.deepcopy(snapshot)
        first = candidate.snapshot_features(snapshot, context, 'team_qb_epa', True)
        second = candidate.snapshot_features(snapshot, context, 'team_qb_epa', True)
        self.assertEqual(first, second)
        self.assertEqual(snapshot, original)
        self.assertEqual(first['NE']['pgo_v0'], 4.0)
        self.assertEqual(first['NE']['qb_cpoe'], 7)
        expected = ch._qb_features('NE-QB', 0, None, context['opponent_epa'])
        self.assertEqual(first['NE']['qb_epa_per_dropback'], expected['qb_epa_per_dropback'])
        self.assertEqual(candidate.snapshot_features(snapshot, context, 'raw')['NE'], features)
        context['season'] = 2026
        with self.assertRaisesRegex(ValueError, '2025'):
            candidate.snapshot_features(snapshot, context, 'raw', True)


class OpponentWalkTests(unittest.TestCase):
    def test_hooks_restore_on_exception_and_nested_calls_fail_closed(self):
        before = (ch._team_views, ch._update_after_game)
        with patch.object(ch, '_walk', side_effect=ValueError('fixture failure')):
            with self.assertRaisesRegex(ValueError, 'fixture failure'):
                candidate.build_rows({}, 'team_qb_epa')
        self.assertEqual((ch._team_views, ch._update_after_game), before)
        self.assertFalse(candidate._WALK_LOCK.locked())
        with patch.object(ch, '_walk', side_effect=lambda *_: candidate.build_rows({}, 'raw')):
            with self.assertRaisesRegex(RuntimeError, 'nest'):
                candidate.build_rows({}, 'team_epa')
        self.assertEqual((ch._team_views, ch._update_after_game), before)
        self.assertFalse(candidate._WALK_LOCK.locked())
        with self.assertRaisesRegex(ValueError, 'mode'):
            candidate.build_rows({}, 'not-an-arm')

    def test_real_walk_changes_only_declared_features_and_keeps_raw_context(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = _synthetic_paths(Path(temp))
            raw, raw_context, _ = candidate.build_rows(paths, 'raw')
            for mode in ('team_epa', 'team_qb_epa'):
                adjusted, context, _ = candidate.build_rows(paths, mode)
                allowed = set(candidate.EPA_PAIRS)
                if mode == 'team_qb_epa':
                    allowed |= set(candidate.QB_EPA) | {'qb_current_minus_full'}
                differences = set()
                self.assertEqual(len(raw), len(adjusted))
                for before, after in zip(raw, adjusted):
                    self.assertEqual((before.game_id, before.actual_margin),
                                     (after.game_id, after.actual_margin))
                    # Its EPA-sign component may change despite identical QB identities.
                    derived = 'changed_or_backup_qb'
                    self.assertEqual({k: v for k, v in before.subgroup_flags.items() if k != derived},
                                     {k: v for k, v in after.subgroup_flags.items() if k != derived})
                    differences |= {k for k in before.features if before.features[k] != after.features[k]}
                self.assertTrue(differences)
                self.assertLessEqual(differences, allowed)
                excluded = {'opponent_epa', 'evaluation_metadata'}
                self.assertEqual({k: v for k, v in raw_context.items() if k not in excluded},
                                 {k: v for k, v in context.items() if k not in excluded})
            again, _, _ = candidate.build_rows(paths, 'raw')
            self.assertEqual(again, raw)

    def test_future_game_mutation_cannot_change_any_earlier_or_own_pregame_row(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            before_paths = _synthetic_paths(Path(first))
            after_paths = _synthetic_paths(Path(second), mutate_game='g4')
            for mode in candidate.MODES:
                with self.subTest(mode=mode):
                    before, before_context, _ = candidate.build_rows(before_paths, mode)
                    after, after_context, _ = candidate.build_rows(after_paths, mode)
                    self.assertEqual([r.features for r in before], [r.features for r in after])
                    self.assertNotEqual(before[-1].actual_margin, after[-1].actual_margin)
                    self.assertNotEqual(before_context['ratios'], after_context['ratios'])


if __name__ == '__main__':
    unittest.main()
