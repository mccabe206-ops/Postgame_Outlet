"""Regressions for source-backed snap identities and missing usage."""
import csv
import tempfile
import unittest
from pathlib import Path

import pgo_challenger as ch
from tests.test_pgo_challenger import _synthetic_paths, _write_csv


def rewrite(path, change):
    with path.open(encoding='utf-8', newline='') as handle:
        rows = list(csv.DictReader(handle))
    change(rows)
    columns = list(dict.fromkeys(k for row in rows for k in row))
    _write_csv(path, columns, rows)


def paths_with_linemen(directory):
    paths = _synthetic_paths(directory)
    for path in paths.values():
        def rename(rows):
            for row in rows:
                for key in ('team', 'opponent_team', 'home_team', 'away_team'):
                    if key in row:
                        row[key] = {'OAK': 'NE', 'SD': 'NYG'}.get(row[key], row[key])
        # Empty injury fixtures already have a valid header.
        if path.name.startswith('injury_reports'):
            continue
        rewrite(path, rename)
    rewrite(paths['weekly_rosters', 2013], lambda rows: rows.extend([
        dict(season=2013, week=1, team='NE', position='OL', gsis_id='00-0036198',
             pfr_id='', full_name='Mike Onwenu', first_name='Michael',
             football_name='Michael', last_name='Onwenu', years_exp=1, draft_number=182),
        dict(season=2013, week=1, team='NYG', position='OL', gsis_id='00-0036246',
             pfr_id='', full_name='Jon Runyan', first_name='Jon',
             last_name='Runyan', years_exp=1, draft_number=192),
    ]))
    rewrite(paths['snap_counts', 2013], lambda rows: rows.extend([
        dict(season=2013, week=1, team='NE', player='Michael Onwenu',
             pfr_player_id='OnweMi00', position='OL', offense_snaps=40, defense_snaps=0),
        dict(season=2013, week=1, team='NYG', player='Jon Runyan Jr.',
             pfr_player_id='RunyJo00', position='OL', offense_snaps=30, defense_snaps=0),
    ]))
    return paths


class SnapIdentityTests(unittest.TestCase):
    def test_source_names_reach_actual_history_and_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = paths_with_linemen(Path(directory))
            _, context, _ = ch._walk(paths, 4)
            self.assertEqual(list(context['snap_history']['00-0036198']['offense']), [0.8])
            self.assertEqual(list(context['snap_history']['00-0036246']['offense']), [0.6])
            coverage = ch._historical_coverage(paths)['snap_pfr_volume']
            self.assertEqual(coverage['exact_name_volume'], 70)
            self.assertEqual(coverage['rejected_name_volume'], 0)

    def test_ambiguous_suffix_does_not_choose_a_player(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = paths_with_linemen(Path(directory))
            def duplicate(rows):
                row = next(r for r in rows if r['gsis_id'] == '00-0036246')
                rows.append({**row, 'gsis_id': 'different-player', 'full_name': 'Jon Runyan Sr.'})
            rewrite(paths['weekly_rosters', 2013], duplicate)
            _, context, _ = ch._walk(paths, 4)
            self.assertFalse(context['snap_history']['00-0036246']['offense'])
            self.assertFalse(context['snap_history']['different-player']['offense'])
            self.assertEqual(ch._historical_coverage(paths)['snap_pfr_volume']['ambiguous_name_volume'], 30)

    def test_unresolved_is_missing_while_explicit_zero_is_observed(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = paths_with_linemen(Path(directory))
            def change(rows):
                for row in rows:
                    if row.get('player') == 'Michael Onwenu':
                        row['player'] = 'Unresolved Source Player'
                    if row.get('player') == 'Jon Runyan Jr.':
                        row['offense_snaps'] = 0
            rewrite(paths['snap_counts', 2013], change)
            _, context, _ = ch._walk(paths, 4)
            self.assertFalse(context['snap_history']['00-0036198']['offense'])
            self.assertEqual(list(context['snap_history']['00-0036246']['offense']), [0.0])
            targets = [r for r in context['role_training_rows'] if r.player_id == '00-0036198']
            self.assertEqual(len(targets), 1)
            self.assertIsNone(targets[0].target_offense_snap_share)

    def test_missing_team_feed_does_not_create_known_pfr_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = paths_with_linemen(Path(directory))
            rewrite(paths['snap_counts', 2013], lambda rows: rows.__setitem__(
                slice(None), [r for r in rows if not (str(r['week']) == '1' and r['team'] == 'NE')]))
            _, context, _ = ch._walk(paths, 4)
            self.assertFalse(context['snap_history']['gsis-lv-old']['offense'])
            target = next(r for r in context['role_training_rows'] if r.player_id == 'gsis-lv-old')
            self.assertIsNone(target.target_offense_snap_share)

    def test_conflicting_and_duplicate_identities_fail(self):
        for conflict in ('duplicate_pfr', 'conflicting_name', 'unlisted_conflicting_pfr', 'duplicate_snap'):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as directory:
                paths = paths_with_linemen(Path(directory))
                if conflict == 'duplicate_pfr':
                    def duplicate(rows):
                        row = next(r for r in rows if r['team'] == 'NE' and str(r['week']) == '1')
                        rows.append({**row, 'gsis_id': 'other-gsis'})
                    rewrite(paths['weekly_rosters', 2013], duplicate)
                elif conflict == 'unlisted_conflicting_pfr':
                    def conflict_roster(rows):
                        next(r for r in rows if r['gsis_id'] == '00-0036198')['pfr_id'] = 'Different00'
                    rewrite(paths['weekly_rosters', 2013], conflict_roster)
                else:
                    def change(rows):
                        row = next(r for r in rows if r.get('player') == 'Michael Onwenu')
                        if conflict == 'duplicate_snap':
                            rows.append(dict(row))
                        else:
                            row['pfr_player_id'] = 'pfr-lv-old'
                    rewrite(paths['snap_counts', 2013], change)
                with self.assertRaises(ValueError):
                    ch._walk(paths, 4)
                with self.assertRaises(ValueError):
                    ch._historical_coverage(paths)


if __name__ == '__main__':
    unittest.main()
