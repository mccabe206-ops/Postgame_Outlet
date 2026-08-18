"""Tests for recovery.py — injury return-timeline reads (Lane-2, testing).

Deterministic: fixed `today` (preseason vs in-season) and a fixed report date.
"""

import unittest
from datetime import date

import recovery

PRE = date(2026, 8, 18)   # preseason — before Week 1 (~Sep 10)
IN = date(2026, 10, 1)    # in-season


def est(status, body, notes="", start="2026-08-10", today=PRE):
    return recovery.estimate(
        {"status": status, "body_part": body, "notes": notes, "start": start},
        today=today)


class RecoveryTests(unittest.TestCase):
    def test_preseason_pup_not_season_ending(self):
        # The Kittle bug: a carryover Achilles on the preseason PUP list must NOT
        # read "out for the season" — PUP is a recovering designation.
        e = est("PUP", "Achilles", "Surgery")
        self.assertFalse(e["season_ending"])
        self.assertIn("PUP", e["eta"])
        self.assertIn("recovering", e["eta"].lower())
        self.assertIn("Achilles", e["typical"])

    def test_inseason_ir_long_injury_is_season_ending(self):
        e = est("IR", "Knee - ACL", "Surgery", today=IN)
        self.assertTrue(e["season_ending"])
        self.assertIn("season", e["eta"].lower())

    def test_inseason_ir_short_injury_min_4_games(self):
        e = est("IR", "Knee", today=IN)   # generic knee, not season-length
        self.assertFalse(e["season_ending"])
        self.assertIn("4 games", e["eta"])

    def test_acl_beats_generic_knee_priority(self):
        self.assertIn("ACL", est("Out", "Knee - ACL")["label"])

    def test_undisclosed_ir_no_body_match(self):
        e = est("IR", "Undisclosed")
        self.assertEqual(e["confidence"], "rough")
        self.assertEqual(e["label"], "")          # no body-part match
        self.assertIn("IR", e["eta"])

    def test_undisclosed_does_not_match_back(self):
        self.assertNotIn("Back", est("Questionable", "Undisclosed")["label"])

    def test_ribs_plural_matches(self):
        self.assertEqual(est("Out", "Ribs")["label"], "Ribs")

    def test_questionable_is_gametime(self):
        self.assertEqual(est("Questionable", "Hamstring")["eta"], "game-time decision")

    def test_report_age_present(self):
        e = est("Out", "Concussion")               # reported Aug 10, today Aug 18
        self.assertIn("reported", e["text"])
        self.assertTrue(e["reported_ago"])
        self.assertIn("Concussion", e["typical"])

    def test_stale_flag_on_old_report(self):
        e = est("PUP", "Achilles", "Surgery", start="2025-12-01")  # ~8 mo before PRE
        self.assertTrue(e["stale"])
        self.assertIn("mo ago", e["reported_ago"])
        self.assertIn("may be outdated", e["text"])

    def test_no_status_returns_none(self):
        self.assertIsNone(recovery.estimate(
            {"status": "", "body_part": "Knee"}, today=PRE))


if __name__ == "__main__":
    unittest.main()
