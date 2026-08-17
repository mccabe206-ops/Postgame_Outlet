"""Build the NFL knowledge base (local SQLite) from nflverse bulk data.

Downloads the clean, free, bulk nflverse history (1999+) and loads it into a local
SQLite file (`data/nfl_kb/nfl.sqlite`, gitignored). Idempotent: each table is
dropped and rebuilt from the requested seasons, so re-running refreshes the data.

Reuses the repo's existing nflverse plumbing (team aliases + fetch) and stays
stdlib-only. This is a *living* DB (unpinned) meant to refresh in-season, unlike
the SHA-pinned pgo model corpus.

Sources (nflverse, CC BY 4.0):
  games       — Lee Sharpe nfldata/data/games.csv (schedule + scores + betting lines
                + situational: rest, div_game, roof, surface, temp, wind, QBs, coaches)
  team_week   — nflverse-data stats_team_week_{season}.csv.gz
  player_week — nflverse-data stats_player_week_{season}.csv.gz  (fantasy backbone)
  rosters     — nflverse-data roster_weekly_{season}.csv

CLI:
    python3 kb_build.py                              # all sources, 1999-2026
    python3 kb_build.py --seasons 2010-2024
    python3 kb_build.py --sources games,player_week  # subset
    python3 kb_build.py --db /tmp/test.sqlite        # alternate DB (tests)
"""

import argparse
import csv
import gzip
import io
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

import kb
from release_ratings import atomic_write_text

try:  # reuse the repo's nflverse team-alias map + fetch helper
    from pgo_sources import ALIASES as _ALIASES, fetch_url
except Exception:  # noqa: BLE001 — stdlib fallback so the KB never hard-depends on pgo
    from urllib.request import urlopen

    def fetch_url(url):
        with urlopen(url) as r:
            return r.read()

    _ALIASES = {"OAK": "LV", "SD": "LAC", "STL": "LAR", "LA": "LAR",
                "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU", "SL": "LAR"}

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
_RELEASES = "https://github.com/nflverse/nflverse-data/releases/download"
SEASONAL = {
    "team_week": _RELEASES + "/stats_team/stats_team_week_{season}.csv.gz",
    "player_week": _RELEASES + "/stats_player/stats_player_week_{season}.csv.gz",
    "rosters": _RELEASES + "/weekly_rosters/roster_weekly_{season}.csv",
}
ALL_SOURCES = ("games",) + tuple(SEASONAL) + ("sleeper",)
TEAM_COLS = {"team", "opponent_team", "home_team", "away_team", "recent_team"}
# index these column-combos when the table has them (fast splits/aggregations)
_INDEX_COMBOS = [("season", "week", "team"), ("season", "week"), ("team",),
                 ("home_team",), ("away_team",), ("player_id",),
                 ("player_display_name",), ("position",), ("season",)]


