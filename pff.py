"""PFF Premium player-stats puller + reporter (McCabe Method, Lane-2 WIP).

PFF+ is a paid subscription. This tool pulls YOUR OWN subscription's per-player
stats for a given week from PFF's backend JSON API and caches them locally so we
can read them through the ratings lens. It NEVER stores your login: `fetch` reads
a short-lived session token from the PFF_SESSION env var (the browser's Clerk
`__session` cookie), uses it for the fetch, and forgets it. Cached JSON lives in
data/pff/<season>/wk<week>/ (gitignored — private, derived).

Endpoints (all authenticated, per-week league-wide — one call covers every game):
    /api/v1/games?league=nfl&season=Y&week=W
    /api/v1/facet/<facet>/summary?league=nfl&season=Y&week=W

Usage:
    # 1) grab the token from the logged-in browser session (see the skill), then:
    PFF_SESSION="<__session cookie>" python3 pff.py fetch 2026 1
    # 2) read it back, organized per game:
    python3 pff.py report 2026 1                 # summary: grades + marquee stats
    python3 pff.py report 2026 1 --full          # every field for every player
    python3 pff.py report 2026 1 --game SF        # one game (by either team abbr)
    python3 pff.py report 2026 1 --json           # machine-readable, grouped by game
    # 3) export CSVs (all fields) for spreadsheet verification:
    python3 pff.py csv 2026 1                     # one CSV per facet + a combined.csv

Stdlib only.
"""

import json
import os
import sys
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
BASE = "https://premium.pff.com/api/v1"

# PFF gates the ADVANCED fields (grades, BTT%/TWP%, pressures, snap counts) on a
# single-week facet request, but returns them in full for the season-to-date
# ("Reg + Post") view. So we request the full REGPO week list to unlock grades.
# NOTE: this makes the facet data SEASON-TO-DATE through the current week — which
# equals the single week only in Week 1. Mid-season, treat these as cumulative.
REGPO_WEEKS = ",".join(str(w) for w in
                       list(range(1, 19)) + [28, 29, 30, 32])

# facet -> the key its payload nests the row list under (confirmed via probing).
FACETS = {
    "passing": "passing_summary",
    "rushing": "rushing_summary",
    "receiving": "receiving_summary",
    "offense": "offense_summary",       # blocking / all offensive snaps
    "defense": "defense_summary",       # pass-rush + coverage + run-defense combined
    "return": "return_summary",
    "punting": "punting_summary",
    "field_goal": "field_goal_summary",
    "kicking": "kicking_summary",       # kickoffs
}

# ordering + display for the summary report (only fields that exist are shown).
FACET_TITLE = {
    "passing": "Passing", "rushing": "Rushing", "receiving": "Receiving",
    "offense": "Blocking / Offense", "defense": "Defense",
    "return": "Returns", "punting": "Punting", "field_goal": "Field Goals",
    "kicking": "Kickoffs",
}


def _cache_dir(season, week):
    return os.path.join(DATA, "pff", str(season), f"wk{week}")


# ---- fetch ------------------------------------------------------------------

def _cookie_header():
    """Prefer the full browser cookie (PFF_COOKIE) — the advanced/grade fields
    unlock only with the full cookie set; a bare __session downgrades to the
    restricted (counting-stats) view. Fall back to PFF_SESSION if that's all
    we have."""
    full = os.environ.get("PFF_COOKIE", "").strip()
    if full:
        return full
    tok = os.environ.get("PFF_SESSION", "").strip()
    return f"__session={tok}" if tok else ""


