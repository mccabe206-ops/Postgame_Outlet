"""Admission of unattributed penalties must never create a player or team grade."""
import copy
from contextlib import ExitStack
import csv
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_season as season
import pgo_season_model as model
import pgo_season_rollover as rollover
import pgo_expected_starters as starters
from tests import test_pgo_season_model as fixtures
from tests import test_pgo_season_boundaries as boundaries


class StatisticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SeasonModelTests.setUpClass()
        cls.sources = json.loads((Path(__file__).parent / 'fixtures/unattributed_penalty_rows.json').read_text())

    def inputs(self, source=0):
        args = fixtures.SeasonModelTests().inputs()
        pool = copy.deepcopy(self.sources[source]['row'])
        for row in args['team_rows']:
            row.update(season_type='REG', penalties=1, penalty_yards=5)
        for row in args['qb_rows']:
            row.update(season_type='REG', penalties=1, penalty_yards=5)
            team = next(t for t in args['team_rows'] if t['team'] == row['team'])
            row.update(game_id=team['game_id'], opponent_team=team['opponent_team'])
        # Deliberately place every unassigned penalty outside the displayed SEA
        # label; the pooled record cannot be interpreted as Seattle production.
        other = next(r for r in args['team_rows'] if r['team'] == 'NE')
        other['penalties'] += int(pool['penalties'])
        other['penalty_yards'] += int(pool['penalty_yards'])
        args['qb_rows'].append(pool)
        return args

    def verify(self, args, receipts=None):
        games = [dict(g, provider_scores={k: str(g[k]) for k in ('home_score', 'away_score')})
                 for g in args['completed_games']]
        rankings = dict(inputs_as_of=args['inputs_as_of'],
                        source_captures=[dict(url=season.URLS[k]) for k in ('team', 'player')])
        if receipts is not None:
            rankings['unattributed_penalties'] = receipts
        state = dict(schedule=games, results=args['completed_games'], rankings=rankings)
        with patch.object(rollover, 'source_bytes', return_value=b'fixture'), \
                patch.object(season, 'csv_rows', side_effect=[args['team_rows'], args['qb_rows']]):
            rollover.verify_statistics(state, '.', 1)

    def test_exact_source_rows_admit_without_affecting_predictions_or_player_history(self):
        for source in range(len(self.sources)):
            args = self.inputs(source); before = copy.deepcopy(args)
            reference = model.build_week(**{**args, 'qb_rows': args['qb_rows'][:-1]})
            with self.subTest(source=source):
                try:
                    result = model.build_week(**args)
                except ValueError as error:
                    self.fail('Reconciled penalty-only aggregate was rejected: ' + str(error))
                receipts = result.pop('unattributed_penalties')
                self.assertEqual(result, reference)
                self.assertEqual(args, before)
                self.assertEqual(len(receipts), 1)
                receipt = receipts[0]
                self.assertEqual(receipt['unattributed_totals']['penalties'], int(args['qb_rows'][-1]['penalties']))
                residuals = {r['team']: r for r in receipt['team_residuals']}
                self.assertEqual(residuals['SEA']['penalties'], 0)
                self.assertEqual(residuals['NE']['penalties'], receipt['unattributed_totals']['penalties'])
                self.assertEqual(receipt['source_row_sha256'], model._sha(model._bytes(args['qb_rows'][-1])))
                self.verify(args, receipts)
                with self.assertRaisesRegex(ValueError, 'receipt'):
                    self.verify(args)
                altered = copy.deepcopy(receipts); altered[0]['unattributed_totals']['penalties'] += 1
                with self.assertRaisesRegex(ValueError, 'receipt'):
                    self.verify(args, altered)

    def test_non_penalty_production_partial_identity_and_malformed_fields_are_rejected(self):
        for field, value in [('attempts', '1'), ('def_sacks', '0.5'), ('targets', '1'),
                             ('attempts', ''), ('player_name', 'Unknown'), ('position', 'LB'),
                             ('player_id', ' '), ('headshot_url', 'unexpected'),
                             ('penalties', '-1'), ('penalty_yards', 'nan'), ('penalties', '1.5'),
                             ('game_id', 'wrong'), ('team', 'DEN'), ('season_type', 'POST'),
                             ('new_production_field', '1')]:
            args = self.inputs(); args['qb_rows'][-1][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                model.partition_player_rows(args['team_rows'], args['qb_rows'], args['completed_games'])
        args = self.inputs(); del args['qb_rows'][-1]['attempts']
        with self.assertRaises(ValueError):
            model.partition_player_rows(args['team_rows'], args['qb_rows'], args['completed_games'])

    def test_missing_extra_duplicate_and_unreconciled_records_fail(self):
        for change in ('missing_team', 'extra_team', 'missing_players', 'duplicate_team',
                       'duplicate_player', 'duplicate_pool', 'changed_pool', 'wrong_player_team'):
            args = self.inputs()
            if change == 'missing_team': args['team_rows'].pop()
            if change == 'extra_team': args['completed_games'].pop()
            if change == 'missing_players': args['qb_rows'].pop(0)
            if change == 'duplicate_team': args['team_rows'].append(copy.deepcopy(args['team_rows'][0]))
            if change == 'duplicate_player': args['qb_rows'].insert(0, copy.deepcopy(args['qb_rows'][0]))
            if change == 'duplicate_pool': args['qb_rows'].append(copy.deepcopy(args['qb_rows'][-1]))
            if change == 'changed_pool': args['qb_rows'][-1]['penalty_yards'] = '118'
            if change == 'wrong_player_team': args['qb_rows'][0]['team'] = args['qb_rows'][1]['team']
            with self.subTest(change=change), self.assertRaises(ValueError):
                model.partition_player_rows(args['team_rows'], args['qb_rows'], args['completed_games'])

    def test_pool_requires_complete_supported_production_columns(self):
        for field in ('def_sacks', 'passing_yards', 'rushing_yards', 'fumbles_total'):
            args = self.inputs(); del args['qb_rows'][-1][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                model.partition_player_rows(args['team_rows'], args['qb_rows'], args['completed_games'])

    def test_future_cohorts_cannot_change_an_admitted_week(self):
        args = self.inputs()
        expected = model.partition_player_rows(args['team_rows'], args['qb_rows'], args['completed_games'])
        args['team_rows'].append({**args['team_rows'][0], 'week': 2, 'penalties': 9999})
        args['qb_rows'].append({**args['qb_rows'][-1], 'week': 2, 'attempts': 9999})
        actual = model.partition_player_rows(args['team_rows'], args['qb_rows'], args['completed_games'])
        self.assertEqual(actual[1], expected[1])
        self.assertEqual([r for r in actual[0] if int(r['week']) == 1], expected[0])

    def test_identity_only_sources_keep_legacy_output_and_verification(self):
        args = fixtures.SeasonModelTests().inputs()
        self.assertNotIn('unattributed_penalties', model.build_week(**args))
        self.verify(args)

    def rehearsal(self, root, failure=None):
        """Mock only captures and unrelated collectors, retaining the real lifecycle."""
        args = self.inputs(1)
        def packed(rows):
            stream = io.StringIO(newline='')
            writer = csv.DictWriter(stream, fieldnames=sorted({k for row in rows for k in row}))
            writer.writeheader(); writer.writerows(rows)
            return gzip.compress(stream.getvalue().encode(), mtime=0)
        schedule_rows = season.csv_rows((model.SOURCE_DIR / 'schedule.csv.gz').read_bytes())
        for row in schedule_rows:
            if row['week'] == '1' and row['game_type'] == 'REG':
                row.update(home_score='24', away_score='21')
        schedule_raw = packed(schedule_rows)
        schedule = season.parse_schedule(schedule_raw)
        old_games = [g for g in schedule if g['week'] == 1]
        builder = boundaries.SeasonBoundaryTests()
        issued = [builder.game(g['game_id'], g['home'], g['away'], g['kickoff']) for g in old_games]
        before = builder.state(issued)
        before['checked_at'] = (min(season.utc(g['kickoff']) for g in old_games) - season.timedelta(hours=2)).isoformat()
        before['weeks'][0]['games'] = season.allocate_confidence(issued, before['calibration'])
        with patch.object(season, 'now', return_value=before['checked_at']):
            original_dir = season.save_state(before, root)
        original_bytes = {p: p.read_bytes() for p in original_dir.iterdir()}
        stamp = args['generated_at']
        events = []
        for game in old_games:
            events.append(dict(id=game['espn_id'], date=game['kickoff'],
                               season=dict(year=2026, type=2), week=dict(number=1),
                               competitions=[dict(id=game['espn_id'],
                                   status=dict(type=dict(completed=True, state='post', name='STATUS_FINAL')),
                                   competitors=[dict(homeAway=side, team=dict(abbreviation=game[side]), score=score)
                                                for side, score in (('home', '24'), ('away', '21'))])]))
        if failure == 'missing_final':
            events[-1]['competitions'][0]['status']['type'] = dict(completed=False, state='in', name='STATUS_IN_PROGRESS')
        if failure == 'missing_statistics':
            args['team_rows'].pop()
        if failure == 'conflicting_statistics':
            args['qb_rows'][-1]['penalty_yards'] = '127'
        depth = [dict(team=team, gsis_id=row['gsis_id'], pos_abb='QB', pos_rank='1', dt=stamp)
                 for team, row in args['selected_roster'].items()]
        captures = {season.URLS['schedule']: schedule_raw, season.URLS['team']: packed(args['team_rows']),
                    season.URLS['player']: packed(args['qb_rows']),
                    season.URLS['roster']: packed(list(args['selected_roster'].values())),
                    season.URLS['depth']: packed(depth),
                    season.SCOREBOARD.format(season=2026, week=1): season.canonical(
                        dict(season=dict(year=2026, type=2), week=dict(number=1), events=events))}
        def fetch(url, root):
            raw = captures[url]
            extension = '.csv.gz' if url in {season.URLS[k] for k in ('schedule', 'team', 'player', 'roster', 'depth')} else '.json'
            path = 'source-archive/' + season.sha(raw) + extension
            (root / 'source-archive').mkdir(exist_ok=True)
            target = root / path
            if not target.exists(): target.write_bytes(raw)
            return raw, dict(url=url, path=path, sha256=season.sha(raw), bytes=len(raw), captured_at=stamp)
        with ExitStack() as stack:
            stack.enter_context(patch.object(starters, 'CONFIG', root / 'starter-config.json'))
            stack.enter_context(patch.object(season, 'now', return_value=stamp))
            stack.enter_context(patch.object(season, 'fetch_source', side_effect=fetch))
            stack.enter_context(patch.object(season, 'legacy_models', return_value=[]))
            stack.enter_context(patch.object(season, 'refresh_availability', return_value=[]))
            for name in ('refresh_replacement_sources', 'refresh_offensive_identity_source', 'refresh_experiments'):
                stack.enter_context(patch.object(season, name))
            stack.enter_context(patch.object(model.ch, 'fit_huber_ridge', side_effect=AssertionError('No fitting')))
            if failure == 'durable_lock':
                save = season.save_state
                deadline = min(season.utc(g['lock_at']) for g in schedule if g['week'] == 2).isoformat()
                def late_save(state, root):
                    with patch.object(season, 'now', return_value=deadline):
                        return save(state, root)
                stack.enter_context(patch.object(season, 'save_state', side_effect=late_save))
                with self.assertRaisesRegex(ValueError, 'durable-write lock'):
                    season.refresh(root)
                self.assertEqual(season.load_current(root), before)
                self.assertEqual({p: p.read_bytes() for p in original_bytes}, original_bytes)
                return
            updated = season.refresh(root)
            self.assertEqual(season.load_current(root), updated)
            self.assertEqual({p: p.read_bytes() for p in original_bytes}, original_bytes)
            self.assertEqual(rollover.check_preserved(before, updated), 16)
            observation = rollover.observe(root)
        return before, updated, observation

    def test_complete_refresh_save_load_and_rollover_with_reconciled_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            before, state, observation = self.rehearsal(Path(tmp))
            self.assertEqual((state['status'], state['current_week'], observation['status']), ('READY', 2, 'VERIFIED'))
            self.assertEqual((len(state['results']), len(state['rankings']['teams'])), (16, 32))
            self.assertEqual(observation['checks']['next_fixtures'], 16)
            self.assertEqual(len(state['rankings']['unattributed_penalties']), 1)
            self.assertEqual(sum(g['confidence']['points'] for g in state['weeks'][0]['games']), 136)
            self.assertEqual(sum(g['confidence']['earned_points'] for g in state['weeks'][0]['games']), 136)
            games = state['weeks'][1]['games']
            self.assertEqual(sum(g['confidence']['points'] for g in games), 136)
            ratings = {r['team']: r['rating'] for r in state['rankings']['teams']}
            for game in games:
                self.assertAlmostEqual(game['home_points'] - game['away_points'], game['margin'])
                self.assertAlmostEqual(game['home_points'] + game['away_points'], game['total'])
                self.assertAlmostEqual(ratings[game['home']] - ratings[game['away']], game['explanation']['neutral_margin'])
                self.assertAlmostEqual(game['confidence']['expected_points'],
                                       game['confidence']['points'] * game['confidence']['win_probability'])
            from pgo_season_view import render_season
            self.assertIn('Week 2', render_season(state))

    def test_incomplete_or_conflicting_inputs_wait_and_late_save_preserves_pointer(self):
        for failure in ('missing_final', 'missing_statistics', 'conflicting_statistics', 'durable_lock'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                result = self.rehearsal(Path(tmp), failure)
                if result is None:
                    continue
                before, state, observation = result
                self.assertEqual(state['current_week'], 1)
                self.assertEqual(state['rankings'], before['rankings'])
                self.assertEqual(observation['status'], 'WAITING')
                self.assertEqual(len(state['results']), 15 if failure == 'missing_final' else 16)
                if failure != 'missing_final':
                    self.assertEqual(state['status'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
