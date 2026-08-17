# NFL Knowledge Base — schema & query guide

A local **SQLite** database of nflverse history, built by `kb_build.py` into
`data/nfl_kb/nfl.sqlite` (gitignored). Query it **read-only** with `kb_query.py` — either
raw SQL or canned reports. This doc is the map: read it, then write SQL for anything.

> **Read-only always.** All access is through a read-only connection; writes/DDL are refused.
> This is analysis only — it never touches ratings or the published site.

## Coverage & honest limits
- **Seasons: 1999–present.** Clean bulk-free data starts at 1999. Pre-1999 (→1920) is a later
  phase (PFR/supplemental, scrape-sensitive) and not here yet.
- **Betting:** `games` has closing `spread_line` / `total_line` (well-populated 1999+) and
  moneylines (more recent). **No historical player-prop odds** (not freely available) — the KB
  powers prop *models* from player stats, not historical prop lines.
- **Source:** nflverse (CC BY 4.0) — Lee Sharpe `nfldata` games + nflverse-data weekly stats,
  rosters. Team abbreviations are normalized to today's 32 (OAK→LV, SD→LAC, STL/LA→LAR, etc.).
- This is a **living** DB (unpinned). Rebuild/refresh: `python3 kb_build.py` (see bottom).

## Discovering the schema
```bash
python3 kb_query.py --schema            # list tables + column counts
python3 kb_query.py --schema player_week   # list a table's columns
```
(`player_week`/`team_week` carry 130–150 columns each — far more than listed below; use
`--schema <table>` to see them all.)

## Tables

### `games` — one row per game (the betting/schedule backbone)
Key columns: `season, week, game_type` (REG/WC/DIV/CON/SB), `gameday, weekday, gametime`,
`home_team, away_team, home_score, away_score`, **`result`** (= home_score − away_score),
`total` (points), `overtime`, betting: **`spread_line`** (>0 = **home favored** by that many),
**`total_line`**, `away_moneyline`, `home_moneyline`, `*_spread_odds`, `over_odds`/`under_odds`;
situational: `away_rest, home_rest, div_game` (0/1), `roof, surface, temp, wind`,
`away_qb_name, home_qb_name, away_coach, home_coach, referee, stadium`.

**Betting math (important):**
- Home covers the spread ⇔ `result > spread_line`. Away covers ⇔ `result < spread_line`. Push ⇔ `=`.
- Over ⇔ `home_score + away_score > total_line`; under ⇔ `<`.
- A team is favored when: it's home and `spread_line > 0`, or away and `spread_line < 0`.

### `team_week` — one row per team per game (weekly team stats)
Keys: `season, week, team, opponent_team, game_id`. ~138 columns of team box/EPA stats
(passing/rushing yards, EPA, first downs, explosive plays, turnovers, etc.). Join to `games` on
`game_id` (or `season, week, team`).

### `player_week` — one row per player per game (fantasy backbone)
Keys: `player_id, season, week, team, opponent_team`. Identity: `player_display_name, position,
position_group`. Fantasy: **`fantasy_points`, `fantasy_points_ppr`**. Volume: `attempts,
completions, passing_yards, passing_tds, carries, rushing_yards, targets, receptions,
receiving_yards`, plus EPA/air-yards/etc. (~150 cols). Join to `rosters` on `(player_id=gsis_id,
season, week)`; to `games` on `game_id`.

### `rosters` — weekly roster (player ↔ team ↔ position)
Keys: `season, week, team`. Identity/keys: `full_name, position, gsis_id, pfr_id, smart_id`,
plus `years_exp, draft_number`. `gsis_id` == `player_week.player_id`.

### `fantasy_value` — Sleeper snapshot: overall value + identity (current, not history)
One row per active NFL player: `sleeper_id, gsis_id, espn_id, full_name, team, position`,
**`search_rank`** (Sleeper overall value/consensus rank — lower = more valuable; a proxy for ADP,
**not** true ADP), `age, years_exp, number, injury_status, snapshot_at`. Join to `player_week` /
`rosters` on **`gsis_id`** (= their `player_id` / `gsis_id`).

### `trending` — Sleeper waiver momentum (current snapshot)
`sleeper_id, direction` ('add'/'drop'), `count` (leagues in the lookback window), `lookback_hours,
snapshot_at`. Join to `fantasy_value` on `sleeper_id` for name/pos/team.

> Sleeper tables are a **current snapshot** (rebuilt each `kb_build.py --sources sleeper`), not
> history. **No ADP or weekly projections** — not in the free Sleeper API.

## Canned reports (betting + fantasy shortcuts)
```bash
python3 kb_query.py --report ats --team NE --since 2010 [--home|--away|--div|--fav|--dog|--rest]
python3 kb_query.py --report ou  --team KC --since 2015 [--home|--away|--div|--rest]
python3 kb_query.py --report leaders --pos RB --season 2024      # PPR leaders
python3 kb_query.py --report usage   --pos WR --season 2024      # carries+targets
```

## Example SQL (the agent writes these)
```sql
-- League scoring by era (historical norms)
SELECT season, ROUND(AVG(home_score+away_score),1) ppg
FROM games WHERE game_type='REG' GROUP BY season ORDER BY season;

-- Road underdogs of 7+ ATS, all teams, since 2006
SELECT COUNT(*) n,
  SUM(CASE WHEN result < spread_line THEN 1 ELSE 0 END) away_covers
FROM games WHERE spread_line >= 7 AND season >= 2006 AND result IS NOT NULL;

-- A QB's per-game passing EPA by season
SELECT season, ROUND(AVG(passing_epa),3) epa_per_game, COUNT(*) g
FROM player_week WHERE player_display_name='Patrick Mahomes' GROUP BY season ORDER BY season;

-- Dome vs outdoor totals
SELECT roof, ROUND(AVG(home_score+away_score),1) ppg, COUNT(*) n
FROM games WHERE game_type='REG' GROUP BY roof ORDER BY ppg DESC;

-- Waiver adds (Sleeper) with their 2024 PPR production
SELECT f.full_name, f.position, f.team, t.count adds,
  ROUND(SUM(pw.fantasy_points_ppr),1) ppr_2024
FROM trending t JOIN fantasy_value f ON t.sleeper_id=f.sleeper_id
LEFT JOIN player_week pw ON pw.player_id=f.gsis_id AND pw.season=2024
WHERE t.direction='add' GROUP BY f.sleeper_id ORDER BY t.count DESC LIMIT 15;
```

## Dashboard (one UI)
```bash
nohup python3 guru_server.py >/tmp/guru_server.log 2>&1 &   # http://127.0.0.1:8790
```
Four tabs, all read-only: **Query** (SQL + canned reports + schema), **Betting** (ATS/OU with
situational filters), **Fantasy** (PPR leaders/usage + Sleeper trending adds/drops + value rank),
**Norms** (league-evolution charts). Links out to the injury (8789) / pick (8787) dashboards.

## Rebuild / refresh
```bash
python3 kb_build.py                       # all sources, 1999–2026 (idempotent full rebuild)
python3 kb_build.py --seasons 2024-2025   # just recent seasons (in-season refresh)
python3 kb_build.py --sources games,player_week
```

## Roadmap (not built yet)
Play-by-play (nflfastR 1999+); pre-1999 scores via PFR; PFR/TeamRankings targeted enrichment;
Sleeper **ADP/projections** (undocumented endpoints or FantasyPros — free API lacks them);
trending *history* (currently latest snapshot only); deeper betting-line history.
_(Done: query CLI, betting/fantasy reports, Sleeper trending + value, the guru dashboard.)_
