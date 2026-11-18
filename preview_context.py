"""Psychological flags + historical trends/systems for one game (Game Previews).

Read-only over the NFL knowledge base (data/nfl_kb/nfl.sqlite). Everything here is
context for the reader — NOT an input to the number unless Sean prices it.

Conventions (reference/kb_schema.md): KB spread_line > 0 = home favored; home covers
when result > spread_line. ESPN/picks lines are home-relative with NEGATIVE = home
favored, so kb_spread = -market. Trends are ALWAYS split by era (2021+, 2010-19,
pre-2010) with 2020 excluded; neutral-site games are excluded from home/away angles
(filter on location, not stadium — intl games carry US stadium names).
"""

import functools
from collections import defaultdict

import kb

ERAS = (("2021+", 2021, 9999), ("2010-19", 2010, 2019), ("pre-2010", 1999, 2009))
MIN_N = 40          # total sample needed to show a trend
PACIFIC_MOUNTAIN = {"SEA", "SF", "LA", "LAC", "LV", "ARI", "DEN"}
EASTERN = {"BUF", "MIA", "NE", "NYJ", "NYG", "PHI", "WAS", "BAL", "PIT", "CLE",
           "CIN", "ATL", "CAR", "TB", "JAX", "IND", "DET"}
COLD_OUTDOOR_HOME = {"BUF", "GB", "CHI", "CLE", "NE", "PIT", "DEN", "NYG", "NYJ", "KC",
                     "CIN", "BAL", "PHI", "WAS", "SEA"}
DOME_OR_WARM = {"MIA", "TB", "JAX", "ARI", "LV", "LA", "LAC", "NO", "ATL", "HOU", "DAL",
                "DET", "MIN", "IND", "SF", "CAR"}
ESPN_TO_KB = {"LAR": "LA", "WSH": "WAS"}


def kb_abbr(a):
    return ESPN_TO_KB.get(a, a)


@functools.lru_cache(maxsize=1)
def _games():
    rows = kb.query(
        "SELECT season, week, gameday, weekday, gametime, away_team, home_team, "
        "away_score, home_score, result, spread_line, total_line, div_game, roof, "
        "temp, location, away_rest, home_rest, away_coach, home_coach, "
        "away_qb_name, home_qb_name FROM games WHERE game_type='REG' "
        "ORDER BY season, week")
    cols = ("season", "week", "gameday", "weekday", "gametime", "away", "home", "away_score",
            "home_score", "result", "spread", "total", "div", "roof", "temp", "location",
            "away_rest", "home_rest", "away_coach", "home_coach", "away_qb", "home_qb")
    return [dict(zip(cols, (r.values() if isinstance(r, dict) else r))) for r in rows]


def _graded():
    return [g for g in _games() if g["result"] is not None and g["spread"] is not None
            and g["season"] != 2020]


@functools.lru_cache(maxsize=1)
def _prev_index():
    """{(season, week, team): previous REG game dict for that team (same season)}"""
    last, out = {}, {}
    for g in _games():
        for t in (g["away"], g["home"]):
            key = (g["season"], t)
            out[(g["season"], g["week"], t)] = last.get(key)
            if g["result"] is not None:
                last[key] = g
    return out


def _side_cover(g, side):
    """'W'/'L'/'P' ATS for the home or away side."""
    if g["result"] == g["spread"]:
        return "P"
    home_cov = g["result"] > g["spread"]
    return "W" if (side == "home") == home_cov else "L"


def _era_split(games_sides, kind="ats"):
    """games_sides: iterable of (game, side) for ATS, or (game, 'over'/'under') for totals."""
    out = []
    total = 0
    for name, lo, hi in ERAS:
        w = l = p = 0
        for g, side in games_sides:
            if not lo <= g["season"] <= hi:
                continue
            if kind == "ats":
                r = _side_cover(g, side)
            else:
                pts = (g["home_score"] or 0) + (g["away_score"] or 0)
                if g["total"] is None:
                    continue
                r = "P" if pts == g["total"] else ("W" if (pts > g["total"]) == (side == "over") else "L")
            w += r == "W"
            l += r == "L"
            p += r == "P"
        n = w + l + p
        total += n
        out.append({"era": name, "w": w, "l": l, "p": p, "n": n,
                    "pct": round(100.0 * w / (w + l), 1) if (w + l) else None})
    return out, total