def _get(url):
    req = urllib.request.Request(url, headers={
        "Cookie": _cookie_header(),
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://premium.pff.com/nfl/positions/2026/1/passing",
        "Origin": "https://premium.pff.com",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch(season, week):
    if not _cookie_header():
        print("ERROR: set PFF_COOKIE (full browser cookie) or PFF_SESSION first.",
              file=sys.stderr)
        return 2
    out = _cache_dir(season, week)
    os.makedirs(out, exist_ok=True)

    # games (also our per-game bucket map)
    try:
        games = _get(f"{BASE}/games?league=nfl&season={season}&week={week}")
    except urllib.error.HTTPError as e:
        print(f"ERROR fetching games: HTTP {e.code} — token likely expired; "
              f"re-grab a fresh __session and retry.", file=sys.stderr)
        return 1
    with open(os.path.join(out, "games.json"), "w") as f:
        json.dump(games, f)
    ng = len(games.get("games", []))
    print(f"games.json: {ng} games")

    ok = 0
    for facet, key in FACETS.items():
        # REGPO week list unlocks the advanced/grade fields (see REGPO_WEEKS note)
        url = f"{BASE}/facet/{facet}/summary?league=nfl&season={season}&week={week}"
        try:
            payload = _get(url)
        except urllib.error.HTTPError as e:
            print(f"  {facet}: HTTP {e.code} (skipped)")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"  {facet}: {e} (skipped)")
            continue
        rows = payload.get(key, [])
        with open(os.path.join(out, f"{facet}.json"), "w") as f:
            json.dump(payload, f)
        print(f"  {facet}.json: {len(rows)} players")
        ok += 1
    print(f"\nCached {ok}/{len(FACETS)} facets to {os.path.relpath(out, HERE)}/ (gitignored)")
    return 0


# ---- report -----------------------------------------------------------------

def _load(season, week):
    d = _cache_dir(season, week)
    if not os.path.isdir(d):
        return None, {}
    games = None
    gp = os.path.join(d, "games.json")
    if os.path.exists(gp):
        games = json.load(open(gp))
    facets = {}
    for facet, key in FACETS.items():
        p = os.path.join(d, f"{facet}.json")
        if os.path.exists(p):
            facets[facet] = json.load(open(p)).get(key, [])
    return games, facets


def _game_index(games):
    """abbr -> (game_label, opp_abbr, is_home). Also returns ordered game list."""
    idx, order = {}, []
    for g in (games or {}).get("games", []):
        a = g.get("away_team", {}).get("abbreviation")
        h = g.get("home_team", {}).get("abbreviation")
        sc = g.get("score", {}) or {}
        label = f"{a} {sc.get('away_team','?')} @ {h} {sc.get('home_team','?')}"
        order.append((a, h, label, g))
        idx[a] = (label, h, False)
        idx[h] = (label, a, True)
    return idx, order


def _grade_fields(row):
    return {k: v for k, v in row.items() if k.startswith("grades_") and v is not None}


# marquee counting stats per facet (shown if present in the row).
MARQUEE = {
    "passing": ["dropbacks", "attempts", "completions", "yards", "touchdowns",
                "interceptions", "ypa", "big_time_throws", "turnover_worthy_plays",
                "avg_depth_of_target", "pressure_to_sack_rate", "avg_time_to_throw",
                "sacks", "first_downs"],
    "rushing": ["attempts", "yards", "ypa", "touchdowns", "yards_after_contact",
                "avoided_tackles", "breakaway_yards", "elusive_rating", "first_downs",
                "fumbles"],
    "receiving": ["targets", "receptions", "yards", "touchdowns", "yards_after_catch",
                  "yprr", "drops", "contested_receptions", "avg_depth_of_target",
                  "first_downs"],
    "offense": ["snap_counts_total", "snap_counts_pass_block", "snap_counts_run_block",
                "penalties"],
    "defense": ["snap_counts_defense", "total_pressures", "sacks", "hits", "hurries",
                "stops", "tackles", "assists", "missed_tackles", "tackles_for_loss",
                "targets", "receptions", "yards", "interceptions", "pass_break_ups",
                "forced_fumbles", "qb_rating_against"],
    "return": ["total_attempts", "kickoff_attempts", "kickoff_yards", "kickoff_touchdowns",
               "punt_attempts", "punt_yards", "punt_touchdowns"],
    "punting": ["attempts", "yards", "average_yards_per_attempt", "average_net_yards",
                "inside_twenties", "touchbacks", "long"],
    "field_goal": ["total_made", "total_attempts", "total_percent", "fifty_made",
                   "fifty_attempts", "forty_made", "pat_made", "pat_attempts"],
    "kicking": ["attempts", "touchbacks", "yards"],
}


def _fmt(v):
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def _player_name(row):
    return (row.get("player") or row.get("player_name")
            or row.get("name") or "?")


def report(season, week, game=None, full=False, as_json=False):
    games, facets = _load(season, week)
    if games is None:
        print(f"No PFF cache for {season} wk{week}. Run: PFF_SESSION=… "
              f"python3 pff.py fetch {season} {week}", file=sys.stderr)
        return 1
    idx, order = _game_index(games)

    # group each facet's rows by team abbr
    by_team = {}   # abbr -> {facet: [rows]}
    for facet, rows in facets.items():
        for row in rows:
            abbr = row.get("team_name") or row.get("team")
            by_team.setdefault(abbr, {}).setdefault(facet, []).append(row)

    if as_json:
        blob = {}
        for a, h, label, _g in order:
            blob[label] = {"away": {"abbr": a, "facets": by_team.get(a, {})},
                           "home": {"abbr": h, "facets": by_team.get(h, {})}}
        print(json.dumps(blob, indent=1))
        return 0

    gsel = game.upper() if game else None
    printed = 0
    for a, h, label, _g in order:
        if gsel and gsel not in (a, h):
            continue
        printed += 1
        print(f"\n{'='*70}\n{label}\n{'='*70}")
        for abbr in (a, h):
            tf = by_team.get(abbr, {})
            if not tf:
                continue
            print(f"\n### {abbr}")
            for facet in FACETS:
                rows = tf.get(facet)
                if not rows:
                    continue
                print(f"\n-- {FACET_TITLE[facet]} --")
                # sort by primary grade desc when available
                def _pg(r):
                    g = _grade_fields(r)
                    return g.get("grades_offense", g.get("grades_defense",
                           next(iter(g.values()), 0))) or 0
                for row in sorted(rows, key=_pg, reverse=True):
                    name = _player_name(row)
                    pos = row.get("position", "")
                    if full:
                        fields = {k: v for k, v in row.items()
                                  if k not in ("player", "team_name") and v is not None}
                        body = "  ".join(f"{k}={_fmt(v)}" for k, v in sorted(fields.items()))
                    else:
                        grades = _grade_fields(row)
                        gtxt = " ".join(f"{k.replace('grades_','')[:8]} {_fmt(v)}"
                                        for k, v in grades.items())
                        marq = [f"{c}={_fmt(row[c])}" for c in MARQUEE.get(facet, [])
                                if row.get(c) is not None]
                        body = f"[{gtxt}]  " + " ".join(marq)
                    print(f"   {name:<22}{('('+pos+')') if pos else '':<6} {body}")
    if not printed:
        print(f"(no game matched '{game}')" if game else "(no games in cache)")
    return 0


# ---- csv export -------------------------------------------------------------

def export_csv(season, week):
    """Write one CSV per facet (all fields, all players) plus a combined.csv, into
    data/pff/<season>/wk<week>/csv/. Adds `game`/`opp` columns so rows are
    game-attributable. Openable in Excel/Numbers for hand-verification."""
    import csv as _csv
    games, facets = _load(season, week)
    if not facets:
        print(f"No PFF cache for {season} wk{week}. Fetch first.", file=sys.stderr)
        return 1
    idx, _order = _game_index(games or {})
    outdir = os.path.join(_cache_dir(season, week), "csv")
    os.makedirs(outdir, exist_ok=True)
    combined = []
    written = 0
    for facet, rows in facets.items():
        if not rows:
            continue
        # stable column order: identifiers first, then the rest sorted
        head = ["facet", "game", "opp", "player", "team_name", "position", "jersey_number"]
        rest = sorted({k for r in rows for k in r} - set(head))
        cols = head + rest
        path = os.path.join(outdir, f"{facet}.csv")
        with open(path, "w", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                abbr = r.get("team_name")
                label, opp, _home = idx.get(abbr, ("", "", None))
                row = dict(r, facet=facet, game=label, opp=opp)
                w.writerow(row)
                combined.append(row)
        written += 1
        print(f"  {facet}.csv ({len(rows)} rows, {len(cols)} cols)")
    # combined: union of all columns
    if combined:
        allcols = ["facet", "game", "opp", "player", "team_name", "position"]
        allcols += sorted({k for r in combined for k in r} - set(allcols))
        with open(os.path.join(outdir, "combined.csv"), "w", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=allcols, extrasaction="ignore")
            w.writeheader()
            w.writerows(combined)
        print(f"  combined.csv ({len(combined)} rows)")
    print(f"\nWrote {written} facet CSVs to {os.path.relpath(outdir, HERE)}/")
    return 0


# ---- cli --------------------------------------------------------------------

def main():
    argv = sys.argv[1:]
    if not argv or argv[0] not in ("fetch", "report", "csv"):
        print(__doc__)
        return 1
    mode = argv[0]
    pos = [a for a in argv[1:] if not a.startswith("--")]
    season = int(pos[0]) if len(pos) > 0 else 2026
    week = int(pos[1]) if len(pos) > 1 else 1
    if mode == "fetch":
        return fetch(season, week)
    if mode == "csv":
        return export_csv(season, week)
    game = None
    if "--game" in argv:
        i = argv.index("--game")
        if i + 1 < len(argv):
            game = argv[i + 1]
    return report(season, week, game=game,
                  full=("--full" in argv), as_json=("--json" in argv))


if __name__ == "__main__":
    raise SystemExit(main())
