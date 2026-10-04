"""Final lists remain visible without rewriting the prediction they arrived after."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_season as api
from tests import test_pgo_season_boundaries as fixtures


class InactiveMonitorTests(unittest.TestCase):
    def fixture(self):
        game = fixtures.SeasonBoundaryTests().game()
        return fixtures.SeasonBoundaryTests().state([game]), game

    def observation(self, game, checked='2026-09-13T16:30:00Z', complete=True):
        return dict(game_id=game['game_id'], home=game['home'], away=game['away'],
                    kickoff=game['kickoff'], lock_at=game['lock_at'], checked_at=checked,
                    summary='Official inactive lists', blocked_reason=None,
                    teams={t: dict(final_inactives_status='VERIFIED_LIST' if complete else 'UNKNOWN')
                           for t in (game['home'], game['away'])})

    def assert_context_failure_isolated(self, failure, failed_index=1, forecast_error=None):
        fixture = fixtures.SeasonBoundaryTests()
        games = [fixture.game(),
                 fixture.game('2026_01_WAS_DAL', home='DAL', away='WAS'),
                 fixture.game('2026_01_BAL_BUF', home='BUF', away='BAL')]
        state = fixture.state(games)
        failed = games[failed_index]
        previous = dict(self.observation(failed, checked='2026-09-13T16:10:00Z'),
                        source_archive='availability-v2/20260913T161000000000Z')
        state['availability_context'] = {failed['game_id']: copy.deepcopy(previous)}
        frozen = copy.deepcopy(state)
        clock = [api.utc('2026-09-13T16:30:00Z')]
        observed = {}

        def now():
            checked = clock[0].isoformat()
            clock[0] += api.timedelta(microseconds=1)
            return checked

        def resolve(inputs, roster, requested, root, checked, **kwargs):
            if failure == 'starter' and any(g['game_id'] == failed['game_id'] for g in requested):
                raise ValueError('Roster and depth chart disagree about starting quarterback')
            return ({t: dict(gsis_id=t + '-old')
                     for g in requested for t in (g['home'], g['away'])}, {})

        def capture(requested, roster, expected, path, *, purpose):
            has_failed = any(g['game_id'] == failed['game_id'] for g in requested)
            if failure == 'source' and has_failed:
                raise OSError('Official inactive source unavailable')
            checked = now()
            observations = {g['game_id']: self.observation(
                g, checked=checked,
                complete=not (failure == 'incomplete' and g['game_id'] == failed['game_id']))
                for g in requested}
            payload = dict(purpose=purpose, games=observations)
            observed.update(copy.deepcopy(observations))
            # Model the archive's refusal to overwrite existing evidence.
            path.mkdir(parents=True, exist_ok=False)
            (path / 'availability.json').write_text(json.dumps(payload), encoding='utf-8')
            return payload

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous_path = root / previous['source_archive'] / 'availability.json'
            previous_path.parent.mkdir(parents=True)
            previous_bytes = json.dumps(dict(purpose='context', games={
                failed['game_id']: {k: v for k, v in previous.items() if k != 'source_archive'}
            })).encode()
            previous_path.write_bytes(previous_bytes)
            with patch.object(api, 'now', side_effect=now), \
                 patch.object(api, 'refresh_forecast_availability', return_value=[],
                              side_effect=forecast_error), \
                 patch.object(api, 'fetch_source', return_value=(b'', {})) as fetch, \
                 patch.object(api, 'csv_rows', return_value=[]), \
                 patch('pgo_expected_starters.apply', side_effect=resolve), \
                 patch('pgo_season_availability.capture_availability', side_effect=capture):
                if forecast_error is None:
                    api.refresh_availability(state, root)
                else:
                    with self.assertRaises(type(forecast_error)) as raised:
                        api.refresh_availability(state, root)
                    self.assertIs(raised.exception, forecast_error)

            # A failure cannot rewrite forecasts, rankings, prior evidence, or its clock.
            self.assertEqual(state['availability_context'][failed['game_id']], previous)
            self.assertEqual(previous_path.read_bytes(), previous_bytes)
            for key, value in frozen.items():
                if key != 'availability_context':
                    self.assertEqual(state[key], value, key)
            for game in games:
                if game['game_id'] == failed['game_id']:
                    continue
                self.assertIn(game['game_id'], state['availability_context'],
                              'An unrelated game must still receive its context observation')
                actual = state['availability_context'][game['game_id']]
                archive = root / actual['source_archive'] / 'availability.json'
                self.assertEqual({k: v for k, v in actual.items() if k != 'source_archive'},
                                 observed[game['game_id']])
                self.assertEqual(json.loads(archive.read_text(encoding='utf-8'))['games'][game['game_id']],
                                 observed[game['game_id']])
            check = state['availability_context_check']
            self.assertEqual(check['status'], 'BLOCKED')
            self.assertIn(failed['game_id'], check['blocked_reason'])
            self.assertEqual(fetch.call_count, 2, 'Roster and depth are shared across context games')

    def test_starter_conflict_in_first_or_middle_game_does_not_stop_other_contexts(self):
        for failed_index in (0, 1):
            with self.subTest(failed_index=failed_index):
                self.assert_context_failure_isolated('starter', failed_index)

    def test_source_failure_or_incomplete_list_does_not_stop_other_contexts(self):
        for failure in ('source', 'incomplete'):
            with self.subTest(failure=failure):
                self.assert_context_failure_isolated(failure)

    def test_prelock_error_is_rethrown_after_independent_context_attempts(self):
        error = ValueError('Prelock availability remains blocked')
        self.assert_context_failure_isolated('starter', forecast_error=error)

    def test_crossing_lock_during_either_forecast_outcome_captures_context_same_run(self):
        for failed in (False, True):
            with self.subTest(failed_forecast=failed):
                state, game = self.fixture()
                before = copy.deepcopy(state['weeks'])
                clock = ['2026-09-13T15:59:59Z']
                error = ValueError('Availability capture must finish before the T-60 lock')
                def forecast(*args):
                    clock[0] = '2026-09-13T16:00:01Z'
                    if failed:
                        raise error
                    return [{'label': 'Earlier valid forecast capture'}]
                observation = self.observation(game, checked='2026-09-13T16:00:01Z')
                selected = {team: dict(gsis_id=team + '-old') for team in ('SEA', 'NE')}
                with tempfile.TemporaryDirectory() as tmp, \
                     patch.object(api, 'now', side_effect=lambda: clock[0]), \
                     patch.object(api, 'refresh_forecast_availability', side_effect=forecast), \
                     patch.object(api, 'fetch_source', return_value=(b'', {})), \
                     patch.object(api, 'csv_rows', return_value=[]), \
                     patch.object(api, 'select_roster', return_value=selected), \
                     patch('pgo_season_availability.capture_availability',
                           return_value={'games': {game['game_id']: observation}}) as capture:
                    if failed:
                        with self.assertRaises(ValueError) as raised:
                            api.refresh_availability(state, Path(tmp))
                        self.assertIs(raised.exception, error)
                    else:
                        refs = api.refresh_availability(state, Path(tmp))
                        self.assertIn({'label': 'Earlier valid forecast capture'}, refs)
                self.assertEqual(capture.call_count, 1)
                self.assertEqual(capture.call_args.kwargs['purpose'], 'context')
                self.assertEqual(state['availability_context'][game['game_id']]['checked_at'], clock[0])
                self.assertEqual(state['weeks'], before)
                self.assertEqual(state['weeks'][0]['games'][0]['pick'], game['pick'])
                self.assertEqual(state['weeks'][0]['games'][0]['confidence'], game['confidence'])

    def test_late_capture_is_separate_and_failed_attempt_retains_its_real_clock(self):
        state, game = self.fixture(); before = copy.deepcopy(state['weeks'])
        observation = self.observation(game)
        selected = {t: dict(gsis_id=t+'-old', full_name=t+' old') for t in ('SEA','NE')}
        with tempfile.TemporaryDirectory() as tmp, patch.object(api, 'now', return_value='2026-09-13T16:30:00Z'), \
             patch.object(api, 'fetch_source', return_value=(b'', {})), patch.object(api, 'csv_rows', return_value=[]), \
             patch.object(api, 'select_roster', return_value=selected), \
             patch('pgo_season_availability.capture_availability', return_value={'games': {game['game_id']: observation}}) as capture:
            api.refresh_availability(state, Path(tmp))
            self.assertEqual(capture.call_args.kwargs['purpose'], 'context')
            self.assertEqual(state['weeks'], before)
            self.assertEqual(state['availability_context'][game['game_id']]['checked_at'], observation['checked_at'])
            saved = copy.deepcopy(state['availability_context'])
            capture.side_effect = OSError('Official source unavailable')
            api.refresh_availability(state, Path(tmp))
            self.assertEqual(state['availability_context'], saved)
            self.assertEqual(state['availability_context_check']['status'], 'BLOCKED')
            self.assertEqual(state['weeks'], before)
            # HTTP errors are normally returned as an incomplete package, not raised.
            capture.side_effect = None
            capture.return_value = {'games': {game['game_id']: self.observation(game, complete=False)}}
            api.refresh_availability(state, Path(tmp))
            self.assertEqual(state['availability_context'], saved)
            self.assertEqual(state['availability_context_check']['status'], 'BLOCKED')
            self.assertIn('SEA', state['availability_context_check']['blocked_reason'])
            state.pop('availability_context')
            state['weeks'][0]['games'][0]['availability'] = self.observation(game, checked='2026-09-13T15:59:00Z')
            before = copy.deepcopy(state['weeks'])
            api.refresh_availability(state, Path(tmp))
            self.assertNotIn(game['game_id'], state.get('availability_context', {}))
            self.assertEqual(state['weeks'], before)

    def test_watch_reports_missing_stale_and_late_verified_without_relabeling_forecast(self):
        state, game = self.fixture()
        state['checked_at'] = '2026-09-13T15:00:00Z'
        self.assertEqual(api.availability_watch(state)['games'][0]['status'], 'AWAITING')
        state['checked_at'] = '2026-09-13T15:50:00Z'
        self.assertEqual(api.availability_watch(state)['games'][0]['status'], 'MISSING')
        state['availability_context'] = {game['game_id']: self.observation(game)}
        state['checked_at'] = '2026-09-13T16:31:00Z'
        self.assertEqual(api.availability_watch(state)['status'], 'READY')
        state['checked_at'] = '2026-09-13T16:45:00Z'
        self.assertEqual(api.availability_watch(state)['games'][0]['status'], 'STALE')
        state['checked_at'] = '2026-09-13T17:05:00Z'
        self.assertEqual(api.availability_watch(state)['games'][0]['status'], 'VERIFIED')
        self.assertEqual(state['weeks'][0]['games'][0], game)

    def test_context_must_match_archived_evidence_and_save_clock(self):
        state, game = self.fixture(); state['checked_at'] = '2026-09-13T16:31:00Z'
        observation = self.observation(game)
        archive = 'availability-v2/20260913T163000000000Z'
        state['availability_context'] = {game['game_id']: dict(observation, source_archive=archive)}
        payload = {'purpose': 'context', 'games': {game['game_id']: observation}}
        with patch('pgo_season_availability.load_availability', return_value=payload):
            api.check_availability_context(state, Path('fixture'), '2026-09-13T16:31:01Z')
            state['availability_context'][game['game_id']]['summary'] = 'Changed without source'
            with self.assertRaisesRegex(ValueError, 'context.*evidence'):
                api.check_availability_context(state, Path('fixture'), '2026-09-13T16:31:01Z')
            state['availability_context'][game['game_id']]['summary'] = observation['summary']
            with self.assertRaisesRegex(ValueError, 'context.*clock'):
                api.check_availability_context(state, Path('fixture'), '2026-09-13T16:29:00Z')


if __name__ == '__main__':
    unittest.main()
