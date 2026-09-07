import copy
import json
from pathlib import Path
import tempfile
import unittest

import pgo_forecast_snapshot as snapshot


class FreshSnapshotTests(unittest.TestCase):
    def test_expected_starter_changes_identity_without_changing_epa(self):
        states = {'JAX': ({'qb_epa_per_dropback': .2}, {'qb_epa_per_dropback': .2})}
        metadata = {'JAX': {'roster': {
            'backup': {'position': 'QB', 'gsis_id': 'backup', 'qb_epa_per_dropback': .2},
            'starter': {'position': 'QB', 'gsis_id': 'starter', 'qb_epa_per_dropback': .1},
        }}}
        source = copy.deepcopy((states, metadata))
        starters = {'JAX': {'gsis_id': 'starter', 'status': 'ACT'}}
        result = snapshot.starter_states(states, metadata, starters)
        self.assertEqual(result['JAX'][0]['qb_epa_per_dropback'], .1)
        self.assertEqual(result['JAX'][1]['qb_current_minus_full'], 0)
        self.assertEqual((states, metadata), source)
        for invalid in ({'gsis_id': 'missing', 'status': 'ACT'},
                        {'gsis_id': 'starter', 'status': 'RES'}):
            with self.assertRaises(ValueError):
                snapshot.starter_states(states, metadata, {'JAX': invalid})

    def test_score_expectations_reconcile_and_reject_impossible_inputs(self):
        self.assertEqual(snapshot.expected_scores(44, 3), (23.5, 20.5))
        self.assertEqual(snapshot.expected_scores(44, -3), (20.5, 23.5))
        for total, margin in ((float('nan'), 3), (44, float('inf')), (10, 11), (-1, 0)):
            with self.assertRaises(ValueError):
                snapshot.expected_scores(total, margin)

    def test_committed_edition_is_reproducible_and_tampering_is_rejected(self):
        directory = Path(__file__).resolve().parents[1] / 'docs/evidence/forecast-lab-2026/september-07'
        if not directory.exists():
            self.skipTest('Fresh edition has not been captured yet')
        data = snapshot.load_snapshot(directory)
        self.assertEqual(len(data['teams']), 32)
        self.assertEqual(len(data['games']), 272)
        self.assertEqual(sum(game['week'] == 1 for game in data['games']), 16)
        mutations = [
            lambda d: d['teams'][0]['contributions'].update(
                pgo_v0=d['teams'][0]['contributions']['pgo_v0'] + 100,
                passing_epa_per_play_for=d['teams'][0]['contributions']['passing_epa_per_play_for'] - 100),
            lambda d: d['teams'][0].update(old_selector_rating=123),
            lambda d: d['teams'][0].update(qb_policy_effect=123),
            lambda d: d['teams'][0].update(qb_name='Invented QB'),
            lambda d: d['games'][0].update(legacy_margin=123),
            lambda d: d['games'][0].update(old_selector_margin=123),
            lambda d: d['games'][0].update(home_points=123),
            lambda d: d['sources'][0].update(sha256='0' * 64),
            lambda d: d.update(generated_at=d['games'][0]['kickoff']),
        ]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                changed = copy.deepcopy(data)
                change(changed)
                with self.assertRaises(ValueError):
                    snapshot.validate_snapshot(changed)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            manifest = json.loads((directory / 'manifest.json').read_bytes())
            for name in ('manifest.json', *manifest['files']):
                (target / name).write_bytes((directory / name).read_bytes())
            raw = (target / 'snapshot.json').read_bytes()
            (target / 'snapshot.json').write_bytes(raw + b' ')
            with self.assertRaises(ValueError):
                snapshot.load_snapshot(target)


if __name__ == '__main__':
    unittest.main()