def _bucket(points):
    a = abs(points)
    if a < 3:
        return (0, 2.5, "PK to 2.5")
    if a < 7:
        return (3, 6.5, "3 to 6.5")
    if a < 10:
        return (7, 9.5, "7 to 9.5")
    return (10, 99, "10+")


def _in_bucket(spread, b):
    return b[0] <= abs(spread) <= b[1]


def _trend(label, side_desc, games_sides, kind="ats"):
    eras, n = _era_split(games_sides, kind)
    if n < MIN_N:
        return None
    modern = eras[0]
    # interest: how far the 2021+ (or, if thin, overall) rate sits from 50%
    w = sum(e["w"] for e in eras)
    l = sum(e["l"] for e in eras)
    overall = 100.0 * w / (w + l) if (w + l) else 50.0
    score = abs((modern["pct"] if modern["n"] >= 20 and modern["pct"] is not None else overall) - 50)
    return {"label": label, "side": side_desc, "eras": eras, "n": n, "score": score,
            "thin_modern": modern["n"] < 30}


def trends(game):
    """Matched historical angles for one upcoming game.

    game: {away, home (KB abbrs), market (home-relative, neg = home fav), total,
           div (bool), neutral (bool), gametime 'HH:MM' ET, weekday, away_rest,
           home_rest, month}
    Returns up to ~4 trends sorted by interest. Each is presented from a side of
    THIS game, e.g. 'IND as a road dog of 10+'."""
    G = _graded()
    out = []
    mk = game.get("market")
    if mk is not None and abs(mk) > 1e-9 and not game.get("neutral"):
        kb_spread = -mk
        b = _bucket(kb_spread)
        home_fav = kb_spread > 0
        fav, dog = (game["home"], game["away"]) if home_fav else (game["away"], game["home"])
        dog_side = "away" if home_fav else "home"
        base = [g for g in G if g["location"] != "Neutral" and _in_bucket(g["spread"], b)
                and (g["spread"] > 0) == home_fav and g["spread"] != 0]
        role = "road" if dog_side == "away" else "home"
        out.append(_trend(f"{role.title()} underdogs of {b[2]}",
                          f"{dog} as a {role} dog (dog ATS)",
                          [(g, dog_side) for g in base]))
        if game.get("div"):
            out.append(_trend(f"Divisional {role} underdogs of {b[2]}",
                              f"{dog} (dog ATS)",
                              [(g, dog_side) for g in base if g["div"]]))
        # rest spots
        for team, side in ((game["away"], "away"), (game["home"], "home")):
            rest, orest = game.get(f"{side}_rest"), game.get(f"{'home' if side == 'away' else 'away'}_rest")
            is_fav = team == fav
            if rest and rest >= 13:
                pool = [(g, side) for g in G if g["location"] != "Neutral"
                        and (g[f"{side}_rest"] or 0) >= 13
                        and ((g["spread"] > 0) == (side == "home")) == is_fav and g["spread"] != 0]
                out.append(_trend(f"{'Home' if side == 'home' else 'Road'} teams off a bye as "
                                  f"{'favorites' if is_fav else 'underdogs'}",
                                  f"{team} off the bye (ATS)", pool))
            if rest and orest and rest - orest >= 3 and not (rest >= 13):
                pool = [(g, side) for g in G if g["location"] != "Neutral"
                        and g[f"{side}_rest"] and g[f"{'home' if side == 'away' else 'away'}_rest"]
                        and g[f"{side}_rest"] - g[f"{'home' if side == 'away' else 'away'}_rest"] >= 3]
                out.append(_trend(f"{'Home' if side == 'home' else 'Road'} teams with 3+ days "
                                  "more rest", f"{team} (ATS)", pool))
        if game.get("weekday") == "Thursday":
            pool = [(g, "home") for g in G if g["weekday"] == "Thursday" and g["location"] != "Neutral"
                    and g["week"] > 1 and ((g["spread"] > 0) == home_fav)]
            out.append(_trend(f"Thursday home {'favorites' if home_fav else 'underdogs'}",
                              f"{game['home']} at home on a Thursday (ATS)", pool))
        # letdown / bounce-back
        prev = _prev_index()
        for team in (game["away"], game["home"]):
            side = "away" if team == game["away"] else "home"
            pg = game.get(f"{side}_prev")
            if not pg:
                continue
            if pg.get("upset_win"):
                pool = _after(G, prev, lambda p, t: _won_as_dog(p, t, 3))
                out.append(_trend("Teams the week after an outright upset win (as a 3+ point dog)",
                                  f"{team} after last week's upset (ATS)",
                                  [(g, s) for g, s in pool]))
            if pg.get("blowout_loss_as_fav"):
                pool = _after(G, prev, lambda p, t: _lost_as_fav_by(p, t, 14))
                out.append(_trend("Teams the week after losing by 14+ as a favorite",
                                  f"{team} bouncing back (ATS)", [(g, s) for g, s in pool]))
    # cold-weather dome/warm teams, late season
    if (game.get("month") or 0) in (11, 12, 1) and game["home"] in COLD_OUTDOOR_HOME \
            and game["away"] in DOME_OR_WARM and not game.get("neutral"):
        pool = [(g, "away") for g in G if g["away"] in DOME_OR_WARM and g["home"] in COLD_OUTDOOR_HOME
                and g["roof"] == "outdoors" and g["gameday"] and g["gameday"][5:7] in ("11", "12", "01")]
        out.append(_trend("Dome/warm-weather teams on the road in cold-weather outdoor "
                          "stadiums (Nov-Jan)", f"{game['away']} (ATS)", pool))
    # totals
    if game.get("total"):
        t = game["total"]
        lo, hi = (t - 1.5, t + 1.5)
        pool = [g for g in G if g["total"] is not None and lo <= g["total"] <= hi]
        if game.get("div"):
            out.append(_trend(f"Divisional games with totals {lo:g}-{hi:g}", "the Under",
                              [(g, "under") for g in pool if g["div"]], kind="tot"))
        prime = (game.get("gametime") or "") >= "19:00"
        if prime:
            out.append(_trend(f"Primetime games with totals {lo:g}-{hi:g}", "the Under",
                              [(g, "under") for g in pool if (g["gametime"] or "") >= "19:00"],
                              kind="tot"))
    out = [t for t in out if t]
    out.sort(key=lambda t: -t["score"])
    return out[:4]


