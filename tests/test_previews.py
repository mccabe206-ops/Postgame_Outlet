import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import previews  # noqa: E402

READY = """---
game_id: 401
status: ready
written_at: 2026-11-18T15:00Z
kickoff: 2026-11-20T01:15Z
away: Indianapolis Colts
home: Houston Texans
away_abbr: IND
home_abbr: HOU
market_at_write: -12.5
our_line_at_write: -9.0
edge_at_write: -3.5
away_qb: Daniel Jones
away_qb_value: -2.0
home_qb: C.J. Stroud
home_qb_value: 1.8
hfa: 2.0
---
## Why the number
Our number is **HOU -9**.

## Assumptions
- OUT: IND 1st string CB Sauce Gardner

## Situational
- Divisional game.

## Updates
"""

PAGE = ('<div class="tabs"><button data-panel="comparison">PGO Model</button>'
        '\n  </div><section id="panel-method"></section><!-- /panel-method -->\n  <x>')


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(previews, "PREVIEWS_DIR", self.tmp.name)
        p.start()
        self.addCleanup(p.stop)
        os.makedirs(previews.week_dir(2026, 11))

    def write(self, name, text):
        with open(os.path.join(previews.week_dir(2026, 11), name), "w") as f:
            f.write(text)

    def test_parse_and_gate(self):
        p = previews.parse(READY)
        self.assertEqual(p["meta"]["market_at_write"], -12.5)
        self.assertEqual(p["meta"]["away_qb"], "Daniel Jones")
        self.assertTrue(previews.is_ready(p))
        draft = previews.parse(READY.replace("Our number", previews.DRAFT_MARKER + " -->Our number"))
        self.assertIn("write-up still a draft", previews.gate_problems(draft))
        self.assertFalse(previews.is_ready(draft))

    def test_drafts_never_publish(self):
        self.write("IND-HOU.md", READY.replace("status: ready", "status: draft"))
        self.assertIsNone(previews.latest_week())
        self.assertEqual(previews.inject_panel(PAGE), PAGE)
        self.assertEqual(previews.at_write_lines(2026, 11), {})

    def test_inject_is_idempotent_and_shows_bet(self):
        self.write("IND-HOU.md", READY)
        self.write("bets.json", '{"bets": {"401": {"side": "away", "confidence": 4, "market_at_pick": -12.5}}}')
        once = previews.inject_panel(PAGE, {"season_record": {}})
        self.assertIn('id="tab-previews"', once)
        self.assertIn("McCabe Bet: IND +12.5", once)
        self.assertIn("HOU -9", once)
        self.assertEqual(previews.inject_panel(once, {"season_record": {}}), once)
        self.assertEqual(previews.at_write_lines(2026, 11), {"401": (-12.5, -9.0)})

    def test_unresolved_check_blocks_ready(self):
        p = previews.parse(READY.replace("- OUT: IND 1st string CB Sauce Gardner",
                                         "- CHECK: IND 1st string CB Sauce Gardner is Questionable"))
        self.assertIn("unresolved CHECK in assumptions", previews.gate_problems(p))

    def test_line_if_wrong(self):
        snap = {"home_total": 2.6, "away_total": -4.5, "hfa": 2.0}
        self.assertEqual(previews._line_if(snap, "home", 0.3), -9.5)
        self.assertEqual(previews._line_if(snap, "away", 3.5), -5.5)

    def test_newest_week_first_older_weeks_one_click_away(self):
        self.write("IND-HOU.md", READY)
        os.makedirs(previews.week_dir(2026, 12))
        with open(os.path.join(previews.week_dir(2026, 12), "IND-HOU.md"), "w") as f:
            f.write(READY.replace("game_id: 401", "game_id: 402"))
        out = previews.inject_panel(PAGE, {"season_record": {}})
        self.assertIn('data-week="2026-12" aria-pressed="true"', out)
        self.assertIn('<div class="gp-week" data-week="2026-11" hidden>', out)
        self.assertLess(out.index("Week 12 Game Previews"), out.index("Week 11 Game Previews"))
        self.assertIn("began in Week 11", out)

    def test_fmt_line(self):
        self.assertEqual(previews.fmt_line(-6.5, "HOU", "IND"), "HOU -6.5")
        self.assertEqual(previews.fmt_line(3.0, "HOU", "IND"), "IND -3")
        self.assertEqual(previews.fmt_line(0.0, "HOU", "IND"), "PK")


if __name__ == "__main__":
    unittest.main()
