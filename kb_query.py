"""Query the NFL knowledge base — read-only.

Two modes:
  1. Raw SQL (read-only, guarded):
       python3 kb_query.py "SELECT season, COUNT(*) FROM games GROUP BY season"
       python3 kb_query.py "SELECT ..." --json
  2. Canned reports for the priority use-cases (betting + fantasy):
       python3 kb_query.py --report ats --team NE --since 2010 --dog
       python3 kb_query.py --report ou  --team KC --since 2015 --home
       python3 kb_query.py --report leaders --pos RB --season 2024
       python3 kb_query.py --report usage   --pos WR --season 2024

The agent's real power is mode 1: read `reference/kb_schema.md`, then write SQL for
anything. All access is via a read-only SQLite connection, so nothing can mutate the
data. Never edits ratings/site (analysis only, like results.py / injuries.py).

Betting definitions (nflverse `games`): `spread_line` positive = home favored by that
many; `result` = home_score - away_score. A team covers when its margin beats its line.

Stdlib only.
"""

import argparse
import json
import sys

import kb

_WRITE = ("insert", "update", "delete", "drop", "alter", "create", "replace",
          "attach", "detach", "pragma", "vacuum", "reindex")


def _print_rows(rows, as_json):
    if as_json:
        print(json.dumps(rows, indent=2, default=str))
        return
    if not rows:
        print("(no rows)")
        return
    cols = list(rows[0].keys())
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    line = "  ".join(c.ljust(widths[c]) for c in cols)
    print(line)
    print("  ".join("-" * widths[c] for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))
    print(f"\n{len(rows)} row(s)")


def run_sql(sql, as_json=False, db_path=kb.DB_PATH):
    s = sql.strip().rstrip(";").strip()
    low = s.lower()
    if not (low.startswith("select") or low.startswith("with")):
        print("Only read-only SELECT/WITH queries are allowed.")
        return 1
    if ";" in s:  # single statement only
        print("One statement at a time (no ';').")
        return 1
    tokens = set(low.replace("(", " ").replace(",", " ").split())
    if tokens & set(_WRITE):
        print("Write/DDL keywords are not allowed (read-only).")
        return 1
    _print_rows(kb.query(s, db_path=db_path), as_json)
    return 0


# ---- canned reports ---------------------------------------------------------

def _games_for_team(team, since, db_path):
    return kb.query(
        "SELECT season, week, game_type, home_team, away_team, home_score, away_score, "
        "result, spread_line, total_line, div_game, home_rest, away_rest "
        "FROM games WHERE (home_team=? OR away_team=?) AND season>=? "
        "AND result IS NOT NULL",
        (team, team, since), db_path=db_path)


def _situational_ok(g, team, a):
    is_home = g["home_team"] == team
    if a.home and not is_home:
        return False
    if a.away and is_home:
        return False
    if a.div and not g.get("div_game"):
        return False
    sl = g.get("spread_line")
    if (a.fav or a.dog) and sl is None:
        return False
    if sl is not None:
        fav = (is_home and sl > 0) or (not is_home and sl < 0)
        if a.fav and not fav:
            return False
        if a.dog and fav:
            return False
    if a.rest:
        rest = (g.get("home_rest") or 0) - (g.get("away_rest") or 0)
        if is_home and rest <= 0:
            return False
        if not is_home and rest >= 0:
            return False
    return True


def report_ats(a, db_path=kb.DB_PATH):
    team = a.team.upper()
    w = l = p = 0
    for g in _games_for_team(team, a.since, db_path):
        if g.get("spread_line") is None or not _situational_ok(g, team, a):
            continue
        is_home = g["home_team"] == team
        # spread_line > 0 = home favored; home covers when result > spread_line.
        home_edge = g["result"] - g["spread_line"]
        edge = home_edge if is_home else -home_edge  # >0 = team covered
        if abs(edge) < 1e-9:
            p += 1
        elif edge > 0:
            w += 1
        else:
            l += 1
    n = w + l
    pct = f"{100.0 * w / n:.1f}%" if n else "n/a"
    filt = " ".join(f for f in ("home", "away", "div", "fav", "dog", "rest")
                    if getattr(a, f)) or "all games"
    print(f"{team} ATS since {a.since} ({filt}): {w}-{l}-{p}  ({pct} cover)")
    return (w, l, p)


