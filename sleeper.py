"""Sleeper NFL player data — injuries + depth order, cached as a daily artifact.

Sleeper's public API (https://api.sleeper.app, no key) publishes one big JSON of
every NFL player with, per player: injury_status (IR/PUP/Out/Doubtful/Questionable/
Sus...), injury_body_part, injury_notes, AND depth_chart_position + depth_chart_order.
That single feed is both an injury source (with severity/body part, which ESPN's feed
leaves blank) and a depth source, joinable to our other data by the stable espn_id.

Sleeper asks callers NOT to hit the players endpoint more than once/minute — it's a
~5MB dump meant to be pulled a few times a day and cached. So this module follows the
same cached-artifact model as depthchart.py: a daily launchd job (or --refresh) writes
the cache; everything else reads it. A TTL is a safety net for a missed run.

Cache: data/sleeper_cache/players.json  (gitignored)
Stdlib only. Uses espn_api.fetch_json (proxy-robust UA handling).

Usage (warm the cache — what the launchd job runs):
    python3 sleeper.py
"""

import json
import os
from datetime import datetime, timezone

from espn_api import fetch_json

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(DATA, "sleeper_cache")
CACHE_FILE = os.path.join(CACHE, "players.json")

PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
TTL_HOURS = 24  # safety net; the daily job is the primary warm

# The 32 NFL team abbreviations we use (match data/ratings.csv via ESPN's index).
# Sleeper uses standard abbreviations that differ from ours in only a couple cases.
SLEEPER_TO_ESPN = {"WAS": "WSH", "LA": "LAR", "JAC": "JAX"}

NFL_ABBRS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
    "DET", "GB", "HOU", "IND", "JAX", "KC", "LV", "LAC", "LAR", "MIA",
    "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SF", "SEA", "TB",
    "TEN", "WSH",
}


def espn_team(sleeper_team):
    """Normalize a Sleeper team abbr to the ESPN abbr we key everything on."""
    if not sleeper_team:
        return None
    return SLEEPER_TO_ESPN.get(sleeper_team, sleeper_team)


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _age_hours(iso, now_iso):
    """Whole hours between two ISO timestamps; large if unknown."""
    try:
        a = datetime.strptime(iso[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        b = datetime.strptime(now_iso[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
        return abs((b - a).total_seconds()) / 3600.0
    except Exception:  # noqa: BLE001
        return 1e9


def get_players(now_iso="", force=False, ttl_hours=TTL_HOURS):
    """Cached read of Sleeper's player dump.

    Returns {fetched_at, from_cache, players: {player_id: {...}}}. Reads the cache
    unless it's missing, older than ttl_hours, or force=True — then downloads and
    rewrites it. now_iso defaults to now (UTC); pass one for deterministic tests.
    """
    now_iso = now_iso or _now_iso()
    if not force and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                cached = json.load(f)
            if _age_hours(cached.get("fetched_at", ""), now_iso) <= ttl_hours:
                cached["from_cache"] = True
                return cached
        except (ValueError, OSError):
            pass  # corrupt/unreadable cache — fall through and re-fetch

    players = fetch_json(PLAYERS_URL, timeout=60)
    bundle = {"fetched_at": now_iso, "players": players}
    os.makedirs(CACHE, exist_ok=True)
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(bundle, f)
    os.replace(tmp, CACHE_FILE)
    bundle["from_cache"] = False
    return bundle


def nfl_players(bundle):
    """Normalized list of active players on the 32 NFL teams.

    Each: {espn_id, name, team (ESPN abbr), position, dcp (depth_chart_position),
           order (depth_chart_order or None), status, body_part, notes, exp, number}.
    """
    out = []
    for p in (bundle.get("players") or {}).values():
        team = espn_team(p.get("team"))
        if team not in NFL_ABBRS or not p.get("active"):
            continue
        out.append({
            "espn_id": p.get("espn_id"),
            "name": p.get("full_name") or " ".join(
                x for x in (p.get("first_name"), p.get("last_name")) if x),
            "team": team,
            "position": p.get("position"),
            "dcp": p.get("depth_chart_position"),
            "order": p.get("depth_chart_order"),
            "status": p.get("injury_status"),
            "body_part": p.get("injury_body_part"),
            "notes": p.get("injury_notes"),
            "practice": p.get("practice_description"),  # DNP/Limited/Full — in-season
            "start": p.get("injury_start_date"),
            "updated": p.get("news_updated"),           # ms epoch of last Sleeper update
            "exp": p.get("years_exp"),
            "number": p.get("number"),
        })
    return out


if __name__ == "__main__":
    b = get_players(force=True)
    print(f"[{b['fetched_at']}] Sleeper players cached: "
          f"{len(b.get('players') or {})} total, "
          f"{len(nfl_players(b))} active on NFL rosters -> {CACHE_FILE}")
