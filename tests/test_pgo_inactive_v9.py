"""Restore admitted opponent evidence without rewriting frozen v8 captures."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import unittest

import pgo_season_availability as availability
from tests.test_pgo_inactive_v8 import (
    EXPECTED, LV_HEADING, article_mutation, package as single_team_package,
)


ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = ROOT / 'docs/evidence/season-2026/availability-v2'
PACKAGES = {'LV': '20261004T194607315850Z', 'LAC': '20261004T194608173677Z'}
HASHES = {
    'LV': 'e21e0054c36e2acbf9e8c02e4009920cd10af23de0e559bf6e558d775fde9324',
    'LAC': '58dd1a34dd80b644a7bd30d18dd9eac19fa56c0e8eef4f0488dff694cb629d39',
}
OPPONENT_HEADINGS = {'LV': 'Chiefs inactives:', 'LAC': "Here are Seattle's inactives:"}
KC_NAMES = ['Jared Wiley', 'Garrett Nussmeier', 'Jadon Canady',
            'Jack Pyburn', 'Diego Pounds', 'Josh Simmons']


def package(team):
    directory = ARCHIVES / PACKAGES[team]
    inputs = json.loads(gzip.decompress((directory / 'inputs.json.gz').read_bytes()))
    capture = json.loads((directory / 'capture.json').read_bytes())
    sources = [dict(source, body=gzip.decompress((directory / source['file']).read_bytes()))
               if 'file' in source else dict(source) for source in capture['sources']]
    return inputs, sources, capture['checked_at']


class InactiveV9Tests(unittest.TestCase):
    def setUp(self):
        self.packages = {team: package(team) for team in PACKAGES}

    def source(self, package_team, source_team=None):
        source_team = package_team if source_team is None else source_team
        return next(source for source in self.packages[package_team][1]
                    if source['kind'] == 'official_inactives' and source.get('team') == source_team)

    def parse(self, team, *, target=None, raw=None, version=9, **changes):
        source = self.source(team)
        options = dict(parser_version=version, source_team=team, source_url=source['url'])
        game = changes.pop('game', self.packages[team][0]['games'][0])
        captured = changes.pop('captured_at', source['captured_at'])
        options.update(changes)
        return availability.parse_final_inactives(
            source['body'] if raw is None else raw, game, target or team, captured, **options)

    def altered(self, team, transform):
        return article_mutation(self.source(team)['body'],
                                lambda article: article.update(articleBody=transform(article['articleBody'])))

    def build(self, team, *, inputs=None, sources=None, checked=None):
        original_inputs, original_sources, original_checked = self.packages[team]
        return availability.build_availability(
            **dict(original_inputs if inputs is None else inputs, parser_version=9),
            sources=original_sources if sources is None else sources,
            checked_at=original_checked if checked is None else checked)

    def test_updated_own_lists_stop_at_exact_corroborated_opponent_boundary(self):
        for team in PACKAGES:
            with self.subTest(team=team):
                self.assertEqual(hashlib.sha256(self.source(team)['body']).hexdigest(), HASHES[team])
                result = self.parse(team)
                self.assertEqual([(row['name'], row['position'], row['status'])
                                  for row in result['observations']], EXPECTED[team])
                self.assertEqual(result['unparsed_lines'], [])
                self.assertFalse(set(KC_NAMES) & {row['name'] for row in result['observations']})
                self.assertNotIn('Jalen Milroe', [row['name'] for row in result['observations']])
                self.assertNotIn('Ladd McConkey', [row['name'] for row in result['observations']])
        jackson = self.parse('LV')['observations'][3]
        self.assertEqual(jackson['position'], 'G/C')
        self.assertEqual(jackson['source_text'], 'G/C Jackson Powers-Johnson')

    def test_kc_opponent_list_matches_frozen_v7_admission_and_designations(self):
        old = self.parse('LV', target='KC', version=7)
        self.assertEqual([row['name'] for row in old['observations']], KC_NAMES)
        self.assertEqual(next(row for row in old['observations']
                              if row['name'] == 'Garrett Nussmeier')['status'], 'INACTIVE')
        self.assertEqual(self.parse('LV', target='KC'), old)
        with self.assertRaises(ValueError):
            self.parse('LV', target='KC', version=8)

    def test_previously_supported_other_club_opponent_lists_stay_exact(self):
        fixtures = json.loads((ROOT / 'tests/fixtures/pgo_availability_v3_articles.json').read_bytes())
        expected = {'CAR': ('CHI', 6), 'PIT': ('ATL', 6), 'NO': ('DET', 5)}
        seen = set()
        for fixture in fixtures:
            source_team = fixture['source_team']
            if source_team not in expected:
                continue
            target, count = expected[source_team]
            season, week, away, home = fixture['game_id'].split('_')
            game = dict(game_id=fixture['game_id'], season=int(season), week=int(week), game_type='REG',
                        away=away, home=home, kickoff='2026-09-13T17:00:00Z', lock_at='2026-09-13T16:00:00Z')
            article = dict(fixture['article'], **{'@type': 'NewsArticle'})
            raw = ('<script type="application/ld+json">' + json.dumps(article) + '</script>').encode()
            with self.subTest(source=source_team, target=target):
                old = availability.parse_final_inactives(raw, game, target, fixture['captured_at'],
                    parser_version=7, source_team=source_team, source_url=fixture['url'])
                self.assertEqual(len(old['observations']), count)
                new = availability.parse_final_inactives(raw, game, target, fixture['captured_at'],
                    parser_version=9, source_team=source_team, source_url=fixture['url'])
                self.assertEqual(new, old)
            seen.add(source_team)
        self.assertEqual(seen, set(expected))

    def test_preexisting_v8_single_team_positives_keep_their_exact_result(self):
        inputs, sources, checked = single_team_package()
        for team in PACKAGES:
            source = next(source for source in sources if source.get('team') == team
                          and source['kind'] == 'official_inactives')
            game = next(game for game in inputs['games'] if team in (game['home'], game['away']))
            with self.subTest(team=team):
                old = availability.parse_final_inactives(source['body'], game, team, source['captured_at'],
                    parser_version=8, source_team=team, source_url=source['url'])
                new = availability.parse_final_inactives(source['body'], game, team, source['captured_at'],
                    parser_version=9, source_team=team, source_url=source['url'])
                self.assertEqual(new, old)
                self.assertEqual([(row['name'], row['position'], row['status'])
                                  for row in new['observations']], EXPECTED[team])

    def test_archived_v8_packages_replay_without_reinterpreting_old_statuses(self):
        for team, name in PACKAGES.items():
            with self.subTest(team=team):
                directory = ARCHIVES / name
                saved = json.loads((directory / 'availability.json').read_bytes())
                self.assertEqual(saved['parser_version'], 8)
                self.assertEqual(availability.load_availability(directory), saved)
        # Preserve the historical capture even though v9 corrects the missed disagreement.
        saved = json.loads((ARCHIVES / PACKAGES['LV'] / 'availability.json').read_bytes())
        self.assertEqual(saved['games']['2026_04_KC_LV']['teams']['KC']['final_inactives_status'], 'VERIFIED_LIST')

    def test_v9_restores_kc_source_disagreement_without_changing_clocks_or_inputs(self):
        before = copy.deepcopy(self.packages)
        for team in PACKAGES:
            result = self.build(team)
            saved = json.loads((ARCHIVES / PACKAGES[team] / 'availability.json').read_bytes())
            self.assertEqual(result['parser_version'], 9)
            for key in ('checked_at', 'purpose', 'policy', 'schema_version', 'sources'):
                self.assertEqual(result[key], saved[key], (team, key))
            game = next(iter(result['games'].values()))
            old_game = next(iter(saved['games'].values()))
            for key in old_game.keys() - {'teams', 'summary'}:
                self.assertEqual(game[key], old_game[key], (team, key))
            rows = [row for row in game['teams'][team]['observations']
                    if row['source_kind'] == 'official_inactives']
            self.assertEqual([(row['name'], row['position'], row['status']) for row in rows], EXPECTED[team])
            for row in rows:
                self.assertEqual(row['captured_at'], self.source(team)['captured_at'])
                self.assertEqual(row['source_sha256'], HASHES[team])
                self.assertNotIn('identity_binding', row)
            if team == 'LV':
                lv = game['teams']['LV']
                self.assertEqual(lv['final_inactives_status'], 'PARTIAL')
                self.assertTrue(any('Conflicting official inactive lists' in error
                                    and "Aidan O'Connell" in error and 'Aidan O\u2019Connell' in error
                                    for error in lv['source_errors']))
                aidan = next(row for row in rows if row['name'] == "Aidan O'Connell")
                self.assertEqual(aidan['identity_status'], 'RESOLVED')
                self.assertEqual(aidan['gsis_id'], '00-0038579')
                kc = game['teams']['KC']
                self.assertEqual(kc['final_inactives_status'], 'PARTIAL')
                self.assertTrue(any('Conflicting official inactive lists' in error
                                    and 'Garrett Nussmeier' in error for error in kc['source_errors']))
                source = next(source for source in self.packages[team][1]
                              if source['kind'] == 'official_inactives' and source.get('team') is None)
                nfl = availability.parse_final_inactives(source['body'], self.packages[team][0]['games'][0],
                    'KC', source['captured_at'], parser_version=9, source_url=source['url'])
                self.assertEqual(next(row for row in nfl['observations']
                                      if row['name'] == 'Garrett Nussmeier')['status'], 'EMERGENCY_QB')
                nfl_lv = availability.parse_final_inactives(source['body'], self.packages[team][0]['games'][0],
                    'LV', source['captured_at'], parser_version=9, source_url=source['url'])
                self.assertIn('Aidan O\u2019Connell', [row['name'] for row in nfl_lv['observations']])
                self.assertEqual(kc['expected_qb_status'], old_game['teams']['KC']['expected_qb_status'])
        self.assertEqual(self.packages, before)

    def test_sea_boundary_does_not_introduce_new_comma_name_identity_admission(self):
        for version in (7, 8, 9):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.parse('LAC', target='SEA', version=version)
        self.assertEqual([row['name'] for row in self.parse('LAC')['observations']],
                         [name for name, position, status in EXPECTED['LAC']])

    def test_metadata_cannot_drop_own_or_opponent_rows_present_in_dom(self):
        for team, row in [('LV', 'G/C Jackson Powers-Johnson'), ('LV', 'T Josh Simmons'),
                          ('LAC', 'DT Dalvin Tomlinson'), ('LAC', 'NT Brandon Pili')]:
            with self.subTest(team=team, row=row), self.assertRaises(ValueError):
                self.parse(team, raw=self.altered(team, lambda body: body.replace(row, '', 1)))

    def test_wrong_duplicate_or_missing_opponent_boundary_stays_rejected(self):
        for team, heading in OPPONENT_HEADINGS.items():
            for replacement in ('Broncos inactives:', '', heading + '\n\n' + heading):
                with self.subTest(team=team, replacement=replacement), self.assertRaises(ValueError):
                    self.parse(team, raw=self.altered(team, lambda body: body.replace(heading, replacement)))
        duplicate_own = self.altered('LV', lambda body: body.replace(LV_HEADING, LV_HEADING + '\n\n' + LV_HEADING))
        with self.assertRaises(ValueError):
            self.parse('LV', raw=duplicate_own)

    def test_duplicate_opponent_name_with_different_position_in_both_views_is_rejected(self):
        raw = self.source('LV')['body']
        original = b'DB Jadon Canady'
        self.assertEqual(raw.count(original), 2, 'One JSON-LD row and one visible DOM row')
        # Existing DE Jack Pyburn remains. Both representations agree on the
        # alteration, so rejection must not rely only on JSON-LD/DOM inequality.
        altered = raw.replace(original, b'DB Jack Pyburn')
        with self.assertRaises(ValueError):
            self.parse('LV', raw=altered)

    def test_unknown_own_rows_bad_composite_and_mismatched_counts_stay_rejected(self):
        for replacement in ('G//C Jackson Powers-Johnson', 'QB/C Jackson Powers-Johnson',
                            'G/C Jackson Powers-Johnson\n\nXX Mystery Player'):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                self.parse('LV', raw=self.altered('LV', lambda body: body.replace(
                    'G/C Jackson Powers-Johnson', replacement)))
        for team, count in [('LV', 'Six'), ('LAC', 'Eight')]:
            raw = article_mutation(self.source(team)['body'], lambda article: article.update(
                headline=article['headline'].replace('Week 4 Inactives', f'Week 4 {count} Inactives')))
            with self.subTest(team=team, count=count), self.assertRaises(ValueError):
                self.parse(team, raw=raw)

    def test_extra_visible_media_or_text_cannot_hide_after_or_between_lists(self):
        for team in PACKAGES:
            raw = self.source(team)['body']
            ending = b'DT Jonah Laulu</strong>' if team == 'LV' else b'DT Dalvin Tomlinson</p>'
            self.assertEqual(raw.count(ending), 1)
            for extra in (b'<div>WR Another Player</div>', b'<img src="extra-inactives.png">',
                          b'<iframe src="extra-list.html"></iframe>', b'<ul><li>WR Another Player</li></ul>'):
                for position, altered in {
                    'after-lists': raw.replace(b'</article>', extra + b'</article>'),
                    'inside-own-list': raw.replace(ending, ending.replace(b'</', extra + b'</', 1)),
                }.items():
                    with self.subTest(team=team, extra=extra, position=position), self.assertRaises(ValueError):
                        self.parse(team, raw=altered)

    def test_source_matchup_period_publication_and_capture_gates_remain_strict(self):
        for team in PACKAGES:
            game = self.packages[team][0]['games'][0]
            wrong_game = dict(game)
            wrong_game['away' if game['home'] == team else 'home'] = 'NE'
            for changes in ({'game': dict(game, week=3)}, {'game': wrong_game},
                            {'source_team': 'NE'}, {'source_url': self.source(team)['url'].replace('week-4', 'week-3')},
                            {'captured_at': '2026-10-04T18:54:00Z'}):
                with self.subTest(team=team, changes=changes), self.assertRaises(ValueError):
                    self.parse(team, **changes)
            for field, value in [('datePublished', '2026-10-03T18:00:00Z'),
                                 ('dateModified', '2026-10-04T20:00:00Z'),
                                 ('dateModified', game['kickoff'])]:
                raw = article_mutation(self.source(team)['body'], lambda article: article.update({field: value}))
                with self.subTest(team=team, field=field, value=value), self.assertRaises(ValueError):
                    self.parse(team, raw=raw)

    def test_legacy_unbound_parser_does_not_bypass_real_club_url_binding(self):
        # The updated named Chargers layout already reaches frozen v8's v2
        # compatibility parser without a source_team. Its legacy result mixes
        # both clubs and the glued heading; it is NOT valid bound-club evidence.
        # Leave that frozen direct API unchanged, and prove the real aggregate
        # rejects this misuse before any parser can consume the club bytes.
        legacy = self.parse('LAC', version=8, source_team=None)
        self.assertEqual(len(legacy['observations']), 14)
        self.assertEqual(legacy['observations'][6]['name'],
                         "Dalvin TomlinsonHere are Seattle's inactives:")
        self.assertEqual(legacy['observations'][7]['name'], 'Jalen Milroe')
        self.assertEqual(self.parse('LAC', source_team=None), legacy)
        with self.assertRaises(ValueError):
            self.parse('LV', source_team=None)
        for team in PACKAGES:
            for primary_is_league in (False, True):
                sources = copy.deepcopy(self.packages[team][1])
                source = next(row for row in sources if row.get('team') == team
                              and row['kind'] == 'official_inactives')
                source['team'] = None
                if primary_is_league:
                    source['url'] = 'https://www.nfl.com/news/fixture-club-redirect'
                with self.subTest(team=team, primary_is_league=primary_is_league):
                    with self.assertRaisesRegex(ValueError, 'allowed official HTTPS URL'):
                        self.build(team, sources=sources)

    def test_late_context_cannot_become_forecast_and_hash_or_identity_failures_remain(self):
        inputs, sources, checked = self.packages['LV']
        forecast = dict(inputs, purpose='forecast')
        forecast.pop('context_identity_evidence', None)
        with self.assertRaisesRegex(ValueError, 'before the T-60 lock'):
            self.build('LV', inputs=forecast)
        corrupt = copy.deepcopy(sources)
        next(source for source in corrupt if source.get('team') == 'LV'
             and source['kind'] == 'official_inactives')['body'] += b' '
        with self.assertRaisesRegex(ValueError, 'hash or size'):
            self.build('LV', sources=corrupt)
        missing = copy.deepcopy(inputs)
        missing['roster'] = [row for row in missing['roster'] if row['gsis_id'] != '00-0039735']
        result = self.build('LV', inputs=missing)['games']['2026_04_KC_LV']['teams']['LV']
        self.assertEqual(result['final_inactives_status'], 'PARTIAL')
        jackson = next(row for row in result['observations'] if row['name'] == 'Jackson Powers-Johnson'
                       and row['source_kind'] == 'official_inactives')
        self.assertEqual(jackson['identity_status'], 'UNRESOLVED')
        self.assertIsNone(jackson['gsis_id'])
        emergency = copy.deepcopy(inputs)
        emergency['expected_qbs']['LV'] = '00-0038579'
        result = self.build('LV', inputs=emergency)['games']['2026_04_KC_LV']
        self.assertEqual(result['teams']['LV']['expected_qb_status'], 'EMERGENCY_QB')
        self.assertEqual(result['qb_gate'], 'BLOCKED_EXPECTED_QB_UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
