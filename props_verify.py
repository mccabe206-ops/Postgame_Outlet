"""Verify prop claims pasted from X (or anywhere): state what's TRUE, then the caveats.

Two claim families:
  player  — "Xavier Hutchinson Over 29.5 Rec Yds 4/4", "TYLER SHOUGH 250+ PASS YARDS",
            "Judkins anytime TD"
  team    — "EAGLES ALLOW MOST RUSH TDS TO QB", "BUCCANEERS ALLOW 7TH MOST RECEIVING
            YARDS TO RB" (defense allowed), "PHI: 4TH MOST RZ WR TARGETS" (offense)

Player verdicts come from KB `player_week` (current season, REG); team ranks from
`player_week` (by opponent) or `pbp` (red-zone = yardline_100 <= 20). Each verdict
carries: games played / team games (DNPs listed), per-game values + margin over the
line, injury designation (Sleeper), best usable market price (props_markets cache),
and — once props_model is in — the model probability.

Never claims more certainty than the data allows: anything it can't compute is
returned as "unverifiable" with the reason.
"""

import re

import kb
import props_identity
from injuries import _norm

# market key -> (player_week expression, human label)
STATS = {
    "pass_yds": ("passing_yards", "pass yds"),
    "rush_yds": ("rushing_yards", "rush yds"),
    "rec_yds": ("receiving_yards", "rec yds"),
    "receptions": ("receptions", "receptions"),
    "pass_tds": ("passing_tds", "pass TDs"),
    "pass_ints": ("passing_interceptions", "INTs"),
    "anytime_td": ("COALESCE(rushing_tds,0)+COALESCE(receiving_tds,0)", "TDs"),
    "rush_rec_yds": ("COALESCE(rushing_yards,0)+COALESCE(receiving_yards,0)",
                     "rush+rec yds"),
    "completions": ("completions", "completions"),
    "pass_att": ("attempts", "pass att"),
    "rush_att": ("carries", "carries"),
    "targets": ("targets", "targets"),
}

# phrase -> market key (longest first when matching)
_STAT_WORDS = [
    (r"rush(?:ing)?\s*\+\s*rec(?:eiving)?\s*y(?:ar)?ds", "rush_rec_yds"),
    (r"pass(?:ing)?\s*y(?:ar)?ds", "pass_yds"),
    (r"rush(?:ing)?\s*y(?:ar)?ds", "rush_yds"),
    (r"rec(?:eiving)?\s*y(?:ar)?ds", "rec_yds"),
    (r"receptions?|recs?\b|catches", "receptions"),
    (r"pass(?:ing)?\s*(?:td|touchdown)s?", "pass_tds"),
    (r"(?:interceptions?|ints?)\b", "pass_ints"),
    (r"anytime\s*(?:td|touchdown)s?|(?:td|touchdown)s?\b", "anytime_td"),
    (r"completions?", "completions"),
    (r"pass(?:ing)?\s*att(?:empt)?s?", "pass_att"),
    (r"rush(?:ing)?\s*att(?:empt)?s?|carries", "rush_att"),
    (r"targets?", "targets"),
]
_STAT_RE = "(?P<stat>" + "|".join(p for p, _ in _STAT_WORDS) + ")"
_NUM = r"(?P<line>\d+(?:\.\d+)?)"

_PLAYER_PATTERNS = [
    # "Name Over 29.5 Rec Yds 4/4"  /  "Name o29.5 receiving yards"
    re.compile(r"^(?P<player>[A-Za-z.'\- ]+?)\s+(?:over|o)\s*" + _NUM + r"\s+" + _STAT_RE
               + r"(?:\s+(?P<hits>\d+)\s*/\s*(?P<games>\d+))?", re.I),
    # "Name Under 40.5 Rush Yds"
    re.compile(r"^(?P<player>[A-Za-z.'\- ]+?)\s+(?P<under>under|u)\s*" + _NUM + r"\s+"
               + _STAT_RE + r"(?:\s+(?P<hits>\d+)\s*/\s*(?P<games>\d+))?", re.I),
    # "TYLER SHOUGH 250+ PASS YARDS"
    re.compile(r"^(?P<player>[A-Za-z.'\- ]+?)\s+" + r"(?P<plus>\d+(?:\.\d+)?)\+\s*"
               + _STAT_RE + r"(?:\s+(?P<hits>\d+)\s*/\s*(?P<games>\d+))?", re.I),
    # "Judkins anytime TD"
    re.compile(r"^(?P<player>[A-Za-z.'\- ]+?)\s+(?P<stat>anytime\s*(?:td|touchdown))", re.I),
]

