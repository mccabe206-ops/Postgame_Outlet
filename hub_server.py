"""Localhost-only Power Ratings HUB — one clickable UI for the whole agent.

A single control panel that fronts all 11 power-ratings menu items so you can
click around instead of remembering commands, while keeping full terminal
parity (every action shows its raw stdout/stderr alongside a rendered view).

It does NOT replace the AI reasoning: for the conversation-heavy tasks (update
ratings, edit a write-up, interpret results) it loads the data into view and
points you back to Claude Code, where the "give a take -> I suggest a move"
flow lives. Mechanical pieces (manual rating tweak, manual write-up save,
running the read-only reports, launching the sub-tools) work fully here.

Lives on the `testing` branch (Lane 2, mccabe-only WIP) — never published to
walshja9. Bound to 127.0.0.1 so ONLY this machine can reach it.

Run:
    python3 hub_server.py            # opens browser to the hub
    python3 hub_server.py --no-open  # don't auto-open

Ports of the sub-tools it launches: pick 8787, team 8788, injury 8789, guru 8790.
This hub: 8786.

Stdlib only (http.server). Stop with Ctrl-C.
"""

import csv
import json
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HOST = "127.0.0.1"
PORT = 8786
REPO = os.path.dirname(os.path.abspath(__file__))
RATINGS = os.path.join(REPO, "data", "ratings.csv")
LOGDIR = "/tmp"

# --- KB chat (Claude API) config ---
KEY_FILE = os.path.join(REPO, "data", ".anthropic_key")   # gitignored secret
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
KB_MODEL = os.environ.get("KB_CHAT_MODEL", "claude-opus-5")
KB_MAX_TOOL_ITERS = 8          # bound the agentic loop (and cost) per question
KB_ROW_CAP = 300               # rows returned to the model per query
KB_CHAR_CAP = 24000            # char cap on a single tool result fed back to model
SCHEMA_DOC = os.path.join(REPO, "reference", "kb_schema.md")

# tool name -> (script, default port)
TOOLS = {
    "pick": ("pick_server.py", 8787),
    "team": ("team_server.py", 8788),
    "injury": ("injury_server.py", 8789),
    "guru": ("guru_server.py", 8790),
    "depth": ("depth_server.py", 8791),
}


# ---------------------------------------------------------------- helpers
def _port_up(port, timeout=0.25):
    try:
        with socket.create_connection((HOST, port), timeout):
            return True
    except OSError:
        return False


def _sh(argv, timeout=180):
    """Run a command in the repo, capture everything. Never uses a shell."""
    try:
        p = subprocess.run(argv, cwd=REPO, capture_output=True, text=True,
                            timeout=timeout)
        return {"rc": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
                "cmd": " ".join(argv)}
    except subprocess.TimeoutExpired:
        return {"rc": 124, "stdout": "", "stderr": f"timed out after {timeout}s",
                "cmd": " ".join(argv)}
    except Exception as e:  # noqa: BLE001
        return {"rc": 1, "stdout": "", "stderr": str(e), "cmd": " ".join(argv)}


def _spawn(argv):
    """Launch a long-running sub-server detached, logging to /tmp."""
    log = open(os.path.join(LOGDIR, argv[1].replace(".py", ".log")), "ab")
    subprocess.Popen(argv, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                     start_new_session=True)


def _git(*args):
    return _sh(["git"] + list(args), timeout=60)


def _read_ratings():
    rows = []
    with open(RATINGS, newline="") as f:
        for r in csv.DictReader(f):
            try:
                qb = float(r.get("qb_value") or 0)
                off = float(r.get("off_value") or 0)
                dfn = float(r.get("def_value") or 0)
            except ValueError:
                qb = off = dfn = 0.0
            rows.append({
                "team": r.get("team", ""), "qb_name": r.get("qb_name", ""),
                "qb": qb, "off": off, "def": dfn, "rating": round(qb + off + dfn, 2),
                "needs_review": (r.get("needs_review") or "").strip().upper(),
                "notes": r.get("notes", ""),
            })
    rows.sort(key=lambda x: x["rating"], reverse=True)
    return rows


def _status():
    br = _git("rev-parse", "--abbrev-ref", "HEAD")["stdout"].strip()
    dirty = _git("status", "-s", "--", "data")["stdout"].strip()
    flagged = [r["team"] for r in _read_ratings() if r["needs_review"] == "Y"]
    servers = {name: _port_up(port) for name, (_, port) in TOOLS.items()}
    return {
        "branch": br,
        "dirty": bool(dirty),
        "dirty_files": dirty,
        "needs_review": {"count": len(flagged), "teams": flagged},
        "servers": servers,
    }


def _ratings_raw(rows):
    out = [f"{'TEAM':<5} {'QB':>6} {'OFF':>6} {'DEF':>6} {'RATING':>7}  QB / notes"]
    for r in rows:
        flag = "  ⚠needs_review" if r["needs_review"] == "Y" else ""
        out.append(f"{r['team']:<5} {r['qb']:>6.1f} {r['off']:>6.1f} "
                   f"{r['def']:>6.1f} {r['rating']:>7.1f}  {r['qb_name']}{flag}")
    return "\n".join(out)


# ---------------------------------------------------------------- actions
def act_launch(body):
    tool = body.get("tool")
    if tool not in TOOLS:
        return {"ok": False, "message": f"unknown tool {tool}"}
    script, port = TOOLS[tool]
    url = f"http://{HOST}:{port}/"
    started = False
    if tool == "team":
        # per-team: restart cleanly with the requested team
        team = (body.get("team") or "").strip()
        if not team:
            return {"ok": False, "message": "team name required"}
        subprocess.run(["pkill", "-f", "team_server.py"], capture_output=True)
        _spawn(["python3", script, "--no-open", team])
        started = True
    elif not _port_up(port):
        _spawn(["python3", script, "--no-open"])
        started = True
    # brief wait for bind
    for _ in range(20):
        if _port_up(port):
            break
        threading.Event().wait(0.15)
    # depth chart: optional team deep-link (the page reads ?q= on load)
    if tool == "depth":
        team = (body.get("team") or "").strip()
        if team:
            from urllib.parse import quote
            url = url + "?q=" + quote(team)
    return {"ok": _port_up(port), "url": url, "started": started,
            "message": "" if _port_up(port) else "server did not come up — check /tmp log"}


