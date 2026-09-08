import copy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

import pgo_challenger as ch
from research.pgo_corrected_roster_candidate import adapter as a


CLOCK = '2025-09-01T00:00:00+00:00'


def raw(pid, position='WR', **kwargs):
    return dict(gsis_id=pid, position=position, status='ACT', birth_date='2000-01-01',
                years_exp='0', draft_number='100', **kwargs)


class AdapterTests(unittest.TestCase):
    def test_age_clock_missing_and_invalid(self):
        self.assertIsNone(a.age_years('', CLOCK))
        self.assertAlmostEqual(a.age_years('2000-01-01', CLOCK), 9375 / 365.2425)
        self.assertEqual(a.age_years('2000-01-01', '2025-08-31T20:00:00-04:00'),
                         a.age_years('2000-01-01', CLOCK))
        self.assertAlmostEqual(a.age_years('2000-01-01', '2025-08-31T23:30:00-04:00') -
                               a.age_years('2000-01-01', '2025-08-31T23:30:00+00:00'), 1/365.2425)
        for invalid in ('garbage', '2020-01-01', '1900-01-01', '2000-01-01garbage'):
            with self.assertRaises(ValueError): a.age_years(invalid, CLOCK)
        with self.assertRaises(ValueError): a.age_years('2000-01-01', '2025-09-01')

    def test_units_and_fixed_ten_hand_calculation(self):
        rows = [raw('q', 'QB'), raw('a'), raw('b', 'OT'), raw('d', 'SS'), raw('k', 'K')]
        rows[2].update(birth_date='1990-01-01', years_exp='8', draft_number='25')
        history = {'a': {'offense': [1]}, 'b': {'offense': [.5]}, 'd': {'defense': [.8]}}
        values, coverage = a.team_features(rows, 'q', history, CLOCK, ())
        young = a.age_years('2000-01-01', CLOCK)
        old = a.age_years('1990-01-01', CLOCK)
        self.assertEqual(set(values), set(a.FEATURES))
        self.assertAlmostEqual(values['qb_age_squared'], (young - 27) ** 2)
        self.assertAlmostEqual(values['offense_role_weighted_age'], (young + old * .5) / 1.5)
        self.assertAlmostEqual(values['offense_young_role_share'], 1 / 1.5)
        self.assertAlmostEqual(values['offense_role_weighted_draft_prior'], .2 / 1.5)
        self.assertAlmostEqual(values['offense_rookie_draft_capital'], .1 / 2)
        self.assertEqual(coverage['offense']['players'], 2)
        self.assertEqual(coverage['defense']['players'], 1)

    def test_missing_metadata_is_not_rookie_or_zero_role(self):
        row = raw('a'); row.update(years_exp='', birth_date='', draft_number='')
        values, coverage = a.team_features([row], None, {}, CLOCK, ())
        self.assertIsNone(values['offense_rookie_draft_capital'])
        self.assertIsNone(values['offense_role_weighted_age'])
        self.assertIsNone(values['offense_role_weighted_draft_prior'])
        self.assertIsNone(values['qb_age_centered'])
        self.assertEqual(coverage['offense']['missing_experience'], 1)
        row.update(years_exp='0')
        values, _ = a.team_features([row], None, {'a': {'offense': [0]}}, CLOCK, ())
        self.assertEqual(values['offense_rookie_draft_capital'], 0)
        self.assertIsNone(values['offense_role_weighted_draft_prior'])
        for field in ('years_exp', 'draft_number'):
            for invalid in ('-1', 'nan', '1.5'):
                with self.subTest(field=field, invalid=invalid):
                    bad = dict(row, **{field: invalid})
                    with self.assertRaises(ValueError): a.team_features([bad], None, {}, CLOCK, ())

    def test_identity_act_selected_qb_and_no_mutation(self):
        rows = [raw('q', 'QB'), raw('backup', 'QB')]
        rows[1]['birth_date'] = '1990-01-01'
        before = copy.deepcopy(rows)
        values, _ = a.team_features(rows, 'q', {}, CLOCK, ())
        self.assertAlmostEqual(values['qb_age_centered'], a.age_years(rows[0]['birth_date'], CLOCK)-27)
        self.assertEqual(rows, before)
        with self.assertRaises(ValueError): a.team_features(rows + [rows[0]], 'q', {}, CLOCK, ())
        with self.assertRaises(ValueError): a.team_features([dict(rows[0], status='RES')], 'q', {}, CLOCK, ())
        with self.assertRaises(ValueError): a.team_features(rows, 'absent', {}, CLOCK, ())
        with self.assertRaises(ValueError): a.team_features(rows, 'q', {}, CLOCK, ('q',))
        smart = dict(rows[0], smart_id='one')
        a.team_features([smart], 'q:one', {}, CLOCK, ('q',))

    def test_hook_preserves_base_and_uses_prior_history(self):
        rows = [raw('q', 'QB'), raw('a')]
        inputs = {'rosters': {(2025, 1, 'NE'): rows}, 'colliding_gsis': ()}
        context = {'snap_history': {'a': {'offense': [.1, .2, .3, .4]}}}
        metadata = {'starter': 'q', 'roster': {'q': {}, 'a': {}}}
        hook = a.RosterHook()
        full, current = {'original': 2}, {'original': 3}
        hook(full, current, metadata, team='NE', season=2025, week=1, kickoff=CLOCK,
             context=context, inputs=inputs)
        self.assertEqual((full['original'], current['original']), (2, 3))
        self.assertEqual({k: full[k] for k in a.FEATURES}, {k: current[k] for k in a.FEATURES})
        self.assertAlmostEqual(hook.coverage[0]['offense']['known_role_mass'], .25)
        # Future data cannot enter this team/week's raw lookup or prior role state.
        inputs['rosters'][2026, 1, 'NE'] = [dict(rows[1], birth_date='1990-01-01')]
        f2, c2 = {'original': 2}, {'original': 3}
        hook(f2, c2, metadata, team='NE', season=2025, week=1, kickoff=CLOCK,
             context=context, inputs=inputs)
        self.assertEqual(f2, full)
        later = copy.deepcopy(context); later['snap_history']['a']['offense'] = [.9]
        f3, c3 = {}, {}
        hook(f3, c3, metadata, team='NE', season=2025, week=1, kickoff=CLOCK,
             context=later, inputs=inputs)
        self.assertEqual(hook.coverage[-1]['offense']['known_role_mass'], .9)

    def test_base_parity_rejects_missing_extra_changed_and_duplicate(self):
        saved = [dict(game_id='g', season=2018, week=1, kickoff=CLOCK,
                      actual_margin=2, features={'base': 3.0})]
        row = ch.FeatureRow('g', 2018, 1, CLOCK, 2, {'base': 3., **dict.fromkeys(a.FEATURES)}, {})
        a.validate_base([row], saved)
        row.features['base'] = 3.001
        with self.assertRaises(ValueError): a.validate_base([row], saved)
        row.features['base'] = 3
        with self.assertRaises(ValueError): a.validate_base([row, row], saved)
        row.features['unexpected'] = 1
        with self.assertRaises(ValueError): a.validate_base([row], saved)

    def test_export_snap_history_is_detached_and_preserves_clock(self):
        context = {'snap_history': {'a': {'offense': [.2], 'defense': []}}}
        base = {'identity': 'old', 'current_strength': {'last_kickoff': CLOCK}}
        with patch.object(a.corrected, 'portable_context', return_value=base):
            exported = a.portable_context(context, {})
        self.assertEqual(exported['current_strength']['last_kickoff'], CLOCK)
        exported['snap_history']['a']['offense'].append(.8)
        self.assertEqual(context['snap_history']['a']['offense'], [.2])

    def test_current_replay_uses_label_and_checks_new_collisions(self):
        import pgo_forecast_corrected as issued
        teams = sorted(a.audit.pgo_model.CURRENT_TEAMS)
        rows = [dict(raw(team, 'QB'), team=team, season='2026', week='1') for team in teams]
        snapshot = dict(inputs_as_of=CLOCK, teams=[dict(team=t, qb_gsis_id=t,
                        features={'base': 2.}) for t in teams])
        context = dict(inputs={'colliding_gsis': []}, snap_history={})
        with patch.object(issued, 'current_features', return_value={t: {'base': 2.} for t in teams}):
            values, _ = a.current_features(context, snapshot, rows)
            self.assertEqual(len(values), 32)
            self.assertEqual(values[teams[0]]['base'], 2.)
            snapshot['teams'][0]['features']['base'] = 3.
            with self.assertRaises(ValueError): a.current_features(context, snapshot, rows)
            snapshot['teams'][0]['features']['base'] = 2.
            with self.assertRaisesRegex(ValueError, 'collision'):
                a.current_features(context, snapshot, rows+[dict(rows[0], team=teams[1])])
            with self.assertRaisesRegex(ValueError, 'collision'):
                a.current_features(context, snapshot, [dict(rows[0], smart_id='a')]+rows[1:]+[dict(rows[0], smart_id='b')])
            with self.assertRaisesRegex(ValueError, 'ID-less'):
                a.current_features(context, snapshot, rows+[dict(rows[0], gsis_id='', pfr_id='')])

    def test_screen_has_exactly_three_criteria_and_stays_hold(self):
        from research.pgo_corrected_roster_candidate import train
        control = {'overall': {'mae': 10}, 'seasons': [{'season': y, 'mae': 10} for y in range(2018, 2026)]}
        candidate = {'overall': {'mae': 9.9}, 'seasons': [{'season': y, 'mae': 9 if y < 2023 else 11} for y in range(2018, 2026)]}
        result = train.screen({'corrected': control, 'candidate': candidate}, {'lower': .01})
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(len(result['checks']), 3)
        self.assertEqual(result['scientific_status'], 'EXPERIMENTAL / HOLD')
        self.assertEqual(train.screen({'corrected': control, 'candidate': candidate}, {'lower': 0})['status'], 'FAIL')

    def test_missing_pattern_symmetry_and_signed_age_square(self):
        from research.pgo_corrected_roster_candidate import train
        names = ['home_field', 'rest_difference', 'qb_age_squared']
        row = ch.FeatureRow('g', 2025, 1, '', 4, dict(zip(names, [1., .5, 7.])), {})
        mirrored = a.audit.symmetric_rows([row])
        self.assertEqual(mirrored[1].features['qb_age_squared'], -7.)
        fit = dict(preprocessor=dict(feature_names=names, medians=[0.]*3, scales=[1.]*3,
                                     missing_features=['qb_age_squared']),
                   coefficients=[0., 2., 3., 4., 0.])
        self.assertEqual(train.symmetry_check(fit, row)['maximum_error'], 0.)
        fit['coefficients'][-1] = .01
        with self.assertRaises(ValueError): train.symmetry_check(fit, row)


if __name__ == '__main__':
    unittest.main()
