"""Market-implied power ratings (McCabe Method, Lane-2 WIP).

Backs out what the betting market thinks each team is worth, on Sean's scale,
so the board can show "Market vs Mine" side by side.

Model: for every game in the last few weeks,
    market home margin  ≈  R_home − R_away + HFA
(HFA from data/hfa.csv + 0.5 primetime, 0 at a neutral site — same as picks.py).
Solved by recency-weighted ridge least squares (ridge keeps it stable with only
~1 game per team per week; it also shrinks the extremes a little, so gaps under
~1 point are noise). Market ratings are then centered on Sean's league mean.

Lines: completed weeks use the frozen closing line in data/line_overrides.json
(`market`), falling back to ESPN's per-event summary pickcenter; the current /
upcoming week uses the live ESPN scoreboard odds (same fallback).

QB re-basing: an old line priced the QB who was expected to start THEN. For each
older game we read ratings.csv as of that game's kickoff (read-only `git show`);
if the team's qb_name differs from today's, the margin is shifted by
(today's QB value − the old QB's value today), both from Sean's current
ratings.csv / qb_depth.csv. Every shift is logged in `adjustments`.

Reads ratings.csv directly (not release_ratings — that raises while any row is
needs_review=Y); `draft` is True if any row is still under review. Read-only:
never writes ratings, lines, or git state.

CLI:  python3 market_ratings.py [week] [year] [--weeks N] [--json]
Stdlib only, Python 3.9+.
"""

import csv
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import picks
from espn_api import fetch_json

REPO = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(REPO, "data")
DEFAULT_WEIGHTS = (1.0, 0.7, 0.4, 0.25)  # current week first, then older


# ---- pure math (unit-tested) -------------------------------------------------