_RANK = r"(?:(?P<rank>\d+)(?:st|nd|rd|th)\s+)?most"
_POS = r"(?P<pos>qbs?|rbs?|wrs?|tes?)"
_TEAM_STAT = (r"(?P<rz>rz\s+|red[\s-]?zone\s+)?(?P<tstat>receiving\s+yards|rec\s+yds|"
              r"receiving\s+tds|receptions|targets|rush(?:ing)?\s+yards|rush\s+yds|"
              r"rush(?:ing)?\s+tds|rush\s+attempts|carries|pass(?:ing)?\s+yards|"
              r"pass\s+yds|pass(?:ing)?\s+tds|pass\s+attempts|completions|tds|"
              r"touchdowns)")
_TEAM_PATTERNS = [
    # "JAGUARS RANK #8 IN SACKS" / "VIKINGS RANK 4TH IN INTERCEPTIONS"  (defense)
    re.compile(r"^(?P<team>[A-Za-z0-9.' ]+?)\s+ranks?\s+#?(?P<rank>\d+)(?:st|nd|rd|th)?\s+in\s+"
               r"(?P<tstat>sacks|interceptions)", re.I),
    # "<TEAM> ALLOW <rank> MOST <stat> TO <POS>"  (defense allowed)
    re.compile(r"^(?P<team>[A-Za-z0-9.' ]+?)\s+allows?\s+" + _RANK + r"\s+" + _TEAM_STAT
               + r"\s+to\s+" + _POS, re.I),
    # "PHI: 4TH MOST RZ WR TARGETS"  (offense)
    re.compile(r"^(?P<team>[A-Za-z]{2,3}):\s*" + _RANK + r"\s+" + r"(?P<rz>rz\s+)?"
               + _POS + r"\s+(?P<tstat>[a-z ]+?)\s*$", re.I),
]

_TEAM_STAT_KEY = [
    (r"receiving\s+yards|rec\s+yds|receiving\s+yds", "rec_yds"),
    (r"receiving\s+tds", "rec_tds"), (r"receptions", "receptions"),
    (r"targets", "targets"), (r"rush(?:ing)?\s+(?:yards|yds)", "rush_yds"),
    (r"rush(?:ing)?\s+tds", "rush_tds"), (r"rush\s+attempts|carries", "carries"),
    (r"pass(?:ing)?\s+(?:yards|yds)", "pass_yds"), (r"pass(?:ing)?\s+tds", "pass_tds"),
    (r"pass\s+attempts", "pass_att"), (r"completions", "completions"),
    (r"tds|touchdowns", "tds"), (r"sacks", "sacks"), (r"interceptions", "def_ints"),
]


def _stat_key(text):
    for pat, key in _STAT_WORDS:
        if re.fullmatch(pat, text.strip(), re.I):
            return key
    return None


def _team_stat_key(text):
    t = re.sub(r"\s+", " ", text.strip().lower())
    for pat, key in _TEAM_STAT_KEY:
        if re.fullmatch(pat, t):
            return key
    return None


def parse_claims(text):
    """Split pasted text into structured claims; unparsed lines are kept as such."""
    out = []
    for raw in re.split(r"[\r\n]+", text or ""):
        line = re.sub(r"\s+", " ", raw).strip(" •-–—*|\t")
        if not line:
            continue
        c = _parse_player(line) or _parse_team(line)
        out.append(c or {"kind": "unparsed", "text": line})
    return out


