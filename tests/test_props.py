"""Prop Board: claim parsing, verification math, market adapters (no network)."""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kb  # noqa: E402
import kb_build  # noqa: E402
import props_identity  # noqa: E402
import props_markets as pm  # noqa: E402
import props_verify as pv  # noqa: E402


class ParseClaimsTests(unittest.TestCase):
    def test_propsedge_over_with_record(self):
        c = pv.parse_claims("Xavier Hutchinson Over 29.5 Rec Yds 4/4")[0]
        self.assertEqual((c["kind"], c["player"], c["market"], c["line"], c["side"]),
                         ("player", "Xavier Hutchinson", "rec_yds", 29.5, "over"))
        self.assertEqual((c["claimed_hits"], c["claimed_games"]), (4, 4))

    def test_toad_plus_format_becomes_half_point_line(self):
        c = pv.parse_claims("TYLER SHOUGH 250+ PASS YARDS")[0]
        self.assertEqual((c["market"], c["line"]), ("pass_yds", 249.5))

    def test_anytime_td_and_under(self):
        a, u = pv.parse_claims("Judkins anytime TD\nJaylen Warren Under 40.5 Rush Yds")
        self.assertEqual((a["market"], a["line"]), ("anytime_td", 0.5))
        self.assertEqual((u["side"], u["market"], u["line"]), ("under", "rush_yds", 40.5))

    def test_team_claims(self):
        d, o, s = pv.parse_claims("BUCCANEERS ALLOW 7TH MOST RECEIVING YARDS TO RB\n"
                                  "PHI: 4TH MOST RZ WR TARGETS\nVIKINGS RANK #1 IN SACKS")
        self.assertEqual((d["side"], d["rank"], d["pos"], d["stat"]),
                         ("allowed", 7, "RB", "rec_yds"))
        self.assertEqual((o["side"], o["rank"], o["redzone"], o["pos"], o["stat"]),
                         ("either", 4, True, "WR", "targets"))
        self.assertEqual((s["stat"], s["rank"], s["side"]), ("sacks", 1, "defense"))

    def test_unparsed_lines_are_kept(self):
        self.assertEqual(pv.parse_claims("Lock it in 🔒")[0]["kind"], "unparsed")


