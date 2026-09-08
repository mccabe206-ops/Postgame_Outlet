"""Small real-walker feature tests. No model coefficient fitting."""
import copy
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.pgo_corrected_roster_candidate import adapter as a
from tests.test_pgo_current_strength import paths_with_starters
from tests.test_pgo_challenger import _add_role_player, _add_current_roster, _write_csv


def read(path):
    with Path(path).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def fixture(root):
    paths = paths_with_starters(root)
    _add_role_player(paths, root, player='role')
    _add_current_roster(paths, root)
    for (name, season), path in paths.items():
        if name != 'weekly_rosters':
            continue
        rows = read(path)
        for row in rows:
            row.update(status='ACT', birth_date='1985-01-01')
        _write_csv(path, list(rows[0]), rows)
    return paths


class TemporalTests(unittest.TestCase):
    def test_same_stack_base_and_future_metadata_performance_and_snaps(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = fixture(Path(temp))
            before, _, _, coverage = a.build_rows(paths)
            with a.audit.construction_scope(paths, active_only=True, half_life_games=4, exposure_fix=True):
                base, _, _ = a.audit.current.build_rows(paths, 'starter_recency')
            base = a.audit.drop_features(base, a.audit.ROSTER_COACH)
            for candidate, original in zip(before, base):
                self.assertEqual({k: v for k, v in candidate.features.items() if k not in a.FEATURES}, original.features)
            # A future season's genuine roster descriptors, current roster, and
            # future realized QB performance cannot change the earlier season.
            path = paths['weekly_rosters', 2014]
            rows = read(path)
            for row in rows:
                row.update(draft_number='1', years_exp='0')
                if row['team'] == 'LA':
                    row['birth_date'] = '1990-01-01'
            _write_csv(path, list(rows[0]), rows)
            rows = read(paths['current_roster', 2026]); rows[0]['years_exp'] = '90'
            _write_csv(paths['current_roster', 2026], list(rows[0]), rows)
            path = paths['player_weekly_stats', 2014]
            rows = read(path)
            for row in rows: row['passing_epa'] = '999'
            _write_csv(path, list(rows[0]), rows)
            after, _, _, _ = a.build_rows(paths)
            self.assertEqual([r.features for r in before[:2]], [r.features for r in after[:2]])
            self.assertNotEqual(before[2].features['qb_age_squared'], after[2].features['qb_age_squared'])
            self.assertNotEqual(before[3].features['qb_epa_per_dropback'], after[3].features['qb_epa_per_dropback'])
            # Own-game realized role affects the later state only.
            path = paths['snap_counts', 2013]
            rows = read(path)
            for row in rows:
                if row['week'] == '1' and row['pfr_player_id'] == 'pfr-role': row['offense_snaps'] = '45'
            _write_csv(path, list(rows[0]), rows)
            snapped, _, _, changed_coverage = a.build_rows(paths)
            self.assertEqual(snapped[0].features, after[0].features)
            old_mass = next(r['offense']['known_role_mass'] for r in coverage if r['season']==2013 and r['week']==2 and r['team']=='LAC')
            new_mass = next(r['offense']['known_role_mass'] for r in changed_coverage if r['season']==2013 and r['week']==2 and r['team']=='LAC')
            self.assertNotEqual(old_mass, new_mass)

    def test_act_filter_before_conflicts_and_exception_restoration(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = fixture(Path(temp))
            before, _, _, _ = a.build_rows(paths)
            path = paths['weekly_rosters', 2013]
            rows = read(path)
            rows.append(dict(rows[0], status='RES', birth_date='bad-date', years_exp='bad'))
            _write_csv(path, list(rows[0]), rows)
            after, _, _, _ = a.build_rows(paths)
            self.assertEqual([r.features for r in before], [r.features for r in after])
            originals = (a.ch._walk, a.ch._team_views, a.ch._update_after_game, a.ch.open_csv, a.ch._qb_features)
            rows.append(dict(rows[0], status='ACT', birth_date='bad-date'))
            _write_csv(path, list(rows[0]), rows)
            with self.assertRaises(ValueError): a.build_rows(paths)
            self.assertEqual(originals, (a.ch._walk, a.ch._team_views, a.ch._update_after_game, a.ch.open_csv, a.ch._qb_features))
            self.assertFalse(a.audit.current._WALK_LOCK.locked())

    def test_same_kickoff_prepares_all_views_before_any_update(self):
        # Use the real corrected walker with a synthetic kickoff batch.
        with tempfile.TemporaryDirectory() as temp:
            paths = fixture(Path(temp))
            events = []
            original_views, original_update = a.ch._team_views, a.ch._update_after_game
            def views(team, *args, **kwargs):
                events.append(('view', team))
                return original_views(team, *args, **kwargs)
            def update(*args, **kwargs):
                events.append(('update', args[0]['game_id']))
                return original_update(*args, **kwargs)
            # Recorded starter times must match the controlled fixture clock.
            schedule = read(paths['schedule_results', None])
            schedule[1]['gameday'] = schedule[0]['gameday']
            _write_csv(paths['schedule_results', None], list(schedule[0]), schedule)
            with patch.object(a.ch, '_team_views', views), patch.object(a.ch, '_update_after_game', update):
                a.build_rows(paths)
            self.assertEqual([e[0] for e in events[:6]], ['view']*4 + ['update']*2)

    def test_validation_outlier_cannot_change_training_preprocessing(self):
        row = a.ch.FeatureRow
        training = [row('a', 2013, 1, '', 0, {'x': 1.}, {}), row('b', 2013, 2, '', 0, {'x': 3.}, {})]
        validation = [row('v', 2014, 1, '', 0, {'x': 5.}, {})]
        first = a.ch.fit_preprocessor(training, ('x',))
        validation[0].features['x'] = 1e100
        second = a.ch.fit_preprocessor(training, ('x',))
        self.assertEqual(first.medians.tolist(), second.medians.tolist())
        self.assertEqual(first.scales.tolist(), second.scales.tolist())
        self.assertEqual(first.missing_features, second.missing_features)
        self.assertGreater(float(second.transform(validation)[0, 0]), 1e90)


if __name__ == '__main__':
    unittest.main()