def _parse_player(line):
    for pat in _PLAYER_PATTERNS:
        m = pat.match(line)
        if not m:
            continue
        g = m.groupdict()
        key = _stat_key(g["stat"])
        if not key:
            continue
        if g.get("plus"):
            ln = float(g["plus"]) - 0.5
        elif g.get("line"):
            ln = float(g["line"])
        else:
            ln = 0.5
        return {"kind": "player", "text": line, "player": g["player"].strip(),
                "market": key, "line": ln,
                "side": "under" if g.get("under") else "over",
                "claimed_hits": int(g["hits"]) if g.get("hits") else None,
                "claimed_games": int(g["games"]) if g.get("games") else None}
    return None


def _parse_team(line):
    for i, pat in enumerate(_TEAM_PATTERNS):
        m = pat.match(line)
        if not m:
            continue
        g = m.groupdict()
        key = _team_stat_key(g["tstat"])
        if not key:
            return {"kind": "unparsed", "text": line, "why": "stat not supported"}
        if key in ("sacks", "def_ints"):
            return {"kind": "team", "text": line, "team": g["team"].strip(),
                    "side": "defense", "rank": int(g["rank"]), "redzone": False,
                    "pos": None, "stat": key}
        return {"kind": "team", "text": line, "team": g["team"].strip(),
                # "PHI: 4TH MOST ..." sheets are matchup notes: ambiguous offense vs allowed
                "side": "allowed" if i == 1 else "either",
                "rank": int(g["rank"]) if g.get("rank") else 1,
                "redzone": bool(g.get("rz")), "pos": g["pos"].upper().rstrip("S"),
                "stat": key}
    return None


# ------------------------------------------------------------------ helpers
def current_season():
    r = kb.query("SELECT MAX(season) AS s FROM player_week")
    return r[0]["s"]


def team_weeks(team, season, through_week=99):
    """Weeks the team has a completed REG game (for 'played X of Y'): union of the
    team's player_week rows and games with a result (either source can lag)."""
    a = kb.query("SELECT DISTINCT week FROM player_week WHERE season=? AND team=? "
                 "AND season_type='REG' AND week<=?", (season, team, through_week))
    b = kb.query("SELECT week FROM games WHERE season=? AND game_type='REG' "
                 "AND result IS NOT NULL AND (home_team=? OR away_team=?) AND week<=?",
                 (season, team, team, through_week))
    return sorted({r["week"] for r in a} | {r["week"] for r in b})


def game_log(player_id, market, season, through_week=99):
    expr = STATS[market][0]
    rows = kb.query(
        f"SELECT week, opponent_team AS opp, {expr} AS v FROM player_week "
        "WHERE season=? AND player_id=? AND season_type='REG' AND week<=? ORDER BY week",
        (season, player_id, through_week))
    return [{"week": r["week"], "opp": r["opp"], "value": r["v"] or 0} for r in rows]


def injury_status(name, team):
    try:
        import sleeper
        for p in sleeper.nfl_players(sleeper.get_players()):
            if _norm(p["name"]) == _norm(name) and (not team or p["team"] == team):
                return {"status": p.get("status"), "body_part": p.get("body_part"),
                        "practice": p.get("practice")}
    except Exception:  # noqa: BLE001 — injury layer is best-effort
        return None
    return None


def market_price(name, market, line, snapshot=None):
    """Best usable market quote for this player/market at (or nearest) the line."""
    try:
        import props_markets
        snap = snapshot or props_markets.latest_snapshot()
    except Exception:  # noqa: BLE001
        snap = None
    if not snap:
        return None
    n = _norm(name)
    rows = [r for r in snap["rows"] if r["usable"] and r["market"] == market
            and _norm(r["player"]) == n]
    if not rows:
        return None
    best = min(rows, key=lambda r: (abs(r["line"] - line), r["spread"] or 0))
    same = [r for r in rows if r["line"] == best["line"]]
    return {"line": best["line"], "exact": best["line"] == line,
            "quotes": [{"source": r["source"], "book": r["book"],
                        "p": round(r["p_fair"], 3)} for r in same],
            "p": round(sum(r["p_fair"] for r in same) / len(same), 3),
            "fetched_at": snap.get("fetched_at")}


