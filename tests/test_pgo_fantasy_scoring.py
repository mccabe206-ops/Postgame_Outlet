import importlib.util
import math
import unittest


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('pgo_fantasy_scoring'), 'scoring module must exist')
        import pgo_fantasy_scoring
        self.scoring = pgo_fantasy_scoring

    def row(self, season, week, player, value, eligible=True):
        s = self.scoring
        return dict(season=season, week=week, game_id=f'{season}_{week}', gsis_id=player,
                    position='WR', evaluation_eligible=eligible, fantasy_points=value * .5,
                    components={name: value if name == 'receptions' else 0.0 for name in s.HALF_PPR})

    def test_canonical_and_linear_scoring(self):
        s = self.scoring
        components = {name: float(i) for i, name in enumerate(s.HALF_PPR)}
        self.assertEqual(s.adjusted_points(7.123456789, components, s.HALF_PPR), 7.123456789)
        self.assertAlmostEqual(s.adjusted_points(7, components, s.PRESETS['ppr']), 7 + .5 * components['receptions'])
        from pgo_fantasy import strong_baseline
        histories = [{name: value * scale for name, value in components.items()} for scale in (1, 0, 2)]
        projected = {name: strong_baseline([r[name] for r in histories], components[name]) for name in components}
        self.assertAlmostEqual(s.score(projected, s.HALF_PPR), strong_baseline([s.score(r, s.HALF_PPR) for r in histories], s.score(components, s.HALF_PPR)))

    def test_week_updates_wait_and_zero_and_state_only_count(self):
        s = self.scoring
        rows = [self.row(2020, 1, 'a', 10), self.row(2020, 1, 'b', 0),
                self.row(2020, 2, 'c', 100), self.row(2020, 2, 'a', 0, False),
                self.row(2020, 3, 'a', 99)]
        predictions, _, _ = s.walk_components(rows)
        indexed = {(r['week'], r['gsis_id']): r for r in predictions}
        self.assertEqual(indexed[1, 'b']['projected_components']['receptions'], 0)
        self.assertEqual(indexed[2, 'c']['projected_components']['receptions'], 5)
        from pgo_fantasy import strong_baseline
        self.assertAlmostEqual(indexed[3, 'a']['projected_components']['receptions'], strong_baseline([10, 0], 110 / 3))
        self.assertEqual(s.walk_components(list(reversed(rows)))[0], predictions)

    def test_invalid_components_and_duplicate_population_rejected(self):
        s = self.scoring
        for bad in ({}, {**s.HALF_PPR, 'receptions': math.nan}, {**s.HALF_PPR, 'unknown': 1}, {**s.HALF_PPR, 'receptions': ''}):
            with self.assertRaises(ValueError):
                s.validate_components(bad)
        row = self.row(2020, 1, 'a', 0)
        with self.assertRaises(ValueError):
            s.walk_components([row, row])

    def test_raw_join_rejects_mismatch_and_retains_legitimate_zero(self):
        s = self.scoring
        base = {**self.row(2020, 1, 'a', 0), 'team': 'NE', 'opponent': 'NYJ'}
        self.assertEqual(s.attach_components([base], [])[0]['components']['receptions'], 0)
        stat = dict(season='2020', week='1', player_id='a', game_id='wrong', team='NE', opponent_team='NYJ', season_type='REG', **{k: '0' for k in s.HALF_PPR})
        with self.assertRaises(ValueError):
            s.attach_components([base], [stat])
        stat['game_id'] = base['game_id']
        stat['receptions'] = '1'
        with self.assertRaises(ValueError):
            s.attach_components([base], [stat])

    def test_evaluation_preserves_frozen_population_and_reports_failed_gates(self):
        s = self.scoring
        predictions, _, _ = s.walk_components([self.row(year, 1, 'a', 2) | {'team': 'NE', 'opponent': 'NYJ'} for year in range(2020, 2026)])
        heldout = [dict(row, strong_prediction=s.score(row['projected_components'], s.HALF_PPR),
                        candidate_prediction=1., primary_pool='true', cold_start=float(row['cold_start']))
                   for row in predictions if row['season'] >= 2022]
        qualified, _ = s.evaluate(predictions, heldout)
        self.assertTrue(qualified['accepted'])
        failed, _ = s.evaluate(predictions, [dict(row, candidate_prediction=100.) for row in heldout])
        self.assertFalse(failed['accepted'])
        self.assertFalse(failed['presets']['ppr']['gates']['pooled_primary_no_worse'])
        for invalid in (heldout + heldout[:1], [dict(row, team='NYJ') for row in heldout],
                        [dict(row, candidate_prediction=math.nan) for row in heldout],
                        [dict(row, fantasy_points=math.nan) for row in heldout],
                        [dict(row, strong_prediction=math.nan) for row in heldout]):
            with self.assertRaises(ValueError):
                s.evaluate(predictions, invalid)

    def test_frozen_artifact_checks_are_complete_when_present(self):
        import json
        from pathlib import Path
        directory = Path(__file__).resolve().parents[1] / 'output/league-profiles/scoring-20260907-qualification'
        if not directory.exists():
            self.skipTest('Separate frozen scoring qualification is not in this checkout')
        s = self.scoring
        bundle = json.loads((directory / 'scoring-components.json').read_bytes())
        self.assertEqual(len(bundle['rows']), 502)
        self.assertEqual(len({(r['game_id'], r['gsis_id']) for r in bundle['rows']}), 502)
        for row in bundle['rows']:
            s.validate_components(row['components'])
            self.assertEqual(s.adjusted_points(row['half_ppr_prediction'], row['components'], s.HALF_PPR), row['half_ppr_prediction'])
        self.assertEqual(bundle['qualification']['heldout_rows'], 30062)
        self.assertEqual(bundle['qualification']['primary_rows'], 6912)


if __name__ == '__main__':
    unittest.main()