def _won_as_dog(g, team, by):
    side = "home" if g["home"] == team else "away"
    dog_pts = g["spread"] if side == "away" else -g["spread"]   # >0 => team was the dog
    won = g["result"] > 0 if side == "home" else g["result"] < 0
    return dog_pts >= by and won


def _lost_as_fav_by(g, team, by):
    side = "home" if g["home"] == team else "away"
    fav = g["spread"] > 0 if side == "home" else g["spread"] < 0
    margin = g["result"] if side == "home" else -g["result"]
    return fav and margin <= -by


def _after(G, prev, cond):
    pool = []
    for g in G:
        for side in ("away", "home"):
            t = g[side]
            p = prev.get((g["season"], g["week"], t))
            if p and p["spread"] is not None and p["result"] is not None and cond(p, t):
                pool.append((g, side))
    return pool


def fmt_trend(t):
    """One markdown bullet: label — side: 2021+ W-L (pct, n) · 2010-19 ... · pre-2010 ..."""
    def era(e):
        if not e["n"]:
            return f'{e["era"]}: none'
        rec = f'{e["w"]}-{e["l"]}' + (f'-{e["p"]}' if e["p"] else "")
        return f'{e["era"]}: {rec} ({e["pct"]:g}%)' if e["pct"] is not None else f'{e["era"]}: {rec}'
    thin = " (thin 2021+ sample)" if t["thin_modern"] else ""
    return f'**{t["label"]}**: {t["side"]}. ' + " · ".join(era(e) for e in t["eras"]) + thin


# ---- psychological flags ----------------------------------------------------------

