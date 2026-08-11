"""Per-team 'update ratings' workspace data.

Pulls together, for one team, everything Sean needs to make a rating call:
  - current QB/Off/Def + total from data/ratings.csv (+ the one-line notes)
  - the live team write-up (data/writeups/<ABBR>.md) that shows on the site
  - the full season results from ESPN (every game: week, opponent, score, W/L),
    most recent first, plus a quick record.

Stdlib only. Used by team_server.py (the browser page) and by the agent when it
reasons about a rating move from Sean's typed context.
"""

import csv
import os

import team_notes
from espn_api import fetch_json
from release_ratings import load_release_rows

try:
    import rosters as _rosters
except Exception:  # noqa: BLE001
    _rosters = None
try:
    import depthchart as _depthchart
except Exception:  # noqa: BLE001
    _depthchart = None

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
WRITEUPS = os.path.join(DATA, "writeups")

TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
SCHED_URL = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
             "teams/{tid}/schedule?season={year}")

# name/abbr helpers ----------------------------------------------------------

_ESPN_CACHE = {}


def espn_team_index():
    """{displayName: {id, abbr}} from ESPN, cached per process."""
    if _ESPN_CACHE:
        return _ESPN_CACHE
    d = fetch_json(TEAMS_URL)
    for t in d["sports"][0]["leagues"][0]["teams"]:
        tt = t["team"]
        _ESPN_CACHE[tt["displayName"]] = {"id": tt["id"], "abbr": tt["abbreviation"]}
    return _ESPN_CACHE


def load_ratings_rows():
    """Full ratings rows keyed by team name (dicts straight from the CSV)."""
    out = {}
    for r in load_release_rows(os.path.join(DATA, "ratings.csv")):
        out[r["team"]] = r
    return out


def team_abbr(name, ratings_rows=None):
    idx = espn_team_index()
    if name in idx:
        return idx[name]["abbr"]
    return None


def load_writeup_md(abbr):
    path = os.path.join(WRITEUPS, f"{abbr}.md")
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return ""


def resolve_team(query):
    """Fuzzy-match a user string ('bills', 'buffalo', 'BUF') to a full team name."""
    q = (query or "").strip().lower()
    rows = load_ratings_rows()
    idx = espn_team_index()
    # exact name
    for name in rows:
        if name.lower() == q:
            return name
    # abbr
    for name, meta in idx.items():
        if meta["abbr"].lower() == q and name in rows:
            return name
    # substring (city or nickname)
    hits = [name for name in rows if q and q in name.lower()]
    if len(hits) == 1:
        return hits[0]
    # nickname-only (last word)
    hits2 = [name for name in rows if q and name.lower().split()[-1] == q]
    if len(hits2) == 1:
        return hits2[0]
    return hits[0] if hits else None


# season results --------------------------------------------------------------

def season_results(name, year):
    """List of the team's games this season, most recent completed first.

    Each: {week, when, home_away, opponent, opp_abbr, team_score, opp_score,
           result ('W'/'L'/None), status, final(bool)}
    """
    idx = espn_team_index()
    meta = idx.get(name)
    if not meta:
        return [], ""
    tid = meta["id"]
    try:
        d = fetch_json(SCHED_URL.format(tid=tid, year=year))
    except Exception:  # noqa: BLE001
        return [], ""
    games = []
    w = l = t = 0
    for e in d.get("events", []):
        comp = e.get("competitions", [{}])[0]
        status = comp.get("status", {}).get("type", {})
        final = status.get("completed", False)
        cs = comp.get("competitors", [])
        me = next((c for c in cs if c.get("team", {}).get("displayName") == name), None)
        opp = next((c for c in cs if c is not me), None)
        if not me or not opp:
            continue

        def _score(c):
            sc = c.get("score")
            if isinstance(sc, dict):
                sc = sc.get("value", sc.get("displayValue"))
            try:
                return int(float(sc))
            except (TypeError, ValueError):
                return None

        ms, os_ = _score(me), _score(opp)
        result = None
        if final and ms is not None and os_ is not None:
            if ms > os_:
                result = "W"; w += 1
            elif ms < os_:
                result = "L"; l += 1
            else:
                result = "T"; t += 1
        games.append({
            "week": e.get("week", {}).get("number"),
            "when": e.get("date", ""),
            "home_away": me.get("homeAway"),
            "opponent": opp.get("team", {}).get("displayName"),
            "opp_abbr": opp.get("team", {}).get("abbreviation"),
            "team_score": ms, "opp_score": os_,
            "result": result, "status": status.get("name"), "final": final,
        })
    # most recent completed first, then upcoming
    games.sort(key=lambda g: (g["final"] is False, -(g["week"] or 0)))
    rec = f"{w}-{l}" + (f"-{t}" if t else "")
    return games, rec


def team_snapshot(name, year):
    """Everything the workspace needs for one team."""
    rows = load_ratings_rows()
    row = rows.get(name, {})
    abbr = team_abbr(name)
    qb = float(row.get("qb_value") or 0)
    off = float(row.get("off_value") or 0)
    dfn = float(row.get("def_value") or 0)
    games, record = season_results(name, year)
    return {
        "name": name, "abbr": abbr,
        "qb_name": row.get("qb_name", ""),
        "qb": qb, "off": off, "def": dfn, "rating": round(qb + off + dfn, 1),
        "notes": row.get("notes", ""),
        "needs_review": row.get("needs_review", ""),
        "writeup_md": load_writeup_md(abbr) if abbr else "",
        "record": record,
        "results": games,
        "year": year,
        "open_threads": team_notes.open_threads(abbr) if abbr else [],
        "resolved_threads": team_notes.list_threads(abbr, "resolved") if abbr else [],
        "injured": _injured_list(name),
        "depth": _depth_chart(abbr),
    }


def _injured_list(name):
    """ESPN injured/out list (live). Empty if module or fetch unavailable."""
    if not _rosters:
        return []
    try:
        return _rosters.fetch_roster(name).get("injured", [])
    except Exception:  # noqa: BLE001
        return []


def _depth_chart(abbr):
    """Cached Ourlads depth chart (refreshed weekly by launchd). {} if unavailable."""
    if not _depthchart or not abbr:
        return {}
    try:
        d = _depthchart.get_depth(abbr)  # no now_iso => prefer cache, don't scrape on view
        return d.get("depth", {})
    except Exception:  # noqa: BLE001
        return {}
