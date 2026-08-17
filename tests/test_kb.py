"""Tests for the NFL knowledge base (kb / kb_build / kb_query) — no network.

Builds a tiny temp SQLite from in-line fixtures, then checks: schema/type
inference, team normalization, read-only enforcement, the read-only SQL guard,
and the ATS / over-under / fantasy report math.
"""

import os
import sqlite3
import tempfile
import types
import unittest

import kb
import kb_build
import kb_query
import kb_sleeper


def _ns(**kw):
    base = dict(team=None, since=1999, home=False, away=False, div=False,
                fav=False, dog=False, rest=False, pos=None, season=None, json=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


def _game(home, away, result, spread, hs, as_, total, div=0, hrest=7, arest=7,
          season=2024, week=1, gtype="REG"):
    return {"season": str(season), "week": str(week), "game_type": gtype,
            "home_team": home, "away_team": away, "result": str(result),
            "spread_line": str(spread), "home_score": str(hs), "away_score": str(as_),
            "total_line": str(total), "div_game": str(div),
            "home_rest": str(hrest), "away_rest": str(arest)}


GAMES = [
    _game("NE", "BUF", result=10, spread=3, hs=27, as_=17, total=40),   # NE home cover; over
    _game("NE", "MIA", result=1, spread=3, hs=20, as_=19, total=45),    # NE home loss; under
    _game("NE", "NYJ", result=3, spread=3, hs=24, as_=21, total=45, div=1),  # push; push
    _game("BUF", "NE", result=-6, spread=-3, hs=17, as_=23, total=42),  # NE away cover; under
    _game("KC", "OAK", result=14, spread=7, hs=31, as_=17, total=44),   # team-normalize OAK->LV
]

PLAYERS = [
    {"player_id": "1", "player_display_name": "Back A", "position": "RB",
     "season": "2024", "week": "1", "fantasy_points_ppr": "25.0", "carries": "20",
     "targets": "4"},
    {"player_id": "1", "player_display_name": "Back A", "position": "RB",
     "season": "2024", "week": "2", "fantasy_points_ppr": "15.0", "carries": "18",
     "targets": "2"},
    {"player_id": "2", "player_display_name": "Back B", "position": "RB",
     "season": "2024", "week": "1", "fantasy_points_ppr": "10.0", "carries": "8",
     "targets": "1"},
]


class KBTests(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.join(tempfile.mkdtemp(), "nfl.sqlite")
        con = sqlite3.connect(self.tmp)
        kb_build.build_table(con, "games", [dict(r) for r in GAMES])
        kb_build.build_table(con, "player_week", [dict(r) for r in PLAYERS])
        con.commit()
        con.close()

    # ---- ingestion -------------------------------------------------------
    def test_type_inference(self):
        self.assertEqual(kb_build._infer_type(["1", "2", ""]), "INTEGER")
        self.assertEqual(kb_build._infer_type(["1.5", "2"]), "REAL")
        self.assertEqual(kb_build._infer_type(["TRUE", "x"]), "TEXT")
        self.assertEqual(kb_build._infer_type(["", ""]), "TEXT")

    def test_numeric_columns_aggregate(self):
        # result stored numeric -> SUM works without CAST
        rows = kb.query("SELECT SUM(result) s FROM games", db_path=self.tmp)
        self.assertEqual(rows[0]["s"], 10 + 1 + 3 - 6 + 14)

    def test_team_normalization(self):
        rows = kb.query("SELECT away_team FROM games WHERE home_team='KC'",
                        db_path=self.tmp)
        self.assertEqual(rows[0]["away_team"], "LV")  # OAK -> LV

    # ---- read-only enforcement ------------------------------------------
    def test_connection_is_read_only(self):
        con = kb.connect_ro(self.tmp)
        with self.assertRaises(sqlite3.OperationalError):
            con.execute("INSERT INTO games (season) VALUES ('2099')")
        con.close()

    def test_sql_guard_rejects_writes(self):
        self.assertEqual(kb_query.run_sql("DELETE FROM games", db_path=self.tmp), 1)
        self.assertEqual(kb_query.run_sql("DROP TABLE games", db_path=self.tmp), 1)
        self.assertEqual(kb_query.run_sql("SELECT 1; SELECT 2", db_path=self.tmp), 1)
        self.assertEqual(
            kb_query.run_sql("SELECT COUNT(*) FROM games", db_path=self.tmp), 0)

    # ---- report math -----------------------------------------------------
    def test_ats_all_and_situational(self):
        self.assertEqual(kb_query.report_ats(_ns(team="NE", since=2024), self.tmp),
                         (2, 1, 1))  # W,L,P,W across 4 games
        self.assertEqual(
            kb_query.report_ats(_ns(team="NE", since=2024, home=True), self.tmp),
            (1, 1, 1))  # only the 3 NE home games

    def test_ou(self):
        self.assertEqual(kb_query.report_ou(_ns(team="NE", since=2024), self.tmp),
                         (1, 2, 1))  # over, under, push

    def test_fantasy_leaders_ranked(self):
        rows = kb_query.report_leaders(_ns(pos="RB", season=2024, json=True), self.tmp)
        self.assertEqual(rows[0]["player"], "Back A")
        self.assertEqual(rows[0]["ppr"], 40.0)  # 25 + 15
        self.assertEqual(rows[1]["player"], "Back B")

    def test_usage_touches(self):
        rows = kb_query.report_usage(_ns(pos="RB", season=2024, json=True), self.tmp)
        self.assertEqual(rows[0]["player"], "Back A")
        self.assertEqual(rows[0]["touches"], 20 + 18 + 4 + 2)


class SleeperTests(unittest.TestCase):
    PLAYERS = {
        "10": {"full_name": "Star RB", "team": "KC", "active": True, "position": "RB",
               "search_rank": 5, "gsis_id": "00-0010", "age": 25, "years_exp": 3,
               "number": 22, "injury_status": None},
        "11": {"full_name": "Vegas WR", "team": "LV", "active": True, "position": "WR",
               "search_rank": 60, "gsis_id": "00-0011"},
        "12": {"full_name": "Not NFL", "team": "XYZ", "active": True},  # excluded
        "13": {"full_name": "Retired", "team": "KC", "active": False},  # excluded
    }
    ADDS = [{"player_id": "10", "count": 500}]
    DROPS = [{"player_id": "11", "count": 30}]

    def test_build_rows_filters_and_shapes(self):
        fv, tr = kb_sleeper.build_rows(self.PLAYERS, self.ADDS, self.DROPS,
                                       "2026-08-17T00:00Z")
        self.assertEqual({r["full_name"] for r in fv}, {"Star RB", "Vegas WR"})
        self.assertEqual(len(tr), 2)
        self.assertEqual({t["direction"] for t in tr}, {"add", "drop"})
        add = next(t for t in tr if t["direction"] == "add")
        self.assertEqual(add["sleeper_id"], "10")
        self.assertEqual(add["count"], 500)

    def test_tables_build_and_query(self):
        fv, tr = kb_sleeper.build_rows(self.PLAYERS, self.ADDS, self.DROPS, "t")
        tmp = os.path.join(tempfile.mkdtemp(), "nfl.sqlite")
        con = sqlite3.connect(tmp)
        kb_build.build_table(con, "fantasy_value", fv)
        kb_build.build_table(con, "trending", tr)
        con.commit()
        con.close()
        rows = kb.query(
            "SELECT f.full_name, t.count FROM trending t "
            "JOIN fantasy_value f ON t.sleeper_id=f.sleeper_id "
            "WHERE t.direction='add'", db_path=tmp)
        self.assertEqual(rows, [{"full_name": "Star RB", "count": 500}])


if __name__ == "__main__":
    unittest.main()
