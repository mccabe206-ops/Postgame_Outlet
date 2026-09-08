import copy
import csv
import gzip
import hashlib
import io
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import numpy
except ImportError:
    raise unittest.SkipTest('numpy not installed - skipping current-strength research tests')
import pgo_challenger as ch
import pgo_current_strength as strength
from tests.test_pgo_challenger import _synthetic_paths, _write_csv


def paths_with_starters(directory):
    paths = _synthetic_paths(directory)
    schedule = paths['schedule_results', None]
    with schedule.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    ids = {'g1': ('gsis-lv-old', 'gsis-lac-qb'),
           'g2': ('gsis-lac-qb', 'gsis-lar-qb'),
           'g3': ('gsis-lar-qb', 'gsis-lac-qb'),
           'g4': ('gsis-lac-qb', 'gsis-lac-new')}
    for row in rows:
        row['away_qb_id'], row['home_qb_id'] = ids[row['game_id']]
    _write_csv(schedule, list(rows[0]), rows)
    return paths


def views_fixture():
    players = {}
    for name, epa, probability in [('expected', 0.1, 0.5), ('best', 0.9, 1.0)]:
        players[name] = dict.fromkeys(ch.QB_FEATURES, 1.0)
        players[name].update(gsis_id='gsis-' + name, position='QB', probability=probability,
                             qb_epa_per_dropback=epa, qb_value=epa,
                             offense_snap_share=1.0, defense_snap_share=0.0)
    full, current = ch.lineup_views('NE', {'NE': players}, {'pgo_v0': 2.0})
    return full, current, {'roster': players, 'starter': 'best'}