# ---------------------------------------------------------------- verifiers
YARDAGE = ("pass_yds", "rush_yds", "rec_yds", "rush_rec_yds")


def verify_player(c, season=None, snapshot=None, model=None, through_week=99,
                  assume_perfect=False):
    """assume_perfect: the sheet claims every game hit ("100%" / "perfect props")
    even when a line has no "4/4". Without it, a bare pick gets a neutral record."""
    season = season or current_season()
    p = props_identity.resolve(c["player"], season)
    if not p:
        return dict(c, verdict="unverifiable", why="player not found / ambiguous")
    log = game_log(p["player_id"], c["market"], season, through_week)
    over = c["side"] == "over"
    for g in log:
        g["hit"] = (g["value"] > c["line"]) if over else (g["value"] < c["line"])
        g["margin"] = round(g["value"] - c["line"], 1)
    hits = sum(g["hit"] for g in log)
    tw = team_weeks(p["team"], season, through_week)
    played = [g["week"] for g in log]
    dnp = [w for w in tw if w not in played]
    claimed = c.get("claimed_hits"), c.get("claimed_games")
    if not log:
        verdict = "unverifiable"
    elif claimed[0] is not None:
        verdict = "true" if (hits, len(log)) == claimed else "false"
    elif assume_perfect:  # "100%"-style sheets imply every game played hit
        verdict = "true" if hits == len(log) else "false"
    else:
        verdict = "record"  # a pick, not a hit-rate claim: report the record only
    caveats = []
    if dnp:
        caveats.append(f"played {len(log)} of {len(tw)} team games (DNP wk "
                       + ", ".join(str(w) for w in dnp) + ")")
    if 0 < len(log) <= 3:
        caveats.append(f"small sample: {len(log)} game(s)")
    thin = ([g for g in log if g["hit"] and abs(g["margin"]) <= max(3, 0.1 * c["line"])]
            if c["market"] in YARDAGE else [])
    if thin:
        caveats.append(f"{len(thin)} hit(s) by a thin margin ("
                       + ", ".join(f"wk{g['week']} {g['margin']:+}" for g in thin) + ")")
    inj = injury_status(p["name"], p["team"])
    if inj and inj.get("status"):
        caveats.append(f"injury: {inj['status']}"
                       + (f" ({inj['body_part']})" if inj.get("body_part") else ""))
    mkt = market_price(p["name"], c["market"], c["line"], snapshot)
    if mkt:
        caveats.append(f"market says {mkt['p']*100:.0f}% at o{mkt['line']}"
                       + ("" if mkt["exact"] else " (nearest line)"))
    out = dict(c, verdict=verdict, resolved=p, hits=hits, games=len(log),
               team_games=len(tw), dnp_weeks=dnp, log=log, injury=inj, price=mkt,
               caveats=caveats, label=STATS[c["market"]][1])
    if model is not None:
        try:
            out["model"] = model(p, c["market"], c["line"])
        except Exception as e:  # noqa: BLE001
            out["model"] = {"error": str(e)[:120]}
    return out


TEAM_NAMES = {  # nickname / city -> ESPN abbr (claims use either)
    "cardinals": "ARI", "falcons": "ATL", "ravens": "BAL", "bills": "BUF",
    "panthers": "CAR", "bears": "CHI", "bengals": "CIN", "browns": "CLE",
    "cowboys": "DAL", "broncos": "DEN", "lions": "DET", "packers": "GB",
    "texans": "HOU", "colts": "IND", "jaguars": "JAX", "chiefs": "KC",
    "chargers": "LAC", "rams": "LAR", "raiders": "LV", "dolphins": "MIA",
    "vikings": "MIN", "patriots": "NE", "saints": "NO", "giants": "NYG",
    "jets": "NYJ", "eagles": "PHI", "steelers": "PIT", "seahawks": "SEA",
    "49ers": "SF", "niners": "SF", "buccaneers": "TB", "bucs": "TB", "titans": "TEN",
    "commanders": "WAS", "jac": "JAX", "wsh": "WAS", "la": "LAR", "lar": "LAR",
}

