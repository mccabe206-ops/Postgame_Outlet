"""PFF team-grade layer for the Market vs Mine view (McCabe Method, Lane-2 WIP).

Turns PFF's season team unit grades into Sean's rating COMPONENTS so the board
can show a fourth read next to Mine / Market / Box:

    pff_off  = z(mean of pass-block, receiving, run, run-block grades) × std(Sean off_value)
    pff_def  = z(defense grade)                                        × std(Sean def_value)
    pff_qb   = z(passing grade)                                         × std(Sean qb_value)
    (each re-centered on Sean's component mean)

    pff_total = Sean's QB value + pff_off + pff_def
              → PFF's read of the roster AROUND your quarterback. The PFF QB grade is
                shown separately and flagged `qb_comparable=False` when today's
                starter isn't the QB who took most of the season's snaps (the pass
                grade then describes someone else).

Input is a cached JSON written by the main Claude session from the logged-in PFF
browser session: data/pff/<season>/team_overview_wk<N>.json (gitignored). This
module NEVER fetches from PFF and never handles cookies. Read-only.

CLI:  python3 pff_team.py [season] [--json]
Stdlib only, Python 3.9+.
"""

import csv
import glob
import io
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(REPO, "data")
PFF_DIR = os.path.join(DATA, "pff")
UNIT_KEYS = ("overall", "off", "pass", "pblk", "recv", "run", "rblk",
             "def", "rdef", "tack", "prsh", "cov", "spec")
# first Thursday kickoff of each season (Week N cutoff = this + 7·(N−1) days)
SEASON_WK1_KICKOFF = {2026: "2026-09-10T23:00:00Z"}


# ---- pure math (unit-tested) -------------------------------------------------

def _mean(xs):
    return sum(xs) / len(xs)


def _std(xs):
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def rescale(values, target_mean, target_std):
    """{key: raw} → {key: z-score mapped onto (target_mean, target_std)}."""
    xs = list(values.values())
    m, s = _mean(xs), _std(xs)
    if s == 0:
        return {k: target_mean for k in values}
    return {k: target_mean + (v - m) / s * target_std for k, v in values.items()}


def components(teams, sean_rows):
    """teams: {team_name: pff unit dict}; sean_rows: {team_name: (qb, off, def)}.
    Returns {team: {pff_off, pff_def, pff_qb, pff_total}} for teams in both."""
    names = [t for t in teams if t in sean_rows]
    q = [sean_rows[t][0] for t in names]
    o = [sean_rows[t][1] for t in names]
    d = [sean_rows[t][2] for t in names]
    off_raw = {t: _mean([teams[t]["pblk"], teams[t]["recv"], teams[t]["run"], teams[t]["rblk"]])
               for t in names}
    pff_off = rescale(off_raw, _mean(o), _std(o))
    pff_def = rescale({t: teams[t]["def"] for t in names}, _mean(d), _std(d))
    pff_qb = rescale({t: teams[t]["pass"] for t in names}, _mean(q), _std(q))
    out = {}
    for t in names:
        out[t] = {"pff_off": pff_off[t], "pff_def": pff_def[t], "pff_qb": pff_qb[t],
                  "pff_total": sean_rows[t][0] + pff_off[t] + pff_def[t]}
    return out


# ---- data --------------------------------------------------------------------

def latest_overview(season):
    """(path, week) of the highest-week cached overview for `season`, or (None, None)."""
    best = (None, None)
    for p in glob.glob(os.path.join(PFF_DIR, str(season), "team_overview_wk*.json")):
        m = re.search(r"team_overview_wk(\d+)\.json$", p)
        if m and (best[1] is None or int(m.group(1)) > best[1]):
            best = (p, int(m.group(1)))
    return best


def _ratings_rows():
    with open(os.path.join(DATA, "ratings.csv"), newline="") as f:
        return list(csv.DictReader(f))


def _qbs_before(iso):
    """{team: qb_name} from the ratings.csv committed before `iso` (read-only git)."""
    try:
        sha = subprocess.run(["git", "-C", REPO, "log", "-1", f"--before={iso}", "--format=%H",
                              "--", "data/ratings.csv"], capture_output=True, text=True,
                             timeout=20).stdout.strip()
        if not sha:
            return None
        text = subprocess.run(["git", "-C", REPO, "show", f"{sha}:data/ratings.csv"],
                              capture_output=True, text=True, timeout=20).stdout
        return {r["team"]: r["qb_name"] for r in csv.DictReader(io.StringIO(text))}
    except Exception:  # noqa: BLE001 — no history = can't judge comparability
        return None


