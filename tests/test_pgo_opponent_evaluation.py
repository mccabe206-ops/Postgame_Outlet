from dataclasses import dataclass
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pgo_opponent_evaluation as evaluation


@dataclass(frozen=True)
class Row:
    game_id: str
    season: int
    week: int
    kickoff: str
    actual_margin: float
    features: dict
    subgroup_flags: dict


class OpponentEvaluationTests(unittest.TestCase):
    def rows(self):
        return [
            Row("a", 2017, 1, "2017-09-01T00:00:00+00:00", 1.0, {"x": 1.0}, {}),
            Row("b", 2018, 2, "2018-09-01T00:00:00+00:00", -2.0, {"x": 2.0}, {}),
            Row("c", 2018, 8, "2018-10-01T00:00:00+00:00", 3.0, {"x": 3.0}, {}),
            Row("d", 2019, 3, "2019-09-01T00:00:00+00:00", 0.0, {"x": 4.0}, {}),
        ]

    def test_expanding_folds_train_only_on_earlier_seasons(self):
        folds = list(evaluation.expanding_folds(self.rows(), seasons=(2018, 2019)))
        self.assertEqual([[row.game_id for row in fold[1]] for fold in folds], [["a"], ["a", "b", "c"]])
        self.assertEqual([[row.game_id for row in fold[2]] for fold in folds], [["b", "c"], ["d"]])

    def test_matching_arms_reject_identity_or_target_drift(self):
        arms = {name: self.rows() for name in evaluation.ARMS}
        evaluation.validate_matching_arms(arms)
        changed = {name: list(rows) for name, rows in arms.items()}
        changed["team_epa"][1] = Row(
            "b", 2018, 2, "2018-09-01T00:00:00+00:00", 99.0, {"x": 2.0}, {},
        )
        with self.assertRaisesRegex(ValueError, "identity"):
            evaluation.validate_matching_arms(changed)

    def test_summary_reports_mae_rmse_winner_ties_and_periods(self):
        rows = [
            {"season": 2018, "week": 1, "actual_margin": 3.0, "candidate": 1.0},
            {"season": 2018, "week": 7, "actual_margin": -1.0, "candidate": 2.0},
            {"season": 2019, "week": 3, "actual_margin": 0.0, "candidate": 0.0},
        ]
        summary = evaluation.metric_views(rows, "candidate")
        self.assertAlmostEqual(summary["overall"]["mae"], 5 / 3)
        self.assertAlmostEqual(summary["overall"]["rmse"], (13 / 3) ** 0.5)
        self.assertEqual(summary["overall"]["winner"], {
            "correct": 1, "denominator": 2, "accuracy": 0.5,
            "actual_ties": 1, "predicted_ties": 1,
        })
        self.assertEqual(summary["weeks_1_4"]["count"], 2)
        self.assertEqual(summary["weeks_5_18"]["count"], 1)
        self.assertEqual([item["season"] for item in summary["seasons"]], [2018, 2019])

    def test_season_block_bootstrap_is_paired_and_deterministic(self):
        rows = [
            {"season": 2018, "actual_margin": 0.0, "raw": 4.0, "candidate": 2.0},
            {"season": 2018, "actual_margin": 0.0, "raw": 2.0, "candidate": 1.0},
            {"season": 2019, "actual_margin": 0.0, "raw": 6.0, "candidate": 3.0},
        ]
        first = evaluation.season_block_bootstrap(
            rows, "candidate", "raw", samples=1000, seed=7,
        )
        second = evaluation.season_block_bootstrap(
            rows, "candidate", "raw", samples=1000, seed=7,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["blocks"], 2)
        self.assertEqual(first["samples"], 1000)
        self.assertEqual(first["mean"], 2.0)
        self.assertGreater(first["lower"], 0.0)

    def test_protected_hash_check_fails_after_byte_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "protected.json"
            path.write_bytes(b"original\n")
            expected = {str(path): evaluation.sha256(path.read_bytes())}
            self.assertEqual(evaluation.verify_protected(expected), expected)
            path.write_bytes(b"changed\n")
            with self.assertRaisesRegex(ValueError, "Protected artifact"):
                evaluation.verify_protected(expected)

    def test_loaded_cache_guard_checks_the_actual_configured_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.csv"
            path.write_bytes(b"original\n")
            paths = {("schedule_results", None): path}
            expected = evaluation.loaded_source_inventory(paths)
            path.write_bytes(b"changed\n")
            with self.assertRaisesRegex(ValueError, "Loaded source"):
                evaluation.verify_loaded_sources(expected, paths)

    def test_v0_reproduction_uses_frozen_parameters_without_selection(self):
        schedule = [{"game_id": "x", "season": "2025"}]
        prediction = mock.Mock(season=2025)
        with (
            mock.patch.object(evaluation.pgo_sources, "open_csv", return_value=iter(schedule)),
            mock.patch.object(evaluation.challenger.pgo_model, "parse_games", return_value=["game"]),
            mock.patch.object(
                evaluation.challenger.pgo_model, "walk_forward",
                return_value=([prediction], {}),
            ) as walk,
            mock.patch.object(
                evaluation.challenger.pgo_model, "select_parameters",
                side_effect=AssertionError("selection is forbidden"),
            ),
        ):
            self.assertEqual(
                evaluation._frozen_v0_predictions({("schedule_results", None): Path("unused")}),
                [prediction],
            )
        walk.assert_called_once_with(["game"], evaluation.challenger.V0_PARAMETERS)


if __name__ == "__main__":
    unittest.main()
