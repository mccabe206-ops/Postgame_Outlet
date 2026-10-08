"""Observed LV prose and LAC footer support must not reinterpret v7 evidence."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import re
import unittest

import pgo_season_availability as availability


PACKAGE = (Path(__file__).resolve().parents[1]
           / 'docs/evidence/season-2026/availability-v2/20261004T185732569517Z')
HASHES = {
    'LAC': '12e2872ba5a3a17e3c3f30e0a751bc7353b92d216ac8301cd8b89259204b94ed',
    'LV': 'ded6522434670b34230c8597a36d2dd1be5a65caee45701d27fdd68a6a1d5b59',
}
EXPECTED = {
    'LAC': [
        ('Derwin James', 'S', 'INACTIVE'),
        ('DJ Uiagalelei', 'QB', 'EMERGENCY_QB'),
        ('Alex Harkey', 'OL', 'INACTIVE'),
        ('Kayode Awosika', 'G', 'INACTIVE'),
        ('Charlie Kolar', 'TE', 'INACTIVE'),
        ('Brenen Thompson', 'WR', 'INACTIVE'),
        ('Dalvin Tomlinson', 'DT', 'INACTIVE'),
    ],
    'LV': [
        ("Aidan O'Connell", 'QB', 'EMERGENCY_QB'),
        ('Darrell Luter Jr.', 'CB', 'INACTIVE'),
        ('Tristin McCollum', 'S', 'INACTIVE'),
        ('Jackson Powers-Johnson', 'G/C', 'INACTIVE'),
        ('Jonah Laulu', 'DT', 'INACTIVE'),
    ],
}
LV_HEADING = "Before kickoff, here are the inactive players for today's game:"
LAC_FOOTER = "This will be updated with Seattle's inactives."
SCRIPT = re.compile(
    r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)


def package():
    inputs = json.loads(gzip.decompress((PACKAGE / 'inputs.json.gz').read_bytes()))
    capture = json.loads((PACKAGE / 'capture.json').read_bytes())
    sources = [dict(source, body=gzip.decompress((PACKAGE / source['file']).read_bytes()))
               if 'file' in source else dict(source) for source in capture['sources']]
    return inputs, sources, capture['checked_at']


def article_mutation(raw, change):
    """Alter only the unique structured article; leave visible DOM untouched."""
    text = raw.decode('utf-8')
    found = []
    for match in SCRIPT.finditer(text):
        value = json.loads(match[1])
        for item in value if isinstance(value, list) else [value]:
            if (isinstance(item, dict) and item.get('@type') in ('NewsArticle', 'Article')
                    and item.get('articleBody')):
                found.append((match, value, item))
    if len(found) != 1:
        raise AssertionError('Saved fixture must have exactly one structured article')
    match, value, item = found[0]
    change(item)
    return (text[:match.start(1)] + json.dumps(value, ensure_ascii=False)
            + text[match.end(1):]).encode('utf-8')


class InactiveV8Tests(unittest.TestCase):
    def setUp(self):
        self.inputs, self.sources, self.checked = package()

    def source(self, team):
        return next(source for source in self.sources
                    if source['kind'] == 'official_inactives' and source.get('team') == team)

    def game(self, team):
        return next(game for game in self.inputs['games'] if team in (game['away'], game['home']))

    def parse(self, team, *, raw=None, version=8, **changes):
        source = self.source(team)
        kwargs = dict(parser_version=version, source_team=team, source_url=source['url'])
        game = changes.pop('game', self.game(team))
        target = changes.pop('target', team)
        captured = changes.pop('captured_at', source['captured_at'])
        kwargs.update(changes)
        return availability.parse_final_inactives(
            source['body'] if raw is None else raw, game, target, captured, **kwargs)

    def altered(self, team, transform):
        return article_mutation(self.source(team)['body'],
                                lambda article: article.update(articleBody=transform(article['articleBody'])))

    def build(self, *, inputs=None, sources=None, checked=None):
        inputs = dict(self.inputs if inputs is None else inputs, parser_version=8)
        return availability.build_availability(
            **inputs, sources=self.sources if sources is None else sources,
            checked_at=self.checked if checked is None else checked)

    def test_observed_articles_keep_exact_names_positions_and_emergency_status(self):
        for team in EXPECTED:
            with self.subTest(team=team):
                source = self.source(team)
                self.assertEqual(hashlib.sha256(source['body']).hexdigest(), HASHES[team])
                parsed = self.parse(team)
                self.assertEqual([(row['name'], row['position'], row['status'])
                                  for row in parsed['observations']], EXPECTED[team])
                self.assertEqual(parsed['unparsed_lines'], [])
                self.assertNotIn('Ladd McConkey', [row['name'] for row in parsed['observations']])
                self.assertTrue(all('identity_binding' not in row for row in parsed['observations']))
        jackson = self.parse('LV')['observations'][3]
        self.assertEqual(jackson['source_text'], 'G/C Jackson Powers-Johnson')

    def test_v7_still_rejects_new_layouts_and_replays_entire_saved_package(self):
        for team in EXPECTED:
            with self.subTest(team=team), self.assertRaises(ValueError):
                self.parse(team, version=7)
        saved = json.loads((PACKAGE / 'availability.json').read_bytes())
        self.assertEqual(saved['parser_version'], 7)
        self.assertEqual(availability.load_availability(PACKAGE), saved)
        self.assertEqual(saved['games']['2026_04_KC_LV']['teams']['LV']['final_inactives_status'], 'UNKNOWN')
        self.assertEqual(saved['games']['2026_04_LAC_SEA']['teams']['LAC']['final_inactives_status'], 'UNKNOWN')

    def test_new_replay_changes_only_supported_teams_without_retiming_or_aliases(self):
        inputs_before = copy.deepcopy(self.inputs)
        sources_before = copy.deepcopy(self.sources)
        saved = json.loads((PACKAGE / 'availability.json').read_bytes())
        rebuilt = self.build()
        self.assertEqual(rebuilt['parser_version'], 8)
        for key in ('checked_at', 'purpose', 'policy', 'schema_version', 'sources'):
            self.assertEqual(rebuilt[key], saved[key], key)
        for game_id, old_game in saved['games'].items():
            game = rebuilt['games'][game_id]
            affected = set(old_game['teams']) & set(EXPECTED)
            if not affected:
                self.assertEqual(game, old_game)
                continue
            for key in old_game.keys() - {'teams', 'summary'}:
                self.assertEqual(game[key], old_game[key], (game_id, key))
            for team, old_team in old_game['teams'].items():
                if team not in affected:
                    # Rejected opponent-source diagnostics may describe the new format.
                    for key in old_team.keys() - {'source_errors'}:
                        self.assertEqual(game['teams'][team][key], old_team[key], (team, key))
                    continue
                current = game['teams'][team]
                self.assertEqual(current['final_inactives_status'], 'VERIFIED_LIST')
                self.assertEqual(current['expected_qb_status'], old_team['expected_qb_status'])
                rows = [row for row in current['observations'] if row['source_kind'] == 'official_inactives']
                self.assertEqual([(row['name'], row['position'], row['status']) for row in rows], EXPECTED[team])
                source = self.source(team)
                for row in rows:
                    self.assertEqual(row['identity_status'], 'RESOLVED')
                    self.assertEqual(row['captured_at'], source['captured_at'])
                    self.assertEqual(row['source_sha256'], HASHES[team])
                    self.assertEqual(row['source_url'], source['url'])
                    self.assertNotIn('identity_binding', row)
        self.assertEqual(self.inputs, inputs_before)
        self.assertEqual(self.sources, sources_before)

    def test_new_headings_cannot_reassign_an_opponent_or_unbound_source(self):
        for team in EXPECTED:
            game = self.game(team)
            opponent = game['home'] if game['away'] == team else game['away']
            for changes in ({'target': opponent}, {'source_team': opponent},
                            {'source_team': None}, {'source_team': 'NE'}):
                with self.subTest(team=team, changes=changes), self.assertRaises(ValueError):
                    self.parse(team, **changes)

    def test_lv_duplicate_heading_unknown_row_and_bad_composite_are_rejected(self):
        transforms = [
            lambda body: body + '\n\n' + body[body.index(LV_HEADING):],
            lambda body: body.replace(LV_HEADING, LV_HEADING + '\n\n' + LV_HEADING),
            lambda body: body.replace('CB Darrell Luter Jr.', 'XX Mystery Player\n\nCB Darrell Luter Jr.'),
            lambda body: body.replace('G/C Jackson', 'G//C Jackson'),
            lambda body: body.replace('G/C Jackson', 'G/XX Jackson'),
            lambda body: body.replace('G/C Jackson', 'QB/C Jackson'),
        ]
        for number, transform in enumerate(transforms):
            with self.subTest(case=number), self.assertRaises(ValueError):
                self.parse('LV', raw=self.altered('LV', transform))

    def test_jsonld_cannot_silently_drop_players_still_in_the_visible_list(self):
        for team, row in [('LV', 'G/C Jackson Powers-Johnson'), ('LAC', 'DT Dalvin Tomlinson')]:
            with self.subTest(team=team), self.assertRaises(ValueError):
                self.parse(team, raw=self.altered(team, lambda body: body.replace(row, '', 1)))

    def test_extra_visible_dom_rows_cannot_be_ignored_outside_paragraphs(self):
        for team in EXPECTED:
            raw = self.source(team)['body']
            for extra in (b'<div>WR Another Player</div>', b'WR Another Player',
                          b'<ul><li>WR Another Player</li></ul>'):
                with self.subTest(team=team, extra=extra), self.assertRaises(ValueError):
                    self.parse(team, raw=raw.replace(b'</article>', extra + b'</article>'))

    def test_visible_media_cannot_hide_extra_entries_after_heading_or_inside_rows(self):
        endings = {'LV': b'DT Jonah Laulu</strong>', 'LAC': b'DT Dalvin Tomlinson</p>'}
        media = (b'<img src="extra-inactives.png">', b'<svg><image href="list.png"/></svg>',
                 b'<iframe src="list.html"></iframe>', b'<object data="list.pdf"></object>',
                 b'<canvas></canvas>', b'<picture><img src="list.png"></picture>',
                 b'<video src="list.mp4"></video>', b'<audio src="list.mp3"></audio>',
                 b'<embed src="list.pdf">', b'<input value="WR Another Player">')
        for team in EXPECTED:
            raw = self.source(team)['body']
            ending = endings[team]
            self.assertEqual(raw.count(ending), 1)
            for extra in media:
                variants = {
                    'after-list': raw.replace(b'</article>', extra + b'</article>'),
                    'inside-row': raw.replace(ending, ending.replace(b'</', extra + b'</', 1)),
                }
                for place, altered in variants.items():
                    with self.subTest(team=team, place=place, extra=extra), self.assertRaises(ValueError):
                        self.parse(team, raw=altered)

    def test_lac_footer_must_be_exact_terminal_and_for_this_opponent(self):
        replacements = [
            LAC_FOOTER + '\nQB Another Player',
            LAC_FOOTER + ' RB Another Player',
            LAC_FOOTER + 'Unexpected update.',
            "This will be updated with Denver's inactives.",
            "This might be updated with Seattle's inactives.",
            LAC_FOOTER + '\n' + LAC_FOOTER,
        ]
        for replacement in replacements:
            with self.subTest(footer=replacement), self.assertRaises(ValueError):
                self.parse('LAC', raw=self.altered('LAC', lambda body: body.replace(LAC_FOOTER, replacement)))

    def test_chargers_marketing_widget_requires_exact_destination_and_terminal_position(self):
        raw = self.source('LAC')['body']
        widgets = re.findall(rb'<iframe\b[^>]*>.*?</iframe>', raw, re.S)
        self.assertEqual(len(widgets), 1)
        widget = widgets[0]
        without = raw.replace(widget, b'')
        self.assertEqual(len(self.parse('LAC', raw=without)['observations']), 7)
        alterations = {
            'wrong-destination': widget.replace(b'chargers.formstack.com', b'other.example'),
            'changed-id': widget.replace(b'id="/sofi_interest_', b'id="/other_interest_'),
            'src': widget.replace(b'<iframe ', b'<iframe src="extra-list.html" '),
            'srcdoc': widget.replace(b'<iframe ', b'<iframe srcdoc="WR Another Player" '),
            'duplicate-attribute': widget.replace(b'<iframe ', b'<iframe title="Formstack content" '),
            'iframe-text': widget.replace(b'</iframe>', b'WR Another Player</iframe>'),
            'iframe-nested-content': widget.replace(b'</iframe>', b'<img src="list.png"></iframe>'),
            'missing-close': widget.replace(b'</iframe>', b''),
        }
        for case, altered in alterations.items():
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.parse('LAC', raw=raw.replace(widget, altered))
        footer = b'<p>' + LAC_FOOTER.encode()
        self.assertEqual(without.count(footer), 1)
        for case, altered in {
            'before-footer': without.replace(footer, widget + footer),
            'inside-row': without.replace(b'DT Dalvin Tomlinson</p>', b'DT Dalvin Tomlinson' + widget + b'</p>'),
            'second-widget': raw.replace(widget, widget + widget),
        }.items():
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.parse('LAC', raw=altered)
        with self.assertRaises(ValueError):
            self.parse('LV', raw=self.source('LV')['body'].replace(b'</article>', widget + b'</article>'))

    def test_new_formats_still_reject_declared_count_mismatch(self):
        for team, count in [('LV', 'Six'), ('LAC', 'Eight')]:
            raw = article_mutation(self.source(team)['body'], lambda article: article.update(
                headline=article['headline'].replace('Week 4 Inactives', f'Week 4 {count} Inactives')))
            with self.subTest(team=team), self.assertRaises(ValueError):
                self.parse(team, raw=raw)

    def test_matchup_week_source_period_and_article_clocks_remain_required(self):
        for team in EXPECTED:
            source = self.source(team)
            game = self.game(team)
            wrong_game = dict(game)
            wrong_game['away' if game['home'] == team else 'home'] = 'NE'
            for changes in ({'game': dict(game, week=3)}, {'game': wrong_game},
                            {'source_url': source['url'].replace('week-4', 'week-3')},
                            {'captured_at': '2026-10-04T18:54:00Z'}):
                with self.subTest(team=team, changes=changes), self.assertRaises(ValueError):
                    self.parse(team, **changes)
            for field, value in [('datePublished', '2026-10-03T18:00:00Z'),
                                 ('dateModified', '2026-10-04T19:00:00Z'),
                                 ('datePublished', game['kickoff'])]:
                raw = article_mutation(source['body'], lambda article: article.update({field: value}))
                with self.subTest(team=team, field=field, value=value), self.assertRaises(ValueError):
                    self.parse(team, raw=raw)

    def test_build_keeps_source_hash_order_and_forecast_cutoff_gates(self):
        corrupted = copy.deepcopy(self.sources)
        next(source for source in corrupted if source.get('team') == 'LV'
             and source['kind'] == 'official_inactives')['body'] += b' '
        with self.assertRaisesRegex(ValueError, 'hash or size'):
            self.build(sources=corrupted)
        with self.assertRaisesRegex(ValueError, 'timestamps are out of order'):
            self.build(checked='2026-10-04T18:54:00Z')
        with self.assertRaisesRegex(ValueError, 'before the T-60 lock'):
            self.build(checked='2026-10-04T19:05:00Z')

    def test_missing_identity_stays_partial_and_emergency_expected_qb_stays_blocked(self):
        inputs = copy.deepcopy(self.inputs)
        inputs['roster'] = [row for row in inputs['roster'] if row['gsis_id'] != '00-0039735']
        result = self.build(inputs=inputs)
        team = result['games']['2026_04_KC_LV']['teams']['LV']
        self.assertEqual(team['final_inactives_status'], 'PARTIAL')
        jackson = next(row for row in team['observations'] if row['name'] == 'Jackson Powers-Johnson'
                       and row['source_kind'] == 'official_inactives')
        self.assertEqual(jackson['identity_status'], 'UNRESOLVED')
        self.assertIsNone(jackson['gsis_id'])
        self.assertNotIn('identity_binding', jackson)
        inputs = copy.deepcopy(self.inputs)
        inputs['expected_qbs']['LV'] = '00-0038579'
        result = self.build(inputs=inputs)['games']['2026_04_KC_LV']
        self.assertEqual(result['teams']['LV']['expected_qb_status'], 'EMERGENCY_QB')
        self.assertEqual(result['qb_gate'], 'BLOCKED_EXPECTED_QB_UNAVAILABLE')
        self.assertIn("Aidan O'Connell is EMERGENCY_QB", result['blocked_reason'])


if __name__ == '__main__':
    unittest.main()