def act_run(body):
    action = body.get("action")
    if action == "ratings":
        rows = _read_ratings()
        return {"ok": True, "rc": 0, "stdout": _ratings_raw(rows), "stderr": "",
                "rendered": {"type": "ratings", "rows": rows}, "cmd": "(read data/ratings.csv)"}
    if action == "results":
        week = str(body.get("week") or "").strip()
        if not week.isdigit():
            return {"ok": False, "message": "enter a week number (1–18)"}
        argv = ["python3", "results.py", week]
        year = str(body.get("year") or "").strip()
        if year.isdigit():
            argv.append(year)
        res = _sh(argv, timeout=180)
        res["ok"] = True
        return res
    if action == "preview":
        res = _sh(["python3", "generate_site.py", "--output", "/tmp/npr_preview.html"])
        res["ok"] = True
        res["preview_path"] = "/tmp/npr_preview.html"
        return res
    if action == "whatchanged":
        stat = _git("diff", "--stat", "HEAD", "--", "data")
        detail = _git("diff", "HEAD", "--", "data/ratings.csv")
        combined = ("=== data/ diff --stat ===\n" + (stat["stdout"] or "(no changes)")
                    + "\n\n=== data/ratings.csv detail ===\n"
                    + (detail["stdout"] or "(no ratings changes)"))
        return {"ok": True, "rc": 0, "stdout": combined, "stderr": "",
                "cmd": "git diff HEAD -- data"}
    if action == "injuries":
        argv = ["python3", "injuries.py"]
        team = (body.get("team") or "").strip()
        if team:
            argv.append(team)
        if body.get("all"):
            argv.append("--all")
        res = _sh(argv, timeout=120)
        res["ok"] = True
        return res
    if action == "kb":
        sql = (body.get("sql") or "").strip()
        if not sql:
            return {"ok": True, "rc": 0, "cmd": "kb_query.py --schema",
                    **_sh(["python3", "kb_query.py", "--schema"], timeout=60)}
        res = _sh(["python3", "kb_query.py", sql], timeout=120)
        res["ok"] = True
        return res
    if action == "trend":
        return act_run_trend(body)
    return {"ok": False, "message": f"unknown action {action}"}


def act_publish_check(_body):
    """Preflight only — never pushes. Confirm the gate + show what would go live."""
    tests = _sh(["python3", "-m", "unittest", "discover", "-s", "tests"], timeout=300)
    stat = _git("diff", "--stat", "HEAD", "--", "data")
    flagged = [r["team"] for r in _read_ratings() if r["needs_review"] == "Y"]
    gate = ("BLOCKED — needs_review=Y for: " + ", ".join(flagged)) if flagged else "clear (all rows N)"
    out = (f"EDITORIAL GATE: {gate}\n\n"
           f"=== test suite (exit {tests['rc']}) ===\n"
           + (tests["stdout"] + tests["stderr"])[-4000:]
           + "\n\n=== what would go live (data/ diff --stat) ===\n"
           + (stat["stdout"] or "(no data changes to publish)")
           + "\n\n----------------------------------------\n"
           "Preflight only. To take it LIVE, tell Claude Code \"publish\" and it will\n"
           "commit + push from main the proven way (dual-push to walshja9 + mccabe).")
    return {"ok": True, "rc": tests["rc"], "stdout": out, "stderr": "",
            "gate_clear": not flagged, "cmd": "publish preflight"}


def act_writeup_get(abbr):
    abbr = (abbr or "").strip().upper()
    path = os.path.join(REPO, "data", "writeups", f"{abbr}.md")
    if not abbr:
        return {"ok": False, "message": "abbr required"}
    content = ""
    if os.path.exists(path):
        with open(path) as f:
            content = f.read()
    return {"ok": True, "abbr": abbr, "content": content, "exists": os.path.exists(path)}


def act_writeup_save(body):
    abbr = (body.get("abbr") or "").strip().upper()
    if not abbr.isalpha() or not (2 <= len(abbr) <= 3):
        return {"ok": False, "message": "abbr must be the 2–3 letter team code"}
    content = body.get("content", "")
    path = os.path.join(REPO, "data", "writeups", f"{abbr}.md")
    with open(path, "w") as f:
        f.write(content)
    return {"ok": True, "message": f"saved data/writeups/{abbr}.md ({len(content)} chars)",
            "path": f"data/writeups/{abbr}.md"}


# ---------------------------------------------------------------- KB chat
def _anthropic_key():
    """Read the API key from env, then the gitignored file. Never logged."""
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k.strip()
    try:
        with open(KEY_FILE) as f:
            return f.read().strip()
    except OSError:
        return None


def _kb_sql(sql):
    """Run one read-only query via kb_query.py --json. Returns (ok, payload)."""
    res = _sh(["python3", "kb_query.py", sql, "--json"], timeout=90)
    if res["rc"] != 0 or not res["stdout"].strip():
        err = (res["stderr"] or res["stdout"] or "query failed").strip()
        # keep only the useful tail of any traceback for the model to self-correct
        return False, err[-1200:]
    try:
        rows = json.loads(res["stdout"])
    except json.JSONDecodeError:
        return False, res["stdout"][:1200]
    capped = rows[:KB_ROW_CAP] if isinstance(rows, list) else rows
    return True, {"row_count": len(rows) if isinstance(rows, list) else 1,
                  "returned": len(capped) if isinstance(capped, list) else 1,
                  "rows": capped}


def _kb_schema(table=None):
    argv = ["python3", "kb_query.py", "--schema"]
    if table:
        argv.append(table)
    return _sh(argv, timeout=30)["stdout"][:KB_CHAR_CAP]


KB_TOOLS = [
    {"name": "run_sql",
     "description": "Execute a single read-only SQLite SELECT/WITH query against the NFL "
                    "knowledge base and return the rows as JSON. Only SELECT/WITH allowed. "
                    "Use LIMIT for exploratory queries. Column names must match the schema — "
                    "call get_schema if unsure.",
     "input_schema": {"type": "object",
                      "properties": {"sql": {"type": "string", "description": "the SELECT/WITH query"}},
                      "required": ["sql"]}},
    {"name": "get_schema",
     "description": "List all tables (no arg) or the full column list of one table. "
                    "team_week/player_week have 130–150 columns — use this to find exact names "
                    "(e.g. turnover / giveaway / takeaway columns) before querying.",
     "input_schema": {"type": "object",
                      "properties": {"table": {"type": "string",
                                     "description": "optional table name, e.g. team_week"}}}},
]


