"""Tests for recovery.py — injury return-timeline estimates (Lane-2, testing).

Deterministic: fixed `today` and a fixed injury `start` date so no wall-clock.
"""

import unittest
from datetime import date

import recovery

TODAY = date(2026, 8, 18)


def est(status, body, notes="", start="2026-08-10"):
    return recovery.estimate(
        {"status": status, "body_part": body, "notes": notes, "start": start},
        today=TODAY)


class RecoveryTests(unittest.TestCase):
    def test_acl_surgery_season_ending(self):
        e = est("PUP", "Knee - ACL", "Surgery")
        self.assertTrue(e["season_ending"])
        self.assertIn("ACL", e["label"])
        self.assertEqual(e["eta"], "out for the season")
        self.assertIn("mo", e["duration"])          # long recovery expressed in months

    def test_acl_beats_generic_knee_priority(self):
        e = est("Out", "Knee - ACL")
        self.assertIn("ACL", e["label"])             # specific diagnosis, not "Knee"

    def test_high_ankle_not_season_ending(self):
        e = est("Out", "High ankle")
        self.assertFalse(e["season_ending"])
        self.assertEqual(e["label"], "High-ankle sprain")
        self.assertIsNotNone(e["week_low"])

    def test_undisclosed_ir_status_fallback(self):
        e = est("IR", "Undisclosed")
        self.assertEqual(e["confidence"], "rough")
        self.assertIn("IR", e["label"])

    def test_undisclosed_does_not_match_back(self):
        # 'disc' is a substring of 'undisclosed' — word-boundary match must not fire.
        e = est("Questionable", "Undisclosed")
        self.assertNotIn("Back", e["label"])

    def test_ribs_plural_matches(self):
        self.assertEqual(est("Out", "Ribs")["label"], "Ribs")

    def test_surgery_variant_preferred(self):
        e = est("PUP", "Foot", "Surgery")
        self.assertIn("surgery", e["label"].lower())

    def test_achilles_surgery_out_for_season(self):
        self.assertTrue(est("IR", "Achilles", "Surgery")["season_ending"])

    def test_no_status_returns_none(self):
        self.assertIsNone(recovery.estimate(
            {"status": "", "body_part": "Knee"}, today=TODAY))

    def test_anchor_prefers_start_date(self):
        e = est("Out", "Hamstring")
        self.assertEqual(e["anchor_kind"], "start")
        self.assertEqual(e["anchor"], "2026-08-10")

    def test_text_is_present_and_labeled(self):
        e = est("Out", "Concussion")
        self.assertIn("typical", e["text"])
        self.assertIn("Concussion", e["text"])


if __name__ == "__main__":
    unittest.main()
