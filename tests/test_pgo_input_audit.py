import csv
import tempfile
import unittest
from pathlib import Path

import pgo_challenger as ch
from research.pgo_input_audit import audit_model


class InputAuditTests(unittest.TestCase):
    def test_active_scope_filters_before_reader_and_restores_after_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "weekly.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=("status", "player"))
                writer.writeheader()
                writer.writerows((
                    {"status": "CUT", "player": "cut"},
                    {"status": "ACT", "player": "active"},
                ))
            original_open = ch.open_csv
            original_load = ch._load_inputs
            original_walk = ch._walk
            original_qb = ch._qb_features
            with self.assertRaisesRegex(RuntimeError, "stop"):
                with audit_model.construction_scope(
                    {("weekly_rosters", 2025): path}, active_only=True,
                    half_life_games=4, exposure_fix=False,
                ):
                    self.assertEqual(
                        [row["player"] for row in ch.open_csv(path)], ["active"],
                    )
                    raise RuntimeError("stop")
            self.assertIs(ch.open_csv, original_open)
            self.assertIs(ch._load_inputs, original_load)
            self.assertIs(ch._walk, original_walk)
            self.assertIs(ch._qb_features, original_qb)
            self.assertEqual(
                [row["player"] for row in ch.open_csv(path)], ["cut", "active"],
            )

    def test_exposure_features_use_metric_specific_denominators(self):
        context = {
            "qb_history": {"qb": {
                "dropbacks": 1000.0,
                "passing_epa": 100.0, "passing_epa_plays": 1000.0,
                "cpoe_sum": 50.0, "cpoe_plays": 1000.0,
                "sack_free_dropbacks": 900.0, "sack_dropbacks": 1000.0,
                "secure_dropbacks": 980.0, "security_dropbacks": 1000.0,
                "rushing_epa": 100.0, "carries": 100.0,
            }},
            "qb_population": {
                "passing_epa": 0.0, "passing_epa_plays": 1000.0,
                "cpoe_sum": 0.0, "cpoe_plays": 1000.0,
                "sack_free_dropbacks": 800.0, "sack_dropbacks": 1000.0,
                "secure_dropbacks": 900.0, "security_dropbacks": 1000.0,
                "rushing_epa": 0.0, "carries": 100.0,
            },
        }
        result = audit_model.exposure_qb_features("qb", 2, 4, context)
        self.assertAlmostEqual(result["qb_epa_per_dropback"], 1 / 12)
        self.assertAlmostEqual(result["qb_rushing_epa_per_carry"], 2 / 3)
        self.assertAlmostEqual(result["qb_experience_prior"], ch.math.log1p(2))
        self.assertEqual(result["qb_draft_prior"], 0.5)

    def test_feature_removal_drops_exact_fields(self):
        row = ch.FeatureRow("g", 2025, 1, "k", 1.0, {"a": 1.0, "b": 2.0}, {})
        result = audit_model.drop_features([row], {"b"})
        self.assertEqual(result[0].features, {"a": 1.0})
        with self.assertRaises(ValueError):
            audit_model.drop_features([row], {"missing"})

    def test_arm_validator_uses_reference4_contract(self):
        row = ch.FeatureRow("g", 2025, 1, "k", 1.0, {"a": 1.0}, {})
        arms = {name: [row] for name in audit_model.ARMS}
        audit_model.validate_arms(arms)
        broken = dict(arms)
        broken["active4"] = [ch.FeatureRow("other", 2025, 1, "k", 1.0, {"a": 1.0}, {})]
        with self.assertRaises(ValueError):
            audit_model.validate_arms(broken)

    def test_symmetric_augmentation_negates_finite_values_and_keeps_missing(self):
        row = ch.FeatureRow(
            "g", 2025, 1, "k", 3.0,
            {"home_field": 1.0, "rest_difference": -0.5, "missing": None}, {},
        )
        original, reversed_row = audit_model.symmetric_rows([row])
        self.assertIs(original, row)
        self.assertEqual(reversed_row.game_id, "g:reversed")
        self.assertEqual(reversed_row.actual_margin, -3.0)
        self.assertEqual(reversed_row.features, {
            "home_field": -1.0, "rest_difference": 0.5, "missing": None,
        })

    def test_winner_denominator_keeps_predicted_ties_as_incorrect(self):
        rows = [
            {"actual_margin": 3, "candidate": 0},
            {"actual_margin": -2, "candidate": -1},
            {"actual_margin": 0, "candidate": 4},
        ]
        result = audit_model.metric_summary(rows, "candidate")
        self.assertEqual(result["winner"], {
            "correct": 1, "denominator": 2, "accuracy": 0.5,
            "actual_ties": 1, "predicted_ties": 1,
        })

    def test_empty_diagnostic_slice_is_explicitly_unavailable(self):
        result = audit_model.metric_summary([], "candidate")
        self.assertEqual(result["count"], 0)
        self.assertIsNone(result["mae"])
        self.assertIsNone(result["winner"]["accuracy"])


if __name__ == "__main__":
    unittest.main()