def _kb_system_prompt():
    try:
        with open(SCHEMA_DOC) as f:
            schema = f.read()
    except OSError:
        schema = "(schema doc unavailable — use get_schema)"
    return (
        "You are the NFL Knowledge Base analyst for Sean's McCabe-Method power-ratings project. "
        "You answer NFL questions by querying a local read-only SQLite DB (nflverse, 1999+) with "
        "the run_sql tool, then explaining the result plainly and honestly.\n\n"
        "RULES:\n"
        "- Write SQLite SELECT/WITH only. If unsure of a column name, call get_schema FIRST — "
        "team_week/player_week have 130–150 columns.\n"
        "- Current date context: it is the 2026 offseason. The 2025 season is COMPLETE "
        "(all 272 regular-season games played). The 2026 season is scheduled but NOT yet "
        "played (0 results). So 'last year' / 'last season' = season 2025 unless the user says "
        "otherwise; a question about 'this week'/'this season' 2026 has no results yet — say so "
        "and offer schedule/betting-line or prior-season context instead.\n"
        "- For 'turnover differential' compute takeaways − giveaways from team_week; confirm the "
        "exact column names via get_schema before writing the query.\n"
        "- For trend questions ('spot trends this week'), run the several queries you need, then "
        "summarize the real numbers — lead with what's notable, cite the figures, and separate "
        "signal from noise (sample size, luck, quality of competition).\n"
        "- Betting math: spread_line>0 = home favored; home covers when result>spread_line; "
        "over when home_score+away_score>total_line.\n"
        "- Honest limits: no data pre-1999, no historical player-prop odds, Sleeper tables are a "
        "current snapshot (no ADP/projections). Say so rather than inventing.\n"
        "- Keep answers tight and terminal-friendly. When you present per-team/per-player figures, "
        "a compact ranked list or table is ideal. Do not fabricate numbers you didn't query.\n\n"
        "=== SCHEMA & QUERY GUIDE ===\n" + schema)


def _anthropic_messages(payload, key):
    """POST to the Messages API via stdlib urllib. Returns parsed JSON or raises."""
    import urllib.request
    import urllib.error
    data = json.dumps(payload).encode()
    req = urllib.request.Request(ANTHROPIC_URL, data=data, method="POST")
    req.add_header("x-api-key", key)
    req.add_header("anthropic-version", ANTHROPIC_VERSION)
    req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"Anthropic API {e.code}: {body[:500]}")


def act_kbchat(body):
    """Agentic NL->SQL loop. body: {question, history:[{role,text}]}."""
    key = _anthropic_key()
    if not key:
        return {"ok": False, "need_key": True,
                "message": "No Anthropic API key found. Add it to data/.anthropic_key "
                           "(see the hub instructions), then retry."}
    question = (body.get("question") or "").strip()
    if not question:
        return {"ok": False, "message": "ask a question"}

    # Build messages: prior turns (text only) + new question
    messages = []
    for h in (body.get("history") or []):
        role = "assistant" if h.get("role") == "assistant" else "user"
        txt = (h.get("text") or "").strip()
        if txt:
            messages.append({"role": role, "content": txt})
    messages.append({"role": "user", "content": question})

    steps = []
    system = _kb_system_prompt()
    try:
        for _ in range(KB_MAX_TOOL_ITERS):
            resp = _anthropic_messages({
                "model": KB_MODEL, "max_tokens": 2000, "system": system,
                "tools": KB_TOOLS, "messages": messages,
            }, key)
            content = resp.get("content", [])
            messages.append({"role": "assistant", "content": content})
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            if resp.get("stop_reason") != "tool_use" or not tool_uses:
                text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
                return {"ok": True, "answer": text.strip() or "(no answer)",
                        "steps": steps, "model": KB_MODEL,
                        "usage": resp.get("usage", {})}
            # execute each requested tool, feed results back
            results = []
            for tu in tool_uses:
                name, inp = tu.get("name"), tu.get("input", {})
                if name == "run_sql":
                    sql = inp.get("sql", "")
                    ok, payload = _kb_sql(sql)
                    steps.append({"sql": sql, "ok": ok,
                                  "rows": payload.get("rows") if ok else None,
                                  "row_count": payload.get("row_count") if ok else None,
                                  "error": None if ok else payload})
                    out = json.dumps(payload)[:KB_CHAR_CAP] if ok else f"ERROR: {payload}"
                elif name == "get_schema":
                    out = _kb_schema(inp.get("table"))
                    steps.append({"sql": f"[schema {inp.get('table') or 'all'}]",
                                  "ok": True, "rows": None, "error": None})
                else:
                    out = f"unknown tool {name}"
                results.append({"type": "tool_result", "tool_use_id": tu.get("id"),
                                "content": out})
            messages.append({"role": "user", "content": results})
        return {"ok": True, "answer": "(stopped after max query steps — try narrowing the question)",
                "steps": steps, "model": KB_MODEL}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e), "steps": steps}


def act_kbstatus():
    return {"has_key": bool(_anthropic_key()), "model": KB_MODEL,
            "key_file": "data/.anthropic_key"}


# ---------------------------------------------------------------- canned trends
# One-click, no-API-key bettable-trend buttons for card 11. Each runs a prebuilt
# read-only query through kb_query.py; the week-relative ones auto-target the
# UPCOMING week so the angle stays relevant every load. Betting math per
# reference/kb_schema.md: result = home_score - away_score; spread_line>0 = home
# favored; home covers when result>spread_line; a favorite (either side) covers
# when ABS(result)>ABS(spread_line) AND SIGN(result)=SIGN(spread_line); over when
# home_score+away_score>total_line.
TREND_SINCE = 2007   # modern-era sample floor for the historical angles

TRENDS = [
    {"id": "slate",
     "label": "📋 This week's slate",
     "desc": "The upcoming week's games with spread + total (unplayed)."},
    {"id": "bigfav_fade",
     "label": "Fade big favs (7+)",
     "desc": "This week #: favorites laying 7+ — do the underdogs cover? (since 2007)"},
    {"id": "home_dog",
     "label": "Home underdogs ATS",
     "desc": "This week #: home underdogs ATS + straight-up upsets (since 2007)"},
    {"id": "div_under",
     "label": "Division unders",
     "desc": "This week #: division games going UNDER the total (since 2007)"},
    {"id": "under_all",
     "label": "UNDER rate (all)",
     "desc": "This week #: all games going UNDER the total (since 2007)"},
    {"id": "fav_su",
     "label": "Do favorites win SU?",
     "desc": "This week #: how often the favorite just wins outright (since 2007)"},
]


def _current_wk():
    """Upcoming (season, week): earliest unplayed REG week in the latest season
    present, falling back to that season's last week. Fully local — no ESPN."""
    rows = _kb_rows(
        "SELECT (SELECT MAX(season) FROM games WHERE game_type='REG') AS s, "
        "COALESCE("
        "(SELECT MIN(week) FROM games WHERE game_type='REG' AND result IS NULL "
        " AND season=(SELECT MAX(season) FROM games WHERE game_type='REG')), "
        "(SELECT MAX(week) FROM games WHERE game_type='REG' "
        " AND season=(SELECT MAX(season) FROM games WHERE game_type='REG'))) AS w")
    try:
        return int(rows[0]["s"]), int(rows[0]["w"])
    except (TypeError, IndexError, KeyError, ValueError):
        return 2026, 1


def _kb_rows(sql):
    """Run a read-only query via kb_query.py --json; return list of dict rows or None."""
    res = _sh(["python3", "kb_query.py", sql, "--json"], timeout=60)
    if res["rc"] != 0 or not res["stdout"].strip():
        return None
    try:
        return json.loads(res["stdout"])
    except json.JSONDecodeError:
        return None


