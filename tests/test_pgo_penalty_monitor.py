import copy
import csv
import gzip
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import pgo_season as season


class PenaltyMonitorTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('pgo_penalty_monitor'), 'Penalty monitor is missing')
        self.api = importlib.import_module('pgo_penalty_monitor')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.package = self.root / 'package'; self.package.mkdir()
        self.state = season.bootstrap()
        self.checked = '2026-09-10T12:00:00+00:00'
        self.state['checked_at'] = self.checked
        fit = copy.deepcopy(season.initial_snapshot()['fit'])
        pp = fit['preprocessor']; position = len(pp['feature_names']) + 1
        pp['feature_names'].append('prior_penalty_yards_per_game')
        pp['medians'].append(0.); pp['scales'].append(1.)
        fit['coefficients'].insert(position, .01)
        states = {r['team']: [float(i + 20), 1.] for i, r in enumerate(self.state['rankings']['teams'])}
        self.seed = {'season': 2025, 'states': states, 'feature': 'prior_penalty_yards_per_game',
                     'half_life_games': 4, 'history_through': self.state['rankings']['history_through']}
        files = {'final-fit.json': fit, 'penalty-seed.json': self.seed,
                 'metrics.json': {'screen': {'passed': False}}}
        manifest = {'files': {}}
        for name, value in files.items():
            raw = season.canonical(value); (self.package / name).write_bytes(raw)
            manifest['files'][name] = {'sha256': season.sha(raw), 'bytes': len(raw)}
        raw = season.canonical(manifest); (self.package / 'manifest.json').write_bytes(raw)
        self.pin = season.sha(raw)

    def refresh(self, state=None, previous=None, checked=None):
        return self.api.refresh_shadow(state or self.state, previous, self.root, checked or self.checked,
                                       package_path=self.package, package_manifest_sha256=self.pin)

    def test_only_future_pairs_are_issued_without_changing_primary_state(self):
        before = copy.deepcopy(self.state)
        result = self.refresh()
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(len(result['games']), 15)
        self.assertNotIn('2026_01_NE_SEA', {g['game_id'] for g in result['games']})
        self.assertTrue(any(g['game_id'] == '2026_01_NE_SEA' for g in result['excluded']))
        main = {g['game_id']: g for w in self.state['weeks'] for g in w['games']}
        for game in result['games']:
            self.assertAlmostEqual(game['control_margin'], main[game['game_id']]['margin'])
            self.assertFalse({'confidence', 'probabilities', 'total'} & set(game))
        self.assertEqual(self.state, before)
        previous = dict(self.state, penalty_shadow=result)
        again = self.refresh(previous, previous, '2026-09-10T13:00:00+00:00')
        self.assertEqual(again['games'], result['games'])

    def test_candidate_failure_retains_pairs_and_still_grades_verified_finals(self):
        result = self.refresh(); previous = dict(self.state, penalty_shadow=result)
        state = copy.deepcopy(previous); game = result['games'][0]
        state['results'] = [dict(game_id=game['game_id'], season=2026, week=1, game_type='REG',
                                 home_team=game['home'], away_team=game['away'], kickoff=game['kickoff'],
                                 home_score=24, away_score=17, actual_margin=7,
                                 finalized_at='2026-09-11T05:00:00+00:00')]
        (self.package / 'final-fit.json').write_text('{}')
        updated = self.refresh(state, previous, '2026-09-11T06:00:00+00:00')
        self.assertEqual(updated['status'], 'BLOCKED')
        self.assertEqual(len(updated['games']), 15)
        self.assertEqual(updated['metrics']['paired_games'], 1)
        self.assertAlmostEqual(updated['metrics']['control']['mae'], abs(7 - game['control_margin']))
        self.assertAlmostEqual(updated['metrics']['control']['bias'], game['control_margin'] - 7)
        self.assertEqual(updated['metrics']['bias_definition'], 'predicted_margin_minus_actual_margin')
        for old, new in zip(result['games'], updated['games']):
            self.assertEqual({k: v for k, v in new.items() if k not in ('grade', 'result')},
                             {k: v for k, v in old.items() if k not in ('grade', 'result')})

    def test_mismatched_qb_clock_or_baseline_excludes_only_candidate(self):
        for field in ('expected_qbs', 'inputs_as_of', 'margin'):
            state = copy.deepcopy(self.state); game = state['weeks'][0]['games'][1]
            if field == 'expected_qbs': game[field][game['home']] = 'Wrong quarterback'
            elif field == 'inputs_as_of': game[field] = '2026-09-08T00:00:00+00:00'
            else: game[field] += 1
            before = copy.deepcopy(state); result = self.refresh(state)
            self.assertEqual(result['status'], 'BLOCKED', field)
            self.assertNotIn(game['game_id'], {g['game_id'] for g in result['games']}, field)
            self.assertEqual(state, before)

    def test_durable_deadline_and_forecast_immutability(self):
        shadow = self.refresh(); state = dict(self.state, penalty_shadow=shadow)
        self.api.check_durable_shadow(state, self.state, self.checked)
        first = shadow['games'][0]
        with self.assertRaisesRegex(ValueError, 'cutoff|deadline'):
            self.api.check_durable_shadow(state, self.state, first['lock_at'])
        previous = copy.deepcopy(state); state['penalty_shadow']['games'][0]['candidate_margin'] += 1
        with self.assertRaisesRegex(ValueError, 'immutable|changed'):
            self.api.check_durable_shadow(state, previous, self.checked)
        state = copy.deepcopy(previous); state['penalty_shadow']['games'][0]['grade'] = {'control': 'W', 'candidate': 'W'}
        self.api.check_durable_shadow(state, previous, '2026-09-20T12:00:00+00:00')
        state['penalty_shadow']['games'].pop()
        with self.assertRaisesRegex(ValueError, 'removed|immutable'):
            self.api.check_durable_shadow(state, previous, self.checked)

    def test_only_verified_completed_week_penalties_enter_history(self):
        game = self.state['weeks'][0]['games'][0]
        self.state['schedule'] = [game]
        rankings = self.state['rankings']
        rankings.update(completed_week=1, inputs_as_of='2026-09-16T12:00:00+00:00', history_through=game['kickoff'])
        self.state['results'] = [dict(game_id=game['game_id'], week=1, home_team=game['home'],
                                      away_team=game['away'], kickoff=game['kickoff'], finalized_at='2026-09-10T04:00:00+00:00')]
        rows = [dict(game_id=game['game_id'], season='2026', week='1', season_type='REG',
                     team=team, opponent_team=opponent, penalties='1', penalty_yards=str(yards))
                for team, opponent, yards in ((game['home'], game['away'], 10), (game['away'], game['home'], 0))]
        def capture(records):
            stream = io.StringIO(); writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader(); writer.writerows(records)
            raw = gzip.compress(stream.getvalue().encode(), mtime=0); digest = season.sha(raw)
            path = self.root / 'source-archive' / (digest + '.csv.gz'); path.parent.mkdir(exist_ok=True); path.write_bytes(raw)
            rankings['source_captures'] = [dict(url=self.api.TEAM_URL, path=path.relative_to(self.root).as_posix(),
                                                sha256=digest, bytes=len(raw), captured_at=rankings['inputs_as_of'])]
        checked = self.api._utc('2026-09-17T12:00:00+00:00')
        capture(rows)
        expected = self.api._penalty_states(self.state, self.root, checked, self.seed)
        capture(rows + [dict(rows[0], week='2', penalty_yards='not yet verified'), dict(rows[1], season='2027', penalty_yards='-999')])
        self.assertEqual(self.api._penalty_states(self.state, self.root, checked, self.seed), expected)
        decay = .5 ** .25
        old = self.seed['states'][game['home']]
        self.assertEqual(expected[game['home']], [decay * old[0] + 10, decay * old[1] + 1])
        old = self.seed['states'][game['away']]
        self.assertEqual(expected[game['away']], [decay * old[0], decay * old[1] + 1])
        rankings['source_captures'][0]['captured_at'] = '2026-09-18T12:00:00+00:00'
        with self.assertRaisesRegex(ValueError, 'clock'):
            self.api._penalty_states(self.state, self.root, checked, self.seed)


if __name__ == '__main__':
    unittest.main()
