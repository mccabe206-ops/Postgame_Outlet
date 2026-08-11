"""Roster + injury data from ESPN, and roster-change detection.

ESPN's roster endpoint gives the full player list per team, grouped
(offense/defense/specialTeam/injuredReserveOrOut/suspended/practiceSquad), with
per-player bio (age/height/weight/experience/jersey) and an injuries field.

This module:
  - fetches a team's current roster (live), incl. an injured/out list
  - snapshots all 32 rosters to a local cache for change-detection
  - diffs the current roster vs. the last snapshot (adds / drops)

ESPN is the reliable structured backbone. Depth-chart ORDER (starter vs backup)
comes from Ourlads — see depthchart.py.

Snapshots live at: data/roster_cache/<ABBR>.json  (gitignored — bulky/derived)
Stdlib only; uses espn_api + team_view's ESPN team index.
"""

import json
import os

import team_view as TV
from espn_api import fetch_json

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(DATA, "roster_cache")

ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{tid}/roster"


def _player(p):
    exp = p.get("experience") or {}
    pos = p.get("position") or {}
    inj = p.get("injuries") or []
    return {
        "name": p.get("displayName"),
        "pos": pos.get("abbreviation") if isinstance(pos, dict) else pos,
        "jersey": p.get("jersey"),
        "age": p.get("age"),
        "exp": exp.get("years") if isinstance(exp, dict) else exp,
        "status": (p.get("status") or {}).get("name") if isinstance(p.get("status"), dict) else p.get("status"),
        "injury": _injury_summary(inj),
    }


def _injury_summary(injuries):
    """Condense ESPN's injuries list to a short string, or '' if healthy."""
    if not injuries:
        return ""
    parts = []
    for i in injuries:
        st = i.get("status") or (i.get("type") or {}).get("description") or ""
        det = i.get("details") or {}
        loc = det.get("location") or ""
        parts.append(" ".join(x for x in [st, loc] if x).strip())
    return "; ".join(p for p in parts if p)


def fetch_roster(name):
    """Live roster for one team (by full name). Returns dict with grouped players
    + a flat injured/out list."""
    meta = TV.espn_team_index().get(name)
    if not meta:
        return {"error": f"unknown team: {name}"}
    d = fetch_json(ROSTER_URL.format(tid=meta["id"]))
    groups = {}
    injured = []
    for grp in d.get("athletes", []):
        gname = grp.get("position", "other")
        players = [_player(p) for p in grp.get("items", [])]
        groups[gname] = players
        if gname in ("injuredReserveOrOut", "suspended"):
            injured.extend({**pl, "group": gname} for pl in players)
    # also catch in-line injury flags on active players
    for gname, players in groups.items():
        if gname in ("injuredReserveOrOut", "suspended"):
            continue
        for pl in players:
            if pl.get("injury"):
                injured.append({**pl, "group": gname})
    total = sum(len(v) for v in groups.values())
    return {"team": name, "abbr": meta["abbr"], "groups": groups,
            "injured": injured, "total": total}


# ---- change detection --------------------------------------------------------

def _roster_names(roster):
    return {p["name"] for g in roster.get("groups", {}).values() for p in g}


def snapshot_path(abbr):
    return os.path.join(CACHE, f"{abbr}.json")


def save_snapshot(roster, now_iso=""):
    os.makedirs(CACHE, exist_ok=True)
    roster = dict(roster)
    roster["snapshot_at"] = now_iso
    with open(snapshot_path(roster["abbr"]), "w") as f:
        json.dump(roster, f, indent=2)


def load_snapshot(abbr):
    p = snapshot_path(abbr)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return None


def diff_vs_snapshot(name):
    """Compare the live roster to the last saved snapshot. Returns
    {added:[...], dropped:[...], has_baseline:bool}. Does NOT update the snapshot."""
    live = fetch_roster(name)
    if "error" in live:
        return live
    prev = load_snapshot(live["abbr"])
    if not prev:
        return {"team": name, "abbr": live["abbr"], "has_baseline": False,
                "added": [], "dropped": [], "note": "No baseline snapshot yet."}
    now_names = _roster_names(live)
    then_names = _roster_names(prev)
    added = sorted(now_names - then_names)
    dropped = sorted(then_names - now_names)
    return {"team": name, "abbr": live["abbr"], "has_baseline": True,
            "since": prev.get("snapshot_at", ""),
            "added": added, "dropped": dropped}


def snapshot_all(now_iso="", sleep_between=0.0):
    """Pull + save all 32 rosters as the change-detection baseline."""
    import time
    idx = TV.espn_team_index()
    done = []
    for name in sorted(idx):
        r = fetch_roster(name)
        if "error" not in r:
            save_snapshot(r, now_iso)
            done.append(r["abbr"])
        if sleep_between:
            time.sleep(sleep_between)
    return done