TREND_TITLE = {
    "slate": "This week's slate",
    "bigfav_fade": "Fade favorites of 7+ (dogs cover)",
    "home_dog": "Home underdogs ATS",
    "div_under": "Division-game unders",
    "under_all": "Unders (all games)",
    "fav_su": "Favorites straight-up",
}


def _trend_hist_sql(tid, week):
    """Aggregate history for the situation, keyed to this week number since 2007.
    None for 'slate' (that button is just the game list, no history)."""
    w = int(week)
    dog_cover = ("SUM(CASE WHEN NOT(ABS(result)>ABS(spread_line) AND "
                 "SIGN(result)=SIGN(spread_line)) AND result<>spread_line THEN 1 ELSE 0 END)")
    fav_cover = ("SUM(CASE WHEN ABS(result)>ABS(spread_line) AND "
                 "SIGN(result)=SIGN(spread_line) THEN 1 ELSE 0 END)")
    base = f"game_type='REG' AND week={w} AND season>={TREND_SINCE} AND result IS NOT NULL"
    if tid == "slate":
        return None
    if tid == "bigfav_fade":
        return (f"SELECT COUNT(*) games, {fav_cover} fav_cover, {dog_cover} dog_cover, "
                f"ROUND(100.0*{dog_cover}/COUNT(*),1) dog_cover_pct "
                f"FROM games WHERE {base} AND ABS(spread_line)>=7")
    if tid == "home_dog":
        return (f"SELECT COUNT(*) games, "
                f"SUM(CASE WHEN result>spread_line THEN 1 ELSE 0 END) dog_cover, "
                f"ROUND(100.0*SUM(CASE WHEN result>spread_line THEN 1 ELSE 0 END)/COUNT(*),1) ats_pct, "
                f"SUM(CASE WHEN result>0 THEN 1 ELSE 0 END) dog_win_su "
                f"FROM games WHERE {base} AND spread_line<0")
    if tid == "div_under":
        return (f"SELECT COUNT(*) games, "
                f"SUM(CASE WHEN home_score+away_score<total_line THEN 1 ELSE 0 END) unders, "
                f"ROUND(100.0*SUM(CASE WHEN home_score+away_score<total_line THEN 1 ELSE 0 END)/COUNT(*),1) under_pct "
                f"FROM games WHERE {base} AND div_game=1 AND total_line IS NOT NULL")
    if tid == "under_all":
        return (f"SELECT COUNT(*) games, "
                f"SUM(CASE WHEN home_score+away_score<total_line THEN 1 ELSE 0 END) unders, "
                f"SUM(CASE WHEN home_score+away_score>total_line THEN 1 ELSE 0 END) overs, "
                f"ROUND(100.0*SUM(CASE WHEN home_score+away_score<total_line THEN 1 ELSE 0 END)/COUNT(*),1) under_pct "
                f"FROM games WHERE {base} AND total_line IS NOT NULL")
    if tid == "fav_su":
        return (f"SELECT COUNT(*) games, "
                f"SUM(CASE WHEN (spread_line>0 AND result>0) OR (spread_line<0 AND result<0) THEN 1 ELSE 0 END) fav_win, "
                f"ROUND(100.0*SUM(CASE WHEN (spread_line>0 AND result>0) OR (spread_line<0 AND result<0) THEN 1 ELSE 0 END)/COUNT(*),1) fav_win_pct "
                f"FROM games WHERE {base} AND spread_line<>0")
    return None


def _trend_applies_sql(tid, season, week):
    """The UPCOMING week's games that fit the situation, each with the suggested
    bet in a 'take' column so it's obvious what the trend says to play."""
    s, w = int(season), int(week)
    slate = f"season={s} AND week={w} AND game_type='REG'"
    if tid == "slate":
        return (f"SELECT away_team, home_team, spread_line, total_line, div_game, gameday "
                f"FROM games WHERE {slate} ORDER BY gameday, gametime")
    if tid == "bigfav_fade":
        # dog gets the points; dog = away when home favored (spread>0), else home
        return (f"SELECT away_team, home_team, spread_line, "
                f"CASE WHEN spread_line>0 THEN away_team ELSE home_team END || ' +' || ABS(spread_line) AS take "
                f"FROM games WHERE {slate} AND ABS(spread_line)>=7 ORDER BY ABS(spread_line) DESC")
    if tid == "home_dog":
        return (f"SELECT away_team, home_team, spread_line, "
                f"home_team || ' +' || ABS(spread_line) AS take "
                f"FROM games WHERE {slate} AND spread_line<0 ORDER BY spread_line")
    if tid == "div_under":
        return (f"SELECT away_team, home_team, total_line, 'Under ' || total_line AS take "
                f"FROM games WHERE {slate} AND div_game=1 ORDER BY total_line DESC")
    if tid == "under_all":
        return (f"SELECT away_team, home_team, total_line, 'Under ' || total_line AS take "
                f"FROM games WHERE {slate} ORDER BY total_line DESC")
    if tid == "fav_su":
        return (f"SELECT away_team, home_team, spread_line, "
                f"CASE WHEN spread_line>0 THEN home_team ELSE away_team END || ' ML' AS take "
                f"FROM games WHERE {slate} AND spread_line<>0 ORDER BY ABS(spread_line) DESC")
    return None


def act_trends_catalog():
    season, week = _current_wk()
    return {"season": season, "week": week, "since": TREND_SINCE, "trends": TRENDS}


def act_run_trend(body):
    tid = body.get("trend")
    if tid not in {t["id"] for t in TRENDS}:
        return {"ok": False, "message": f"unknown trend {tid}"}
    season, week = _current_wk()
    title = TREND_TITLE.get(tid, tid)
    parts = []

    hist = _trend_hist_sql(tid, week)
    if hist:
        h = _sh(["python3", "kb_query.py", hist], timeout=90)
        parts.append(f"=== HISTORY — {title} · Week {week}, since {TREND_SINCE} ===\n"
                     + (h["stdout"] or h["stderr"] or "(no data)"))

    applies = _trend_applies_sql(tid, season, week)
    if applies:
        a = _sh(["python3", "kb_query.py", applies], timeout=90)
        out = (a["stdout"] or "").rstrip()
        if tid == "slate":
            head = f"=== THIS WEEK'S SLATE — Week {week} {season} ==="
        elif not out or out.startswith("0 row") or "0 row(s)" in out:
            head = f"=== APPLIES THIS WEEK (Week {week} {season}) ==="
            out = "No games on this week's slate fit this situation."
        else:
            head = (f"=== APPLIES THIS WEEK — Week {week} {season} "
                    f"('take' = the side/total this trend plays) ===")
        parts.append(head + "\n" + (out or a["stderr"] or "(no data)"))

    return {"ok": True, "rc": 0, "stdout": "\n\n".join(parts) or "(no output)",
            "stderr": "", "cmd": f"trend: {tid} · Week {week} {season}"}


