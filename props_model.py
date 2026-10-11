"""Player-prop projection model: P(over line) for every market row, vs the market.

Per player-game projection (stdlib only):
  base   = recency-weighted per-game mean this season, shrunk toward a prior
           (last season's per-game mean if >= 4 games, else the position mean)
           -> (sum w_i x_i + K * prior) / (sum w_i + K),  w = DECAY^(games ago)
  opp    = opponent allowed-to-position per game / league per game, shrunk (K_OPP),
           applied as opp ** ALPHA[market]
  script = (team implied points / LG_IMPLIED) ** BETA[market], implied from the
           game's spread + total (KB closing lines historically, live ESPN lines now)
  mean   = base * opp_factor * script_factor   (x 0.95 if listed Questionable)

Distributions (dispersion fit by props_backtest on held-out seasons):
  yardage            sqrt(Y) ~ Normal(mu, sigma[market]),  E[Y] = mu^2 + sigma^2
  receptions/TD/INT  negative binomial(mean, r[market]);  anytime TD = P(rush+rec TD >= 1)

Edge board: compares model P to the best executable price across Kalshi /
Polymarket / books and shows a LEAN only if edge >= MIN_EDGE, the market is
calibrated in that probability bin (data/props/calibration.json), the player isn't
injury-listed, and he has >= MIN_GAMES games this season. Everything else: "no edge".
"""

import json
import math
import os
from collections import defaultdict

import kb

HERE = os.path.dirname(os.path.abspath(__file__))
CALIB_PATH = os.path.join(HERE, "data", "props", "calibration.json")

MARKET_STAT = {
    "pass_yds": lambda r: r.get("passing_yards") or 0,
    "rush_yds": lambda r: r.get("rushing_yards") or 0,
    "rec_yds": lambda r: r.get("receiving_yards") or 0,
    "receptions": lambda r: r.get("receptions") or 0,
    "pass_tds": lambda r: r.get("passing_tds") or 0,
    "pass_ints": lambda r: r.get("passing_interceptions") or 0,
    "anytime_td": lambda r: (r.get("rushing_tds") or 0) + (r.get("receiving_tds") or 0),
}
POSITIONS = {
    "pass_yds": ("QB",), "pass_tds": ("QB",), "pass_ints": ("QB",),
    "rush_yds": ("QB", "RB", "WR"), "rec_yds": ("RB", "WR", "TE"),
    "receptions": ("RB", "WR", "TE"), "anytime_td": ("QB", "RB", "WR", "TE"),
}
YARDAGE = ("pass_yds", "rush_yds", "rec_yds")

# defaults; props_backtest overwrites via calibration.json["params"]
PARAMS = {
    "K": 2.5, "DECAY": 0.85, "K_OPP": 4.0, "LG_IMPLIED": 22.5,
    "ALPHA": {m: 0.5 for m in MARKET_STAT},
    "BETA": {"pass_yds": 0.5, "rush_yds": 0.5, "rec_yds": 0.5, "receptions": 0.3,
             "pass_tds": 1.0, "pass_ints": 0.0, "anytime_td": 1.0},
    "SIGMA": {"pass_yds": 2.6, "rush_yds": 2.4, "rec_yds": 2.6},  # sqrt-scale SD
    "R": {"receptions": 12.0, "pass_tds": 20.0, "pass_ints": 30.0, "anytime_td": 8.0},
}
MIN_EDGE = 0.04
# Markets are sharp and know things the model can't (news, roles, weather). Until the
# forward ledger measures it, the model only gets this much weight vs the market fair.
W_MODEL = 0.35
MIN_GAMES = 3
CAL_TOL = 0.05
CAL_MIN_N = 150
SHEET_TO_KB = {"WSH": "WAS", "LA": "LAR", "JAC": "JAX"}


def load_params():
    p = json.loads(json.dumps(PARAMS))
    try:
        with open(CALIB_PATH) as f:
            c = json.load(f)
        for k, v in (c.get("params") or {}).items():
            if isinstance(v, dict):
                p.setdefault(k, {}).update(v)
            else:
                p[k] = v
        p["_calibration"] = c.get("markets", {})
    except (OSError, ValueError):
        p["_calibration"] = {}
    return p


