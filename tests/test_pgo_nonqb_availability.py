import copy
from datetime import datetime, timezone
import hashlib
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_nonqb_availability as availability


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/evidence/forecast-lab-2026/september-08-corrected'
NOW = '2026-09-09T18:00:00+00:00'


class NonQBAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.base = json.loads((BASE / 'snapshot.json').read_bytes())
        self.fit = json.loads((BASE / 'final-fit.json').read_bytes())
        self.evidence = {'as_of': NOW, 'teams': [
            dict(team=t['team'], source_kind='formal_game_status' if t['team'] in ('NE', 'SEA') else 'unknown',
                 report_date='2026-09-09', source_url='https://www.nfl.com/injuries/', captured_at=NOW)
            for t in self.base['teams']], 'players': []}
        self.roles = []

    def add(self, team, player_id, position, status, share):
        self.evidence['players'].append(dict(team=team, gsis_id=player_id, name=player_id,
            position=position, status=status, source_url='https://www.nfl.com/injuries/',
            source_file='nfl.html', captured_at=NOW, report_date='2026-09-09'))
        self.roles.append(dict(team=team, gsis_id=player_id, position=position,
            snap_share=share, sample_count=4 if share is not None else 0,
            last_observed='2025-12-28' if share is not None else None,
            previous_team=team, source_note='Four positive prior unit snap observations'))

    def build(self, clock=NOW):
        return availability.build_scenario(self.base, self.fit, self.evidence, self.roles, clock)

    def raw_source(self, directory):
        path = Path(directory) / 'nfl.html'
        raw = b'<p>Official captured injury report</p>'
        path.write_bytes(raw)
        self.evidence['sources'] = [dict(source_file='nfl.html', bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(), url='https://www.nfl.com/injuries/', captured_at=NOW, status=200)]

    def test_saved_model_arithmetic_and_independent_uncertain_endpoints_preserve_inputs(self):
        self.add('NE', '00-0099001', 'RB', 'OUT', .5)
        self.add('NE', '00-0099002', 'WR', 'QUESTIONABLE', .25)
        self.add('SEA', '00-0099003', 'S', 'OUT', .4)
        self.add('SEA', '00-0099004', 'DB', 'DOUBTFUL', .3)
        before = copy.deepcopy((self.base, self.fit, self.evidence, self.roles))
        result = self.build()
        teams = {t['team']: t for t in result['teams']}
        offense, defense = .23844341202177172, .11899054685052164
        self.assertAlmostEqual(teams['NE']['known_out_delta'], -.5 * offense)
        self.assertAlmostEqual(teams['NE']['all_uncertain_out_delta'], -.75 * offense)
        self.assertAlmostEqual(teams['SEA']['known_out_delta'], -.4 * defense)
        game = next(g for g in result['games'] if g['game_id'] == '2026_01_NE_SEA')
        self.assertAlmostEqual(game['known_out_margin'], game['base_margin'] - .4 * defense + .5 * offense)
        self.assertAlmostEqual(game['margin_low'], game['base_margin'] - .7 * defense + .5 * offense)
        self.assertAlmostEqual(game['margin_high'], game['base_margin'] - .4 * defense + .75 * offense)
        self.assertEqual(len(teams), 32)
        self.assertEqual(teams['BUF']['status'], 'UNKNOWN')
        self.assertIsNone(teams['BUF']['known_out_delta'])
        self.assertEqual((self.base, self.fit, self.evidence, self.roles), before)

    def test_unknown_role_partial_coverage_and_qb_never_publish_adjusted_ratings(self):
        self.add('NE', '00-0099001', 'RB', 'OUT', .5)
        self.add('NE', '00-0099002', 'WR', 'QUESTIONABLE', None)
        self.add('SEA', '00-0099003', 'QB', 'OUT', None)
        for t in self.build()['teams']:
            if t['team'] in ('NE', 'SEA'):
                self.assertEqual(t['status'], 'PARTIAL')
                self.assertEqual(t['unknown_count'], 1)
                self.assertIsNone(t['known_out_rating'])
        game = self.build()['games'][0]
        self.assertIsNone(game['known_out_margin'])
        self.evidence['teams'][0]['source_kind'] = 'practice_only'
        self.assertIsNone(self.build()['teams'][0]['known_out_rating'])

    def test_only_unpriced_players_have_unknown_subtotals(self):
        self.add('LAR', '00-0099001', 'DT', 'IR', None)
        team = next(t for t in self.build()['teams'] if t['team'] == 'LAR')
        self.assertEqual(team['status'], 'PARTIAL')
        self.assertIsNone(team['known_out_delta'])
        self.assertIsNone(team['all_uncertain_out_delta'])

    def test_invalid_identity_status_role_time_and_base_fail(self):
        self.add('NE', '00-0099001', 'RB', 'OUT', .5)
        cases = [
            ('share_nan', lambda: self.roles[0].update(snap_share=float('nan'))),
            ('share_bool', lambda: self.roles[0].update(snap_share=True)),
            ('share_zero', lambda: self.roles[0].update(snap_share=0.)),
            ('share_over', lambda: self.roles[0].update(snap_share=1.1)),
            ('duplicate', lambda: self.evidence['players'].append(dict(self.evidence['players'][0]))),
            ('role_team', lambda: self.roles[0].update(team='SEA')),
            ('status', lambda: self.evidence['players'][0].update(status='DNP')),
            ('future', lambda: self.evidence['players'][0].update(captured_at='2026-09-10T00:00:00Z')),
            ('naive', lambda: self.evidence.update(as_of='2026-09-09T18:00:00')),
            ('role_date', lambda: self.roles[0].update(last_observed='2026-08-01')),
            ('unsafe_url', lambda: self.evidence['players'][0].update(source_url='javascript:alert(1)')),
            ('base', lambda: self.base['teams'][0].update(rating=100.)),
            ('fit', lambda: self.fit['coefficients'].__setitem__(1, 100.)),
        ]
        originals = copy.deepcopy((self.base, self.fit, self.evidence, self.roles))
        for name, mutate in cases:
            with self.subTest(name=name):
                self.base, self.fit, self.evidence, self.roles = copy.deepcopy(originals)
                mutate()
                with self.assertRaises(ValueError):
                    self.build()

    def test_cutoff_is_exclusive_and_per_game(self):
        result = self.build('2026-09-09T23:20:00Z')
        self.assertEqual(result['games'][0]['status'], 'CUTOFF_PASSED')
        self.assertIsNone(result['games'][0]['known_out_margin'])
        self.assertNotEqual(result['games'][1]['status'], 'CUTOFF_PASSED')

    def test_excluded_reserve_conflict_blocks_complete_report(self):
        self.evidence['excluded'] = [dict(team='NE', name='Unmatched reserve', status='IR',
            source_file='nfl.html', reason='No exact roster identity')]
        team = next(t for t in self.build()['teams'] if t['team'] == 'NE')
        self.assertEqual(team['status'], 'PARTIAL')
        self.assertEqual(team['unknown_count'], 1)
        self.assertIsNone(team['known_out_rating'])

    def test_same_unit_slash_position_joins_broad_roster_position(self):
        self.add('NE', '00-0099001', 'T/G', 'IR', .5)
        self.roles[0]['position'] = 'OL'
        team = next(t for t in self.build()['teams'] if t['team'] == 'NE')
        self.assertEqual(team['status'], 'COMPLETE')
        self.assertAlmostEqual(team['known_out_delta'], -.5 * .23844341202177172)
        self.assertEqual(availability._unit('T/DT'), 'unknown')

    def test_role_observation_ratio_and_median_are_replayed(self):
        self.add('NE', '00-0099001', 'RB', 'OUT', .5)
        role = self.roles[0]
        role.update(sample_count=1, last_observed='2025 Week 18', observations=[
            dict(season=2025, week=18, team='NE', game_id='2025_18_MIA_NE',
                 share=.5, unit_snaps=25., team_unit_denominator=50., identity_method='pfr',
                 roster_row=dict(team='NE', season='2025', week='18', gsis_id='00-0099001',
                                 pfr_id='TestPl00', full_name='Test Player', position='RB', status='ACT'),
                 snap_row=dict(team='NE', season='2025', week='18', game_type='REG',
                               game_id='2025_18_MIA_NE', pfr_player_id='TestPl00', player='Test Player',
                               offense_snaps='25', defense_snaps='0'))])
        self.assertEqual(next(t for t in self.build()['teams'] if t['team'] == 'NE')['status'], 'COMPLETE')
        role['observations'][0]['unit_snaps'] = 20.
        with self.assertRaises(ValueError):
            self.build()

    def test_package_role_selection_and_observation_name_match_raw_roster(self):
        from research.pgo_nonqb_availability_20260909 import prepare_roles
        roster = dict(team='NE', season='2025', week='18', gsis_id='00-0099001',
                      pfr_id='TestPl00', full_name='Test Player', position='RB', status='ACT')
        snap = dict(team='NE', season='2025', week='18', game_type='REG', game_id='2025_18_MIA_NE',
                    pfr_player_id='TestPl00', player='Test Player', offense_snaps='25', defense_snaps='0')
        current = {**roster, 'season': '2026', 'week': '1'}
        witness = dict(season=2025, week=18, team='NE', game_id='2025_18_MIA_NE', share=1.,
                       unit_snaps=25., team_unit_denominator=25., identity_method='pfr', roster_row=roster, snap_row=snap)
        role = dict(team='NE', gsis_id=roster['gsis_id'], position='RB', source_hashes=availability.HISTORY_HASHES,
                    current_roster_sha256='current', current_roster_row=current, observations=[witness])
        entries, payloads = {}, {}
        for name, row, sha in [('roster', roster, availability.HISTORY_HASHES['weekly_rosters']),
                               ('snaps', snap, availability.HISTORY_HASHES['snap_counts']),
                               ('current', current, 'current')]:
            entries[name] = {'sha256': sha}
            payloads['raw/' + name] = (','.join(row) + '\n' + ','.join(row.values()) + '\n').encode()
        history = {(roster['gsis_id'], 'offense'): [dict(witness, week=17), witness]}
        evidence = {'players': [dict(team='NE', gsis_id=roster['gsis_id'], name='Test Player')]}
        with patch.object(availability, '_all_sources', return_value=entries), \
                patch.object(prepare_roles, 'role_observations', return_value=history):
            with self.assertRaisesRegex(ValueError, 'last four'):
                availability._verify_role_witnesses([role], evidence, payloads)
            history[roster['gsis_id'], 'offense'] = [witness]
            availability._verify_role_witnesses([role], evidence, payloads)
            evidence['players'][0]['name'] = 'Wrong Player Name'
            with self.assertRaisesRegex(ValueError, 'name'):
                availability._verify_role_witnesses([role], evidence, payloads)

    def test_package_roundtrip_exclusive_write_and_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'scenario'
            self.raw_source(temp)
            self.assertIsNone(availability.load_package(output))
            with patch.object(availability, '_now', return_value=datetime.fromisoformat(NOW)):
                result = availability.save_package(self.base, self.fit, self.evidence, self.roles, output, source_root=temp)
                with self.assertRaises(FileExistsError):
                    availability.save_package(self.base, self.fit, self.evidence, self.roles, output, source_root=temp)
            self.assertEqual(availability.load_package(output), result)
            (output / 'scenario.json').write_text('{}')
            with self.assertRaises(ValueError):
                availability.load_package(output)

    def test_current_depth_annotation_matches_captured_latest_rows(self):
        row = dict(team='NE', gsis_id='00-0099001', dt='2026-09-09T12:00:00Z', pos_abb='C', pos_rank='2')
        raw = gzip.compress((','.join(row) + '\n' + ','.join(row.values()) + '\n').encode())
        source = dict(source_file='depth.csv.gz', sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                      url='https://example.com/depth.csv.gz', captured_at=NOW, status=200)
        evidence = dict(depth_source=source, depth_as_of=row['dt'])
        roles = [dict(team='NE', gsis_id=row['gsis_id'], current_depth_rows=[dict(row)])]
        availability._verify_depth_rows(roles, evidence, {'raw/depth.csv.gz': raw}, {'depth.csv.gz': source})
        roles[0]['current_depth_rows'][0]['pos_rank'] = '1'
        with self.assertRaisesRegex(ValueError, 'depth'):
            availability._verify_depth_rows(roles, evidence, {'raw/depth.csv.gz': raw}, {'depth.csv.gz': source})

    def test_crossing_cutoff_during_write_does_not_leave_valid_package(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'scenario'
            self.raw_source(temp)
            clocks = [datetime.fromisoformat('2026-09-09T23:19:59+00:00'),
                      datetime.fromisoformat('2026-09-09T23:19:59+00:00'),
                      datetime.fromisoformat('2026-09-09T23:20:00+00:00')]
            with patch.object(availability, '_now', side_effect=clocks):
                with self.assertRaises(ValueError):
                    availability.save_package(self.base, self.fit, self.evidence, self.roles, output, source_root=temp)
            with self.assertRaises(ValueError):
                availability.load_package(output)


if __name__ == '__main__':
    unittest.main()
