import csv
import tempfile
import unittest
from pathlib import Path

import pgo_roster_strength as strength


class RosterStrengthTests(unittest.TestCase):
    def _paths(self, directory, rows_by_season):
        paths = {}
        fields = (
            "player_id", "position", "season", "week", "season_type",
            "targets", "receiving_epa", "carries", "rushing_epa",
        )
        for season, rows in rows_by_season.items():
            path = Path(directory) / f"players-{season}.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
            paths[("player_weekly_stats", season)] = path
        return paths

    @staticmethod
    def _row(player, position, season, *, targets=0, receiving_epa="", carries=0, rushing_epa=""):
        return {
            "player_id": player, "position": position, "season": season,
            "week": 1, "season_type": "REG", "targets": targets,
            "receiving_epa": receiving_epa, "carries": carries,
            "rushing_epa": rushing_epa,
        }

    def test_receiving_quality_uses_fixed_shrinkage_role_weights_and_prior_for_missing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(directory, {
                2025: [
                    self._row("A", "WR", 2025, targets=10, receiving_epa=10),
                    self._row("B", "WR", 2025, targets=10, receiving_epa=0),
                ],
            })
            hook = strength.build_roster_hook(paths)
            metadata = {"roster": {
                "A": {"gsis_id": "A", "position": "WR", "offense_snap_share": 0.6, "probability": 0.0},
                "B": {"gsis_id": "B", "position": "WR", "offense_snap_share": 0.4, "probability": 1.0},
                "C": {"gsis_id": "C", "position": "WR", "offense_snap_share": 0.2, "probability": 1.0},
            }}
            full, current, metadata = hook(
                {}, {}, metadata, team="NE", season=2026, week=1,
                kickoff="2026-09-09T00:00:00Z", context={}, inputs={},
            )
        # Population mean=.5; A=(10+50*.5)/(10+50), B=(0+50*.5)/(10+50),
        # C has no history and receives the position prior.
        expected = (0.6 * (35 / 60) + 0.4 * (25 / 60) + 0.2 * 0.5) / 1.2
        self.assertAlmostEqual(full["quality_wr_receiving"], expected)
        self.assertEqual(current["quality_wr_receiving"], full["quality_wr_receiving"])
        audit = metadata["roster_strength"]["quality_wr_receiving"]
        self.assertAlmostEqual(audit["observed_role_weight_coverage"], 1 / 1.2)
        self.assertEqual(audit["players_using_position_prior"], 1)
        self.assertEqual(full["quality_te_receiving"], None)
        self.assertEqual(metadata["unavailable_player_quality"], ["offensive_line", "defense"])

    def test_prior_window_weights_completed_seasons_and_ignores_current_season(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(directory, {
                2023: [self._row("A", "WR", 2023, targets=10, receiving_epa=0)],
                2024: [self._row("A", "WR", 2024, targets=10, receiving_epa=10)],
                2025: [self._row("A", "WR", 2025, targets=10, receiving_epa=10)],
                2026: [self._row("A", "WR", 2026, targets=10, receiving_epa=-1000)],
            })
            hook = strength.build_roster_hook(paths)
            metadata = {"roster": {"A": {
                "gsis_id": "A", "position": "WR", "offense_snap_share": 1.0,
            }}}
            full, _, audit = hook(
                {}, {}, metadata, team="NE", season=2026, week=1,
                kickoff="2026-09-09T00:00:00Z", context={}, inputs={},
            )
        # The single-player population mean is weighted (10 + 5 + 0) / (10 + 5 + 2.5).
        self.assertAlmostEqual(full["quality_wr_receiving"], 15 / 17.5)
        self.assertEqual(audit["roster_strength_window"]["seasons"], [2025, 2024, 2023])
        self.assertEqual(audit["roster_strength_window"]["weights"], [1.0, 0.5, 0.25])

    def test_no_positive_roster_role_weight_is_missing_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(directory, {
                2025: [self._row("A", "TE", 2025, targets=10, receiving_epa=5)],
            })
            hook = strength.build_roster_hook(paths)
            metadata = {"roster": {"A": {
                "gsis_id": "A", "position": "TE", "offense_snap_share": None,
            }}}
            full, current, metadata = hook(
                {}, {}, metadata, team="NE", season=2026, week=1,
                kickoff="2026-09-09T00:00:00Z", context={}, inputs={},
            )
        self.assertIsNone(full["quality_te_receiving"])
        self.assertIsNone(current["quality_te_receiving"])
        self.assertEqual(
            metadata["roster_strength"]["quality_te_receiving"]["players_without_role_weight"], 1,
        )

    def test_feature_contract_is_exact(self):
        self.assertEqual(strength.FEATURE_NAMES, (
            "quality_wr_receiving", "quality_te_receiving",
            "quality_rb_receiving", "quality_rb_rushing",
        ))
        self.assertEqual(strength.PRIOR_OPPORTUNITIES, {
            "quality_wr_receiving": 50.0,
            "quality_te_receiving": 50.0,
            "quality_rb_receiving": 30.0,
            "quality_rb_rushing": 75.0,
        })

    def test_colliding_gsis_uses_prior_and_is_counted_ambiguous(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(directory, {
                2025: [
                    self._row("A", "WR", 2025, targets=10, receiving_epa=10),
                    self._row("B", "WR", 2025, targets=10, receiving_epa=0),
                ],
            })
            hook = strength.build_roster_hook(paths)
            metadata = {"roster": {"smart:A": {
                "gsis_id": "A", "position": "WR", "offense_snap_share": 1.0,
            }}}
            full, _, metadata = hook(
                {}, {}, metadata, team="NE", season=2026, week=1,
                kickoff="2026-09-09T00:00:00Z", context={},
                inputs={"colliding_gsis": {"A"}},
            )
        self.assertEqual(full["quality_wr_receiving"], 0.5)
        audit = metadata["roster_strength"]["quality_wr_receiving"]
        self.assertEqual(audit["ambiguous_player_ids"], 1)
        self.assertEqual(audit["players_using_position_prior"], 1)
        self.assertEqual(audit["observed_role_weight_coverage"], 0.0)

    def test_source_season_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(directory, {
                2025: [self._row("A", "WR", 2024, targets=10, receiving_epa=1)],
            })
            with self.assertRaisesRegex(ValueError, "source season"):
                strength.build_roster_hook(paths)


if __name__ == "__main__":
    unittest.main()