# ------------------------------------------------------------------ data
class History:
    """In-memory player_week + games for a season range (fast walk-forward)."""

    COLS = ("player_id", "player_display_name", "position", "team", "opponent_team",
            "season", "week", "season_type", "passing_yards", "rushing_yards",
            "receiving_yards", "receptions", "passing_tds", "passing_interceptions",
            "rushing_tds", "receiving_tds", "targets", "carries", "attempts")

    def __init__(self, lo, hi, query=None):
        q = query or kb.query
        rows = q("SELECT " + ",".join(self.COLS) + " FROM player_week WHERE season "
                 "BETWEEN ? AND ? AND season_type='REG'", (lo, hi))
        self.by_player = defaultdict(list)          # (season, pid) -> [row] by week
        self.allowed = defaultdict(float)           # (season, opp, pos, market, week)
        self.team_games = defaultdict(set)          # (season, team) -> {week}
        for r in rows:
            r = dict(r)
            self.by_player[(r["season"], r["player_id"])].append(r)
            self.team_games[(r["season"], r["team"])].add(r["week"])
            for m, f in MARKET_STAT.items():
                if r["position"] in POSITIONS[m]:
                    self.allowed[(r["season"], r["opponent_team"], r["position"], m,
                                  r["week"])] += f(r)
        for v in self.by_player.values():
            v.sort(key=lambda r: r["week"])
        self.games = {}
        for g in q("SELECT season, week, home_team, away_team, spread_line, total_line "
                   "FROM games WHERE season BETWEEN ? AND ? AND game_type='REG'", (lo, hi)):
            g = dict(g)
            self.games[(g["season"], g["week"], g["home_team"])] = g
            self.games[(g["season"], g["week"], g["away_team"])] = g
        self._pos_mean = {}
        self._lg_allowed = {}

    def prior_games(self, season, pid, week):
        return [r for r in self.by_player.get((season, pid), []) if r["week"] < week]

    def pos_mean(self, season, pos, market, week):
        """League per-game mean for regulars at pos (players with the stat > 0)."""
        key = (season, pos, market, week)
        if key not in self._pos_mean:
            f = MARKET_STAT[market]
            tot = n = 0
            for (s, _pid), rows in self.by_player.items():
                if s != season:
                    continue
                for r in rows:
                    if r["week"] < week and r["position"] == pos:
                        v = f(r)
                        if v > 0 or market in ("anytime_td", "pass_ints", "pass_tds"):
                            tot += v
                            n += 1
            self._pos_mean[key] = (tot / n) if n else None
        return self._pos_mean[key]

    def opp_factor(self, season, opp, pos, market, week, k_opp):
        """Shrunk (allowed per game by opp) / (league allowed per team-game)."""
        key = (season, pos, market, week)
        if key not in self._lg_allowed:
            tot = 0.0
            tg = 0
            for (s, o, p, m, w), v in self.allowed.items():
                if s == season and p == pos and m == market and w < week:
                    tot += v
            for (s, t), weeks in self.team_games.items():
                if s == season:
                    tg += sum(1 for w in weeks if w < week)
            self._lg_allowed[key] = (tot / tg) if tg else None
        lg = self._lg_allowed[key]
        if not lg:
            return 1.0
        g = sum(1 for w in self.team_games.get((season, opp), ()) if w < week)
        tot = sum(self.allowed.get((season, opp, pos, market, w), 0.0)
                  for w in self.team_games.get((season, opp), ()) if w < week)
        return (tot + k_opp * lg) / ((g + k_opp) * lg)

    def implied_points(self, season, week, team):
        g = self.games.get((season, week, team))
        if not g or g.get("spread_line") is None or g.get("total_line") is None:
            return None, None
        sp, tot = float(g["spread_line"]), float(g["total_line"])
        home = g["home_team"] == team
        mine = (tot + sp) / 2.0 if home else (tot - sp) / 2.0  # nflverse: + = home fav
        opp = g["away_team"] if home else g["home_team"]
        return mine, opp


