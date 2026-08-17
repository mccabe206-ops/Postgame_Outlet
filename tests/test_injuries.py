"""Tests for the injury scanner (injuries.py) — no network.

Sleeper and Ourlads are mocked; we assert on the analysis (starter/effective
detection, clusters, severity, depth-disagreement flags) and the --json CLI shape.
"""

import contextlib
import io
import json
import unittest
from unittest.mock import patch

import injuries


def norm_player(name, team, position, dcp=None, order=None, status=None,
                body_part=None, notes=None):
    """A player in the shape sleeper.nfl_players() returns."""
    return {"espn_id": None, "name": name, "team": team, "position": position,
            "dcp": dcp, "order": order, "status": status, "body_part": body_part,
            "notes": notes, "exp": 3, "number": None}


def raw_player(pid, name, team, position, dcp=None, order=None, status=None,
               body_part=None, notes=None, active=True):
    """A player in Sleeper's raw players/nfl shape."""
    return {pid: {"full_name": name, "team": team, "position": position,
                  "depth_chart_position": dcp, "depth_chart_order": order,
                  "injury_status": status, "injury_body_part": body_part,
                  "injury_notes": notes, "active": active, "years_exp": 3,
                  "number": None, "espn_id": pid}}


class RoleDetectionTests(unittest.TestCase):
    def test_starter_from_order_one(self):
        players = [norm_player("Star Corner", "SF", "CB", dcp="LCB", order=1,
                               status="Out")]
        res = injuries.analyze_team("SF", players, {})
        self.assertEqual(res["injuries"][0]["role"], "STARTER")

    def test_effective_starter_promotion(self):
        # order-1 is Out -> the injured order-2 player is the promoted starter
        players = [
            norm_player("Front Man", "SF", "TE", dcp="TE", order=1, status="Out"),
            norm_player("Next Up", "SF", "TE", dcp="TE", order=2, status="IR"),
        ]
        res = injuries.analyze_team("SF", players, {})
        roles = {i["name"]: i["role"] for i in res["injuries"]}
        self.assertEqual(roles["Front Man"], "STARTER")
        self.assertEqual(roles["Next Up"], "EFFECTIVE")

    def test_healthy_backup_is_backup(self):
        # order-1 is healthy -> the injured order-2 is a plain backup
        players = [
            norm_player("Front Man", "SF", "TE", dcp="TE", order=1, status=None),
            norm_player("Depth Guy", "SF", "TE", dcp="TE", order=2, status="Questionable"),
        ]
        res = injuries.analyze_team("SF", players, {})
        roles = {i["name"]: i["role"] for i in res["injuries"]}
        self.assertEqual(roles["Depth Guy"], "BACKUP")

    def test_ol_lump_uses_five_starter_slots(self):
        players = [norm_player("Left Tackle", "SF", "OL", dcp="OL", order=4,
                               status="Out")]
        res = injuries.analyze_team("SF", players, {})
        self.assertEqual(res["injuries"][0]["role"], "STARTER")  # order<=5 = starter

    def test_no_depth_slot_is_shelved(self):
        players = [norm_player("On IR", "SF", "WR", dcp=None, order=None, status="IR")]
        res = injuries.analyze_team("SF", players, {})
        self.assertEqual(res["injuries"][0]["role"], "SHELVED")


class ClusterTests(unittest.TestCase):
    def _db_starters(self, n_injured):
        players = [
            norm_player("SS Man", "DET", "S", dcp="SS", order=1, status="PUP"),
            norm_player("FS Man", "DET", "S", dcp="FS", order=1,
                        status="PUP" if n_injured >= 2 else None),
        ]
        return injuries.analyze_team("DET", players, {})

    def test_cluster_fires_for_two_starters(self):
        res = self._db_starters(2)
        self.assertEqual(len(res["clusters"]), 1)
        self.assertEqual(res["clusters"][0]["group"], "DB")
        self.assertEqual(res["clusters"][0]["count"], 2)

    def test_no_cluster_for_one_starter(self):
        res = self._db_starters(1)
        self.assertEqual(res["clusters"], [])


