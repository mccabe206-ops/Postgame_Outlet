"""Resolve a free-text player name (market or X post) to a KB player.

Matches on the normalized name (injuries._norm: lowercase, no punctuation, no Jr/III),
optionally narrowed by team. Never guesses: ambiguous or unknown names come back
unresolved so the caller can show them as "unmatched".
"""

import kb
from injuries import _norm

_CACHE = {}


def roster(season):
    """{norm_name: [ {player_id, name, position, team}, ... ]} from player_week."""
    if season in _CACHE:
        return _CACHE[season]
    rows = kb.query(
        "SELECT player_id, player_display_name AS name, position, team, MAX(week) AS wk "
        "FROM player_week WHERE season=? AND season_type='REG' "
        "GROUP BY player_id, team ORDER BY wk", (season,))
    idx = {}
    for r in rows:
        r = dict(r)
        recs = idx.setdefault(_norm(r["name"]), [])
        recs[:] = [x for x in recs if x["player_id"] != r["player_id"]]  # latest team wins
        recs.append(r)
    _CACHE[season] = idx
    return idx


_LAST = {}


def _by_last(season):
    if season not in _LAST:
        idx = {}
        for recs in roster(season).values():
            for c in recs:
                parts = _norm(c["name"]).split()
                if parts:
                    idx.setdefault(parts[-1], []).append(c)
        _LAST[season] = idx
    return _LAST[season]


def resolve(name, season, teams=None):
    """Return the player dict, or None if unknown / ambiguous."""
    cands = roster(season).get(_norm(name), [])
    if teams:
        tset = {t.upper() for t in teams if t}
        narrowed = [c for c in cands if c["team"] in tset]
        cands = narrowed or cands
    if len(cands) == 1:
        return cands[0]
    if not cands:
        # last-name + first-initial fallback ("P.Nacua", "Pat Freiermuth" vs "Patrick")
        n = _norm(name).split()
        if len(n) >= 2:
            pool = [c for c in _by_last(season).get(n[-1], [])
                    if _norm(c["name"]).startswith(n[0][0])]
            if teams:
                pool = [c for c in pool if c["team"] in {t.upper() for t in teams}] or pool
            if len(pool) == 1:
                return pool[0]
    return None
