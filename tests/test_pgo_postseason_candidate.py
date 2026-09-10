import csv
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_pgo_current_strength import paths_with_starters
from tests.test_pgo_challenger import _write_csv
from research.pgo_postseason_candidate import adapter as a
from research.pgo_postseason_candidate import train as t


def fixture(directory, *, postseason=True, change=0):
    paths = paths_with_starters(directory)
    for (name, season), path in paths.items():
        rows = list(csv.DictReader(path.read_text(encoding='utf-8').splitlines()))
        if name == 'weekly_rosters':
            for row in rows:
                row['status'] = 'ACT'
        if postseason and season == 2013:
            additions = []
            for row in rows:
                if row.get('week') == '2':
                    row = {**row, 'week': '22'}
                    if 'game_id' in row:
                        row['game_id'] = 'post'
                    if name in {'team_weekly_stats', 'player_weekly_stats'}:
                        row['passing_epa'] = str(float(row['passing_epa']) + change)
                    additions.append(row)
            rows += additions
        if name == 'schedule_results' and postseason:
            base = next(r for r in rows if r['game_id'] == 'g2')
            rows += [{**base, 'game_id': 'post', 'week': '22', 'game_type': 'SB',
                      'gameday': '2014-02-02', 'location': 'Neutral',
                      'home_score': str(float(base['home_score']) + change)},
                     {**base, 'game_id': 'pre', 'week': '0', 'game_type': 'PRE'},
                     {**base, 'game_id': 'incomplete', 'week': '23', 'game_type': 'WC',
                      'home_score': ''}]
        if rows:
            _write_csv(path, list(rows[0]), rows)
    return paths


class PostseasonTests(unittest.TestCase):
    def test_screen_uses_locked_three_conditions_without_promoting(self):
        def metric(mae):
            return dict(overall=dict(mae=mae), seasons=[dict(season=s, mae=mae) for s in range(2018, 2026)])
        result = t.screen({'candidate': metric(9.), 'corrected': metric(10.)}, {'lower': .01})
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['scientific_status'], 'EXPERIMENTAL / HOLD')
        self.assertEqual(t.screen({'candidate': metric(9.), 'corrected': metric(10.)}, {'lower': 0.})['status'], 'FAIL')

    def test_exclusive_run_directory_cannot_reopen(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'run'
            a.corrected.start_run(output, {'status': 'STARTED'})
            with self.assertRaises(FileExistsError):
                a.corrected.start_run(output, {'status': 'REPLACED'})

    def test_reg_only_input_reproduces_corrected_construction(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = fixture(Path(temp), postseason=False)
            with a.audit.construction_scope(paths, active_only=True, half_life_games=4, exposure_fix=True):
                expected, context, _ = a.audit.current.build_rows(paths, 'starter_recency')
            actual, candidate_context, _, report = a.build_rows(paths)
            self.assertEqual([asdict(r) for r in actual],
                             [asdict(r) for r in a.audit.drop_features(expected, a.audit.ROSTER_COACH)])
            self.assertEqual(candidate_context['ratings'], context['ratings'])
            self.assertEqual(report['postseason_games'], 0)

    def test_pinned_history_restores_aliases_and_matches_frozen_role_semantics(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = fixture(Path(temp))
            old_audit, old_current = a.audit.ch, a.audit.current.ch
            rows, _, _, report = a.build_rows(paths, include_postseason=False)
            self.assertEqual([r.game_id for r in rows], ['g1', 'g2', 'g3', 'g4'])
            self.assertEqual(report['postseason_games'], 0)
            self.assertIs(a.audit.ch, old_audit)
            self.assertIs(a.audit.current.ch, old_current)
            self.assertEqual(report['historical_core_sha256'], a.PINNED_CORE_SHA256)

    def test_postseason_updates_all_histories_but_is_not_a_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('base', 'post', 'changed'):
                (root / name).mkdir()
            baseline, bc, _, _ = a.build_rows(fixture(root / 'base', postseason=False))
            rows, context, _, report = a.build_rows(fixture(root / 'post'))
            changed, cc, _, _ = a.build_rows(fixture(root / 'changed', change=50))
            self.assertEqual([r.game_id for r in rows], ['g1', 'g2', 'g3', 'g4'])
            self.assertEqual([r.features for r in rows[:2]], [r.features for r in changed[:2]])
            self.assertEqual([r.features for r in rows[:2]], [r.features for r in baseline[:2]])
            self.assertNotEqual(rows[2].features['pgo_v0'], changed[2].features['pgo_v0'])
            self.assertNotEqual(rows[2].features['passing_epa_per_play_for'], changed[2].features['passing_epa_per_play_for'])
            self.assertNotEqual(rows[2].features['qb_epa_per_dropback'], changed[2].features['qb_epa_per_dropback'])
            self.assertNotEqual(context['current_strength']['qb_history'], bc['current_strength']['qb_history'])
            self.assertEqual(report['postseason_games'], 1)
            self.assertEqual(report['game_types'], {'REG': 4, 'SB': 1})
            self.assertTrue(report['postseason'][0]['neutral'])
            self.assertEqual(report['postseason'][0]['game_id'], 'post')

    def test_scoped_reader_restores_original_even_when_walk_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = fixture(Path(temp))
            original = a.ch.open_csv
            with patch.object(a.audit.current, 'build_rows', side_effect=ValueError('test failure')):
                with self.assertRaisesRegex(ValueError, 'test failure'):
                    a.build_rows(paths)
            self.assertIs(a.ch.open_csv, original)

    def test_missing_postseason_team_production_stops_construction(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = fixture(Path(temp))
            path = paths['team_weekly_stats', 2013]
            rows = [r for r in csv.DictReader(path.read_text().splitlines()) if r['week'] != '22']
            _write_csv(path, list(rows[0]), rows)
            with self.assertRaisesRegex(ValueError, 'postseason.*team|team.*postseason'):
                a.build_rows(paths)

    def test_scoring_includes_postseason_with_team_specific_denominators(self):
        rows = [dict(game_id='reg', season='2025', game_type='REG', week='1',
                     home_team='NE', away_team='SEA', home_score='20', away_score='10'),
                dict(game_id='sb', season='2025', game_type='SB', week='22',
                     home_team='NE', away_team='SEA', home_score='13', away_score='29'),
                dict(game_id='other', season='2025', game_type='REG', week='2',
                     home_team='NE', away_team='LAR', home_score='30', away_score='21')]
        rates, mean = a._score_rates(rows)
        self.assertEqual(rates['NE'], dict(pf=21., pa=20., games=3, postseason_games=1))
        self.assertEqual(rates['SEA'], dict(pf=19.5, pa=16.5, games=2, postseason_games=1))
        self.assertEqual(rates['LAR']['games'], 1)
        self.assertEqual(mean, 41.)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            a._score_rates(rows + rows[:1])
        with self.assertRaisesRegex(ValueError, 'scor'):
            a._score_rates([{**rows[0], 'home_score': 'nan'}])


if __name__ == '__main__':
    unittest.main()
