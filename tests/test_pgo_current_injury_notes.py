import re
import json
from pathlib import Path
import tempfile
import unittest

import pgo_comparison as comparison


class CurrentInjuryNotesTests(unittest.TestCase):
    source = comparison.HERE / 'research/pgo_opening_night_20260909/injuries/injury-source.json'

    def test_current_notes_preserve_every_saved_projection_byte_and_are_idempotent(self):
        saved = comparison.PUBLIC_OUTPUT.read_text(encoding='utf-8')
        page = comparison.add_current_injury_notes(saved, self.source)
        self.assertEqual(comparison.strip_current_injury_notes(page),
                         comparison.strip_current_injury_notes(saved))
        self.assertEqual(comparison.add_current_injury_notes(page, self.source), page)
        self.assertIsNotNone(comparison._extract_published_fantasy_panel(page))
        for identifier, status in [('00-0040734', 'Game designation: OUT'),
                                   ('00-0040648', 'Game designation: QUESTIONABLE'),
                                   ('00-0033288', 'no final game designation supplied')]:
            row = re.search(r'<tr class="fantasy-row"[^>]*data-player-id="' + identifier +
                            r'"[^>]*>(.*?)</tr>', page, re.S)[1]
            self.assertIn(status, row)
            self.assertIn('Official report</a>', row)
            self.assertNotIn('Final inactives pending.', row)
        self.assertIn('points and league values have not been recalculated', page)

    def test_official_inactive_news_preserves_emergency_qb_language_and_saved_values(self):
        data = json.loads(self.source.read_bytes())
        data['source_as_of'] = '2026-09-09T22:53:00Z'
        for source in data['team_sources']:
            if source['team'] in ('NE', 'SEA'):
                source.update(source_kind='official_news', captured_at='2026-09-09T22:52:00Z',
                              source_url='https://example.com/final-inactives')
        data['players'] = [p for p in data['players'] if p['team'] not in ('NE', 'SEA')]
        notes = [('NE', '00-0040734', 'TreVeyon Henderson', 'RB', 'Inactive for Week 1'),
                 ('SEA', 'emergency-qb-fixture', 'Emergency QB', 'QB',
                  'Inactive except as emergency third quarterback <not ordinary OUT>')]
        for team, identifier, name, position, text in notes:
            data['players'].append(dict(team=team, gsis_id=identifier, player=name, position=position,
                source_url='https://example.com/final-inactives', availability_text=text))
        saved = comparison.PUBLIC_OUTPUT.read_text(encoding='utf-8')
        extra = ('<tr class="fantasy-row" data-team="SEA" data-player-id="emergency-qb-fixture" '
                 'data-base-points="1.25" data-inactive="false"><th class="fantasy-player">'
                 'Emergency QB</th><td>1.25</td></tr>')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'final-inactives.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            page = comparison.add_current_injury_notes(saved, path)
            self.assertEqual(comparison.strip_current_injury_notes(page),
                             comparison.strip_current_injury_notes(saved))
            self.assertIsNotNone(comparison._extract_published_fantasy_panel(page))
            henderson = re.search(r'<tr class="fantasy-row"[^>]*data-player-id="00-0040734"[^>]*>(.*?)</tr>', page, re.S)[1]
            self.assertIn('Inactive for Week 1', henderson)
            self.assertIn('datetime="2026-09-09T22:52:00Z"', henderson)
            self.assertNotIn('Final inactives pending', page)
            qb_page = '<section id="panel-fantasy">' + extra + '</section>'
            annotated = comparison.add_current_injury_notes(qb_page, path)
            self.assertIn('emergency third quarterback &lt;not ordinary OUT&gt;', annotated)
            self.assertNotIn('Game designation: OUT', annotated)
            self.assertEqual(comparison.strip_current_injury_notes(annotated), qb_page)
            self.assertEqual(comparison.add_current_injury_notes(annotated, path), annotated)
            wrong_team = qb_page.replace('data-team="SEA"', 'data-team="NE"')
            self.assertEqual(comparison.add_current_injury_notes(wrong_team, path), wrong_team)

    def test_identity_requires_same_team_and_unknown_players_are_not_declared_healthy(self):
        row = ('<tr class="fantasy-row" data-team="BUF" data-player-id="00-0040734">'
               '<th scope="row" class="fantasy-player">Different team</th><td>11.4</td></tr>')
        page = '<section id="panel-fantasy">' + row + '</section>'
        self.assertEqual(comparison.add_current_injury_notes(page, self.source), page)

    def test_source_capture_cannot_follow_the_saved_snapshot(self):
        data = json.loads(self.source.read_bytes())
        next(row for row in data['team_sources'] if row['team'] == 'NE')['captured_at'] = '2027-01-01T00:00:00Z'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'invalid.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'later than the injury snapshot'):
                comparison.add_current_injury_notes(comparison.PUBLIC_OUTPUT.read_text(encoding='utf-8'), path)


if __name__ == '__main__':
    unittest.main()
