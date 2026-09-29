import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import market_ratings  # noqa: E402
import pff_team  # noqa: E402


def _unit(pblk, recv, run, rblk, dfn, pas):
    return {"pblk": pblk, "recv": recv, "run": run, "rblk": rblk, "def": dfn, "pass": pas}


class RescaleTests(unittest.TestCase):
    def test_rescale_maps_onto_target_mean_and_std(self):
        out = pff_team.rescale({"a": 50, "b": 60, "c": 70, "d": 80}, 0.0, 1.0)
        vals = list(out.values())
        self.assertAlmostEqual(sum(vals) / 4, 0.0)
        self.assertAlmostEqual(pff_team._std(vals), 1.0)
        self.assertLess(out["a"], out["b"])

    def test_constant_input_returns_target_mean(self):
        out = pff_team.rescale({"a": 60, "b": 60}, 0.5, 1.0)
        self.assertEqual(out, {"a": 0.5, "b": 0.5})


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.teams = {
            "A": _unit(80, 80, 80, 80, 80, 90),
            "B": _unit(70, 70, 70, 70, 70, 70),
            "C": _unit(60, 60, 60, 60, 60, 60),
            "D": _unit(50, 50, 50, 50, 50, 40),
        }
        # Sean: (qb, off, def) — off/def spread std = sqrt(1.25) with mean 0
        self.sean = {"A": (4.0, 1.5, 1.5), "B": (1.0, 0.5, 0.5),
                     "C": (-1.0, -0.5, -0.5), "D": (-2.0, -1.5, -1.5)}

    def test_components_centered_and_scaled_to_seans_spread(self):
        c = pff_team.components(self.teams, self.sean)
        offs = [c[t]["pff_off"] for t in "ABCD"]
        self.assertAlmostEqual(sum(offs) / 4, 0.0)
        self.assertAlmostEqual(pff_team._std(offs), pff_team._std([1.5, 0.5, -0.5, -1.5]))
        # evenly spaced grades + evenly spaced ratings → PFF reproduces Sean exactly
        for t in "ABCD":
            self.assertAlmostEqual(c[t]["pff_off"], self.sean[t][1])
            self.assertAlmostEqual(c[t]["pff_def"], self.sean[t][2])

    def test_total_uses_seans_qb_value(self):
        c = pff_team.components(self.teams, self.sean)
        for t in "ABCD":
            self.assertAlmostEqual(c[t]["pff_total"],
                                   self.sean[t][0] + c[t]["pff_off"] + c[t]["pff_def"])

    def test_teams_missing_from_ratings_are_skipped(self):
        teams = dict(self.teams, E=_unit(99, 99, 99, 99, 99, 99))
        self.assertNotIn("E", pff_team.components(teams, self.sean))


class ConsensusTests(unittest.TestCase):
    def test_both_reads_same_side(self):
        self.assertEqual(market_ratings.consensus(1.2, 1.0), "high")
        self.assertEqual(market_ratings.consensus(-1.0, -2.5), "low")

    def test_split_or_small_or_missing(self):
        self.assertIsNone(market_ratings.consensus(1.2, -1.2))
        self.assertIsNone(market_ratings.consensus(0.9, 2.0))
        self.assertIsNone(market_ratings.consensus(1.5, None))


if __name__ == "__main__":
    unittest.main()
