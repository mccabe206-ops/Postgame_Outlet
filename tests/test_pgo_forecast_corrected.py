import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

import pgo_challenger as ch
import pgo_forecast_corrected as corrected


class CorrectedConstructionTests(unittest.TestCase):
    def test_current_features_use_fresh_metadata_and_decay_without_mutation(self):
        totals = {'dropbacks': 400., 'passing_epa': 80., 'passing_epa_plays': 400.,
                  'cpoe_sum': 800., 'cpoe_plays': 400., 'sack_free_dropbacks': 380.,
                  'sack_dropbacks': 400., 'secure_dropbacks': 390., 'security_dropbacks': 400.,
                  'rushing_epa': 20., 'carries': 100.}
        context = {'season': 2025, 'ratings': {'NE': 8.},
                   'ratios': {'NE': {name: .1 for name in ch.PERFORMANCE_FEATURES}},
                   'inputs': {'colliding_gsis': []},
                   'current_strength': {'last_kickoff': '2025-09-08T00:00:00+00:00',
                                        'qb_history': {'id': totals}, 'qb_population': dict(totals)}}
        before = copy.deepcopy(context)
        roster = {'NE': {'gsis_id': 'id', 'years_exp': '2', 'draft_number': '3'}}
        result = corrected.current_features(context, roster, '2026-09-08T06:00:00+00:00')['NE']
        self.assertEqual(result['pgo_v0'], 4.)
        self.assertAlmostEqual(result['qb_log_dropbacks'], __import__('math').log1p(200.))
        self.assertAlmostEqual(result['qb_experience_prior'], __import__('math').log1p(2))
        self.assertAlmostEqual(result['qb_draft_prior'], 1 / 3 ** .5)
        self.assertEqual(result['offense_availability'], 0.)
        self.assertEqual(set(result), set(ch.PERFORMANCE_FEATURES) | set(ch.QB_FEATURES) |
                         {'pgo_v0', 'offense_availability', 'defense_availability', 'qb_current_minus_full'})
        self.assertEqual(context, before)

    def test_unknown_coverage_is_explicit_and_unavailable_qb_blocks(self):
        self.assertEqual(corrected.team_coverage({'source_kind': 'no_formal_report'}, 'id')['status'], 'UNKNOWN')
        value = corrected.team_coverage({'source_kind': 'formal_injury_report',
                                        'known_unavailable': [{'gsis_id': 'id'}]}, 'id')
        self.assertEqual(value['status'], 'BLOCKED_EXPECTED_QB_UNAVAILABLE')

    def test_nonfinite_fitted_values_fail(self):
        fit = {'preprocessor': {'feature_names': ['x'], 'medians': [0.], 'scales': [1.],
                               'missing_features': []}, 'coefficients': [0., float('nan')]}
        with self.assertRaisesRegex(ValueError, 'finite'):
            corrected.score({'x': 1.}, fit)

    def test_missing_fractional_and_nonfinite_qb_experience_fail(self):
        context = {'season': 2025, 'inputs': {'colliding_gsis': []}, 'current_strength': {
            'last_kickoff': '2026-01-05T00:00:00+00:00', 'qb_history': {}, 'qb_population': {}}}
        for value in (None, '', '1.5', 'nan', 'inf', '-1'):
            with self.subTest(years_exp=value), self.assertRaisesRegex(ValueError, 'years_exp'):
                corrected.current_features(context, {'NE': {'gsis_id': 'qb', 'years_exp': value}},
                                           '2026-09-08T12:00:00+00:00')


class CorrectedPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.incumbent = corrected.incumbent.load_snapshot(corrected.INCUMBENT_DIR)

    def setUp(self):
        loader = mock.patch.object(corrected.incumbent, 'load_snapshot', return_value=copy.deepcopy(self.incumbent))
        loader.start(); self.addCleanup(loader.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.capture, self.run, self.output = (self.root / n for n in ('capture', 'run', 'output'))
        self.capture.mkdir(); self.run.mkdir()
        teams = sorted(corrected.pgo_model.CURRENT_TEAMS)
        roster = [dict(team=t, gsis_id='test-' + t, full_name=t + ' QB', position='QB',
                       status='ACT', season='2026', week='1', years_exp='2', draft_number='3') for t in teams]
        depth = [dict(team=t, gsis_id='test-' + t, pos_abb='QB', pos_rank='1',
                      dt='2026-09-08T00:00:00+00:00') for t in teams]
        for name, values in [('roster.csv.gz', roster), ('depth.csv.gz', depth)]:
            (self.capture / name).write_bytes(gzip.compress(corrected._csv(values, list(values[0]))))
        (self.capture / 'schedule.csv.gz').write_bytes((corrected.INCUMBENT_DIR / 'schedule.csv.gz').read_bytes())
        (self.capture / 'nfl-injuries.html').write_bytes(b'<p>No formal reports</p>')
        capture = {'sources': [dict(file=p.name, url='https://example.com/' + p.name,
                                    captured_at='2026-09-08T01:00:00+00:00', status=200,
                                    bytes=p.stat().st_size, sha256=corrected._hash(p.read_bytes()))
                               for p in sorted(self.capture.iterdir())]}
        (self.capture / 'capture.json').write_bytes(corrected._json(capture))
        injury = next(s for s in capture['sources'] if s['file'] == 'nfl-injuries.html')
        qualification = {'status': 'PASS', 'failed_checks': [], 'charter_sha256': corrected.CHARTER_SHA256,
                         'capture_manifest_sha256': corrected._hash((self.capture / 'capture.json').read_bytes()),
                         'chosen_qbs': [dict(team=t, gsis_id='test-' + t) for t in teams],
                         'raw_injury_sources': [injury],
                         'coverage': {t: {'source_kind': 'no_formal_report', 'source_file': injury['file'],
                                          'source_url': injury['url'], 'captured_at': injury['captured_at']}
                                      for t in teams}}
        self.qualification = self.capture / 'qualification.json'
        self.qualification.write_bytes(corrected._json(qualification))
        totals = dict(dropbacks=100., passing_epa=10., passing_epa_plays=100., cpoe_sum=200.,
                      cpoe_plays=100., sack_free_dropbacks=95., sack_dropbacks=100., secure_dropbacks=99.,
                      security_dropbacks=100., rushing_epa=5., carries=20.)
        context = {'season': 2025, 'ratings': {t: i / 10 for i, t in enumerate(teams)},
                   'ratios': {t: {k: .1 for k in ch.PERFORMANCE_FEATURES} for t in teams},
                   'inputs': {'colliding_gsis': []}, 'current_strength': {
                       'last_kickoff': '2026-01-05T01:20:00+00:00',
                       'qb_history': {'test-' + t: dict(totals) for t in teams}, 'qb_population': dict(totals)}}
        context_raw = corrected._json(context)
        names = sorted(set(ch.PERFORMANCE_FEATURES) | set(ch.QB_FEATURES) |
                       {'pgo_v0', 'offense_availability', 'defense_availability', 'qb_current_minus_full',
                        'home_field', 'rest_difference'})
        coefficients = [0.] + [2.5 if k == 'home_field' else 1. if k == 'pgo_v0' else 0. for k in names]
        fit = {'preprocessor': {'feature_names': names, 'missing_features': [],
                               'medians': [0.] * len(names), 'scales': [1.] * len(names)},
               'coefficients': coefficients, 'charter_sha256': corrected.CHARTER_SHA256,
               'historical_context_sha256': corrected._hash(context_raw)}
        for name, raw in [('historical-context.json', context_raw), ('final-fit.json', corrected._json(fit))]:
            (self.run / name).write_bytes(raw)
        (self.run / 'run-receipt.json').write_bytes(corrected._json({'completed_at': '2026-09-08T02:00:00+00:00'}))
        manifest = {'files': {p.name: {'bytes': p.stat().st_size, 'sha256': corrected._hash(p.read_bytes())}
                              for p in self.run.iterdir()}}
        (self.run / 'manifest.json').write_bytes(corrected._json(manifest))
        patches = [mock.patch.object(corrected, 'RUN_MANIFEST_SHA256', corrected._hash((self.run / 'manifest.json').read_bytes())),
                   mock.patch.object(corrected, 'APPROVED_SOURCE_PAIRS', frozenset({(
                       corrected._hash((self.capture / 'capture.json').read_bytes()),
                       corrected._hash(self.qualification.read_bytes()))}))]
        for patch in patches:
            patch.start(); self.addCleanup(patch.stop)
        with mock.patch.object(corrected, 'datetime') as clock:
            clock.now.return_value = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
            self.data = corrected.build_snapshot(self.run, self.capture, self.qualification, self.output)

    def rewrite_snapshot(self, change):
        data = copy.deepcopy(self.data)
        change(data)
        raw = corrected._json(data)
        (self.output / 'snapshot.json').write_bytes(raw)
        manifest = corrected._read(self.output / 'manifest.json')
        manifest['files']['snapshot.json'] = {'bytes': len(raw), 'sha256': corrected._hash(raw)}
        (self.output / 'manifest.json').write_bytes(corrected._json(manifest))

    def test_full_package_replays_and_preserves_incumbent_comparisons(self):
        result = corrected.load_snapshot(self.output)
        self.assertEqual(result, self.data)
        self.assertEqual(len(result['teams']), 32)
        self.assertEqual(len(result['games']), 16)
        self.assertTrue(all(t['coverage']['status'] == 'UNKNOWN' for t in result['teams']))
        old = {g['game_id']: g for g in corrected.incumbent.load_snapshot(corrected.INCUMBENT_DIR)['games']}
        for game in result['games']:
            self.assertEqual(game['incumbent_margin'], old[game['game_id']]['margin'])
            self.assertEqual(game['pgo_v0_margin'], old[game['game_id']]['pgo_v0_margin'])

    def test_remanifested_predictions_contributions_and_baselines_fail(self):
        for change in (lambda d: d['games'][0].update(margin=99.),
                       lambda d: d['games'][0].update(incumbent_margin=99.),
                       lambda d: d['teams'][0]['contributions'].update(pgo_v0=99.),
                       lambda d: d['teams'][0]['features'].update(qb_experience_prior=99.),
                       lambda d: d['method'].update(status='VALIDATED')):
            self.rewrite_snapshot(change)
            with self.assertRaises(ValueError):
                corrected.load_snapshot(self.output)

    def test_capture_pin_preserves_reviewed_coverage_and_prior_pairs(self):
        original = corrected.APPROVED_SOURCE_PAIRS
        with mock.patch.object(corrected, 'APPROVED_SOURCE_PAIRS', original | {('later-capture', 'later-qualification')}):
            corrected.load_snapshot(self.output)
        with mock.patch.object(corrected, 'APPROVED_SOURCE_PAIRS', frozenset()):
            with self.assertRaisesRegex(ValueError, 'capture/qualification'):
                corrected.load_snapshot(self.output)

    def test_unknown_edition_and_source_bytes_fail(self):
        self.rewrite_snapshot(lambda d: d.update(edition='unknown'))
        with self.assertRaisesRegex(ValueError, 'schema'):
            corrected.load_snapshot(self.output)
        (self.output / 'roster.csv.gz').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'member'):
            corrected.load_snapshot(self.output)

    def test_missing_snapshot_fields_fail_as_validation_errors(self):
        self.rewrite_snapshot(lambda d: d.pop('fit'))
        with self.assertRaisesRegex(ValueError, 'schema'):
            corrected.load_snapshot(self.output)

    def test_raw_capture_http_error_is_rejected(self):
        capture = corrected._read(self.capture / 'capture.json')
        capture['sources'][0]['status'] = 404
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            corrected._inputs(self.capture, capture, corrected._read(self.qualification))

    def test_fit_with_neutral_offset_is_rejected(self):
        fit = corrected._read(self.run / 'final-fit.json')
        fit['coefficients'][0] = .1
        with self.assertRaisesRegex(ValueError, 'symmetry'):
            corrected._derive(self.output, corrected._read(self.capture / 'capture.json'),
                              corrected._read(self.qualification),
                              corrected._read(self.run / 'historical-context.json'), fit,
                              self.data['inputs_as_of'], self.incumbent, self.data['generated_at'])

    def test_refresh_after_opening_cutoff_omits_completed_game_preserves_sunday(self):
        schedule = list(corrected.pgo_sources.open_csv(self.output / 'schedule.csv.gz'))
        opening = min(self.data['games'], key=lambda g: g['kickoff'])
        for row in schedule:
            if row['game_id'] == opening['game_id']:
                row['home_score'], row['away_score'] = '21', '14'
        raw = gzip.compress(corrected._csv(schedule, list(schedule[0])))
        (self.output / 'schedule.csv.gz').write_bytes(raw)
        capture = corrected._read(self.output / 'capture.json')
        for item in capture['sources']:
            if item['file'] == 'schedule.csv.gz':
                item.update(bytes=len(raw), sha256=corrected._hash(raw))
        qualification = corrected._read(self.qualification)
        result = corrected._derive(self.output, capture, qualification,
                                   corrected._read(self.run / 'historical-context.json'),
                                   corrected._read(self.run / 'final-fit.json'),
                                   self.data['inputs_as_of'], self.incumbent,
                                   '2026-09-10T12:00:00+00:00')
        self.assertEqual(len(result[1]), 15)
        self.assertNotIn(opening['game_id'], {g['game_id'] for g in result[1]})
        self.assertTrue(any(g['kickoff'].startswith('2026-09-13') for g in result[1]))
        self.assertEqual(result[5][0]['reason'], 'EXISTING_CUTOFF_ELAPSED')

    def test_unavailable_qb_blocks_only_its_game(self):
        qualification = corrected._read(self.qualification)
        team = self.data['teams'][0]['team']
        qualification['coverage'][team].update(source_kind='formal_injury_report', report_date='2026-09-07',
                                               known_unavailable=[{'gsis_id': 'test-' + team,
                                               'source_url': qualification['coverage'][team]['source_url']}])
        result = corrected._derive(self.output, corrected._read(self.capture / 'capture.json'), qualification,
                                   corrected._read(self.run / 'historical-context.json'),
                                   corrected._read(self.run / 'final-fit.json'),
                                   self.data['inputs_as_of'], self.incumbent, self.data['generated_at'])
        self.assertEqual(len(result[0]), 32)
        self.assertEqual(len(result[1]), 15)
        self.assertFalse(any(team in (g['home'], g['away']) for g in result[1]))
        self.assertEqual(result[5][0]['reason'], 'EXPECTED_QB_UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
