"""Depth-chart view data: Ourlads starter->backup ORDER joined to ESPN player
photos + jersey numbers.

Ourlads (depthchart.py) is the authority for depth ORDER but gives names only.
ESPN's roster endpoint gives each player an id + headshot + jersey. We join the
two by normalized name so the depth-chart view can show a photo for each player.

Grouped into offense / defense / special teams / reserves, each a list of
{slot, players:[{name, order, jersey, pos, photo, id, note, status, matched}]}.

Read-only. Stdlib only (reuses espn_api + team_view + depthchart). Lane-2 tool
(testing branch); never touches ratings or the site.
"""
import re
import unicodedata

from espn_api import fetch_json
import team_view as TV
import depthchart as D

ROSTER_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{tid}/roster"
HEADSHOT = "https://a.espncdn.com/i/headshots/nfl/players/full/{pid}.png"

# Ourlads slot -> side. Order within each list is the display order on the view.
OFFENSE = ["QB", "RB", "FB", "HB", "LWR", "SWR", "RWR", "TE",
           "LT", "LG", "C", "RG", "RT"]
DEFENSE = ["LDE", "DE", "RDE", "NT", "LDT", "DT", "RDT",
           "LOLB", "SLB", "WLB", "MLB", "LILB", "RILB", "ROLB", "LB",
           "LCB", "RCB", "CB", "NB", "SS", "FS", "DB"]
SPECIAL = ["PK", "PT", "LS", "H", "KO", "PR", "KR"]
RESERVE = ["IR", "PUP", "NFI", "SUS"]

_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?")


def norm(name):
    """Normalize a player name for cross-source matching."""
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    n = n.lower().replace(".", " ").replace("'", "")
    n = _SUFFIX.sub("", n)
    n = re.sub(r"[^a-z ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _espn_index(tid):
    """name(normalized) -> {id, jersey, photo, pos} for every athlete on the
    ESPN roster (all groups). Returns {} if the fetch fails."""
    try:
        data = fetch_json(ROSTER_URL.format(tid=tid))
    except Exception:
        return {}
    idx = {}
    for grp in data.get("athletes") or []:
        for p in grp.get("items") or []:
            nm = norm(p.get("displayName") or p.get("fullName"))
            if not nm or nm in idx:
                continue
            pid = p.get("id")
            hs = (p.get("headshot") or {}).get("href")
            pos = p.get("position") or {}
            idx[nm] = {
                "id": pid,
                "jersey": p.get("jersey"),
                "photo": hs or (HEADSHOT.format(pid=pid) if pid else None),
                "pos": pos.get("abbreviation") if isinstance(pos, dict) else None,
            }
    return idx


def _slot_players(depth, slot, espn_idx):
    out = []
    for i, pl in enumerate(depth.get(slot) or []):
        nm = pl.get("name")
        m = espn_idx.get(norm(nm)) or {}
        out.append({
            "name": nm,
            "order": i + 1,
            "jersey": m.get("jersey"),
            "pos": m.get("pos"),
            "id": m.get("id"),
            "photo": m.get("photo"),
            "note": pl.get("note") or "",
            "status": pl.get("status") or "",
            "matched": bool(m),
        })
    return out


def _side(depth, slots, espn_idx):
    groups = []
    for slot in slots:
        players = _slot_players(depth, slot, espn_idx)
        if players:
            groups.append({"slot": slot, "players": players})
    return groups


def team_depth(name_or_abbr, refresh=False):
    """Resolve a team, pull its Ourlads depth chart, attach ESPN photos.

    Returns {ok, abbr, name, source, fetched_at, from_cache,
             offense, defense, special, reserve, unmatched} or {ok:False,...}.
    """
    # resolve_team() returns the full team display name (a string) or None.
    name = TV.resolve_team(name_or_abbr)
    idx = TV.espn_team_index()
    if not name:
        # Direct abbr match against the ESPN index as a fallback.
        q = (name_or_abbr or "").strip().lower()
        name = next((tn for tn, m in idx.items() if (m.get("abbr") or "").lower() == q), None)
    meta = idx.get(name) if name else None
    if not meta:
        return {"ok": False, "message": f"could not resolve team '{name_or_abbr}'"}
    abbr, tid = meta.get("abbr"), meta.get("id")
    if not tid or not abbr:
        return {"ok": False, "message": f"could not resolve team '{name_or_abbr}'"}

    dep = D.get_depth(abbr, force=refresh)
    depth = dep.get("depth") or {}
    espn_idx = _espn_index(tid)

    offense = _side(depth, OFFENSE, espn_idx)
    defense = _side(depth, DEFENSE, espn_idx)
    special = _side(depth, SPECIAL, espn_idx)
    reserve = _side(depth, RESERVE, espn_idx)

    unmatched = sum(
        1 for grp in (offense + defense + special + reserve)
        for p in grp["players"] if not p["matched"]
    )
    return {
        "ok": True,
        "abbr": abbr,
        "name": name,
        "source": dep.get("source"),
        "ourlads_abbr": dep.get("ourlads_abbr"),
        "fetched_at": dep.get("fetched_at"),
        "from_cache": dep.get("from_cache"),
        "photo_source": "ESPN",
        "offense": offense,
        "defense": defense,
        "special": special,
        "reserve": reserve,
        "unmatched": unmatched,
    }


def all_abbrs():
    idx = TV.espn_team_index()
    return sorted({m.get("abbr") for m in idx.values() if m.get("abbr")})


if __name__ == "__main__":
    import json
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "Buffalo Bills"
    print(json.dumps(team_depth(t), indent=1)[:2000])
