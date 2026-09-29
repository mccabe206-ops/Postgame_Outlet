import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import market_ratings as M  # noqa: E402


class FitMathTests(unittest.TestCase):
    def _games(self, truth, hfa=1.5, reps=3):
        teams = sorted(truth)
        games = []
        for _ in range(reps):
            for i, h in enumerate(teams):
                for a in teams[i + 1:]:
                    games.append((h, a, truth[h] - truth[a] + hfa, hfa, 1.0))
                    games.append((a, h, truth[a] - truth[h] + hfa, hfa, 1.0))
        return teams, games

    def test_recovers_ratings_differences_without_ridge(self):
        truth = {"A": 4.0, "B": 1.0, "C": -0.5, "D": -4.5}
        teams, games = self._games(truth)
        got = M.center_to(M.solve_ratings(games, teams, lam=1e-9), sum(truth.values()) / 4)
        for t in teams:
            self.assertAlmostEqual(got[t], truth[t], places=4)

    def test_ridge_shrinks_toward_mean_but_keeps_order(self):
        truth = {"A": 4.0, "B": 1.0, "C": -0.5, "D": -4.5}
        teams, games = self._games(truth, reps=1)
        got = M.center_to(M.solve_ratings(games, teams, lam=2.0), 0.0)
        self.assertEqual(sorted(teams, key=lambda t: -got[t]), ["A", "B", "C", "D"])
        self.assertLess(got["A"] - got["D"], truth["A"] - truth["D"])

    def test_neutral_site_and_weights(self):
        # neutral game (hfa 0) says A is 3 better; a zero-weight game says otherwise
        games = [("A", "B", 3.0, 0.0, 1.0), ("B", "A", 10.0, 0.0, 0.0)]
        got = M.solve_ratings(games, ["A", "B"], lam=1e-9)
        self.assertAlmostEqual(got["A"] - got["B"], 3.0, places=4)

    def test_center_to_matches_target_mean(self):
        got = M.center_to({"A": 1.0, "B": 3.0}, 0.6)
        self.assertAlmostEqual(sum(got.values()) / 2, 0.6)
        self.assertAlmostEqual(got["B"] - got["A"], 2.0)


if __name__ == "__main__":
    unittest.main()