# ---------------------------------------------------------------- projection
def project(hist, season, pid, week, market, params=None, opp=None, implied=None,
            questionable=False):
    """Projected mean for the player's game in `week`, or None if ineligible."""
    P = params or PARAMS
    prior_rows = hist.prior_games(season, pid, week)
    last = hist.by_player.get((season - 1, pid), [])
    ref = prior_rows[-1] if prior_rows else (last[-1] if last else None)
    if not ref or ref["position"] not in POSITIONS[market]:
        return None
    pos, team = ref["position"], (prior_rows[-1]["team"] if prior_rows else ref["team"])
    f = MARKET_STAT[market]
    xs = [f(r) for r in prior_rows]
    if len(last) >= 4:
        prior = sum(f(r) for r in last) / len(last)
    else:
        prior = hist.pos_mean(season, pos, market, week) or hist.pos_mean(
            season - 1, pos, market, 99) or 0.0
    n = len(xs)
    w = [P["DECAY"] ** (n - 1 - i) for i in range(n)]
    base = (sum(wi * x for wi, x in zip(w, xs)) + P["K"] * prior) / (sum(w) + P["K"])
    if implied is None or opp is None:
        imp, o = hist.implied_points(season, week, team)
        implied = implied if implied is not None else imp
        opp = opp or o
    of = hist.opp_factor(season, opp, pos, market, week, P["K_OPP"]) if opp else 1.0
    sf = (implied / P["LG_IMPLIED"]) if implied else 1.0
    mean = (max(base, 0.0) * (max(of, 0.2) ** P["ALPHA"][market])
            * (max(sf, 0.3) ** P["BETA"][market]))
    if questionable:
        mean *= 0.95
    return {"mean": mean, "base": base, "opp_factor": of, "script": sf, "games": n,
            "position": pos, "team": team, "opp": opp}


def _phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _nb_cdf(k, m, r):
    """P(X <= k) for negative binomial with mean m, dispersion r (Poisson as r->inf)."""
    if k < 0:
        return 0.0
    m = max(m, 1e-6)
    if r >= 1e6:
        p = math.exp(-m)
        c = p
        for i in range(1, k + 1):
            p *= m / i
            c += p
        return min(c, 1.0)
    q = m / (r + m)
    p = (r / (r + m)) ** r
    c = p
    for i in range(k):
        p *= (i + r) / (i + 1) * q
        c += p
    return min(c, 1.0)


def p_over(mean, line, market, params=None):
    P = params or PARAMS
    if mean is None:
        return None
    if market in YARDAGE:
        s = P["SIGMA"][market]
        mu = math.sqrt(max(mean - s * s, 0.25))
        if line <= 0:
            return 1.0
        return 1.0 - _phi((math.sqrt(line) - mu) / s)
    k = int(math.floor(line))  # over 4.5 == X >= 5 == 1 - CDF(4)
    return 1.0 - _nb_cdf(k, mean, P["R"][market])


# ------------------------------------------------------------- live edge board
def _live_context(season, week):
    """{kb_team: (implied_points, opp)} from live ESPN lines, KB lines as fallback."""
    ctx = {}
    try:
        import spreads
        p = spreads.fetch_week(week, season)
        for e in p.get("events", []):
            c = e["competitions"][0]
            if c["status"]["type"]["state"] != "pre":
                continue
            t = {x["homeAway"]: x["team"]["abbreviation"] for x in c["competitors"]}
            odds = (c.get("odds") or [{}])[0]
            sp, tot = odds.get("spread"), odds.get("overUnder")
            h, a = SHEET_TO_KB.get(t["home"], t["home"]), SHEET_TO_KB.get(t["away"], t["away"])
            if sp is None or tot is None:
                continue
            home_pts = (tot - sp) / 2.0  # ESPN spread is home-relative, negative = fav
            ctx[h] = (home_pts, a)
            ctx[a] = (tot - home_pts, h)
    except Exception:  # noqa: BLE001 — fall back to KB lines inside project()
        pass
    return ctx


