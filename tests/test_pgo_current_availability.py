import unittest

from research.pgo_current_strength import build_availability_scenario as scenario


class CurrentAvailabilityScenarioTests(unittest.TestCase):
    def test_no_formal_report_is_unknown_and_has_no_delta(self):
        result = scenario.availability_adjustments(
            "NE", "no_formal_report", [], {},
        )
        self.assertEqual(result, {
            "status": "UNKNOWN_NO_FORMAL_REPORT",
            "offense_availability": None,
            "defense_availability": None,
            "matched_players": 0,
        })

    def test_formal_report_uses_existing_role_share(self):
        roster = [{
            "team": "NE", "gsis_id": "A", "position": "RB",
            "availability_probability": 0.7,
            "offense_snap_share": 0.4, "defense_snap_share": 0.0,
        }]
        overlay = {("NE", "A"): {
            "availability_probability": 0.7,
            "offense_snap_share": None, "defense_snap_share": None,
        }}
        result = scenario.availability_adjustments(
            "NE", "formal_injury_report", roster, overlay,
        )
        self.assertAlmostEqual(result["offense_availability"], -0.12)
        self.assertEqual(result["defense_availability"], -0.0)
        self.assertEqual(result["matched_players"], 1)

    def test_missing_role_or_reduced_qb_fails_closed(self):
        overlay = {("NE", "A"): {
            "availability_probability": 0.7,
            "offense_snap_share": None, "defense_snap_share": None,
        }}
        for position, offense in (("WR", None), ("QB", 1.0)):
            roster = [{
                "team": "NE", "gsis_id": "A", "position": position,
                "availability_probability": 0.7,
                "offense_snap_share": offense, "defense_snap_share": 0.0,
            }]
            with self.subTest(position=position):
                with self.assertRaises(ValueError):
                    scenario.availability_adjustments(
                        "NE", "formal_injury_report", roster, overlay,
                    )


if __name__ == "__main__":
    unittest.main()