def _solve(A, b):
    """Gaussian elimination with partial pivoting (A is square, well-posed)."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        piv = M[c][c]
        if abs(piv) < 1e-12:
            continue
        for r in range(n):
            if r != c and M[r][c]:
                f = M[r][c] / piv
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def solve_ratings(games, teams, lam=0.3):
    """Weighted ridge fit. games: iterable of (home, away, home_margin, hfa, weight).
    Returns {team: rating} (uncentered; ridge pulls toward 0)."""
    ix = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    A = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    for h, a, margin, hfa, w in games:
        i, j = ix[h], ix[a]
        y = margin - hfa
        A[i][i] += w; A[j][j] += w
        A[i][j] -= w; A[j][i] -= w
        b[i] += w * y; b[j] -= w * y
    for i in range(n):
        A[i][i] += lam
    x = _solve(A, b)
    return {t: x[ix[t]] for t in teams}


def center_to(ratings, target_mean):
    m = sum(ratings.values()) / len(ratings)
    return {t: v - m + target_mean for t, v in ratings.items()}


# ---- data --------------------------------------------------------------------

def _read_csv_text(text):
    return list(csv.DictReader(io.StringIO(text)))


def _current_rows():
    with open(os.path.join(DATA, "ratings.csv"), newline="") as f:
        return list(csv.DictReader(f))


def _qb_values_today(rows):
    val = {r["qb_name"]: float(r["qb_value"] or 0) for r in rows}
    path = os.path.join(DATA, "qb_depth.csv")
    if os.path.exists(path):
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                try:
                    val.setdefault(r["qb_name"], float(r["value"]))
                except (TypeError, ValueError):
                    pass
    return val


_COMMIT_CACHE = {}
_ROWS_CACHE = {}


def _qbs_as_of(iso_utc):
    """{team: qb_name} from the ratings.csv committed before `iso_utc` (None if
    git/history unavailable). Read-only."""
    try:
        sha = _COMMIT_CACHE.get(iso_utc)
        if sha is None:
            sha = subprocess.run(
                ["git", "-C", REPO, "log", "-1", f"--before={iso_utc}",
                 "--format=%H", "--", "data/ratings.csv"],
                capture_output=True, text=True, timeout=20).stdout.strip()
            _COMMIT_CACHE[iso_utc] = sha
        if not sha:
            return None
        if sha not in _ROWS_CACHE:
            text = subprocess.run(
                ["git", "-C", REPO, "show", f"{sha}:data/ratings.csv"],
                capture_output=True, text=True, timeout=20).stdout
            _ROWS_CACHE[sha] = {r["team"]: r["qb_name"] for r in _read_csv_text(text)}
        return _ROWS_CACHE[sha]
    except Exception:  # noqa: BLE001 — no git history = no re-basing, not a failure
        return None


def _event_market(e, overrides):
    """(home-relative spread, source) — neg = home favored."""
    c = e["competitions"][0]
    gid = e.get("id")
    final = (c.get("status") or e.get("status") or {}).get("type", {}).get("completed")
    ov = overrides.get(gid) or {}
    if final and ov.get("market") is not None:
        return float(ov["market"]), "frozen close"
    odds = c.get("odds") or []
    sp = odds[0].get("spread") if odds else None
    if sp is not None:
        return float(sp), "ESPN live"
    if ov.get("market") is not None:
        return float(ov["market"]), "frozen"
    sp, _det = picks._summary_market(gid)
    if sp is not None:
        return float(sp), "ESPN summary"
    return None, None


def fit(year, through_week, weights=None, lam=0.3, n_weeks=None):
    """Market-implied ratings using weeks (through_week − n + 1 … through_week).
    weights[0] applies to through_week, weights[1] to the week before, etc."""
    weights = tuple(weights or DEFAULT_WEIGHTS)
    if n_weeks is not None:
        weights = weights[:n_weeks]
    rows = _current_rows()
    mine = {r["team"]: round(float(r["qb_value"] or 0) + float(r["off_value"] or 0)
                             + float(r["def_value"] or 0), 1) for r in rows}
    qb_now = {r["team"]: (r["qb_name"], float(r["qb_value"] or 0)) for r in rows}
    review = {r["team"]: (r.get("needs_review") or "").strip().upper() == "Y" for r in rows}
    qb_val = _qb_values_today(rows)
    hfa, default_hfa = picks.load_hfa()
    overrides = picks.load_line_overrides()

    games, adjustments, used = [], [], []
    for k, w in enumerate(weights):
        wk = through_week - k
        if wk < 1:
            break
        payload = fetch_json(picks.SCOREBOARD.format(year=year, week=wk))
        n_wk = 0
        for e in payload.get("events", []):
            c = e["competitions"][0]
            comp = {t["homeAway"]: t for t in c["competitors"]}
            if "home" not in comp or "away" not in comp:
                continue
            home = comp["home"]["team"]["displayName"]
            away = comp["away"]["team"]["displayName"]
            if home not in mine or away not in mine:
                continue
            mkt, src = _event_market(e, overrides)
            if mkt is None:
                continue
            kickoff = e.get("date", "")
            neutral = bool(c.get("neutralSite"))
            prime = picks._is_primetime(kickoff)
            eh = 0.0 if neutral else hfa.get(home, default_hfa) + (0.5 if prime else 0.0)
            margin = -mkt
            if k > 0:  # re-base older lines to today's starters
                then = _qbs_as_of(kickoff)
                if then:
                    for team, sign in ((home, 1), (away, -1)):
                        old = then.get(team)
                        new_name, new_val = qb_now[team]
                        if old and old != new_name:
                            if old in qb_val:
                                d = new_val - qb_val[old]
                                margin += sign * d
                                adjustments.append({"week": wk, "team": team, "from": old,
                                                    "to": new_name, "shift": round(d, 1)})
                            else:
                                adjustments.append({"week": wk, "team": team, "from": old,
                                                    "to": new_name, "shift": None,
                                                    "note": "old QB not in ratings/qb_depth — not re-based"})
            games.append((home, away, margin, eh, w))
            n_wk += 1
        used.append({"week": wk, "weight": w, "games": n_wk})

    teams = sorted(mine)
    raw = solve_ratings(games, teams, lam=lam)
    mean_mine = sum(mine.values()) / len(mine)
    mkt = center_to(raw, mean_mine)
    out = []
    for t in sorted(teams, key=lambda t: -mkt[t]):
        out.append({"team": t, "qb": qb_now[t][0], "market": round(mkt[t], 1),
                    "mine": mine[t], "gap": round(mine[t] - mkt[t], 1),
                    "needs_review": review[t]})
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return {"season": year, "through_week": through_week, "lam": lam,
            "weeks": used, "games_used": len(games), "adjustments": adjustments,
            "draft": any(review.values()), "mean": round(mean_mine, 2),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "teams": out}


def _default_week_year():
    w, y = picks.current_week_year()
    return (w or 1), (y or datetime.now().year)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    n_weeks = None
    if "--weeks" in argv:
        i = argv.index("--weeks")
        n_weeks = int(argv[i + 1]); del argv[i:i + 2]
    pos = [a for a in argv if not a.startswith("--")]
    dw, dy = _default_week_year()
    week = int(pos[0]) if pos else dw
    year = int(pos[1]) if len(pos) > 1 else dy
    res = fit(year, week, n_weeks=n_weeks)
    if as_json:
        print(json.dumps(res, indent=2))
        return 0
    wk = ", ".join(f"Wk{u['week']}×{u['weight']} ({u['games']})" for u in res["weeks"])
    print(f"Market-implied ratings — {year} through Week {week}  [{res['games_used']} games: {wk}]"
          + ("  DRAFT (needs_review=Y rows)" if res["draft"] else ""))
    print(f"{'#':>2}  {'Team':<24} {'QB':<20} {'Market':>6} {'Mine':>6} {'Gap':>6}")
    for r in res["teams"]:
        print(f"{r['rank']:>2}  {r['team']:<24} {r['qb']:<20} {r['market']:+6.1f} {r['mine']:+6.1f} {r['gap']:+6.1f}"
              + ("  ⚠" if r["needs_review"] else ""))
    if res["adjustments"]:
        print("QB re-basing: " + "; ".join(
            f"Wk{a['week']} {a['team']}: {a['from']}→{a['to']} "
            + (f"{a['shift']:+.1f}" if a["shift"] is not None else "(skipped)")
            for a in res["adjustments"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
