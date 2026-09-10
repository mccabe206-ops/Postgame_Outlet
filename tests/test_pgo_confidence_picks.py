import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_confidence_picks as c


def fixture():
    return {'edition': c.EDITION, 'generated_at': '2026-09-09T22:00:00+00:00', 'games': [
        dict(game_id=name, season=2026, week=1, game_type='REG', home=home, away=away,
             kickoff=kickoff, margin=margin, corrected_margin=-margin)
        for name, home, away, kickoff, margin in [
            ('early', 'SEA', 'NE', '2026-09-10T00:20:00+00:00', 3.),
            ('late-a', 'BUF', 'NYJ', '2026-09-13T17:00:00+00:00', 1.),
            ('late-b', 'BAL', 'PIT', '2026-09-13T17:00:00+00:00', -8.)]]}


class ConfidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calibration = c._calibration()

    def pool(self):
        return c._derive(fixture(), '2026-09-10T00:25:00+00:00', copy.deepcopy(self.calibration))

    def package(self, directory, pool):
        raw = c._bytes(pool); (directory/'picks.json').write_bytes(raw)
        manifest = dict(schema_version=1, generated_at=pool['generated_at'], durable_at=pool['generated_at'],
                        code_sha256=c._sha(Path(c.__file__).read_bytes()), source_manifest_sha256=c.SOURCE_MANIFEST_SHA,
                        files={'picks.json': {'sha256': c._sha(raw), 'bytes': len(raw)}})
        (directory/'manifest.json').write_bytes(c._bytes(manifest))
        return c._sha((directory/'manifest.json').read_bytes())

    def test_cutoff_exclusion_ranking_unconditional_probabilities_and_immutability(self):
        source = fixture(); before = copy.deepcopy(source)
        p = c._derive(source, '2026-09-09T23:20:00+00:00', self.calibration)
        self.assertEqual(source, before)
        self.assertEqual(['early'], [g['game_id'] for g in p['excluded']])
        self.assertEqual([1, 2], [g['confidence_points'] for g in p['games']])
        self.assertEqual('PIT', p['games'][1]['selected_team'])
        self.assertAlmostEqual(p['expected_points_total'], sum(g['confidence_points']*g['win_probability'] for g in p['games']))
        self.assertAlmostEqual(self.calibration['tie_probability'], 9/2129)
        for g in p['games']: self.assertAlmostEqual(sum(g['probabilities'].values()), 1.)

    def test_future_naive_duplicate_nonfinite_and_empty_sources_rejected(self):
        for stamp in ['2026-09-09T23:00:00', '2026-09-09T21:00:00+00:00', '2026-09-14T00:00:00+00:00']:
            with self.assertRaises(ValueError): c._derive(fixture(), stamp, self.calibration)
        for mutation in ('duplicate', 'nan', 'missing'):
            f = fixture()
            if mutation == 'duplicate': f['games'].append(f['games'][0])
            if mutation == 'nan': f['games'][0]['margin'] = float('nan')
            if mutation == 'missing': f['games'] = []
            with self.assertRaises(ValueError): c._derive(f, '2026-09-10T00:25:00+00:00', self.calibration)

    def test_strict_replay_does_not_refit_and_catches_rehashed_semantic_mutation(self):
        from research.pgo_confidence_pool_20260909 import check
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); pool = self.pool(); pin = self.package(directory, pool)
            with patch.object(check, 'slope', side_effect=AssertionError('reader refit')):
                self.assertEqual(c.load_verified(directory, pin, fixture()), pool)
            altered = copy.deepcopy(pool); altered['games'][0]['margin'] += 1
            altered_pin = self.package(directory, altered)
            with self.assertRaises(ValueError): c.load_verified(directory, pin, fixture())
            with self.assertRaises(ValueError): c.load_verified(directory, altered_pin, fixture())
            altered = copy.deepcopy(pool); altered['games'][0]['confidence_points'] = 99
            with self.assertRaises(ValueError): c.load_verified(directory, self.package(directory, altered), fixture())

    def test_clock_and_missing_exclusion_and_bad_calibration_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for kind in ('clock', 'exclusion', 'slope'):
                p = self.pool()
                if kind == 'exclusion': p['excluded'] = []
                if kind == 'slope': p['calibration']['slopes']['postseason'] *= 2
                pin = self.package(directory, p)
                if kind == 'clock':
                    m = json.loads((directory/'manifest.json').read_bytes()); m['durable_at'] = '2026-09-13T16:00:00+00:00'
                    (directory/'manifest.json').write_bytes(c._bytes(m)); pin = c._sha((directory/'manifest.json').read_bytes())
                with self.assertRaises(ValueError): c.load_verified(directory, pin, fixture())

    def test_source_pins_fail_closed(self):
        with patch.object(c, 'METHOD_SHA', '0'*64):
            with self.assertRaises(ValueError): c._method_history()
        with patch.object(c, 'HISTORY_SHA', '0'*64):
            with self.assertRaises(ValueError): c._method_history()

    def test_partial_final_result_grades_ties_zero_without_reranking(self):
        p = self.pool(); before = copy.deepcopy(p); g = p['games'][1]
        r = dict(game_id=g['game_id'], home_team=g['home'], away_team=g['away'], kickoff=g['kickoff'],
                 home_score=20, away_score=20, finalized_at='2026-09-13T21:00:00+00:00')
        graded = c.grade(p, [r]); self.assertEqual(graded['earned_points'], 0)
        self.assertEqual(graded['available_points'], 2); self.assertEqual(graded['finalized_games'], 1)
        self.assertGreater(graded['metrics']['postseason']['log_loss'], 0)
        self.assertEqual(p, before)
        r['away_score'] = 21
        self.assertEqual(c.grade(p, [r])['earned_points'], 2)
        with self.assertRaises(ValueError): c.grade(p, [r, r])
        r['home_team'] = 'WRONG'
        with self.assertRaises(ValueError): c.grade(p, [r])
        self.assertIsNone(c.grade(p, [])['metrics']['postseason']['log_loss'])

    def test_capture_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(c, '_calibration', side_effect=AssertionError('refit before overwrite rejection')):
            with self.assertRaises(FileExistsError): c.capture(Path(temp))


if __name__ == '__main__':
    unittest.main()