class _KBCase(unittest.TestCase):
    """Temp KB with a tiny 2026 season."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "nfl.sqlite")
        con = sqlite3.connect(self.db)
        pw = []
        # P1 (LAR WR): weeks 1 & 4 only — team played 1-4
        for wk, yds in ((1, 74), (4, 125)):
            pw.append(dict(player_id="P1", player_display_name="Puka Nacua", position="WR",
                           team="LAR", opponent_team="SF", season=2026, week=wk,
                           season_type="REG", receiving_yards=yds, receptions=5,
                           rushing_tds=0, receiving_tds=0))
        for wk in (1, 2, 3, 4):  # teammate so LAR has rows every week
            pw.append(dict(player_id="P2", player_display_name="Davante Adams",
                           position="WR", team="LAR", opponent_team="SF", season=2026,
                           week=wk, season_type="REG", receiving_yards=40 + wk,
                           receptions=3, rushing_tds=0, receiving_tds=1 if wk == 2 else 0))
            pw.append(dict(player_id="P3", player_display_name="Some Back", position="RB",
                           team="SF", opponent_team="LAR", season=2026, week=wk,
                           season_type="REG", receiving_yards=10, receptions=2,
                           rushing_tds=0, receiving_tds=0))
        kb_build.build_table(con, "player_week", pw)
        kb_build.build_table(con, "games", [
            dict(season=2026, week=w, game_type="REG", home_team="LAR", away_team="SF",
                 result=3) for w in (1, 2, 3, 4)])
        con.execute("CREATE TABLE pbp (game_id TEXT, season INTEGER, week INTEGER, "
                    "season_type TEXT, posteam TEXT, defteam TEXT, sack REAL, "
                    "interception REAL, yardline_100 REAL)")
        for w in (1, 2, 3, 4):
            con.execute("INSERT INTO pbp VALUES (?,?,?,?,?,?,?,?,?)",
                        (f"g{w}", 2026, w, "REG", "LAR", "SF", 1 if w < 3 else 0, 0, 50))
            con.execute("INSERT INTO pbp VALUES (?,?,?,?,?,?,?,?,?)",
                        (f"g{w}", 2026, w, "REG", "SF", "LAR", 0, 1, 50))
        con.commit()
        con.close()
        real_query = kb.query
        self.p = mock.patch.object(kb, "query",
                                   lambda sql, params=(): real_query(sql, params, self.db))
        self.p.start()
        props_identity._CACHE.clear()
        self.p2 = mock.patch.object(pv, "injury_status", return_value=None)
        self.p2.start()

    def tearDown(self):
        self.p.stop()
        self.p2.stop()
        props_identity._CACHE.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)


class VerifyPlayerTests(_KBCase):
    def test_true_but_caveated_small_sample_and_dnp(self):
        v = pv.verify("Puka Nacua 70+ Rec Yards", season=2026, snapshot={"rows": []},
                      assume_perfect=True)[0]
        self.assertEqual(v["verdict"], "true")
        self.assertEqual((v["hits"], v["games"], v["team_games"]), (2, 2, 4))
        self.assertEqual(v["dnp_weeks"], [2, 3])
        self.assertTrue(any("2 of 4" in c for c in v["caveats"]))
        self.assertTrue(any("thin margin" in c for c in v["caveats"]))  # wk1 +4.5

    def test_claimed_record_mismatch_is_false(self):
        v = pv.verify("Puka Nacua Over 69.5 Rec Yds 4/4", season=2026,
                      snapshot={"rows": []})[0]
        self.assertEqual(v["verdict"], "false")  # he played 2, not 4

    def test_bare_pick_reports_record_only(self):
        v = pv.verify("Davante Adams anytime TD", season=2026, snapshot={"rows": []})[0]
        self.assertEqual((v["verdict"], v["hits"], v["games"]), ("record", 1, 4))
        self.assertFalse(any("thin margin" in c for c in v["caveats"]))

    def test_through_week_cuts_later_games(self):
        v = pv.verify("Puka Nacua 70+ Rec Yards", season=2026, snapshot={"rows": []},
                      through_week=3, assume_perfect=True)[0]
        self.assertEqual((v["games"], v["team_games"]), (1, 3))

    def test_market_price_attached_from_snapshot(self):
        snap = {"fetched_at": "x", "rows": [
            dict(source="kalshi", book="kalshi", player="Puka Nacua", market="rec_yds",
                 line=69.5, p_fair=0.61, usable=True, spread=0.01),
            dict(source="polymarket", book="polymarket", player="Puka Nacua",
                 market="rec_yds", line=69.5, p_fair=0.20, usable=False, spread=0.6)]}
        v = pv.verify("Puka Nacua 70+ Rec Yards", season=2026, snapshot=snap)[0]
        self.assertEqual(v["price"]["p"], 0.61)  # the unusable thin quote is ignored
        self.assertTrue(v["price"]["exact"])
        self.assertEqual(v["market"], "rec_yds")

    def test_unknown_player_is_unverifiable(self):
        v = pv.verify("Nobody Real Over 9.5 Rec Yds", season=2026, snapshot={"rows": []})[0]
        self.assertEqual(v["verdict"], "unverifiable")


class VerifyTeamTests(_KBCase):
    def test_allowed_rank_with_zero_fill(self):
        # LAR allows RB rec yds (SF backs vs LAR) = 40; SF allows none -> SF ranked 2nd
        v = pv.verify("RAMS ALLOW MOST RECEIVING YARDS TO RB", season=2026)[0]
        self.assertEqual(v["verdict"], "true")
        v2 = pv.verify("49ERS ALLOW MOST RECEIVING YARDS TO RB", season=2026)[0]
        self.assertEqual(v2["verdict"], "close")

    def test_sacks_rank(self):
        v = pv.verify("49ERS RANK #1 IN SACKS", season=2026)[0]
        self.assertEqual(v["verdict"], "true")  # SF defense: 2 sacks vs LAR's 0

    def test_ambiguous_team_format_picks_matching_reading(self):
        v = pv.verify("LAR: MOST WR RECEPTIONS", season=2026)[0]
        self.assertEqual(v["verdict"], "true")
        self.assertTrue(any("read as team OFFENSE" in c for c in v["caveats"]))


class MarketAdapterTests(unittest.TestCase):
    def test_kalshi_ladder_rows(self):
        mk = [{"ticker": "KXNFLPASSYDS-26OCT11MINNO-NOTSHOUGH6-250",
               "event_ticker": "KXNFLPASSYDS-26OCT11MINNO",
               "title": "Tyler Shough: 250+ passing yards", "floor_strike": 249.5,
               "yes_bid_dollars": "0.4200", "yes_ask_dollars": "0.4300",
               "open_interest_fp": "3539.39", "status": "active"}]
        r = pm.parse_kalshi(mk, "pass_yds", "t")[0]
        self.assertEqual((r["event_key"], r["player"], r["line"]), ("MIN@NO", "Tyler Shough",
                                                                     249.5))
        self.assertAlmostEqual(r["p_fair"], 0.425)
        self.assertTrue(r["usable"])

    def test_kalshi_event_keys_map_team_codes(self):
        self.assertEqual(pm.kalshi_event_key("KXNFLREC-26OCT11PHIJAC"), "PHI@JAX")
        self.assertEqual(pm.kalshi_event_key("KXNFLREC-26OCT12BUFLA"), "BUF@LAR")
        self.assertEqual(pm.kalshi_event_key("KXNFLREC-26OCT11NYGWAS"), "NYG@WSH")

    def test_kalshi_anytime_keeps_only_one_plus(self):
        base = {"event_ticker": "KXNFLTD-26OCT11BALATL", "yes_bid_dollars": "0.3",
                "yes_ask_dollars": "0.32", "open_interest_fp": "500", "status": "active"}
        mk = [dict(base, ticker="a", title="X Y: 1+ touchdowns", floor_strike=0.5),
              dict(base, ticker="b", title="X Y: 2+ touchdowns", floor_strike=1.5)]
        self.assertEqual([r["raw_id"] for r in pm.parse_kalshi(mk, "anytime_td", "t")], ["a"])

    def test_polymarket_placeholder_rejected_and_liquid_kept(self):
        ev = [{"title": "Raiders vs. Patriots - Player Props",
               "slug": "nfl-lv-ne-2026-10-11-player-props", "markets": [
                   {"id": "1", "question": "TreVeyon Henderson: Rushing Yards O/U 39.5",
                    "sportsMarketType": "rushing_yards", "line": 39.5,
                    "outcomes": '["Over", "Under"]', "outcomePrices": '["0.5","0.5"]',
                    "bestBid": 0.62, "bestAsk": 0.63, "liquidityNum": 39578},
                   {"id": "2", "question": "Tyler Shough: Passing Touchdowns O/U 0.5",
                    "sportsMarketType": "passing_touchdowns", "line": 0.5,
                    "outcomes": '["Over", "Under"]', "outcomePrices": '["0.385","0.615"]',
                    "bestBid": 0.01, "bestAsk": 0.76, "liquidityNum": 0}]}]
        a, b = pm.parse_polymarket(ev, "t")
        self.assertEqual(a["event_key"], "LV@NE")
        self.assertTrue(a["usable"])
        self.assertAlmostEqual(a["p_fair"], 0.625)
        self.assertFalse(b["usable"])  # 75c spread, no liquidity = empty book

    def test_devig_and_american(self):
        self.assertAlmostEqual(pm.american_to_prob(-110), 110 / 210)
        self.assertAlmostEqual(pm.american_to_prob(150), 0.4)
        self.assertAlmostEqual(pm.devig_two_way(110 / 210, 110 / 210), 0.5)

    def test_oddsapi_event_parse_devigs_two_way(self):
        ev = {"id": "e1", "home_team": "New Orleans Saints", "away_team": "Minnesota Vikings",
              "bookmakers": [{"key": "draftkings", "markets": [
                  {"key": "player_pass_yds", "outcomes": [
                      {"name": "Over", "description": "Tyler Shough", "price": -115,
                       "point": 245.5},
                      {"name": "Under", "description": "Tyler Shough", "price": -105,
                       "point": 245.5}]},
                  {"key": "player_anytime_td", "outcomes": [
                      {"name": "Yes", "description": "Alvin Kamara", "price": 120}]}]}]}
        abbr = {"New Orleans Saints": "NO", "Minnesota Vikings": "MIN"}.get
        rows = pm.parse_oddsapi_event(ev, "t", abbr=abbr)
        py = next(r for r in rows if r["market"] == "pass_yds")
        self.assertEqual((py["event_key"], py["line"], py["book"]), ("MIN@NO", 245.5,
                                                                    "draftkings"))
        self.assertAlmostEqual(py["p_fair"], (115 / 215) / (115 / 215 + 105 / 205))
        td = next(r for r in rows if r["market"] == "anytime_td")
        self.assertTrue(td["vig_included"])

    def test_oddsapi_credit_guard(self):
        calls = []

        def fake_get(url, headers=None):
            calls.append(url)
            if "/events?" in url:
                return [{"id": "e1"}, {"id": "e2"}], {"x-requests-remaining": "55"}
            return {"bookmakers": []}, {"x-requests-remaining": "48"}

        with self.assertRaises(pm.CreditGuardError):
            pm.fetch_oddsapi(get=fake_get, key="k", reserve=50, log=lambda m: None)
        self.assertEqual(len(calls), 1)  # refused before spending any odds credits

    def test_oddsapi_without_key_is_skipped(self):
        with mock.patch.object(pm, "odds_api_key", return_value=None):
            self.assertEqual(pm.fetch_oddsapi(get=None, log=lambda m: None), [])


class PbpLoaderTests(unittest.TestCase):
    def test_streaming_loader_trims_and_normalizes(self):
        import gzip
        import io
        hdr = ",".join(kb_build.PBP_COLS + ("extra_col",))
        vals = {c: "" for c in kb_build.PBP_COLS}
        vals.update(game_id="2026_01_SF_LA", season="2026", week="1", posteam="LA",
                    defteam="SF", yardline_100="12", pass_attempt="1",
                    receiver_player_id="P1")
        line = ",".join(vals[c] for c in kb_build.PBP_COLS) + ",x"
        data = gzip.compress((hdr + "\n" + line + "\n").encode())
        tmp = tempfile.mkdtemp()
        try:
            con = sqlite3.connect(os.path.join(tmp, "t.sqlite"))
            n, got = kb_build.build_pbp(con, (2026, 2026), fetch=lambda u: data,
                                        log=lambda m: None)
            self.assertEqual((n, got), (1, [2026]))
            row = con.execute("SELECT posteam, yardline_100, typeof(week) FROM pbp").fetchone()
            self.assertEqual(row, ("LAR", 12.0, "integer"))
            cols = [r[1] for r in con.execute("PRAGMA table_info(pbp)")]
            self.assertNotIn("extra_col", cols)
            con.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
