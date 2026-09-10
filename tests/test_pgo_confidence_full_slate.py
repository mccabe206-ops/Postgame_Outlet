import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_confidence_full_slate as full


class FullSlateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((full.base.SOURCE_DIR/'snapshot.json').read_bytes())
        cls.original = full._original(cls.snapshot)

    def pool(self):
        return full._derive(self.snapshot, self.original, '2026-09-10T01:00:00+00:00')

    def package(self, path, pool):
        raw = full.base._bytes(pool); (path/'picks.json').write_bytes(raw)
        m = dict(schema_version=1, kind=full.KIND, generated_at=pool['generated_at'], durable_at=pool['generated_at'],
                 code_sha256=full.base._sha(Path(full.__file__).read_bytes()), source_confidence_manifest_sha256=full.ORIGINAL_PIN,
                 source_snapshot_manifest_sha256=full.base.SOURCE_MANIFEST_SHA,
                 files={'picks.json': {'sha256': full.base._sha(raw), 'bytes': len(raw)}})
        (path/'manifest.json').write_bytes(full.base._bytes(m))
        return full.base._sha((path/'manifest.json').read_bytes())

    def test_sixteen_unique_points_only_opener_late_and_prior_fields_exact(self):
        before = copy.deepcopy((self.snapshot, self.original)); p = self.pool()
        self.assertEqual(len(p['games']), 16); self.assertEqual(p['max_points'], 136)
        self.assertEqual({g['confidence_points'] for g in p['games']}, set(range(1, 17)))
        self.assertEqual([g['game_id'] for g in p['games'] if g['added_after_lock']], [full.OPENER])
        prior = {g['game_id']: g for g in self.original['games']}
        for g in p['games']:
            if g['game_id'] in prior:
                r = {k: v for k, v in g.items() if k not in ('added_after_lock', 'confidence_points', 'expected_points')}
                self.assertEqual(r, {k: v for k, v in prior[g['game_id']].items() if k not in ('confidence_points', 'expected_points')})
            self.assertEqual(g['expected_points'], g['confidence_points']*g['win_probability'])
        self.assertEqual((self.snapshot, self.original), before)

    def test_build_and_load_never_refit(self):
        from research.pgo_confidence_pool_20260909 import check
        with patch.object(check, 'slope', side_effect=AssertionError('refit')), patch.object(full.base, '_calibration', side_effect=AssertionError('refit')):
            p = full.build(self.snapshot, '2026-09-10T01:00:00+00:00')
            with tempfile.TemporaryDirectory() as temp:
                d = Path(temp); pin = self.package(d, p)
                self.assertEqual(full.load_verified(d, pin, self.snapshot), p)

    def test_rehashed_wrong_late_flag_points_or_probability_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            for field, value in [('added_after_lock', True), ('confidence_points', 99), ('win_probability', .99)]:
                p = self.pool(); g = next(g for g in p['games'] if g['game_id'] != full.OPENER); g[field] = value
                with self.assertRaises(ValueError): full.load_verified(d, self.package(d, p), self.snapshot)

    def test_clock_wrong_source_missing_opener_and_more_locks_rejected(self):
        for at in ['2026-09-10T00:00:00+00:00', '2026-09-10T01:00:00', '2026-09-13T20:00:00+00:00']:
            with self.assertRaises(ValueError): full._derive(self.snapshot, self.original, at)
        s = copy.deepcopy(self.snapshot); s['games'][0]['margin'] += 1
        with self.assertRaises(ValueError): full._derive(s, self.original, '2026-09-10T01:00:00+00:00')
        s = copy.deepcopy(self.snapshot); s['games'] = [g for g in s['games'] if g['game_id'] != full.OPENER]
        with self.assertRaises(ValueError): full._derive(s, self.original, '2026-09-10T01:00:00+00:00')

    def test_source_pin_and_overwrite_rejected(self):
        with patch.object(full, 'BASE_CODE_SHA', '0'*64):
            with self.assertRaises(ValueError): full._original(self.snapshot)
        with tempfile.TemporaryDirectory() as temp, patch.object(full, '_original', side_effect=AssertionError('read before overwrite reject')):
            with self.assertRaises(FileExistsError): full.capture(Path(temp))

    def test_portable_replay_accepts_one_ulp_and_rejects_material_error(self):
        probabilities = full.base._probabilities
        def rounded(*args):
            p = probabilities(*args)
            return {k: math.nextafter(v, math.inf) for k, v in p.items()}
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp); p = self.pool(); pin = self.package(d, p)
            with patch.object(full.base, '_probabilities', side_effect=rounded):
                self.assertEqual(full._original(self.snapshot), self.original)
                self.assertEqual(full.load_verified(d, pin, self.snapshot), p)
        def wrong(*args):
            p = probabilities(*args); p['away'] += 1e-8
            return p
        with patch.object(full.base, '_probabilities', side_effect=wrong):
            with self.assertRaises(ValueError): full._original(self.snapshot)

    def test_portable_replay_keeps_strict_types_and_nonfinite_rejection(self):
        for left, right in [(1, 1.0), (False, 0), ([1], [1, 2]), ({'x': 1}, {'y': 1}), (float('nan'), float('nan')), (float('inf'), float('inf'))]:
            self.assertFalse(full._same_replay(left, right))
        x = .5; y = x
        for _ in range(5): y = math.nextafter(y, math.inf)
        self.assertFalse(full._same_replay(x, y))


if __name__ == '__main__':
    unittest.main()
