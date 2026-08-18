"""Tests for the injury -> ratings-workflow integration (Lane-2, testing branch).

Covers team_view._rating_signal (the soft qualitative injury flags) and the
team_notes watch-item round-trip that the workspace "+ Watch" / "resolve"
buttons drive. Stdlib only, no network — team_notes uses a temp dir.
"""

import os
import tempfile
import unittest

import team_view
import team_notes


def _inj(name, group, role, severity, status, position=""):
    return {"name": name, "group": group, "role": role, "severity": severity,
            "status": status, "position": position, "body_part": "", "notes": ""}


class RatingSignalTests(unittest.TestCase):
    def test_empty_detail_no_flags(self):
        self.assertEqual(team_view._rating_signal({}), [])
        self.assertEqual(team_view._rating_signal({"injuries": [], "clusters": []}), [])

    def test_qb_priced_in_flag(self):
        detail = {"injuries": [_inj("Backup QB", "QB", "STARTER", 5, "IR", "QB")],
                  "clusters": []}
        flags = team_view._rating_signal(detail, "Starter QB")
        self.assertEqual(len(flags), 1)
        self.assertIn("already", flags[0].lower())
        self.assertIn("QB:", flags[0])

    def test_cluster_flagged_on_correct_side(self):
        detail = {
            "injuries": [_inj("A", "DB", "STARTER", 5, "PUP", "CB"),
                         _inj("B", "DB", "STARTER", 4, "Out", "S")],
            "clusters": [{"group": "DB", "count": 2, "players": ["A", "B"]}],
        }
        flags = team_view._rating_signal(detail)
        self.assertTrue(any(f.startswith("Defense: DB cluster") for f in flags))
        # players in a cluster are NOT also listed as individual severe starters
        self.assertFalse(any("1 starter out" in f for f in flags))

    def test_severe_starter_grouped_by_side(self):
        detail = {"injuries": [_inj("Left Tackle", "OL", "STARTER", 5, "IR", "LT")],
                  "clusters": []}
        flags = team_view._rating_signal(detail)
        self.assertTrue(any(f.startswith("Offense: 1 starter out") for f in flags))
        self.assertIn("Left Tackle", flags[0])

    def test_backups_and_questionable_excluded(self):
        detail = {"injuries": [
            _inj("Depth Guy", "WR", "BACKUP", 5, "IR", "WR"),       # backup -> skip
            _inj("Day-to-day", "LB", "STARTER", 1, "Questionable", "LB"),  # sev<3 -> skip
        ], "clusters": []}
        self.assertEqual(team_view._rating_signal(detail), [])

    def test_effective_starter_counts(self):
        detail = {"injuries": [_inj("Promoted", "WR", "EFFECTIVE", 4, "Out", "WR")],
                  "clusters": []}
        flags = team_view._rating_signal(detail)
        self.assertTrue(any("Offense: 1 starter out" in f for f in flags))


class SleeperDetailGuardTests(unittest.TestCase):
    def test_absent_modules_degrade_to_empty(self):
        orig = team_view._injuries
        try:
            team_view._injuries = None  # simulate main/walshja9 (no injury scanner)
            self.assertEqual(team_view._sleeper_detail("SF"), {})
        finally:
            team_view._injuries = orig


class WatchItemRoundTripTests(unittest.TestCase):
    """What the '+ Watch' and 'resolve' buttons do, at the data layer."""

    def setUp(self):
        self._orig = team_notes.NOTES_DIR
        self._tmp = tempfile.mkdtemp()
        team_notes.NOTES_DIR = self._tmp

    def tearDown(self):
        team_notes.NOTES_DIR = self._orig

    def test_add_then_resolve(self):
        self.assertEqual(team_notes.open_threads("SF"), [])
        th = team_notes.add_thread("SF", "George Kittle Achilles",
                                   "PUP · starter (TE)", "2026-08-17T20:00:00Z")
        self.assertEqual(th["status"], "open")
        opened = team_notes.open_threads("SF")
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0]["topic"], "George Kittle Achilles")

        ok, _ = team_notes.resolve_thread("SF", th["id"], "back healthy",
                                          "2026-09-01T20:00:00Z")
        self.assertTrue(ok)
        self.assertEqual(team_notes.open_threads("SF"), [])
        self.assertEqual(len(team_notes.list_threads("SF", "resolved")), 1)


if __name__ == "__main__":
    unittest.main()
