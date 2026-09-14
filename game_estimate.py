"""Expected-score model for the McCabe Method (Lane-2 analysis tool).

Fits a transparent linear model of POINTS from box-score process stats
(total yards, turnovers, first downs) on nflverse history in the local KB, then
estimates what each team "should have" scored in a given game and compares it to
the actual score. The gap is a luck / sustainability read:

  actual - expected  >0  → scored MORE than the stats support (TD/finishing luck,
                            short fields, defensive/ST scores — often unsustainable)
                     <0  → scored LESS than the stats support (stalled drives,
                            missed kicks, red-zone stalls — often positive regression)

It does NOT touch ratings — it's evidence for Task: Update ratings, like results.py.

Stdlib only (sqlite3 + math). Reads the KB read-only.

CLI:
    python3 game_estimate.py model                 # fit + print coefficients & fit
    python3 game_estimate.py week 1 2026           # every final game: exp vs actual
    python3 game_estimate.py week 1 2026 --game JAX # one game (either team abbr)
"""

import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "nfl_kb", "nfl.sqlite")
SINCE = 2015  # modern-scoring-era training window

# predictor labels (the constant is added internally); must be derivable from
# BOTH the KB (for fitting) and an ESPN box score (for applying).
PREDICTORS = ["total_yards", "turnovers", "first_downs"]


