import json
from pathlib import Path
import unittest

import pgo_forecast_lab as lab


class PrimaryExplanationTests(unittest.TestCase):
    def test_postseason_explanations_use_saved_rank_terms_dates_and_report_context(self):
        path = Path(__file__).resolve().parents[1] / 'docs/evidence/forecast-lab-2026/september-09-postseason/snapshot.json'
        snapshot = json.loads(path.read_bytes())
        before = path.read_bytes()
        rendered = lab._corrected_section(snapshot, latest_inactive_notes=True)
        self.assertEqual(rendered.count('id="postseason-rating-'), 32)
        self.assertIn('Why does New England rank #6?', rendered)
        self.assertIn('September 9, 2026', rendered)
        self.assertIn('regular season and playoffs', rendered)
        self.assertNotIn('Why does New England rank #1?', rendered)
        self.assertNotIn('id="corrected-rating-', rendered)
        self.assertIn('Report saved with this forecast', rendered)
        self.assertIn('latest-inactive-notes', rendered)
        self.assertIn('What holds this rating back', rendered)
        self.assertIn('did not establish an accuracy improvement', rendered)
        for team in snapshot['teams']:
            card = rendered.split(f'id="postseason-rating-{team["team"]}"', 1)[1].split('</details></details>', 1)[0]
            self.assertIn(f'#{team["rank"]} {team["team"]}', card)
            self.assertIn(f'PGO rating {team["rating"]:+.3f}', card)
            self.assertIn(lab._snapshot_kickoff_time(team['coverage']['captured_at']), card)
        self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
