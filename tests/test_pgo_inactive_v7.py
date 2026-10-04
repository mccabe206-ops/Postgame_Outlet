"""New captures understand observed Week 4 layouts; prior packages stay frozen."""
import gzip
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import pgo_season_availability as availability


ROOT = Path(__file__).resolve().parents[1] / 'docs/evidence/season-2026/availability-v2'
PACKAGES = {
    'ARI': '20261004T165040655301Z', 'HOU': '20261004T165041499152Z',
    'JAX': '20261004T165043757132Z', 'PHI': '20261004T165045264473Z',
    'NYJ': '20261004T165047724375Z',
}


def package(team):
    root = ROOT / PACKAGES[team]
    inputs = json.loads(gzip.decompress((root / 'inputs.json.gz').read_bytes()))
    capture = json.loads((root / 'capture.json').read_bytes())
    sources = [dict(s, body=gzip.decompress((root / s['file']).read_bytes()))
               if 'file' in s else dict(s) for s in capture['sources']]
    return inputs, sources, capture['checked_at']


def parse(team, source_team=None, target=None, raw=None, version=7):
    inputs, sources, checked = package(team)
    source = next(s for s in sources if s['kind'] == 'official_inactives'
                  and s.get('team') == (source_team or team))
    return availability.parse_final_inactives(
        source['body'] if raw is None else raw, inputs['games'][0], target or team,
        source['captured_at'], parser_version=version,
        source_team=source['team'], source_url=source['url'])