class SeverityAndDepthTests(unittest.TestCase):
    def test_severe_sorts_above_watch(self):
        players = [
            norm_player("Questionable Star", "SF", "WR", dcp="LWR", order=1,
                        status="Questionable"),
            norm_player("IR Star", "SF", "RB", dcp="RB", order=1, status="IR"),
        ]
        res = injuries.analyze_team("SF", players, {})
        self.assertEqual(res["injuries"][0]["name"], "IR Star")  # severe first

    def test_depth_disagreement_flagged(self):
        # Sleeper says starter (SS order 1); Ourlads has him behind another guy
        players = [norm_player("Test Starter", "SF", "S", dcp="SS", order=1,
                               status="Out")]
        ourlads = {"SS": [{"name": "Someone Else"}, {"name": "Test Starter"}]}
        res = injuries.analyze_team("SF", players, ourlads)
        self.assertEqual(res["injuries"][0]["ourlads_agree"], "differs")

    def test_depth_agreement_flagged(self):
        players = [norm_player("Test Starter", "SF", "S", dcp="SS", order=1,
                               status="Out")]
        ourlads = {"SS": [{"name": "Test Starter"}, {"name": "Someone Else"}]}
        res = injuries.analyze_team("SF", players, ourlads)
        self.assertEqual(res["injuries"][0]["ourlads_agree"], "agrees")

    def test_reserve_bucket_not_treated_as_active_depth(self):
        # a name found only in Ourlads' IR bucket counts as 'absent' from the chart
        players = [norm_player("Shelf Star", "SF", "WR", dcp="LWR", order=1,
                               status="Out")]
        ourlads = {"IR": [{"name": "Shelf Star"}]}
        res = injuries.analyze_team("SF", players, ourlads)
        self.assertEqual(res["injuries"][0]["ourlads_agree"], "absent")


class KeepFilterTests(unittest.TestCase):
    def test_questionable_backup_folded_by_default(self):
        inj = {"role": "BACKUP", "severity": injuries._sev("Questionable")}
        self.assertFalse(injuries._keep(inj, include_backups=False))
        self.assertTrue(injuries._keep(inj, include_backups=True))

    def test_severe_backup_surfaces(self):
        inj = {"role": "BACKUP", "severity": injuries._sev("IR")}
        self.assertTrue(injuries._keep(inj, include_backups=False))

    def test_questionable_starter_always_shown(self):
        inj = {"role": "STARTER", "severity": injuries._sev("Questionable")}
        self.assertTrue(injuries._keep(inj, include_backups=False))


class CliJsonTests(unittest.TestCase):
    def _bundle(self):
        players = {}
        players.update(raw_player("1", "SS Man", "DET", "S", dcp="SS", order=1,
                                  status="PUP", body_part="Achilles", notes="Surgery"))
        players.update(raw_player("2", "FS Man", "DET", "S", dcp="FS", order=1,
                                  status="PUP", body_part="Knee"))
        players.update(raw_player("3", "Healthy Guy", "DET", "QB", dcp="QB", order=1))
        return {"fetched_at": "2026-08-16T07:15Z", "players": players, "from_cache": True}

    def test_json_payload_shape(self):
        bundle = self._bundle()
        with patch.object(injuries.sleeper, "get_players", return_value=bundle), \
             patch.object(injuries, "_ourlads_depth", return_value={}):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = injuries.main(["--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("DET", payload["teams"])
        det = payload["teams"]["DET"]
        self.assertEqual(len(det["clusters"]), 1)
        self.assertEqual(det["clusters"][0]["group"], "DB")
        names = {i["name"] for i in det["injuries"]}
        self.assertIn("SS Man", names)
        self.assertNotIn("Healthy Guy", names)  # no injury -> not listed
        self.assertEqual(payload["summary"]["clusters"], 1)


if __name__ == "__main__":
    unittest.main()