def _calibrated(cal, market, p):
    c = cal.get(market)
    if not c:
        return False, "no backtest yet"
    for b in c.get("bins", []):
        if b["lo"] <= p < b["hi"]:
            if b["n"] < CAL_MIN_N:
                return False, f"thin bin (n={b['n']})"
            if abs(b["obs"] - b["pred"]) > CAL_TOL:
                return False, f"miscalibrated bin ({b['pred']:.2f} vs {b['obs']:.2f})"
            return True, ""
    return False, "bin missing"


_HIST = {}


def _hist(season):
    if season not in _HIST:
        _HIST.clear()
        _HIST[season] = History(season - 1, season)
    return _HIST[season]


def _injury_map():
    """{gsis_id: status} from the raw Sleeper bundle (names differ: Josh vs Joshua)."""
    try:
        import sleeper
        out = {}
        for p in sleeper.get_players()["players"].values():
            if p.get("gsis_id") and p.get("injury_status"):
                out[p["gsis_id"].strip()] = p["injury_status"]
        return out
    except Exception:  # noqa: BLE001
        return {}


OUT_STATUSES = ("Out", "IR", "Doubtful", "PUP", "Sus", "NA")
MAX_DISAGREE = 0.20  # model vs sharp market gap above this = model is missing info


def _role_change(hist, season, week, player, market, inj):
    """Teammate at the same position, out this week, who out-produced this player."""
    f = MARKET_STAT[market]
    mine = hist.prior_games(season, player["player_id"], week)
    my_avg = (sum(f(r) for r in mine) / len(mine)) if mine else 0.0
    for (s, pid), rows in hist.by_player.items():
        if s != season or pid == player["player_id"] or inj.get(pid) not in OUT_STATUSES:
            continue
        prior = [r for r in rows if r["week"] < week]
        if not prior or prior[-1]["team"] != player["team"] or \
                prior[-1]["position"] != player.get("position", prior[-1]["position"]):
            continue
        avg = sum(f(r) for r in prior) / len(prior)
        if avg > my_avg:
            return prior[-1]["player_display_name"]
    return None