# ---------------------------------------------------------------- page
PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Power Ratings — Hub</title>
<style>
 :root{--bg:#0e1116;--card:#171c24;--line:#273040;--ink:#e6edf3;--dim:#93a1b0;
       --good:#2ea043;--bad:#e5534b;--warn:#d8c534;--accent:#3b82f6}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
   font:15px/1.45 -apple-system,Segoe UI,Roboto,sans-serif}
 header{padding:16px 22px;border-bottom:1px solid var(--line);display:flex;
   align-items:center;gap:14px;position:sticky;top:0;background:var(--bg);z-index:5;flex-wrap:wrap}
 h1{font-size:19px;margin:0}
 .pill{font-size:12px;padding:3px 10px;border-radius:20px;border:1px solid var(--line);color:var(--dim)}
 .pill.on{color:var(--good);border-color:#1c4a2b;background:#12331d}
 .pill.off{color:var(--dim)}
 .pill.warn{color:var(--warn);border-color:#4a4a1c;background:#2a2f0e}
 .pill.bad{color:var(--bad);border-color:#4a1c1c;background:#331212}
 #bar{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;padding:18px 22px}
 .cardbox{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;
   display:flex;flex-direction:column;gap:8px}
 .cardbox h3{margin:0;font-size:15px;display:flex;align-items:center;gap:8px}
 .n{display:inline-flex;width:22px;height:22px;align-items:center;justify-content:center;
   border-radius:6px;background:#12233f;color:#9dc1ff;font-size:12px;font-weight:700;flex:0 0 auto}
 .cardbox p{margin:0;color:var(--dim);font-size:12.5px;min-height:32px}
 .cardbox.wide{grid-column:1/-1}
 .trendgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;width:100%}
 .trendgrid button{width:100%;text-align:center}
 .kbtools{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 button.go{background:#12233f;border:1px solid var(--accent);color:#dbe9ff;padding:7px 12px;
   border-radius:8px;cursor:pointer;font-size:13.5px}
 button.go:hover{background:#193253} button.go.alt{background:var(--card);border-color:var(--line);color:var(--ink)}
 button.go:disabled{opacity:.5;cursor:not-allowed}
 input,textarea,select{background:#0e1116;border:1px solid var(--line);color:var(--ink);
   border-radius:8px;padding:6px 9px;font-size:13.5px;font-family:inherit}
 input.sm{width:66px} textarea{width:100%;min-height:120px;font-family:ui-monospace,Menlo,monospace}
 .note{font-size:11.5px;color:var(--warn)}
 #out{position:sticky;bottom:0;background:#0b0e13;border-top:1px solid var(--line);max-height:44vh;
   display:flex;flex-direction:column}
 #outhead{padding:8px 16px;display:flex;gap:12px;align-items:center;border-bottom:1px solid var(--line)}
 #outhead .title{font-weight:600} #outhead .cmd{color:var(--dim);font-size:12px;
   font-family:ui-monospace,Menlo,monospace}
 .toggle{margin-left:auto;display:flex;gap:0;border:1px solid var(--line);border-radius:8px;overflow:hidden}
 .toggle button{background:var(--card);border:0;color:var(--dim);padding:5px 12px;cursor:pointer;font-size:12.5px}
 .toggle button.sel{background:#12233f;color:#dbe9ff}
 #outbody{overflow:auto;padding:12px 16px}
 pre{margin:0;white-space:pre-wrap;word-break:break-word;font:12.5px/1.5 ui-monospace,Menlo,monospace;color:#cdd9e5}
 table.r{border-collapse:collapse;width:100%} table.r th,table.r td{padding:6px 10px;
   border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
 table.r th:first-child,table.r td:first-child,table.r th.l,table.r td.l{text-align:left}
 table.r th{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.04em}
 tr.flag td{background:#2a2f0e}
 .close{cursor:pointer;color:var(--dim);border:1px solid var(--line);border-radius:6px;padding:3px 8px;background:var(--card)}
 .rc-ok{color:var(--good)} .rc-bad{color:var(--bad)}
 dialog{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:12px;
   padding:18px;max-width:560px;width:92%}
 dialog::backdrop{background:rgba(0,0,0,.6)}
</style></head><body>
<header>
  <h1>⚡ Power Ratings Hub</h1>
  <span class="pill" id="p-branch">branch…</span>
  <span class="pill" id="p-gate">gate…</span>
  <div id="bar"><span class="pill" id="p-dirty">…</span>
    <span class="pill" id="s-pick">pick</span><span class="pill" id="s-team">team</span>
    <span class="pill" id="s-injury">injury</span><span class="pill" id="s-guru">guru</span>
    <button class="close" onclick="refresh()">↻</button></div>
</header>

<div class="grid" id="cards"></div>

<div id="out" style="display:none">
  <div id="outhead">
    <span class="title" id="out-title">output</span>
    <span class="cmd" id="out-cmd"></span>
    <span id="out-rc"></span>
    <span class="toggle"><button id="tg-rend" class="sel" onclick="setView('rendered')">Rendered</button>
      <button id="tg-raw" onclick="setView('raw')">Raw</button></span>
    <span class="close" onclick="document.getElementById('out').style.display='none'">✕</span>
  </div>
  <div id="outbody"></div>
</div>

<dialog id="dlg"><div id="dlg-body"></div></dialog>

<script>
const CARDS = [
 {n:1, t:"Open pick sheet", d:"Your editable weekly pick sheet (matchups, market vs. your line, edge; pick 5 with confidence).",
   render:c=>btn(c,"Open pick sheet",()=>launch('pick'))},
 {n:2, t:"Update ratings", d:"Open a team workspace, then bring your take to Claude Code — I suggest a move & draft the write-up. Quick manual tweak below.",
   render:c=>{teamOpen(c); manualRating(c);}},
 {n:3, t:"Show current ratings", d:"The full 32-team board from your ratings, best to worst.",
   render:c=>btn(c,"Show board",()=>run({action:'ratings'},"Current ratings"))},
 {n:4, t:"Edit a write-up", d:"Load a team blurb to edit here (manual save), or bring your take to Claude Code for a drafted rewrite.",
   render:c=>writeupCard(c)},
 {n:5, t:"Results & grading", d:"ESPN final scores + stats, picks graded vs. market, luck/quality read, rating signals.",
   render:c=>weekRun(c,'results',"Results & grading")},
 {n:6, t:"Preview locally", d:"Regenerate the site to a private local file — no publish.",
   render:c=>btn(c,"Build preview",()=>run({action:'preview'},"Local preview"))},
 {n:7, t:"Publish (preflight)", d:"Run the gate + tests and show exactly what would go live. To go live, say “publish” to Claude Code.",
   render:c=>btn(c,"Run preflight",()=>publishCheck(),"alt")},
 {n:8, t:"Publish an edition", d:"Named board snapshot (e.g. “Week 3”). Triggered as a manual GitHub Action — confirm the label with Claude Code.",
   render:c=>{const p=el('p');p.className='note';p.textContent='Handled via the publish-edition GitHub Action; tell Claude Code the label to run it.';c.appendChild(p);}},
 {n:9, t:"What changed", d:"Everything edited in data/ since the last publish (diff --stat + ratings detail).",
   render:c=>btn(c,"Show diff",()=>run({action:'whatchanged'},"What changed"))},
 {n:10, t:"Injury report", d:"Every team's rating-relevant injuries (Sleeper). Open the dashboard, or run the CLI scan.",
   render:c=>injuryCard(c)},
 {n:12, t:"Depth charts", d:"Starter → backup order (Ourlads) with player photos + jersey numbers. List or field-diagram view; pick a team.",
   render:c=>depthCard(c)},
 {n:11, t:"NFL knowledge base", wide:true, d:"Chat in plain English — “turnover differential per team last year”, “spot the trends this week”. Model writes read-only SQL, cites the numbers. One-click trends + a raw SQL box work with no key.",
   render:c=>kbCard(c)},
];

function el(t,cls,txt){const e=document.createElement(t);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e;}
function btn(c,label,fn,cls){const b=el('button',(cls?'go '+cls:'go'),label);b.onclick=fn;
  const r=el('div','row');r.appendChild(b);c.appendChild(r);return b;}

function buildCards(){
  const g=document.getElementById('cards'); g.innerHTML='';
  for(const cd of CARDS){
    const box=el('div','cardbox'+(cd.wide?' wide':''));
    const h=el('h3'); h.appendChild(el('span','n',cd.n)); h.appendChild(document.createTextNode(cd.t));
    box.appendChild(h); box.appendChild(el('p',null,cd.d));
    cd.render(box); g.appendChild(box);
  }
}

// ---- card builders that need inputs
function teamOpen(c){
  const r=el('div','row'); const i=el('input'); i.placeholder='team (e.g. Bills / BUF)'; i.style.flex='1';
  const b=el('button','go','Open workspace'); b.onclick=()=>{ if(!i.value.trim())return alert('enter a team');
    launch('team',{team:i.value.trim()}); };
  r.appendChild(i); r.appendChild(b); c.appendChild(r);
}
function manualRating(c){
  const r=el('div','row'); r.style.marginTop='2px';
  const note=el('span','note','Manual tweak (no AI): '); c.appendChild(note);
  const abbr=el('input','sm'); abbr.placeholder='ABBR';
  const qb=el('input','sm'); qb.placeholder='qb'; const off=el('input','sm'); off.placeholder='off';
  const df=el('input','sm'); df.placeholder='def';
  const b=el('button','go alt','Preview edit'); b.onclick=()=>alert('Manual CSV edits go through Claude Code so the gate + notes stay honest. Type: “set '+(abbr.value||'BUF')+' qb '+(qb.value||'x')+'” to me.');
  [abbr,qb,off,df,b].forEach(x=>r.appendChild(x)); c.appendChild(r);
}
function writeupCard(c){
  const r=el('div','row'); const i=el('input'); i.placeholder='team ABBR (e.g. SEA)'; i.style.flex='1';
  const b=el('button','go','Load'); b.onclick=async()=>{
    const j=await api('/api/writeup?abbr='+encodeURIComponent(i.value.trim()));
    if(!j.ok)return alert(j.message||'load failed'); openWriteupEditor(j);
  };
  r.appendChild(i); r.appendChild(b); c.appendChild(r);
}
function injuryCard(c){
  const r=el('div','row');
  const b1=el('button','go','Open dashboard'); b1.onclick=()=>launch('injury');
  const i=el('input'); i.placeholder='team (blank = all)'; i.style.width='120px';
  const b2=el('button','go alt','Run scan'); b2.onclick=()=>run({action:'injuries',team:i.value.trim()},"Injury scan");
  [b1,i,b2].forEach(x=>r.appendChild(x)); c.appendChild(r);
}
function depthCard(c){
  const r=el('div','row');
  const b1=el('button','go','Open depth charts'); b1.onclick=()=>launch('depth');
  const i=el('input'); i.placeholder='team (optional)'; i.style.width='130px';
  const b2=el('button','go alt','Open team'); b2.onclick=()=>launch('depth',{team:i.value.trim()});
  [b1,i,b2].forEach(x=>r.appendChild(x)); c.appendChild(r);
}
function kbCard(c){
  const r=el('div','kbtools');
  const chat=el('button','go','💬 Chat with KB'); chat.onclick=openKbChat;
  const b1=el('button','go alt','Open guru'); b1.onclick=()=>launch('guru');
  r.appendChild(chat); r.appendChild(b1); c.appendChild(r);
  // one-click canned trends — no API key needed, auto-target the upcoming week
  const tl=el('div','note'); tl.id='trend-label'; tl.textContent='One-click bettable trends (no key needed):';
  tl.style.marginTop='6px'; c.appendChild(tl);
  const trow=el('div','trendgrid'); trow.id='trend-btns'; trow.textContent='loading trends…'; c.appendChild(trow);
  loadTrends(trow);
  const sqlLbl=el('div','note','Or write raw SQL:'); sqlLbl.style.marginTop='8px'; c.appendChild(sqlLbl);
  const ta=el('textarea'); ta.placeholder='SELECT … (blank = show schema)'; ta.style.minHeight='140px'; c.appendChild(ta);
  const r2=el('div','row'); r2.style.marginTop='2px';
  const b2=el('button','go','Run raw SQL'); b2.onclick=()=>run({action:'kb',sql:ta.value},"KB query");
  r2.appendChild(b2); c.appendChild(r2);
}
async function loadTrends(row){
  try{
    const j=await api('/api/trends');
    row.innerHTML='';
    const wk = j.week!=null ? ` · Wk${j.week} ${j.season}` : '';
    const lbl=document.getElementById('trend-label');
    if(lbl && j.week!=null) lbl.textContent=`One-click bettable trends for Week ${j.week} ${j.season} (no key needed):`;
    (j.trends||[]).forEach(t=>{
      const b=el('button','go alt',t.label); b.title=t.desc;
      b.onclick=()=>run({action:'trend',trend:t.id}, t.label+wk);
      row.appendChild(b);
    });
  }catch(e){ row.textContent='(trends unavailable)'; }
}

// ---- KB chat (Claude API backed)
let KB_HISTORY=[];
function genericTable(rows){
  if(!rows || !rows.length) return el('pre',null,'(no rows)');
  const cols=Object.keys(rows[0]);
  const t=el('table','r'); const head='<thead><tr>'+cols.map(c=>`<th class="l">${c}</th>`).join('')+'</tr></thead>';
  t.innerHTML=head; const tb=el('tbody');
  rows.slice(0,60).forEach(r=>{const tr=el('tr');
    tr.innerHTML=cols.map(c=>`<td class="l">${r[c]==null?'':String(r[c])}</td>`).join(''); tb.appendChild(tr);});
  t.appendChild(tb);
  const wrap=el('div'); wrap.appendChild(t);
  if(rows.length>60) wrap.appendChild(el('div','note',`(showing 60 of ${rows.length} rows)`));
  return wrap;
}
function stepBlock(s){
  const d=el('details'); d.style.margin='6px 0';
  const sum=el('summary'); sum.style.cursor='pointer'; sum.style.color='#9dc1ff';
  sum.textContent = (s.ok?'✓ ':'✗ ')+'SQL'+(s.row_count!=null?` · ${s.row_count} rows`:'');
  d.appendChild(sum);
  const pre=el('pre'); pre.textContent=s.sql; pre.style.marginTop='6px'; d.appendChild(pre);
  if(s.error){ const e=el('pre'); e.textContent='ERROR: '+s.error; e.style.color='var(--bad)'; d.appendChild(e); }
  else if(s.rows){ d.appendChild(genericTable(s.rows)); }
  return d;
}
function kbMsg(role,node){
  const wrap=el('div'); wrap.style.margin='10px 0'; wrap.style.padding='10px 12px';
  wrap.style.borderRadius='10px';
  wrap.style.background = role==='user' ? '#12233f' : 'var(--card)';
  wrap.style.border='1px solid var(--line)';
  const who=el('div'); who.style.fontSize='11px'; who.style.color='var(--dim)'; who.style.marginBottom='4px';
  who.textContent = role==='user' ? 'you' : 'KB analyst';
  wrap.appendChild(who); wrap.appendChild(node);
  document.getElementById('kb-transcript').appendChild(wrap);
  const sc=document.getElementById('kb-transcript'); sc.scrollTop=sc.scrollHeight;
  return wrap;
}
async function openKbChat(){
  let dlg=document.getElementById('kbdlg');
  if(!dlg){
    dlg=document.createElement('dialog'); dlg.id='kbdlg';
    dlg.style.maxWidth='860px'; dlg.style.width='94%'; dlg.style.padding='0';
    dlg.innerHTML=`
      <div style="padding:12px 16px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px">
        <b>NFL Knowledge Base — chat</b><span id="kb-model" class="pill"></span>
        <span id="kb-keywarn" class="pill warn" style="display:none">no API key</span>
        <span class="close" style="margin-left:auto" onclick="document.getElementById('kbdlg').close()">✕</span>
      </div>
      <div id="kb-transcript" style="max-height:56vh;overflow:auto;padding:14px 16px"></div>
      <div id="kb-keyhelp" style="display:none;padding:0 16px 8px"></div>
      <div style="display:flex;gap:8px;padding:12px 16px;border-top:1px solid var(--line)">
        <input id="kb-input" style="flex:1" placeholder="Ask about the NFL… (Enter to send)">
        <button class="go" id="kb-send" onclick="kbSend()">Send</button>
      </div>`;
    document.body.appendChild(dlg);
    dlg.querySelector('#kb-input').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();kbSend();}});
  }
  const st=await api('/api/kbstatus');
  document.getElementById('kb-model').textContent=st.model;
  document.getElementById('kb-keywarn').style.display = st.has_key?'none':'inline-block';
  const help=document.getElementById('kb-keyhelp');
  if(!st.has_key){
    help.style.display='block';
    help.innerHTML='<div class="note">No key found. In your <b>own Terminal</b> run:<br>'
      +'<code>read -rs \"k?Anthropic key: \" && printf %s \"$k\" &gt; ~/projects/Postgame_Outlet/data/.anthropic_key '
      +'&amp;&amp; chmod 600 ~/projects/Postgame_Outlet/data/.anthropic_key &amp;&amp; unset k</code><br>then reopen this chat.</div>';
  } else { help.style.display='none'; }
  dlg.showModal();
  document.getElementById('kb-input').focus();
}
async function kbSend(){
  const inp=document.getElementById('kb-input'); const q=inp.value.trim(); if(!q) return;
  inp.value=''; const sendBtn=document.getElementById('kb-send'); sendBtn.disabled=true;
  kbMsg('user', el('div',null,q));
  const thinking=kbMsg('assistant', el('div','note','thinking… (running queries)'));
  try{
    const j=await api('/api/kbchat',{question:q,history:KB_HISTORY});
    thinking.remove();
    if(!j.ok){ kbMsg('assistant', el('pre',null,'⚠ '+(j.message||'error'))); sendBtn.disabled=false; return; }
    const box=el('div');
    const ans=el('div'); ans.style.whiteSpace='pre-wrap'; ans.textContent=j.answer; box.appendChild(ans);
    if(j.steps && j.steps.length){
      const lbl=el('div','note',`${j.steps.length} quer${j.steps.length>1?'ies':'y'} run`); lbl.style.marginTop='8px';
      box.appendChild(lbl);
      j.steps.forEach(s=>box.appendChild(stepBlock(s)));
    }
    if(j.usage){ const u=el('div','note',`tokens: ${j.usage.input_tokens||'?'} in / ${j.usage.output_tokens||'?'} out`);
      u.style.marginTop='6px'; box.appendChild(u); }
    kbMsg('assistant', box);
    KB_HISTORY.push({role:'user',text:q}); KB_HISTORY.push({role:'assistant',text:j.answer});
  }catch(e){ thinking.remove(); kbMsg('assistant', el('pre',null,'⚠ '+e)); }
  sendBtn.disabled=false; inp.focus();
}
function weekRun(c,action,title){
  const r=el('div','row'); const wk=el('input','sm'); wk.placeholder='week';
  const yr=el('input','sm'); yr.placeholder='year';
  const b=el('button','go','Run'); b.onclick=()=>run({action,week:wk.value,year:yr.value},title);
  [wk,yr,b].forEach(x=>r.appendChild(x)); c.appendChild(r);
}

// ---- actions
async function api(path,body){
  const opt = body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {};
  const r = await fetch(path,opt); return r.json();
}
async function launch(tool,extra){
  showOut(tool+" server","launching…","",null);
  const j = await api('/api/launch',Object.assign({tool},extra||{}));
  if(j.ok){ window.open(j.url,'_blank'); showOut(tool+" server", j.url, (j.started?"started + ":"already up, ")+"opened in a new tab",0,{type:'text'}); }
  else showOut(tool+" server","",j.message||'failed',1,{type:'text'});
  refresh();
}
async function run(body,title){
  showOut(title,"running…","",null);
  const j = await api('/api/run',body);
  if(j.ok===false){ showOut(title,"",j.message||'error',1,{type:'text'}); return; }
  LAST = j; renderOut(title);
}
async function publishCheck(){
  showOut("Publish preflight","running tests…","",null);
  const j = await api('/api/publish',{step:'check'});
  LAST = j; renderOut("Publish preflight");
}

// ---- output panel (raw <-> rendered)
let LAST=null, VIEW='rendered';
function showOut(title,cmd,msg,rc,extra){
  document.getElementById('out').style.display='flex';
  document.getElementById('out-title').textContent=title;
  document.getElementById('out-cmd').textContent=cmd||'';
  const rcE=document.getElementById('out-rc');
  rcE.textContent = rc==null?'' : (rc===0?'✓ exit 0':'✗ exit '+rc);
  rcE.className = rc==null?'':(rc===0?'rc-ok':'rc-bad');
  const bd=document.getElementById('outbody'); bd.innerHTML='';
  const pre=el('pre'); pre.textContent = msg||''; bd.appendChild(pre);
}
function setView(v){ VIEW=v;
  document.getElementById('tg-rend').classList.toggle('sel',v==='rendered');
  document.getElementById('tg-raw').classList.toggle('sel',v==='raw');
  if(LAST) renderOut(document.getElementById('out-title').textContent);
}
function renderOut(title){
  const j=LAST; document.getElementById('out').style.display='flex';
  document.getElementById('out-title').textContent=title;
  document.getElementById('out-cmd').textContent=j.cmd||'';
  const rcE=document.getElementById('out-rc');
  rcE.textContent = j.rc==null?'':(j.rc===0?'✓ exit 0':'✗ exit '+j.rc);
  rcE.className = j.rc===0?'rc-ok':(j.rc==null?'':'rc-bad');
  const bd=document.getElementById('outbody'); bd.innerHTML='';
  if(VIEW==='rendered' && j.rendered && j.rendered.type==='ratings'){
    bd.appendChild(ratingsTable(j.rendered.rows));
  } else {
    const pre=el('pre');
    let txt = (j.stdout||''); if(j.stderr) txt += (txt?'\n':'')+'[stderr]\n'+j.stderr;
    pre.textContent = txt || '(no output)';
    bd.appendChild(pre);
    if(j.preview_path){ const b=el('button','go alt','Open preview file');
      b.onclick=()=>window.open('file://'+j.preview_path,'_blank'); b.style.marginTop='10px'; bd.appendChild(b);}
  }
}
function ratingsTable(rows){
  const t=el('table','r');
  t.innerHTML='<thead><tr><th class="l">#</th><th class="l">Team</th><th class="l">QB</th>'
    +'<th>qb</th><th>off</th><th>def</th><th>rating</th></tr></thead>';
  const tb=el('tbody');
  rows.forEach((r,i)=>{const tr=el('tr'); if(r.needs_review==='Y')tr.className='flag';
    tr.innerHTML=`<td class="l">${i+1}</td><td class="l">${r.team}</td><td class="l">${r.qb_name||''}</td>`
      +`<td>${r.qb.toFixed(1)}</td><td>${r.off.toFixed(1)}</td><td>${r.def.toFixed(1)}</td>`
      +`<td><b>${r.rating.toFixed(1)}</b>${r.needs_review==='Y'?' ⚠':''}</td>`;
    tb.appendChild(tr);});
  t.appendChild(tb); return t;
}

// ---- write-up editor dialog
function openWriteupEditor(j){
  const dlg=document.getElementById('dlg'); const b=document.getElementById('dlg-body'); b.innerHTML='';
  b.appendChild(el('h3',null,'Write-up — data/writeups/'+j.abbr+'.md'+(j.exists?'':' (new)')));
  const note=el('p','note','Manual save writes the file directly. For a drafted rewrite from your take, use Claude Code.');
  b.appendChild(note);
  const ta=el('textarea'); ta.value=j.content; ta.style.minHeight='240px'; b.appendChild(ta);
  const r=el('div','row'); r.style.marginTop='10px';
  const save=el('button','go','Save'); save.onclick=async()=>{
    const res=await api('/api/writeup',{abbr:j.abbr,content:ta.value});
    if(res.ok){ dlg.close(); showOut("Write-up saved",res.path,res.message,0,{type:'text'}); refresh(); }
    else alert(res.message||'save failed');
  };
  const cancel=el('button','go alt','Cancel'); cancel.onclick=()=>dlg.close();
  r.appendChild(save); r.appendChild(cancel); b.appendChild(r);
  dlg.showModal();
}

// ---- status bar
async function refresh(){
  let s; try{ s=await api('/api/status'); }catch(e){ return; }
  const br=document.getElementById('p-branch'); br.textContent='branch: '+s.branch;
  br.className='pill '+(s.branch==='testing'?'on':'warn');
  const gate=document.getElementById('p-gate');
  if(s.needs_review.count){ gate.textContent='gate: '+s.needs_review.count+' need review'; gate.className='pill bad'; }
  else { gate.textContent='gate: clear'; gate.className='pill on'; }
  const d=document.getElementById('p-dirty');
  d.textContent = s.dirty?'data: uncommitted':'data: clean'; d.className='pill '+(s.dirty?'warn':'off');
  for(const k of ['pick','team','injury','guru']){
    const e=document.getElementById('s-'+k); const up=s.servers[k];
    e.textContent=k+(up?' ●':' ○'); e.className='pill '+(up?'on':'off'); e.title=up?'running':'stopped';
  }
}
buildCards(); refresh(); setInterval(refresh, 8000);
</script></body></html>"""


# ---------------------------------------------------------------- server
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def _json_body(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/healthz":
            return self._send(200, "ok", "text/plain")
        if u.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/api/status":
            try:
                return self._send(200, json.dumps(_status()))
            except Exception as e:  # noqa: BLE001
                return self._send(502, json.dumps({"error": str(e)}))
        if u.path == "/api/writeup":
            return self._send(200, json.dumps(act_writeup_get((q.get("abbr") or [""])[0])))
        if u.path == "/api/kbstatus":
            return self._send(200, json.dumps(act_kbstatus()))
        if u.path == "/api/trends":
            return self._send(200, json.dumps(act_trends_catalog()))
        return self._send(404, "not found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        body = self._json_body()
        try:
            if u.path == "/api/launch":
                return self._send(200, json.dumps(act_launch(body)))
            if u.path == "/api/run":
                return self._send(200, json.dumps(act_run(body)))
            if u.path == "/api/publish":
                return self._send(200, json.dumps(act_publish_check(body)))
            if u.path == "/api/writeup":
                return self._send(200, json.dumps(act_writeup_save(body)))
            if u.path == "/api/kbchat":
                return self._send(200, json.dumps(act_kbchat(body)))
        except Exception as e:  # noqa: BLE001
            return self._send(500, json.dumps({"ok": False, "message": str(e)}))
        return self._send(404, "not found", "text/plain")


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Power Ratings Hub live at {url}  (Ctrl-C to stop)")
    if "--no-open" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