def report_ou(a, db_path=kb.DB_PATH):
    team = a.team.upper()
    o = u = p = 0
    for g in _games_for_team(team, a.since, db_path):
        tl = g.get("total_line")
        hs, as_ = g.get("home_score"), g.get("away_score")
        if tl is None or hs is None or as_ is None or not _situational_ok(g, team, a):
            continue
        pts = hs + as_
        if abs(pts - tl) < 1e-9:
            p += 1
        elif pts > tl:
            o += 1
        else:
            u += 1
    n = o + u
    pct = f"{100.0 * o / n:.1f}%" if n else "n/a"
    filt = " ".join(f for f in ("home", "away", "div", "fav", "dog", "rest")
                    if getattr(a, f)) or "all games"
    print(f"{team} O/U since {a.since} ({filt}): {o} over / {u} under / {p} push  "
          f"({pct} over)")
    return (o, u, p)


def report_leaders(a, db_path=kb.DB_PATH):
    rows = kb.query(
        "SELECT player_display_name AS player, position AS pos, "
        "COUNT(*) AS g, ROUND(SUM(fantasy_points_ppr),1) AS ppr, "
        "ROUND(AVG(fantasy_points_ppr),1) AS ppg "
        "FROM player_week WHERE position=? AND season=? "
        "GROUP BY player_id ORDER BY ppr DESC LIMIT 25",
        (a.pos.upper(), a.season), db_path=db_path)
    if not a.json:
        print(f"Fantasy PPR leaders — {a.pos.upper()} {a.season}")
    _print_rows(rows, a.json)
    return rows


def report_usage(a, db_path=kb.DB_PATH):
    rows = kb.query(
        "SELECT player_display_name AS player, COUNT(*) AS g, "
        "SUM(COALESCE(carries,0)) AS car, SUM(COALESCE(targets,0)) AS tgt, "
        "SUM(COALESCE(carries,0)+COALESCE(targets,0)) AS touches "
        "FROM player_week WHERE position=? AND season=? "
        "GROUP BY player_id ORDER BY touches DESC LIMIT 25",
        (a.pos.upper(), a.season), db_path=db_path)
    if not a.json:
        print(f"Usage (carries+targets) — {a.pos.upper()} {a.season}")
    _print_rows(rows, a.json)
    return rows


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description="Query the NFL knowledge base (read-only).")
    ap.add_argument("sql", nargs="?", help="a SELECT/WITH query")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--schema", nargs="?", const="*",
                    help="list tables (or columns of TABLE) and exit")
    ap.add_argument("--report", choices=("ats", "ou", "leaders", "usage"))
    ap.add_argument("--team")
    ap.add_argument("--since", type=int, default=1999)
    ap.add_argument("--pos")
    ap.add_argument("--season", type=int)
    for f in ("home", "away", "div", "fav", "dog", "rest"):
        ap.add_argument(f"--{f}", action="store_true")
    a = ap.parse_args(argv)

    if a.schema:
        if a.schema == "*":
            for t in kb.list_tables():
                print(f"{t}  ({len(kb.columns(t))} cols)")
            print("\nColumns of a table: python3 kb_query.py --schema <table>")
        else:
            print(f"{a.schema}:")
            for c in kb.columns(a.schema):
                print(f"  {c}")
        return 0

    if a.report in ("ats", "ou"):
        if not a.team:
            print("--team is required for that report")
            return 1
        (report_ats if a.report == "ats" else report_ou)(a)
        return 0
    if a.report in ("leaders", "usage"):
        if not (a.pos and a.season):
            print("--pos and --season are required for that report")
            return 1
        (report_leaders if a.report == "leaders" else report_usage)(a)
        return 0
    if a.sql:
        return run_sql(a.sql, a.json)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