# team stat -> (player_week expr, pbp filter + value expr, pbp player-id col)
_TEAM_PW = {"rec_yds": "receiving_yards", "rec_tds": "receiving_tds",
            "receptions": "receptions", "targets": "targets", "rush_yds": "rushing_yards",
            "rush_tds": "rushing_tds", "carries": "carries", "pass_yds": "passing_yards",
            "pass_tds": "passing_tds", "pass_att": "attempts", "completions": "completions",
            "tds": "COALESCE(rushing_tds,0)+COALESCE(receiving_tds,0)"}
_TEAM_PBP = {  # red-zone versions: (where, value, player col)
    "targets": ("pass_attempt=1 AND sack=0 AND receiver_player_id IS NOT NULL", "1",
                "receiver_player_id"),
    "receptions": ("complete_pass=1", "1", "receiver_player_id"),
    "carries": ("rush_attempt=1", "1", "rusher_player_id"),
    "rec_tds": ("pass_touchdown=1", "1", "receiver_player_id"),
    "rush_tds": ("rush_touchdown=1", "1", "rusher_player_id"),
    "tds": ("touchdown=1 AND td_player_id IS NOT NULL", "1", "td_player_id"),
}


def _team_abbr(t):
    s = t.strip().lower()
    return TEAM_NAMES.get(s, s.upper())


def _team_games(season, through_week, side):
    tcol = "defteam" if side == "allowed" else "posteam"
    return {r["t"]: r["g"] for r in kb.query(
        f"SELECT {tcol} AS t, COUNT(DISTINCT game_id) AS g FROM pbp WHERE season=? "
        f"AND season_type='REG' AND week<=? AND {tcol} IS NOT NULL GROUP BY {tcol}",
        (season, through_week))}


def team_ranks(stat, pos, side, redzone, season, through_week=99):
    """[(team, total, games, per_game)] for ALL teams (zero-filled), total desc."""
    games = _team_games(season, through_week, side)
    if stat in ("sacks", "def_ints"):  # team defense counts straight from pbp
        col = "sack" if stat == "sacks" else "interception"
        rows = kb.query(
            f"SELECT defteam AS t, SUM({col}) AS v FROM pbp WHERE season=? "
            f"AND season_type='REG' AND week<=? GROUP BY defteam", (season, through_week))
        vals = {r["t"]: r["v"] or 0 for r in rows if r["t"]}
    elif redzone:
        if stat not in _TEAM_PBP:
            return None
        where, val, pcol = _TEAM_PBP[stat]
        tcol = "defteam" if side == "allowed" else "posteam"
        rows = kb.query(
            f"SELECT p.{tcol} AS t, SUM({val}) AS v "
            f"FROM pbp p JOIN (SELECT DISTINCT player_id, position FROM player_week "
            f"WHERE season=?) w ON w.player_id=p.{pcol} "
            f"WHERE p.season=? AND p.season_type='REG' AND p.week<=? "
            f"AND p.yardline_100<=20 AND w.position=? AND {where} GROUP BY p.{tcol}",
            (season, season, through_week, pos))
        vals = {r["t"]: r["v"] or 0 for r in rows if r["t"]}
    else:
        expr = _TEAM_PW.get(stat)
        if not expr:
            return None
        team_col = "opponent_team" if side == "allowed" else "team"
        rows = kb.query(
            f"SELECT {team_col} AS t, SUM({expr}) AS v FROM player_week WHERE season=? "
            f"AND season_type='REG' AND week<=? AND position=? GROUP BY {team_col}",
            (season, through_week, pos))
        vals = {r["t"]: r["v"] or 0 for r in rows if r["t"]}
    out = [(t, vals.get(t, 0), g, (vals.get(t, 0) / g) if g else 0.0)
           for t, g in games.items()]
    return sorted(out, key=lambda x: -x[1])