# ---- tiny linear algebra (OLS via normal equations) -------------------------
def _solve(A, b):
    """Solve A x = b for a small symmetric system via Gaussian elimination."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        piv = M[c][c]
        if abs(piv) < 1e-12:
            raise ValueError("singular system")
        M[c] = [v / piv for v in M[c]]
        for r in range(n):
            if r != c and M[r][c]:
                f = M[r][c]
                M[r] = [rv - f * cv for rv, cv in zip(M[r], M[c])]
    return [M[i][n] for i in range(n)]


def _ols(X, y):
    """Ordinary least squares. X rows include the leading 1. Returns (beta, r2)."""
    k = len(X[0])
    XtX = [[sum(X[r][i] * X[r][j] for r in range(len(X))) for j in range(k)] for i in range(k)]
    Xty = [sum(X[r][i] * y[r] for r in range(len(X))) for i in range(k)]
    beta = _solve(XtX, Xty)
    ybar = sum(y) / len(y)
    ss_tot = sum((v - ybar) ** 2 for v in y)
    ss_res = sum((y[r] - sum(beta[i] * X[r][i] for i in range(k))) ** 2 for r in range(len(X)))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return beta, r2


# ---- training data from the KB ----------------------------------------------
def _con():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def _training(con):
    q = """
      SELECT g.home_team, g.away_team, g.home_score, g.away_score, t.team,
             COALESCE(t.passing_yards,0)+COALESCE(t.rushing_yards,0) AS total_yards,
             COALESCE(t.passing_interceptions,0)+COALESCE(t.fumbles_lost_total,0) AS turnovers,
             COALESCE(t.passing_first_downs,0)+COALESCE(t.rushing_first_downs,0) AS first_downs
      FROM team_week t JOIN games g ON t.game_id=g.game_id
      WHERE t.season>=? AND g.game_type='REG' AND g.result IS NOT NULL
    """
    X, y = [], []
    for r in con.execute(q, (SINCE,)):
        home_team, away_team, hs, as_, team, ty, to, fd = r
        if hs is None or as_ is None:
            continue
        pts = hs if team == home_team else as_
        X.append([1.0, float(ty), float(to), float(fd)])
        y.append(float(pts))
    return X, y


def fit_model():
    with _con() as con:
        X, y = _training(con)
    beta, r2 = _ols(X, y)
    return {"beta": beta, "r2": r2, "n": len(y)}


def expected_points(model, total_yards, turnovers, first_downs):
    b = model["beta"]
    return b[0] + b[1] * total_yards + b[2] * turnovers + b[3] * first_downs


# ---- apply to an ESPN box score ---------------------------------------------
def _box_inputs(side_box):
    """Pull (total_yards, turnovers, first_downs) from a results.fetch_boxscore side."""
    ty = side_box.get("total_yards")
    to = side_box.get("turnovers")
    fd = None
    for s in side_box.get("all_stats", []):
        if s.get("name") == "firstDowns":
            try:
                fd = float(s.get("value"))
            except (TypeError, ValueError):
                fd = None
    return ty, to, fd


def competitive_score(summary, garbage_lead=25, q4_lead=21, one_score=8):
    """Points each team scored while the game was still COMPETITIVE — the number
    to lean on for a rating/prediction signal.

    Garbage time = the game is out of hand: a lead of `garbage_lead`+ (25 = a true
    four-possession game) any time, OR `q4_lead`+ (21) in the 4th quarter. Crucially
    it is NOT a one-way latch: if the trailing team claws back to within one score
    (<= `one_score` = 8, a chance to tie/take the lead), the game is competitive
    again and its scoring counts. Only scoring that happens while the game is out
    of hand (and stays that way) is stripped."""
    prev = {"away": 0, "home": 0}
    comp = {"away": 0, "home": 0}
    garbage = False
    decided_at = None
    for p in summary.get("scoringPlays", []):
        aw, hm = p.get("awayScore"), p.get("homeScore")
        if aw is None or hm is None:
            continue
        q = (p.get("period") or {}).get("number") or 0
        margin_after = abs(aw - hm)
        # credit this play if the game wasn't out of hand, OR this play is a
        # comeback that pulls it back to one score
        if (not garbage) or margin_after <= one_score:
            comp["away"] += max(0, aw - prev["away"])
            comp["home"] += max(0, hm - prev["home"])
        # update state on the post-play margin
        if margin_after <= one_score:
            garbage = False
        elif margin_after >= garbage_lead or (q >= 4 and margin_after >= q4_lead):
            if not garbage:
                decided_at = (q, p.get("clock", {}).get("displayValue"))
            garbage = True
        prev = {"away": aw, "home": hm}
    return comp["away"], comp["home"], decided_at


def estimate_week(week, year, game=None):
    from espn_api import fetch_json
    from results import fetch_boxscore
    model = fit_model()
    print(f"Expected-points model: pts = {model['beta'][0]:.2f} "
          f"+ {model['beta'][1]:.4f}*yards + {model['beta'][2]:.2f}*turnovers "
          f"+ {model['beta'][3]:.3f}*first_downs   (R²={model['r2']:.2f}, n={model['n']:,} team-games, {SINCE}+)\n")
    sb = fetch_json("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
                    f"scoreboard?dates={year}&seasontype=2&week={week}")
    gsel = game.upper() if game else None
    for e in sb.get("events", []):
        c = e["competitions"][0]
        if not c.get("status", {}).get("type", {}).get("completed"):
            continue
        comp = {t["homeAway"]: t for t in c["competitors"]}
        ha = {s: comp[s]["team"]["abbreviation"] for s in ("home", "away")}
        if gsel and gsel not in ha.values():
            continue
        box = fetch_boxscore(e["id"])
        if not box.get("home") or not box.get("away"):
            continue
        summary = fetch_json("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
                             f"summary?event={e['id']}")
        ca, ch, dec = competitive_score(summary)
        comp_pts = {"away": ca, "home": ch}
        print("=" * 64)
        rows = {}
        for s in ("away", "home"):
            ty, to, fd = _box_inputs(box[s])
            if None in (ty, to, fd):
                continue
            exp = expected_points(model, ty, to, fd)
            act = float(comp[s].get("score"))
            rows[s] = (ha[s], act, exp, ty, int(to), int(fd))
        if len(rows) < 2:
            print(f"{ha['away']} @ {ha['home']} — incomplete box"); continue
        (aa, aact, aexp, aty, ato, afd) = rows["away"]
        (ha_, hact, hexp, hty, hto, hfd) = rows["home"]
        print(f"{aa} @ {ha_}   actual {int(aact)}-{int(hact)}   "
              f"expected {aexp:.0f}-{hexp:.0f}")
        for s, (ab, act, exp, ty, to, fd) in (("away", rows["away"]), ("home", rows["home"])):
            gap = act - exp
            g = int(round(act - comp_pts[s]))
            gtxt = f"  ({g} in garbage time)" if g else ""
            tag = "over-performed (watch)" if gap >= 6 else ("under-performed (positive regression)" if gap <= -6 else "in line")
            print(f"  {('AWAY '+ab) if s=='away' else ('HOME '+ab):<10} actual {int(act):>2}  expected {exp:4.1f}  gap {gap:+5.1f}  "
                  f"[{int(ty)} yds, {to} TO, {fd} 1D]  {tag}{gtxt}")
        am, em = (aact - hact), (aexp - hexp)
        print(f"  margin: actual {am:+.0f} (away)   expected {em:+.1f}   "
              f"model {'agreed on winner' if (am>0)==(em>0) or am==0 else 'disagreed on winner'}")
        # decided-time competitive score — the suggested "true result" signal
        if dec:
            print(f"  SUGGESTED (competitive score, before it was decided in Q{dec[0]} {dec[1]}): "
                  f"{aa} {ca} - {ch} {ha_}")
            lead = "away" if ca > ch else "home"
            print(f"    → lean on {ca}-{ch}: the trailing team's box is garbage-inflated, "
                  f"and the leader ({(aa if lead=='away' else ha_)}) coasted after — treat its number as a floor.")
        else:
            print(f"  competitive throughout — expected vs actual is the clean read (no garbage adjustment).")
    return 0


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("model", "week"):
        print(__doc__); return 1
    if a[0] == "model":
        m = fit_model()
        print(f"pts = {m['beta'][0]:.3f} + {m['beta'][1]:.4f}*yards "
              f"+ {m['beta'][2]:.3f}*turnovers + {m['beta'][3]:.3f}*first_downs")
        print(f"R²={m['r2']:.3f} on n={m['n']:,} team-games ({SINCE}+ regular season)")
        return 0
    pos = [x for x in a[1:] if not x.startswith("--")]
    week = int(pos[0]) if pos else 1
    year = int(pos[1]) if len(pos) > 1 else 2026
    game = None
    if "--game" in a and a.index("--game") + 1 < len(a):
        game = a[a.index("--game") + 1]
    return estimate_week(week, year, game)


if __name__ == "__main__":
    raise SystemExit(main())