def qb_comparability(season, through_week, current):
    """{team: bool}: today's QB was the listed pre-game starter in a majority of the
    weeks covered by the PFF data (a proxy for 'took most of the dropbacks')."""
    wk1 = SEASON_WK1_KICKOFF.get(season)
    if not wk1 or not through_week:
        return {t: None for t in current}
    base = datetime.strptime(wk1, "%Y-%m-%dT%H:%M:%SZ")
    starters = [_qbs_before((base + timedelta(days=7 * k)).strftime("%Y-%m-%dT%H:%M:%SZ"))
                for k in range(through_week)]
    starters = [s for s in starters if s]
    if not starters:
        return {t: None for t in current}
    out = {}
    for t, qb in current.items():
        same = sum(1 for s in starters if s.get(t) == qb)
        out[t] = same * 2 > len(starters)
    return out


def build(season=2026):
    path, week = latest_overview(season)
    if not path:
        return None
    with open(path) as f:
        raw = json.load(f)
    rows = _ratings_rows()
    sean = {r["team"]: (float(r["qb_value"] or 0), float(r["off_value"] or 0),
                        float(r["def_value"] or 0)) for r in rows}
    qbs = {r["team"]: r["qb_name"] for r in rows}
    teams = {t["name"]: t for t in raw.get("teams", []) if t.get("name") in sean}
    comp = components(teams, sean)
    qok = qb_comparability(season, raw.get("through_week") or week, qbs)
    out = []
    for name, c in comp.items():
        q, o, d = sean[name]
        mine = round(q + o + d, 1)
        out.append({
            "team": name, "qb": qbs[name], "mine": mine, "mine_qb": q, "mine_off": o, "mine_def": d,
            "pff_off": round(c["pff_off"], 1), "pff_def": round(c["pff_def"], 1),
            "pff_qb": round(c["pff_qb"], 1), "qb_comparable": qok.get(name),
            "pff_total": round(c["pff_total"], 1), "gap_pff": round(mine - c["pff_total"], 1),
            "units": {k: teams[name].get(k) for k in UNIT_KEYS},
        })
    out.sort(key=lambda r: -abs(r["gap_pff"]))
    return {"season": season, "through_week": raw.get("through_week") or week,
            "fetched": raw.get("fetched"), "source": raw.get("source"), "teams": out}


def by_team(season=2026):
    """{team: row} or {} when no cache — for market_ratings / hub integration."""
    try:
        res = build(season)
    except Exception:  # noqa: BLE001 — PFF layer is optional
        return {}, None
    if not res:
        return {}, None
    return {r["team"]: r for r in res["teams"]}, {k: res[k] for k in ("through_week", "fetched", "source")}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    pos = [a for a in argv if not a.startswith("--")]
    season = int(pos[0]) if pos else 2026
    res = build(season)
    if not res:
        print(f"No PFF team overview cached under data/pff/{season}/ — the Claude session fetches it.")
        return 1
    if "--json" in argv:
        print(json.dumps(res, indent=2))
        return 0
    print(f"PFF team grades → your scale — {season} through Week {res['through_week']} (fetched {res['fetched']})")
    print(f"{'Team':<24} {'Mine Q/O/D':>17}  {'PFF O/D':>11}  {'PFF tot':>7} {'Mine':>6} {'Gap':>6}  {'PFF QB':>7}")
    for r in res["teams"]:
        qb = f"{r['pff_qb']:+.1f}" + ("" if r["qb_comparable"] else "*")
        print(f"{r['team']:<24} {r['mine_qb']:+5.1f}/{r['mine_off']:+5.1f}/{r['mine_def']:+5.1f}  "
              f"{r['pff_off']:+5.1f}/{r['pff_def']:+5.1f}  {r['pff_total']:+7.1f} {r['mine']:+6.1f} "
              f"{r['gap_pff']:+6.1f}  {qb:>7}")
    print("* PFF pass grade mostly reflects a different QB than today's starter — not comparable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