def _rows(url, data):
    text = (gzip.decompress(data) if url.lower().endswith(".gz") else data).decode(
        "utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def _norm_team(v):
    if not v:
        return v
    u = v.strip().upper()
    return _ALIASES.get(u, u)


def _infer_type(values):
    """INTEGER if every non-empty value is an int, REAL if numeric, else TEXT."""
    seen = is_int = is_real = False
    is_int = is_real = True
    for v in values:
        if v is None or v == "":
            continue
        seen = True
        if is_int:
            try:
                int(v)
            except (ValueError, TypeError):
                is_int = False
        try:
            float(v)
        except (ValueError, TypeError):
            is_real = False
            is_int = False
    if not seen:
        return "TEXT"
    if is_int:
        return "INTEGER"
    if is_real:
        return "REAL"
    return "TEXT"


def build_table(con, name, rows):
    """Create `name` from a list of dict rows: union columns, normalize teams,
    infer per-column types, insert. Returns the ordered column list."""
    cols, seen = [], set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                cols.append(k)
    tcols = [c for c in cols if c in TEAM_COLS]
    if tcols:
        for r in rows:
            for c in tcols:
                if r.get(c):
                    r[c] = _norm_team(r[c])
    types = {c: _infer_type([r.get(c) for r in rows]) for c in cols}
    q = lambda c: '"' + c + '"'  # noqa: E731
    con.execute(f'DROP TABLE IF EXISTS {q(name)}')
    con.execute(f'CREATE TABLE {q(name)} ('
                + ", ".join(f'{q(c)} {types[c]}' for c in cols) + ")")
    ins = (f'INSERT INTO {q(name)} (' + ",".join(q(c) for c in cols) + ") VALUES ("
           + ",".join("?" * len(cols)) + ")")
    con.executemany(ins, [[(None if (r.get(c) in (None, "")) else r.get(c))
                            for c in cols] for r in rows])
    for combo in _INDEX_COMBOS:
        if all(c in cols for c in combo):
            idx = "idx_%s_%s" % (name, "_".join(combo))
            con.execute(f'CREATE INDEX IF NOT EXISTS {q(idx)} ON {q(name)} ('
                        + ",".join(q(c) for c in combo) + ")")
    return cols


def build(seasons, sources, db_path, log=print):
    lo, hi = seasons
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    manifest = {"built_at": built_at, "seasons": [lo, hi], "sources": []}
    try:
        if "games" in sources:
            rows = [r for r in _rows(GAMES_URL, fetch_url(GAMES_URL))
                    if r.get("season") and lo <= int(r["season"]) <= hi]
            cols = build_table(con, "games", rows)
            manifest["sources"].append(
                {"table": "games", "url": GAMES_URL, "rows": len(rows),
                 "columns": len(cols)})
            log(f"  games: {len(rows)} rows, {len(cols)} cols")
        for name, tmpl in SEASONAL.items():
            if name not in sources:
                continue
            allrows, got = [], []
            for s in range(lo, hi + 1):
                url = tmpl.format(season=s)
                try:
                    allrows.extend(_rows(url, fetch_url(url)))
                    got.append(s)
                except Exception as e:  # noqa: BLE001 — a season may not exist yet
                    log(f"    {name} {s}: skipped ({e})")
            if not allrows:
                log(f"  {name}: no data")
                continue
            cols = build_table(con, name, allrows)
            manifest["sources"].append(
                {"table": name, "url": tmpl, "rows": len(allrows),
                 "columns": len(cols), "seasons": [got[0], got[-1]] if got else []})
            log(f"  {name}: {len(allrows)} rows, {len(cols)} cols "
                f"({got[0]}-{got[-1]})" if got else f"  {name}: 0")
        if "sleeper" in sources:  # non-seasonal current snapshot: fantasy value + trending
            import kb_sleeper
            fv, tr = kb_sleeper.collect(built_at)
            build_table(con, "fantasy_value", fv)
            build_table(con, "trending", tr)
            manifest["sources"].append(
                {"table": "fantasy_value", "url": "sleeper:players", "rows": len(fv)})
            manifest["sources"].append(
                {"table": "trending", "url": "sleeper:trending", "rows": len(tr)})
            log(f"  fantasy_value: {len(fv)} rows | trending: {len(tr)} rows")
        con.commit()
    finally:
        con.close()
    atomic_write_text(kb.LOCK_PATH if db_path == kb.DB_PATH
                      else os.path.join(os.path.dirname(db_path), "sources.lock.json"),
                      json.dumps(manifest, indent=2) + "\n")
    return manifest


def _parse_seasons(s):
    if "-" in s:
        lo, hi = s.split("-", 1)
        return int(lo), int(hi)
    return int(s), int(s)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description="Build the NFL knowledge base (SQLite).")
    ap.add_argument("--seasons", default="1999-2026")
    ap.add_argument("--sources", default=",".join(ALL_SOURCES))
    ap.add_argument("--refresh", action="store_true", help="(rebuild is always full)")
    ap.add_argument("--db", default=kb.DB_PATH)
    a = ap.parse_args(argv)
    seasons = _parse_seasons(a.seasons)
    sources = [s.strip() for s in a.sources.split(",") if s.strip()]
    bad = [s for s in sources if s not in ALL_SOURCES]
    if bad:
        print(f"unknown source(s): {bad}; valid: {list(ALL_SOURCES)}")
        return 1
    print(f"Building NFL KB {seasons[0]}-{seasons[1]} -> {a.db}")
    m = build(seasons, sources, a.db)
    print(f"Done. {len(m['sources'])} tables. Query with: python3 kb_query.py \"SELECT ...\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