class InactiveV7Tests(unittest.TestCase):
    def test_legacy_compact_club_and_nfl_matchup_articles_remain_supported(self):
        from tests.test_pgo_season_availability import SeasonAvailabilityTests
        fixture = SeasonAvailabilityTests(); fixture.setUp()
        for source_team, url in [('NE', 'https://www.patriots.com/news/week-2-inactives'),
                                 (None, 'https://www.nfl.com/news/week-2-patriots-seahawks-inactives')]:
            with self.subTest(source_team=source_team):
                result = availability.parse_final_inactives(fixture.article().encode(), fixture.game, 'NE',
                    fixture.now, parser_version=7, source_team=source_team, source_url=url)
                self.assertEqual(len(result['observations']), 2)
                self.assertEqual(result['observations'][1]['status'], 'EMERGENCY_QB')
                for raw in [fixture.article(headline='Week 1 Inactives: Patriots at Seahawks'),
                            fixture.article(published='2026-09-20T16:30:00Z')]:
                    with self.assertRaises(ValueError):
                        availability.parse_final_inactives(raw.encode(), fixture.game, 'NE', fixture.now,
                            parser_version=7, source_team=source_team, source_url=url)

    def test_v7_forecast_uses_new_layout_without_context_aliases(self):
        inputs, sources, checked = package('JAX')
        inputs.update(parser_version=7, purpose='forecast')
        inputs.pop('context_identity_evidence', None)
        inputs['games'][0].update(kickoff='2026-10-04T18:00:00Z', lock_at='2026-10-04T17:00:00Z')
        result = availability.build_availability(**inputs, sources=sources, checked_at=checked)
        team = next(iter(result['games'].values()))['teams']['JAX']
        rows = [r for r in team['observations'] if r['source_kind'] == 'official_inactives']
        self.assertEqual(len(rows), 7)
        row = next(r for r in rows if r['name'] == 'CJ Williams')
        self.assertEqual(row['identity_status'], 'UNRESOLVED')
        self.assertNotIn('identity_binding', row)
        self.assertEqual(team['final_inactives_status'], 'PARTIAL')

    def test_observed_club_layouts_keep_exact_team_boundaries(self):
        cases = [('HOU', 'HOU', 5, 'Nate Thomas'),
                 ('JAX', 'JAX', 7, 'CJ Williams'),
                 ('PHI', 'PHI', 8, 'Lane Johnson'),
                 ('NYJ', 'NYJ', 7, 'Kiko Mauigoa'),
                 ('NYJ', 'CHI', 6, 'Caleb Williams')]
        for source_team, target, count, wanted in cases:
            with self.subTest(team=target):
                try:
                    result = parse(source_team, target=target)
                except ValueError as error:
                    self.fail(f'Observed complete club list rejected: {error}')
                rows = result['observations']
                self.assertEqual(len(rows), count)
                self.assertIn(wanted, [r['name'] for r in rows])
                self.assertFalse(result['unparsed_lines'])
                self.assertFalse(any('|' in r['name'] for r in rows))
                if target == 'PHI':
                    self.assertNotIn('Aaron Donald', [r['name'] for r in rows])

    def test_empty_identified_ad_between_nfl_card_and_lists_is_bounded(self):
        inputs, sources, checked = package('NYJ')
        source = next(s for s in sources if s['kind'] == 'official_inactives' and s.get('team') is None)
        raw = source['body']
        for team, count in [('NYJ', 7), ('CHI', 6)]:
            with self.subTest(team=team):
                try:
                    result = availability.parse_final_inactives(raw, inputs['games'][0], team,
                        source['captured_at'], parser_version=7, source_url=source['url'])
                except ValueError as error:
                    self.fail(f'Exact matchup separated by empty ad rejected: {error}')
                self.assertEqual(len(result['observations']), count)
        ads = re.findall(rb'<div id="ad-slot-[^"]+"></div>', raw[:raw.index(b'<h3>JETS</h3>')])
        self.assertTrue(ads, 'Saved matchup has an explicit empty advertisement')
        marker = ads[-1]
        for replacement in [marker.replace(b'></div>', b'>Unrelated player news</div>'),
                            marker.replace(b'ad-slot-', b'unknown-slot-'),
                            marker.replace(b'></div>', b'><a href="/teams/other">other</a></div>')]:
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                availability.parse_final_inactives(raw.replace(marker, replacement), inputs['games'][0], 'CHI',
                    source['captured_at'], parser_version=7, source_url=source['url'])

    def test_new_contexts_retain_identity_and_source_disagreements(self):
        from pgo_inactive_names_v7 import capture_evidence
        expected = {'ARI': 'PARTIAL', 'NYG': 'VERIFIED_LIST', 'HOU': 'PARTIAL', 'JAX': 'VERIFIED_LIST',
                    'PHI': 'PARTIAL', 'NYJ': 'VERIFIED_LIST', 'CHI': 'VERIFIED_LIST'}
        for team in PACKAGES:
            inputs, sources, checked = package(team)
            inputs.update(parser_version=7, context_identity_evidence=capture_evidence(inputs['games']))
            result = availability.build_availability(**inputs, sources=sources, checked_at=checked)
            actual = next(iter(result['games'].values()))['teams']
            for target in ({'NYJ', 'CHI'} if team == 'NYJ' else {'ARI', 'NYG'} if team == 'ARI' else {team}):
                with self.subTest(team=target):
                    self.assertEqual(actual[target]['final_inactives_status'], expected[target])
                    if target in ('ARI', 'HOU', 'PHI'):
                        self.assertTrue(any('Conflicting official inactive lists' in e
                                            for e in actual[target]['source_errors']))
            if team == 'NYJ':
                self.assertEqual(actual['CHI']['expected_qb_status'], 'INACTIVE')
                self.assertIn('Caleb Williams is INACTIVE', next(iter(result['games'].values()))['blocked_reason'])

    def test_v6_packages_still_replay_their_original_partial_and_unknown_results(self):
        for team in PACKAGES:
            with self.subTest(team=team):
                root = ROOT / PACKAGES[team]
                saved = json.loads((root / 'availability.json').read_bytes())
                self.assertEqual(availability.load_availability(root), saved)
                self.assertEqual(saved['parser_version'], 6)

    def test_context_identity_evidence_cannot_enter_a_v7_forecast(self):
        inputs, sources, checked = package('HOU')
        inputs.update(parser_version=7, purpose='forecast', context_identity_evidence={})
        with self.assertRaisesRegex(ValueError, 'context-only|context identity'):
            availability.build_availability(**inputs, sources=sources, checked_at=checked)

    def test_unadmitted_alias_or_position_cannot_imply_source_agreement(self):
        from pgo_inactive_names_v7 import capture_evidence
        inputs, sources, checked = package('HOU')
        inputs.update(parser_version=7, context_identity_evidence=capture_evidence(inputs['games']))
        original = availability.parse_final_inactives
        for name, position, status in [('Nate Thomas', 'OT', 'VERIFIED_LIST'),
                                       ('Nate Thomas Jr', 'OT', 'PARTIAL'),
                                       ('Nate Thomas', 'RB', 'PARTIAL')]:
            def altered(*args, **kwargs):
                parsed = original(*args, **kwargs)
                if args[2] == 'HOU' and kwargs.get('source_team') is None:
                    for row in parsed['observations']:
                        if row['name'] == 'Nate Tomas':
                            row.update(name=name, position=position)
                return parsed
            with self.subTest(name=name, position=position), patch.object(
                    availability, 'parse_final_inactives', side_effect=altered):
                result = availability.build_availability(**inputs, sources=sources, checked_at=checked)
                team = next(iter(result['games'].values()))['teams']['HOU']
                self.assertEqual(team['final_inactives_status'], status)
                conflicts = [e for e in team['source_errors'] if 'Conflicting official inactive lists' in e]
                if status == 'PARTIAL':
                    self.assertTrue(any('only [' + name + ']' in e for e in conflicts))
                else:
                    self.assertEqual(conflicts, [])

    def test_wrong_matchup_period_clock_or_jersey_column_stays_rejected(self):
        inputs, sources, checked = package('PHI')
        source = next(s for s in sources if s.get('team') == 'PHI' and s['kind'] == 'official_inactives')
        for changes in [dict(week=3), dict(home='DAL')]:
            game = dict(inputs['games'][0], **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                availability.parse_final_inactives(source['body'], game, 'PHI', source['captured_at'],
                    parser_version=7, source_team='PHI', source_url=source['url'])
        with self.assertRaises(ValueError):
            parse('PHI', raw=source['body'].replace(b'Lane Johnson | 65', b'Lane Johnson | unavailable'))
        with self.assertRaises(ValueError):
            availability.parse_final_inactives(source['body'], inputs['games'][0], 'PHI', '2026-10-04T14:00:00Z',
                parser_version=7, source_team='PHI', source_url=source['url'])