def _rank_of(table, team, idx):
    """1-based rank range (best, worst) for team on column idx, ties shared."""
    vals = [row[idx] for row in table]
    mine = next((row[idx] for row in table if row[0] == team), None)
    if mine is None:
        return None
    better = sum(1 for v in vals if v > mine)
    tied = sum(1 for v in vals if v == mine)
    return better + 1, better + tied


def verify_team(c, season=None, through_week=99):
    if c.get("side") == "either":  # grade both readings, keep the one that matches
        res = [verify_team(dict(c, side=sd), season, through_week)
               for sd in ("allowed", "offense")]
        order = {"true": 0, "close": 1, "false": 2, "unverifiable": 3}
        best = min(res, key=lambda r: order.get(r["verdict"], 9))
        other = [r for r in res if r is not best][0]
        best = dict(best)
        best["caveats"] = ([f"read as {'defense ALLOWED' if best['side'] == 'allowed' else 'team OFFENSE'}"
                            " (sheet wording is ambiguous)"] + best.get("caveats", [])
                           + [f"other reading ({other['side']}): "
                              + "; ".join(other.get("caveats", [])[:1])])
        return best
    season = season or current_season()
    team = _team_abbr(c["team"])
    tbl = team_ranks(c["stat"], c.get("pos"), c["side"], c.get("redzone"), season,
                     through_week)
    if not tbl:
        return dict(c, verdict="unverifiable",
                    why="stat not computable from KB" + (" (red zone)" if c["redzone"] else ""))
    tot = _rank_of(tbl, team, 1)
    pg = _rank_of(sorted(tbl, key=lambda x: -x[3]), team, 3)
    if not tot:
        return dict(c, verdict="unverifiable", why=f"team {team} not found")
    want = c["rank"]
    ok_tot = tot[0] <= want <= tot[1]
    ok_pg = pg[0] <= want <= pg[1]
    row = next(r for r in tbl if r[0] == team)
    fmt = lambda r: f"{r[0]}" if r[0] == r[1] else f"T-{r[0]}"  # noqa: E731
    caveats = [f"actual: {fmt(tot)} by total ({row[1]:.0f} in {row[2]} g), "
               f"{fmt(pg)} per game ({row[3]:.1f}/g)"]
    if row[2] <= 4:
        caveats.append(f"small sample: {row[2]} games")
    near = abs(tot[0] - want) <= 2 or abs(pg[0] - want) <= 2
    verdict = "true" if (ok_tot or ok_pg) else ("close" if near else "false")
    return dict(c, verdict=verdict, team_abbr=team, rank_total=tot, rank_pg=pg,
                value=row[1], games=row[2], per_game=round(row[3], 2), caveats=caveats)


def verify(text, season=None, snapshot=None, model=None, through_week=99,
           assume_perfect=False):
    out = []
    for c in parse_claims(text):
        if c["kind"] == "player":
            out.append(verify_player(c, season, snapshot, model, through_week,
                                     assume_perfect))
        elif c["kind"] == "team":
            out.append(verify_team(c, season, through_week))
        else:
            out.append(dict(c, verdict="unparsed"))
    return out


def _fmt(v):
    mark = {"true": "✅", "false": "❌", "close": "≈", "unverifiable": "⚠️",
            "unparsed": "·", "record": "📋"}.get(v["verdict"], "?")
    s = f"{mark} {v['text']}"
    if v["kind"] == "player" and v.get("log"):
        s += "\n     " + "  ".join(f"wk{g['week']} {g['value']:g}{'✓' if g['hit'] else '✗'}"
                               for g in v["log"])
    for cv in v.get("caveats", []):
        s += f"\n     • {cv}"
    if v.get("why"):
        s += f"\n     • {v['why']}"
    return s


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(description="Verify pasted prop claims (stdin).")
    ap.add_argument("--through-week", type=int, default=99,
                    help="grade as of this week (posts are made before later games)")
    ap.add_argument("--perfect", action="store_true",
                    help="the sheet claims every game hit (100%%-style)")
    a = ap.parse_args()
    for v in verify(sys.stdin.read(), through_week=a.through_week,
                    assume_perfect=a.perfect):
        print(_fmt(v))
