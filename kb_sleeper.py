"""Sleeper fantasy-market snapshot for the NFL knowledge base.

Pulls the *free, documented* Sleeper API and assembles two KB tables:
  fantasy_value — one row per active NFL player: overall value rank (search_rank),
                  identity + join keys (gsis_id -> player_week.player_id), metadata.
  trending      — current waiver momentum: adds/drops with league counts.

These are a *current snapshot* (rebuilt each run), not history. There is NO ADP or
weekly-projection data in the free API — deliberately omitted rather than invented.

Reuses `sleeper.get_players()` (the existing cached ~15MB dump) + `espn_api.fetch_json`.
Pure assembly (`build_rows`) is separated from the live fetch (`collect`) for testing.
Stdlib only.
"""

import sleeper
from espn_api import fetch_json

TRENDING_URL = ("https://api.sleeper.app/v1/players/nfl/trending/{direction}"
                "?lookback_hours={hours}&limit={limit}")


def fetch_trending(direction, hours=24, limit=200):
    """direction in {'add','drop'} -> list of {player_id, count}."""
    return fetch_json(TRENDING_URL.format(direction=direction, hours=hours, limit=limit))


def build_rows(players, adds, drops, now_iso, hours=24):
    """Pure assembly: (fantasy_value_rows, trending_rows) from raw Sleeper data.

    `players` is Sleeper's {player_id: {...}} dump; `adds`/`drops` are the trending
    lists. Only players on the 32 NFL teams are kept.
    """
    fv = []
    for pid, p in players.items():
        team = sleeper.espn_team(p.get("team"))
        if team not in sleeper.NFL_ABBRS or not p.get("active"):
            continue
        fv.append({
            "sleeper_id": pid,
            "gsis_id": p.get("gsis_id"),
            "espn_id": p.get("espn_id"),
            "full_name": p.get("full_name"),
            "team": team,
            "position": p.get("position"),
            "search_rank": p.get("search_rank"),
            "age": p.get("age"),
            "years_exp": p.get("years_exp"),
            "number": p.get("number"),
            "injury_status": p.get("injury_status"),
            "snapshot_at": now_iso,
        })
    tr = []
    for direction, rows in (("add", adds), ("drop", drops)):
        for r in rows or []:
            tr.append({
                "sleeper_id": r.get("player_id"),
                "direction": direction,
                "count": r.get("count"),
                "lookback_hours": hours,
                "snapshot_at": now_iso,
            })
    return fv, tr


def collect(now_iso, hours=24, limit=200):
    """Live: fetch the players dump + trending, return (fantasy_value, trending) rows."""
    bundle = sleeper.get_players()
    adds = fetch_trending("add", hours, limit)
    drops = fetch_trending("drop", hours, limit)
    return build_rows(bundle.get("players") or {}, adds, drops, now_iso, hours)