class CurrentStrengthTests(unittest.TestCase):
    def test_calendar_decay_halves_every_total_once_and_rejects_backwards_time(self):
        context = {}
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        state = strength._advance_qb_clock(context, start)
        state['qb_history']['a'].update(passing_epa=100, passing_epa_plays=200,
                                         dropbacks=200, cpoe_sum=300, carries=20)
        state['qb_population'].update(passing_epa=100, passing_epa_plays=200,
                                      dropbacks=200, cpoe_sum=300, carries=20)
        then = start + timedelta(days=365.25)
        strength._advance_qb_clock(context, then)
        expected = dict(passing_epa=50, passing_epa_plays=100,
                        dropbacks=100, cpoe_sum=150, carries=10)
        self.assertEqual(dict(state['qb_history']['a']), expected)
        self.assertEqual(dict(state['qb_population']), expected)
        strength._advance_qb_clock(context, then)
        self.assertEqual(dict(state['qb_history']['a']), expected)
        with self.assertRaisesRegex(ValueError, 'backwards'):
            strength._advance_qb_clock(context, start)

    def test_recorded_id_beats_best_epa_without_changing_availability(self):
        raw = views_fixture()
        saved = copy.deepcopy(raw)
        full, current, metadata = strength._selected_views(raw, 'gsis-expected', {}, 'starter', team='NE')
        self.assertEqual(metadata['starter'], 'expected')
        self.assertEqual(full['qb_epa_per_dropback'], 0.1)
        self.assertAlmostEqual(current['qb_epa_per_dropback'], 0.5)
        self.assertEqual(current['offense_availability'], raw[1]['offense_availability'])
        self.assertEqual(raw, saved)

    def test_missing_and_ambiguous_starters_do_not_fall_back(self):
        for starter in ('', 'unknown'):
            full, current, metadata = strength._selected_views(views_fixture(), starter, {}, 'starter', team='NE')
            self.assertIsNone(metadata['starter'])
            for view in (full, current):
                self.assertTrue(all(view[k] is None for k in ch.QB_FEATURES))
                self.assertIsNone(view['qb_current_minus_full'])
                self.assertEqual(view['pgo_v0'], 2.0)
        raw = views_fixture()
        raw[2]['roster']['duplicate'] = dict(raw[2]['roster']['expected'])
        full, _, metadata = strength._selected_views(raw, 'gsis-expected', {}, 'starter', team='NE')
        self.assertIsNone(metadata['starter'])
        self.assertIsNone(full['qb_epa_per_dropback'])

    def test_recency_uses_effective_sample_but_keeps_experience_and_draft(self):
        raw = views_fixture()
        context = {}
        state = strength._advance_qb_clock(context, datetime(2025, 1, 1, tzinfo=timezone.utc))
        for name, total in [('expected', 20), ('best', -20)]:
            state['qb_history'][name].update(passing_epa=total, passing_epa_plays=100,
                                              dropbacks=100, rushing_epa=10, carries=20)
        state['qb_population'].update(passing_epa=0, passing_epa_plays=200,
                                      dropbacks=200, rushing_epa=20, carries=40)
        full, _, metadata = strength._selected_views(raw, 'gsis-expected', context, 'starter_recency', team='NE')
        self.assertEqual(metadata['starter'], 'expected')
        self.assertAlmostEqual(full['qb_epa_per_dropback'], (100 / 300) * 0.2)
        self.assertEqual(full['qb_log_dropbacks'], math.log1p(100))
        self.assertEqual(full['qb_experience_prior'], 1)
        self.assertEqual(full['qb_draft_prior'], 1)

    def test_real_walk_raw_reproduces_and_all_starter_games_are_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = paths_with_starters(Path(temp))
            original, _, _ = ch._walk(paths, 4)
            raw, _, _ = strength.build_rows(paths, 'raw')
            self.assertEqual(raw, original)
            for mode in ('starter', 'starter_recency'):
                rows, context, _ = strength.build_rows(paths, mode)
                self.assertEqual([(r.game_id, r.actual_margin) for r in rows],
                                 [(r.game_id, r.actual_margin) for r in raw])
                self.assertEqual(context['current_strength']['coverage']['matched'], 8)
                self.assertEqual(context['current_strength']['coverage']['team_games'], 8)
                self.assertEqual(len(context['current_strength']['coverage']['unavailable']), 0)

    def test_future_result_changes_do_not_change_earlier_or_own_pregame_features(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = root / 'before', root / 'after'
            a.mkdir(); b.mkdir()
            before_paths = paths_with_starters(a)
            after_paths = paths_with_starters(b)
            stat_path = after_paths['player_weekly_stats', 2014]
            with stat_path.open(newline='', encoding='utf-8') as handle:
                stats = list(csv.DictReader(handle))
            for row in stats:
                if row['week'] == '2':
                    row['passing_epa'] = '9999'
            _write_csv(stat_path, list(stats[0]), stats)
            for mode in ('starter', 'starter_recency'):
                before, _, _ = strength.build_rows(before_paths, mode)
                after, _, _ = strength.build_rows(after_paths, mode)
                self.assertEqual([r.features for r in before], [r.features for r in after])

    def test_hook_receives_real_metadata_and_restores_functions_on_failure(self):
        originals = ch._team_views, ch._update_after_game
        calls = []
        def hook(full, current, metadata, **kwargs):
            self.assertIn(metadata['starter'], metadata['roster'])
            self.assertIn('inputs', kwargs)
            full['profile'] = current['profile'] = 3.0
            metadata['roster_strength'] = {'profile': {'observed_role_weight_coverage': 0.75}}
            calls.append((kwargs['season'], kwargs['week'], kwargs['team']))
        with tempfile.TemporaryDirectory() as temp:
            paths = paths_with_starters(Path(temp))
            rows, context, _ = strength.build_rows(paths, 'starter', hook)
            self.assertEqual(len(calls), 8)
            self.assertTrue(all(r.features['profile'] == 0 for r in rows))
            receipts = context['current_strength']['roster_coverage']
            self.assertEqual(len(receipts), 8)
            self.assertEqual(receipts[0]['features']['profile']['observed_role_weight_coverage'], 0.75)
            def fail(*args, **kwargs):
                raise RuntimeError('hook failed')
            with self.assertRaisesRegex(RuntimeError, 'hook failed'):
                strength.build_rows(paths, 'starter', fail)
        self.assertEqual((ch._team_views, ch._update_after_game), originals)
        self.assertFalse(strength._WALK_LOCK.locked())

    def test_missing_historical_starter_keeps_game_and_reports_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = paths_with_starters(Path(temp))
            source = paths['schedule_results', None]
            with source.open(newline='', encoding='utf-8') as handle:
                games = list(csv.DictReader(handle))
            games[0]['home_qb_id'] = 'not-on-roster'
            _write_csv(source, list(games[0]), games)
            rows, context, _ = strength.build_rows(paths, 'starter_recency')
            self.assertEqual(len(rows), 4)
            self.assertIsNone(rows[0].features['qb_epa_per_dropback'])
            coverage = context['current_strength']['coverage']
            self.assertEqual(coverage['matched'], 7)
            self.assertEqual(coverage['missing_roster'], 1)
            self.assertEqual(coverage['unavailable'][0]['game_id'], 'g1')
            self.assertEqual(coverage['unavailable'][0]['gsis_id'], 'not-on-roster')

    def test_snapshot_metadata_uses_verified_act_roster_and_historical_role_weights(self):
        rows = [dict(team='NE', season='2026', week='1', status=status,
                     gsis_id=identity, position=position, years_exp='3')
                for identity, position, status in [('q', 'QB', 'ACT'), ('w', 'WR', 'ACT'),
                                                   ('inactive', 'WR', 'RES')]]
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        raw = gzip.compress(stream.getvalue().encode())
        snapshot = {'sources': [{'name': 'roster.csv.gz', 'bytes': len(raw),
                                 'sha256': hashlib.sha256(raw).hexdigest()}],
                    'generated_at': '2026-09-07T22:00:00+00:00',
                    'teams': [{'team': 'NE', 'qb_gsis_id': 'q'}]}
        context = {'snap_history': {'w': {'offense': [0.2, 0.4, 0.6, 0.8], 'defense': []}},
                   'qb_history': {}, 'qb_population': {}}
        strength._state(context)['inputs'] = {'injuries': {}}
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'roster.csv.gz'
            source.write_bytes(raw)
            metadata = strength._snapshot_metadata(snapshot, context, temp)['NE']
            self.assertEqual(set(metadata['roster']), {'q', 'w'})
            self.assertEqual(metadata['starter'], 'q')
            self.assertEqual(metadata['roster']['w']['offense_snap_share'], 0.5)
            self.assertIsNone(metadata['roster']['q']['offense_snap_share'])
            source.write_bytes(raw + b'changed')
            with self.assertRaisesRegex(ValueError, 'hash/size'):
                strength._snapshot_metadata(snapshot, context, temp)

    def test_snapshot_decays_to_asof_and_offseason_does_not_compound(self):
        instant = datetime(2025, 1, 1, tzinfo=timezone.utc)
        context = {'season': 2025}
        state = strength._advance_qb_clock(context, instant)
        state['inputs'] = {}
        state['qb_history']['expected'].update(passing_epa=40, passing_epa_plays=200,
                                               dropbacks=200)
        state['qb_population'].update(passing_epa=0, passing_epa_plays=400, dropbacks=400)
        snapshot = {'edition': 'pgo-active-roster-2026-09-07',
                    'generated_at': (instant + timedelta(days=365.25)).isoformat(),
                    'teams': [{'team': 'NE', 'qb_gsis_id': 'gsis-expected',
                               'features': {**views_fixture()[0], 'pgo_v0': 8.0}}]}
        saved = copy.deepcopy(snapshot)
        history = copy.deepcopy(state['qb_history'])
        metadata = {'NE': views_fixture()[2]}
        with patch.object(strength, '_snapshot_metadata', return_value=metadata):
            first = strength.snapshot_features(snapshot, context, 'starter_recency')
            second = strength.snapshot_features(snapshot, context, 'starter_recency')
        self.assertEqual(first, second)
        self.assertEqual(first['NE']['pgo_v0'], 4.0)
        self.assertAlmostEqual(first['NE']['qb_epa_per_dropback'], (100 / 300) * 0.2)
        self.assertEqual(first['NE']['qb_log_dropbacks'], math.log1p(100))
        self.assertEqual(snapshot, saved)
        self.assertEqual(state['qb_history'], history)
        self.assertEqual(strength.snapshot_features(snapshot, context, 'raw', False)['NE'],
                         snapshot['teams'][0]['features'])

        def hook(full, current, metadata, **kwargs):
            full['quality'] = current['quality'] = 7.0
            metadata['roster_strength'] = {'quality': {'observed_role_weight_coverage': 0.4}}
        with patch.object(strength, '_snapshot_metadata', return_value=metadata):
            with_hook = strength.snapshot_features(snapshot, context, 'starter_recency', roster_hook=hook)
        self.assertEqual(with_hook['NE']['quality'], 7.0)
        self.assertEqual(state['snapshot_roster_coverage'][0]['features']['quality']
                         ['observed_role_weight_coverage'], 0.4)


if __name__ == '__main__':
    unittest.main()
