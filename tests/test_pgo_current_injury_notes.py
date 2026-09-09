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
        self.assertEqual(comparison.strip_current_injury_notes(page), saved)
        self.assertEqual(comparison.add_current_injury_notes(page, self.source), page)
        self.assertIsNotNone(comparison._extract_published_fantasy_panel(page))
        for identifier, status in [('00-0040734', 'Game designation: OUT'),
                                   ('00-0040648', 'Game designation: QUESTIONABLE'),
                                   ('00-0033288', 'no final game designation supplied')]:
            row = re.search(r'<tr class="fantasy-row"[^>]*data-player-id="' + identifier +
                            r'"[^>]*>(.*?)</tr>', page, re.S)[1]
            self.assertIn(status, row)
            self.assertIn('Official report</a>', row)
            self.assertIn('Final inactives pending.', row)
        self.assertIn('points and league values have not been recalculated', page)

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