def _qb_history(name):
    """{team: [seasons]} the QB started for (from KB starter fields)."""
    if not name:
        return {}
    hist = defaultdict(set)
    for g in _games():
        for side in ("away", "home"):
            if g[f"{side}_qb"] == name:
                hist[g[side]].add(g["season"])
    return hist


def _coach_history(name):
    hist = defaultdict(set)
    for g in _games():
        for side in ("away", "home"):
            if g[f"{side}_coach"] == name:
                hist[g[side]].add(g["season"])
    return hist


def _span(seasons):
    s = sorted(seasons)
    return f"{s[0]}" if len(s) == 1 else f"{s[0]}-{s[-1]}"


def psych_flags(game, ratings_rows=None):
    """Plain-language, non-obvious psychological/situational spots for one game.

    game: as for trends(), plus away_qb/home_qb names, away_coach/home_coach,
    season, kickoff_et_hour, away_prev/home_prev ({upset_win, blowout_loss_as_fav,
    opp, score}), away_next/home_next ({opp, strong, prime}), records {team: (w, l)},
    team_ratings {abbr: total}, away_road_streak."""
    flags = []
    a, h, season = game["away"], game["home"], game["season"]
    for team, opp, side in ((a, h, "away"), (h, a, "home")):
        qb = game.get(f"{side}_qb")
        hist = _qb_history(qb)
        prior = {s for s in hist.get(opp, set()) if s < season}
        if prior:
            flags.append(f"Revenge spot: {team} QB {qb} started for {opp} ({_span(prior)}).")
        coach = game.get(f"{side}_coach")
        ch = _coach_history(coach)
        prior = {s for s in ch.get(opp, set()) if s < season}
        if prior:
            flags.append(f"Revenge spot: {team} head coach {coach} coached {opp} ({_span(prior)}).")
    for team, side in ((a, "away"), (h, "home")):
        p = game.get(f"{side}_prev") or {}
        if p.get("upset_win"):
            flags.append(f"Letdown watch: {team} is coming off an outright upset win "
                         f"({p.get('score')} vs {p.get('opp')}).")
        if p.get("blowout_loss_as_fav"):
            flags.append(f"Bounce-back spot: {team} lost by 14+ as a favorite last week "
                         f"({p.get('score')} vs {p.get('opp')}).")
        n = game.get(f"{side}_next") or {}
        tr = game.get("team_ratings") or {}
        opp = h if side == "away" else a
        if n.get("strong") and tr.get(opp) is not None and tr[opp] <= -2.0:
            flags.append(f"Look-ahead watch: {team} faces {n.get('opp')} next"
                         f"{' in primetime' if n.get('prime') else ''}, after this game against a "
                         f"lower-rated {opp}.")
    if a in PACIFIC_MOUNTAIN and h in EASTERN and (game.get("gametime") or "") < "14:00" \
            and not game.get("neutral"):
        flags.append(f"Body clock: {a} plays a 1 p.m. ET kickoff, 10 a.m. back home.")
    if (game.get("away_road_streak") or 0) >= 3:
        flags.append(f"Long road stretch: {a}'s third straight game away from home.")
    if (game.get("month") or 0) in (11, 12, 1) and h in COLD_OUTDOOR_HOME and a in DOME_OR_WARM \
            and not game.get("neutral"):
        flags.append(f"Weather: {a} (dome/warm-weather team) outdoors in {h} late in the season.")
    rec = game.get("records") or {}
    wk = game.get("week") or 0
    for team in (a, h):
        w, l = rec.get(team, (None, None))
        if w is None or (w + l) < 8:
            continue
        pct = w / (w + l)
        if pct <= 0.3:
            flags.append(f"Motivation watch: {team} is {w}-{l}; at this stage, effort and "
                         "evaluation mode (young players, resting vets) can creep in.")
    both = [rec.get(t) for t in (a, h)]
    if wk >= 10 and all(r and (r[0] + r[1]) >= 8 and r[0] / (r[0] + r[1]) >= 0.6 for r in both):
        flags.append("Playoff stakes: both teams are winning-record contenders; seeding on the line.")
    return flags