def edge_board(event="", market="", snapshot=None):
    import picks
    import props_identity
    import props_markets
    P = load_params()
    cal = P.get("_calibration", {})
    snap = snapshot or props_markets.latest_snapshot()
    if not snap:
        return {"ready": False, "why": "no market prices yet — refresh on the Markets tab"}
    week, season = picks.current_week_year()
    hist = _hist(season)
    ctx = _live_context(season, week)
    inj = _injury_map()
    groups = {}
    for r in snap["rows"]:
        if not r["usable"] or (event and r.get("event_key") != event) or \
                (market and r["market"] != market):
            continue
        groups.setdefault((r["player"], r["market"], r["line"], r.get("event_key")),
                          []).append(r)
    out = []
    for (player, mk, line, ek), quotes in groups.items():
        teams = [SHEET_TO_KB.get(t, t) for t in (ek or "").split("@") if t]
        pl = props_identity.resolve(player, season, teams)
        if not pl:
            continue
        if pl["team"] not in ctx:
            continue  # kicked off / final / no live line: prices are stale or settling
        imp, opp = ctx[pl["team"]]
        status = inj.get(pl["player_id"])
        if status in OUT_STATUSES:
            continue
        pj = project(hist, season, pl["player_id"], week, mk, P, opp=opp, implied=imp,
                     questionable=(status == "Questionable"))
        if not pj:
            continue
        pm = p_over(pj["mean"], line, mk, P)
        over_cost, under_cost, best_o, best_u = 1.0, 1.0, "", ""
        for q in quotes:
            if q["source"] == "oddsapi":
                raw = q.get("p_over_raw") or q["p_fair"]
                oc, uc = raw, 1 - q["p_fair"] + (raw - q["p_fair"])
            else:
                oc = q["p_ask"] if q["p_ask"] is not None else q["p_fair"]
                uc = (1 - q["p_bid"]) if q["p_bid"] is not None else 1 - q["p_fair"]
            if oc < over_cost:
                over_cost, best_o = oc, q["book"]
            if uc < under_cost:
                under_cost, best_u = uc, q["book"]
        fair = sum(q["p_fair"] for q in quotes) / len(quotes)
        pb = W_MODEL * pm + (1 - W_MODEL) * fair  # market-anchored blend
        e_over, e_under = pb - over_cost, (1 - pb) - under_cost
        side, edge, book, cost = (("over", e_over, best_o, over_cost) if e_over >= e_under
                                  else ("under", e_under, best_u, under_cost))
        caveats = []
        if status:
            caveats.append(f"injury: {status}")
        if pj["games"] < MIN_GAMES:
            caveats.append(f"only {pj['games']} games")
        ok, why = _calibrated(cal, mk, pm if side == "over" else 1 - pm)
        if not ok:
            caveats.append("model " + why)
        lean = None
        if edge >= MIN_EDGE and ok and not status and pj["games"] >= MIN_GAMES:
            lean = f"{side.upper()} {line}"
        if not 0.03 <= fair <= 0.97:
            continue  # near-certain / settling markets carry no information
        rc = _role_change(hist, season, week, pl, mk, inj)
        if rc:
            caveats.append(f"role change: {rc} out — model history understates usage")
        if abs(pm - fair) > MAX_DISAGREE:
            caveats.append(f"model {pm:.0%} vs market {fair:.0%}: gap too large to trust "
                           "(likely news the model lacks)")
        if lean and (rc or abs(pm - fair) > MAX_DISAGREE):
            lean = None
        out.append({"player": pl["name"], "team": pl["team"], "event_key": ek,
                    "player_id": pl["player_id"], "week": week, "season": season,
                    "market": mk, "line": line, "p_model": round(pm, 3),
                    "p_blend": round(pb, 3),
                    "mean": round(pj["mean"], 1), "p_market": round(cost, 3),
                    "p_fair": round(fair, 3), "best_book": book, "side": side,
                    "edge": round(edge, 3), "lean": lean, "caveats": caveats,
                    "sources": sorted({q["book"] for q in quotes})})
    out.sort(key=lambda r: (r["lean"] is None, -r["edge"]))
    best = set()  # one lean per player/market/side: the best-priced ladder rung
    for r in out:
        if not r["lean"]:
            continue
        k = (r["player_id"], r["market"], r["side"])
        if k in best:
            r["lean"] = None
            r["caveats"].append("better line on the board")
        best.add(k)
    out.sort(key=lambda r: (r["lean"] is None, -r["edge"]))
    return {"ready": True, "week": week, "season": season,
            "fetched_at": snap.get("fetched_at"), "calibrated": bool(cal),
            "w_model": W_MODEL, "proven": ledger_summary().get("proven", False),
            "rows": out[:6000]}


# ------------------------------------------------------------------ ledger
LEDGER_PATH = os.path.join(HERE, "data", "props", "ledger.jsonl")
LEDGER_PROVEN_N = 200  # graded leans needed before the board stops saying "unproven"


def log_board(board):
    """Append this board's pre-game rows (one per player/market/line/week, first seen
    wins) so they can be graded after the games."""
    if not board.get("ready"):
        return 0
    seen = set()
    try:
        with open(LEDGER_PATH) as f:
            for ln in f:
                r = json.loads(ln)
                seen.add((r["season"], r["week"], r["player_id"], r["market"], r["line"]))
    except OSError:
        pass
    n = 0
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, "a") as f:
        for r in board["rows"]:
            k = (r["season"], r["week"], r["player_id"], r["market"], r["line"])
            if k in seen:
                continue
            seen.add(k)
            f.write(json.dumps(dict(r, logged_at=board.get("fetched_at"))) + "\n")
            n += 1
    return n


def grade_ledger(query=None):
    """Fill in the actual result for ledger rows whose games are in player_week.
    One query per (season, week) — run nightly, not per page load."""
    q = query or kb.query
    try:
        with open(LEDGER_PATH) as f:
            rows = [json.loads(ln) for ln in f]
    except OSError:
        return {"graded": 0}
    todo = {(r["season"], r["week"]) for r in rows if r.get("actual") is None}
    stats = {}
    for season, week in todo:
        for g in q("SELECT * FROM player_week WHERE season=? AND week=? "
                   "AND season_type='REG'", (season, week)):
            g = dict(g)
            stats[(season, week, g["player_id"])] = g
    n = 0
    for r in rows:
        if r.get("actual") is not None:
            continue
        g = stats.get((r["season"], r["week"], r["player_id"]))
        if not g:
            continue
        y = MARKET_STAT[r["market"]](g)
        r["actual"] = y
        r["over_hit"] = y > r["line"]
        n += 1
    if n:
        tmp = LEDGER_PATH + ".tmp"
        with open(tmp, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        os.replace(tmp, LEDGER_PATH)
    return {"graded": n}


def ledger_summary():
    try:
        with open(LEDGER_PATH) as f:
            rows = [json.loads(ln) for ln in f]
    except OSError:
        return {"rows": 0, "proven": False}
    g = [r for r in rows if r.get("actual") is not None]
    leans = [r for r in g if r.get("lean")]
    def _won(r):
        return r["over_hit"] if r["side"] == "over" else not r["over_hit"]
    roi = (sum((1 / r["p_market"] - 1) if _won(r) else -1 for r in leans) / len(leans)
           if leans else None)
    brier = lambda key: (sum((r[key] - r["over_hit"]) ** 2 for r in g) / len(g)  # noqa: E731
                         if g else None)
    return {"rows": len(rows), "graded": len(g), "leans_graded": len(leans),
            "lean_win_rate": (sum(_won(r) for r in leans) / len(leans)) if leans else None,
            "lean_roi": roi, "brier_model": brier("p_model"), "brier_market": brier("p_fair"),
            "brier_blend": brier("p_blend") if g and "p_blend" in g[0] else None,
            "proven": bool(leans and len(leans) >= LEDGER_PROVEN_N and roi and roi > 0)}


def prob_for_claim(player, market, line):
    """Model P(over) for the player's next game (used by the verifier)."""
    import picks
    if market not in MARKET_STAT:
        return None
    P = load_params()
    week, season = picks.current_week_year()
    hist = _hist(season)
    imp, opp = _live_context(season, week).get(player["team"], (None, None))
    pj = project(hist, season, player["player_id"], week, market, P, opp=opp, implied=imp)
    if not pj:
        return None
    return {"p": round(p_over(pj["mean"], line, market, P), 3), "mean": round(pj["mean"], 1),
            "week": week}


# -------------------------------------------------------------- real bets
BETS_PATH = os.path.join(HERE, "data", "props", "bets.jsonl")


def log_bet(bet):
    """Append one real ticket (dict: season, week, player_id, player, market, line,
    side, stake, payout, price, book, placed_at, p_model, p_blend)."""
    os.makedirs(os.path.dirname(BETS_PATH), exist_ok=True)
    with open(BETS_PATH, "a") as f:
        f.write(json.dumps(bet) + "\n")


def grade_bets(query=None):
    """Settle open tickets from player_week; returns the running P&L."""
    q = query or kb.query
    try:
        with open(BETS_PATH) as f:
            bets = [json.loads(ln) for ln in f]
    except OSError:
        return {"bets": 0}
    changed = False
    for b in bets:
        if b.get("result"):
            continue
        got = q("SELECT * FROM player_week WHERE season=? AND week=? AND player_id=? "
                "AND season_type='REG'", (b["season"], b["week"], b["player_id"]))
        if not got:
            continue
        y = MARKET_STAT[b["market"]](dict(got[0]))
        won = (y > b["line"]) if b["side"] == "over" else (y < b["line"])
        b.update(actual=y, result="win" if won else "loss",
                 profit=round((b["payout"] - b["stake"]) if won else -b["stake"], 2))
        changed = True
    if changed:
        tmp = BETS_PATH + ".tmp"
        with open(tmp, "w") as f:
            for b in bets:
                f.write(json.dumps(b) + "\n")
        os.replace(tmp, BETS_PATH)
    done = [b for b in bets if b.get("result")]
    return {"bets": len(bets), "settled": len(done),
            "record": f"{sum(b['result'] == 'win' for b in done)}-"
                      f"{sum(b['result'] == 'loss' for b in done)}",
            "profit": round(sum(b["profit"] for b in done), 2),
            "staked": round(sum(b["stake"] for b in bets), 2)}
