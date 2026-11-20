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
import re
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

try:
    import team_view as TV  # abbr <-> full team-name resolution (Lane-2 core file)
except Exception:  # noqa: BLE001
    TV = None

try:
    import snapshot as SNAP_MOD  # freeze/read historical board snapshots
except Exception:  # noqa: BLE001
    SNAP_MOD = None

try:
    import market_ratings as MKT  # market-implied ratings (Market vs Mine view)
except Exception:  # noqa: BLE001
    MKT = None

try:
    import picks as PICKS  # weekly slate: market line, my line, edge (same as pick sheet)
except Exception:  # noqa: BLE001
    PICKS = None

# Static, offline abbr map for the compact board/slate views.
TEAM_ABBR = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}

HOST = "127.0.0.1"
PORT = 8786
REPO = os.path.dirname(os.path.abspath(__file__))
RATINGS = os.path.join(REPO, "data", "ratings.csv")
SNAPSHOTS = os.path.join(REPO, "data", "snapshots.json")
QB_DEPTH = os.path.join(REPO, "data", "qb_depth.csv")
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
    "game": ("game_server.py", 8792),
    "props": ("prop_server.py", 8793),
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


# ---------------------------------------------------------------- QB board
def _string_num(s):
    """Leading integer of a qb_depth 'string' cell ('2','3'…); high if blank."""
    m = re.match(r"\s*(\d+)", s or "")
    return int(m.group(1)) if m else 99


def _qb_depth_by_team():
    """Backups per team from qb_depth.csv, ordered by depth-chart string (QB2,
    QB3, …), then by value within a string."""
    depth = {}
    try:
        with open(QB_DEPTH, newline="") as f:
            for r in csv.DictReader(f):
                t = r.get("team", "")
                try:
                    v = float(r.get("value") or 0)
                except ValueError:
                    v = 0.0
                depth.setdefault(t, []).append({
                    "name": r.get("qb_name", ""), "v": v,
                    "string": (r.get("string") or "").strip(),
                    "notes": r.get("notes", ""),
                })
    except OSError:
        pass
    for t in depth:
        depth[t].sort(key=lambda x: (_string_num(x["string"]), -x["v"]))
    return depth


def act_qb_board():
    """32 teams ranked by their ACTIVE STARTER's QB rating, with the backup
    (QB2) and third-string (QB3) + values alongside."""
    depth = _qb_depth_by_team()
    board = []
    for r in _read_ratings():
        d = depth.get(r["team"], [])
        board.append({
            "team": r["team"],
            "starter": {"name": r["qb_name"], "v": r["qb"],
                        "review": r["needs_review"] == "Y"},
            "backup": d[0] if len(d) > 0 else None,
            "third": d[1] if len(d) > 1 else None,
        })
    board.sort(key=lambda x: x["starter"]["v"], reverse=True)
    for i, b in enumerate(board, 1):
        b["rank"] = i
    return {"ok": True, "board": board}


def act_qb_history():
    """Starter QB rating per team across saved snapshots (Preseason, Week N…)
    plus the live 'Current' column — for the week-to-week view. Teams ordered
    by current starter rating."""
    labels, per_team = [], {}
    for label, value in _load_snaps().items():
        e = _norm_snap(value)
        labels.append(label)
        for row in e["rows"]:
            per_team.setdefault(row.get("team", ""), {})[label] = {
                "name": row.get("qb_name", ""), "v": row.get("qb")}
    cur_rows = _read_ratings()
    cur = {r["team"]: r["qb"] for r in cur_rows}
    for r in cur_rows:
        per_team.setdefault(r["team"], {})["Current"] = {"name": r["qb_name"], "v": r["qb"]}
    labels.append("Current")
    teams = sorted(per_team.keys(), key=lambda t: cur.get(t, -99), reverse=True)
    out = [{"team": t, "current_qb": next((r["qb_name"] for r in cur_rows if r["team"] == t), ""),
            "cells": [per_team[t].get(l) for l in labels]} for t in teams]
    return {"ok": True, "labels": labels, "teams": out}


_MARKET_CACHE = {"at": 0.0, "key": None, "data": None}
MARKET_TTL = 600  # seconds — ESPN lines + one git lookup per older game


def act_market(week=None, year=None, refresh=False):
    """Market-implied ratings vs Sean's (market_ratings.fit), cached ~10 min.
    Read-only; works while rows are needs_review=Y (flags draft)."""
    import time
    if MKT is None:
        return {"ok": False, "message": "market_ratings.py not available on this branch"}
    try:
        if not week or not year:
            dw, dy = MKT._default_week_year()
            week, year = int(week or dw), int(year or dy)
        # ratings.csv mtime in the key so an edit shows up without waiting out the TTL
        key = (int(week), int(year), os.path.getmtime(RATINGS))
        now = time.time()
        c = _MARKET_CACHE
        if refresh or c["key"] != key or now - c["at"] > MARKET_TTL or c["data"] is None:
            c["data"] = MKT.fit(int(year), int(week))
            c["key"], c["at"] = key, now
        return {"ok": True, **c["data"]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)}


_SLATE_CACHE = {"at": 0.0, "data": None}
SLATE_TTL = 120  # seconds — one ESPN scoreboard call per refresh window


def act_slate(refresh=False):
    """Upcoming week's games with market line, my line and edge — the exact numbers
    the pick sheet shows (picks.build_sheet), trimmed for the hub's week board."""
    import time
    if PICKS is None:
        return {"ok": False, "message": "picks.py unavailable"}
    now = time.time()
    if not refresh and _SLATE_CACHE["data"] and now - _SLATE_CACHE["at"] < SLATE_TTL:
        return _SLATE_CACHE["data"]
    try:
        s = PICKS.build_sheet()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"could not load the slate: {e}"}
    games = []
    for g in s.get("games", []):
        games.append({
            "game_id": g["game_id"], "kickoff": g["kickoff"], "locked": g["locked"],
            "final": g["final"], "neutral": g["neutral"],
            "away": g["away"], "home": g["home"],
            "away_abbr": TEAM_ABBR.get(g["away"], g["away"][:3].upper()),
            "home_abbr": TEAM_ABBR.get(g["home"], g["home"][:3].upper()),
            "away_score": g["away_score"], "home_score": g["home_score"],
            "market": g["market"], "my_spread": g["my_spread"], "edge": g["edge"],
            "pick_side": g["pick_side"], "pick_confidence": g["pick_confidence"],
        })
    data = {"ok": True, "season": s.get("season"), "week": s.get("week"),
            "picked_count": s.get("picked_count", 0), "max_picks": s.get("max_picks", 5),
            "games": games, "generated": s.get("generated")}
    _SLATE_CACHE.update(at=now, data=data)
    return data


def act_board():
    rows = _read_ratings()
    for r in rows:
        r["abbr"] = TEAM_ABBR.get(r["team"], "")
    return {"ok": True, "rows": rows}


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
        if body.get("full"):
            argv.append("--full")
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
    if action == "pff":
        season = str(body.get("year") or "2026").strip()
        week = str(body.get("week") or "1").strip()
        if not week.isdigit():
            return {"ok": False, "message": "enter a week number"}
        argv = ["python3", "pff.py", "report", season, week]
        game = (body.get("game") or "").strip()
        if game:
            argv += ["--game", game]
        if body.get("full"):
            argv.append("--full")
        res = _sh(argv, timeout=120)
        res["ok"] = True
        if res.get("rc") and "No PFF cache" in (res.get("stdout", "") + res.get("stderr", "")):
            res["stdout"] = (res.get("stdout", "") + "\n\nNo cache yet — PFF data is pulled via "
                             "the browser session in Claude Code (tell it: \"fetch PFF week N\").")
        return res
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


# ---------------------------------------------------------------- snapshots (history)
def _load_snaps():
    try:
        with open(SNAPSHOTS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _norm_snap(value):
    """Accept the legacy bare-list form and the current object form."""
    if isinstance(value, list):
        return {"published_at": "", "rows": value, "corrections": []}
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        return {"published_at": value.get("published_at", ""), "rows": value["rows"],
                "corrections": list(value.get("corrections", []))}
    return {"published_at": "", "rows": [], "corrections": []}


def act_snapshots_list():
    """Every saved snapshot with its date + team count (newest last, as stored)."""
    out = []
    for label, value in _load_snaps().items():
        e = _norm_snap(value)
        out.append({"label": label, "published_at": e["published_at"],
                    "teams": len(e["rows"]), "corrections": len(e["corrections"])})
    return {"ok": True, "snapshots": out}


def act_snapshot_get(label):
    """One snapshot's full board, sorted best→worst, with current rating + delta."""
    snaps = _load_snaps()
    if label not in snaps:
        return {"ok": False, "message": f"no snapshot named '{label}'"}
    e = _norm_snap(snaps[label])
    cur = {r["team"]: r["rating"] for r in _read_ratings()}
    rows = []
    for r in sorted(e["rows"], key=lambda x: x.get("rating", 0), reverse=True):
        team = r.get("team", "")
        now = cur.get(team)
        rows.append({
            "team": team, "qb_name": r.get("qb_name", ""),
            "qb": r.get("qb", 0), "off": r.get("off", 0), "def": r.get("def", 0),
            "rating": r.get("rating", 0),
            "current": now,
            "delta": (round(now - r.get("rating", 0), 1) if now is not None else None),
        })
    return {"ok": True, "label": label, "published_at": e["published_at"],
            "rows": rows, "corrections": e["corrections"]}


def act_snapshot_create(body):
    """Freeze the CURRENT ratings under an immutable label (via snapshot.py).
    Writes data/snapshots.json locally — it does NOT publish; that stays a
    separate explicit step."""
    label = (body.get("label") or "").strip()
    if not label:
        return {"ok": False, "message": "a label is required (e.g. 'Week 2 2026')"}
    if SNAP_MOD is None:
        return {"ok": False, "message": "snapshot module unavailable (are you on the testing branch?)"}
    snaps = SNAP_MOD.load_snaps()
    if label in snaps:
        return {"ok": False, "message": f"'{label}' already exists — snapshots are immutable"}
    try:
        SNAP_MOD.add_snapshot(snaps, label, SNAP_MOD.snapshot_current())
        SNAP_MOD.save_snaps(snaps)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)}
    n = len(snaps[label]["rows"])
    return {"ok": True, "label": label, "teams": n,
            "message": f"saved snapshot '{label}' ({n} teams). Local only — not published."}


# ---------------------------------------------------------------- team editor
def _resolve_team(q):
    """Map an abbr or name to (full_team_name, abbr). Returns (None, None) if unresolved."""
    q = (q or "").strip()
    if not q or TV is None:
        return (None, None)
    name = TV.resolve_team(q)
    idx = TV.espn_team_index()
    if not name:
        ql = q.lower()
        name = next((tn for tn, m in idx.items() if (m.get("abbr") or "").lower() == ql), None)
    if not name:
        return (None, None)
    return (name, (idx.get(name) or {}).get("abbr"))


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return 0.0
    return xs[n // 2] if n % 2 else round((xs[n // 2 - 1] + xs[n // 2]) / 2, 2)


def _league_context():
    """Per-component min/median/max across the 32 teams — honest, data-grounded
    reference (there is no method.md band file to load)."""
    rows = _read_ratings()
    out = {}
    for k in ("qb", "off", "def", "rating"):
        vals = [r[k] for r in rows]
        out[k] = {"min": min(vals), "med": _median(vals), "max": max(vals)}
    return out


def act_team_get(q):
    """Everything the merged editor needs for one team: current rating components,
    the write-up markdown, and league context."""
    name, abbr = _resolve_team(q)
    if not name:
        return {"ok": False, "message": f"could not resolve team '{q}'"}
    row = None
    with open(RATINGS, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("team") == name:
                row = r
                break
    if row is None:
        return {"ok": False, "message": f"'{name}' not found in ratings.csv"}
    wu = act_writeup_get(abbr) if abbr else {"content": "", "exists": False}

    def fnum(v):
        try:
            return float(v or 0)
        except ValueError:
            return 0.0
    qb, off, dfn = fnum(row.get("qb_value")), fnum(row.get("off_value")), fnum(row.get("def_value"))
    return {
        "ok": True, "team": name, "abbr": abbr,
        "qb_name": row.get("qb_name", ""),
        "qb": qb, "off": off, "def": dfn, "rating": round(qb + off + dfn, 2),
        "needs_review": (row.get("needs_review") or "").strip().upper(),
        "notes": row.get("notes", ""),
        "writeup": wu.get("content", ""), "writeup_exists": wu.get("exists", False),
        "league": _league_context(),
    }


def act_rating_save(body):
    """Direct, GATED rating edit: writes qb/off/def to ratings.csv, forces
    needs_review=Y (can't publish until cleared), and requires a reason -> notes.
    Preserves column order + minimal quoting."""
    name, abbr = _resolve_team(body.get("team") or body.get("abbr") or "")
    if not name:
        return {"ok": False, "message": "team required / unresolved"}
    reason = (body.get("reason") or "").strip()
    if not reason:
        return {"ok": False, "message": "a one-line reason is required (it becomes the notes)"}
    vals = {}
    for k, col in (("qb", "qb_value"), ("off", "off_value"), ("def", "def_value")):
        try:
            vals[col] = f"{float(body.get(k)):g}"
        except (TypeError, ValueError):
            return {"ok": False, "message": f"{k} must be a number"}

    with open(RATINGS, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    hit = next((r for r in rows if r.get("team") == name), None)
    if hit is None:
        return {"ok": False, "message": f"'{name}' not found in ratings.csv"}
    old = f"QB {hit.get('qb_value')} / Off {hit.get('off_value')} / Def {hit.get('def_value')}"
    hit.update(vals)
    hit["needs_review"] = "Y"
    hit["notes"] = reason
    with open(RATINGS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)
    total = round(sum(float(vals[c]) for c in ("qb_value", "off_value", "def_value")), 2)
    return {"ok": True, "team": name, "abbr": abbr, "total": total,
            "old": old, "new": f"QB {vals['qb_value']} / Off {vals['off_value']} / Def {vals['def_value']}",
            "message": f"{name}: {old} -> new total {total}. needs_review=Y (won't publish until you clear it; "
                       f"tell Claude Code to finalize after review)."}


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
PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Power Ratings Hub</title>
<style>
 :root{--bg:#07090d;--s1:#0d1117;--s2:#131921;--s3:#1a222d;--line:#1d2632;--line2:#2a3545;
   --ink:#e9eef4;--dim:#8794a5;--faint:#566274;
   --acc:#2fd27a;--acc-ink:#03140a;--acc-soft:rgba(47,210,122,.12);--acc-line:rgba(47,210,122,.35);
   --neg:#ff5c6c;--neg-soft:rgba(255,92,108,.12);--warn:#f5b84a;--warn-soft:rgba(245,184,74,.12);
   --good:var(--acc);--bad:var(--neg);--card:var(--s2);--accent:var(--acc);
   --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
   --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
   color-scheme:dark}
 *{box-sizing:border-box}
 [hidden]{display:none!important}
 html,body{margin:0;background:var(--bg);color:var(--ink)}
 body{font:14px/1.45 var(--sans);-webkit-font-smoothing:antialiased;min-height:100vh}
 button{font:inherit;color:inherit}
 .num,td.n{font-family:var(--mono);font-variant-numeric:tabular-nums}

 /* header */
 .top{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:14px;flex-wrap:wrap;
   padding:12px 24px;background:rgba(7,9,13,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
 .brand{display:flex;align-items:center;gap:10px}
 .logo{width:32px;height:32px;border-radius:8px;background:var(--acc);color:var(--acc-ink);display:grid;place-items:center;
   font:800 13px/1 var(--sans);letter-spacing:-.02em}
 .bt{font-weight:700;font-size:15px;letter-spacing:-.01em}
 .bs{font-size:11.5px;color:var(--dim)}
 .hstat{margin-left:auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
 .chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;padding:4px 10px;border-radius:999px;
   border:1px solid var(--line2);color:var(--dim);background:var(--s1);white-space:nowrap}
 .chip::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--faint)}
 .chip.plain::before{display:none}
 .chip.ok{color:var(--acc);border-color:var(--acc-line);background:var(--acc-soft)} .chip.ok::before{background:var(--acc)}
 .chip.warn{color:var(--warn);border-color:rgba(245,184,74,.35);background:var(--warn-soft)} .chip.warn::before{background:var(--warn)}
 .chip.bad{color:var(--neg);border-color:rgba(255,92,108,.35);background:var(--neg-soft)} .chip.bad::before{background:var(--neg)}
 .icon{width:32px;height:32px;border-radius:8px;border:1px solid var(--line2);background:var(--s1);cursor:pointer;color:var(--dim)}
 .icon:hover{color:var(--ink);border-color:var(--faint)}

 /* layout */
 .wrap{max-width:1280px;margin:0 auto;padding:20px 24px 120px;display:flex;flex-direction:column;gap:18px}
 .cols{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:18px;align-items:start}
 .side{display:flex;flex-direction:column;gap:18px;min-width:0}
 @media(max-width:1180px){.cols{grid-template-columns:minmax(0,1fr)}
   .side{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));align-items:start}}
 .panel{background:var(--s1);border:1px solid var(--line);border-radius:14px;min-width:0;overflow:hidden}
 .ph{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:16px 18px 12px}
 .ph h2{margin:0;font-size:16px;font-weight:700;letter-spacing:-.01em}
 .sub{font-size:12px;color:var(--dim);margin-top:2px}
 .pa{display:flex;gap:8px;align-items:center;flex-wrap:wrap}

 /* buttons */
 .btn,.go{display:inline-flex;align-items:center;gap:6px;padding:7px 12px;border-radius:8px;cursor:pointer;
   font-size:13px;font-weight:600;border:1px solid var(--line2);background:var(--s2);color:var(--ink);white-space:nowrap}
 .btn:hover,.go:hover{border-color:var(--faint);background:var(--s3)}
 .btn.pri{background:var(--acc);border-color:var(--acc);color:var(--acc-ink)}
 .btn.pri:hover{filter:brightness(1.08);background:var(--acc)}
 .livebtn{text-decoration:none} .ldot{width:8px;height:8px;border-radius:50%;background:var(--acc-ink);opacity:.45}
 .ldot.on{opacity:1;animation:lpl 1.6s infinite}
 @keyframes lpl{0%{box-shadow:0 0 0 0 rgba(3,20,10,.55)}70%{box-shadow:0 0 0 6px rgba(3,20,10,0)}100%{box-shadow:0 0 0 0 rgba(3,20,10,0)}}

 .go{color:var(--acc);border-color:var(--acc-line);background:var(--acc-soft)}
 .go:hover{background:rgba(47,210,122,.2);border-color:var(--acc)}
 .go.alt{color:var(--ink);border-color:var(--line2);background:var(--s2)}
 .go:disabled,.btn:disabled{opacity:.5;cursor:not-allowed}
 .close{cursor:pointer;color:var(--dim);border:1px solid var(--line2);border-radius:8px;padding:5px 10px;background:var(--s2);font-size:12.5px}
 .close:hover{color:var(--ink)}
 .tgl{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;color:var(--dim);cursor:pointer;user-select:none}
 .tgl input{accent-color:var(--acc)}
 input,textarea,select{background:var(--bg);border:1px solid var(--line2);color:var(--ink);border-radius:8px;
   padding:7px 10px;font-size:13px;font-family:inherit;min-width:0}
 input:focus,textarea:focus{outline:none;border-color:var(--acc)}
 input.sm{width:70px} textarea{width:100%;min-height:110px;font-family:var(--mono);font-size:12.5px}
 .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 .note{font-size:12px;color:var(--dim)}
 .subhd{margin:14px 0 6px;font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--faint)}
 .subhd:first-of-type{margin-top:4px}
 .trendgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;width:100%}
 .trendgrid button{width:100%;justify-content:center}
 .kbtools{display:flex;gap:8px;flex-wrap:wrap}

 /* tables */
 .tbl-wrap{overflow-x:auto;border-top:1px solid var(--line)}
 .tbl-wrap.tall{max-height:760px;overflow-y:auto}
 table.slate,table.board{width:100%;border-collapse:collapse}
 .slate th,.board th{position:sticky;top:0;background:var(--s1);z-index:1;padding:9px 12px;font-size:10.5px;font-weight:700;
   text-transform:uppercase;letter-spacing:.07em;color:var(--faint);text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
 .slate td,.board td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
 .slate th.l,.slate td.l,.board th.l,.board td.l{text-align:left}
 .slate tbody tr:last-child td,.board tbody tr:last-child td{border-bottom:0}
 .slate tbody tr:hover,.board tbody tr:hover{background:var(--s2)}
 .slate .when{color:var(--dim);font-size:12px}
 .slate .when b{color:var(--ink);font-weight:600}
 .mu{display:flex;align-items:center;gap:8px;font-weight:700;letter-spacing:.01em}
 .mu .at{color:var(--faint);font-weight:400}
 .mu .lean{color:var(--acc)}
 .line{font-family:var(--mono);font-variant-numeric:tabular-nums;font-size:13px}
 .line .t{color:var(--dim);margin-right:5px;font-family:var(--sans);font-size:12px;font-weight:600}
 .edge{display:inline-flex;align-items:center;gap:6px;justify-content:flex-end;min-width:86px;padding:4px 9px;border-radius:7px;
   font-family:var(--mono);font-size:13px;font-weight:700;color:var(--dim)}
 .edge .t{font-family:var(--sans);font-size:11.5px;font-weight:700}
 .edge.hot{background:var(--acc-soft);color:var(--acc);box-shadow:inset 0 0 0 1px var(--acc-line)}
 .edge.none{font-weight:400;color:var(--faint)}
 .pk{display:inline-flex;gap:5px;align-items:center;font-size:12px;font-weight:700;color:var(--warn)}
 .res-w{color:var(--acc)} .res-l{color:var(--neg)}
 .empty{padding:22px 18px;color:var(--dim);font-size:13px}
 .board tbody tr{cursor:pointer}
 .board .rk{color:var(--faint);font-family:var(--mono);width:30px}
 .tm{display:flex;flex-direction:column;line-height:1.2}
 .tm b{font-size:13.5px} .tm span{font-size:11.5px;color:var(--dim)}
 .board .qbn{color:var(--dim);font-size:12.5px}
 .pos{color:var(--acc)} .neg{color:var(--neg)} .zero{color:var(--dim)}
 .tot{display:flex;align-items:center;justify-content:flex-end;gap:10px}
 .tot .v{font-family:var(--mono);font-weight:700;font-size:14px;min-width:44px;text-align:right}
 .bar{position:relative;width:92px;height:6px;border-radius:3px;background:var(--s3)}
 .bar::after{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--line2)}
 .bar i{position:absolute;top:0;bottom:0;border-radius:3px}
 .bar i.p{left:50%;background:var(--acc)} .bar i.m{right:50%;background:var(--neg)}
 .flagd{color:var(--warn);margin-left:4px}
 @media(max-width:640px){
   .hide-sm{display:none}
   .top{padding:10px 16px} .wrap{padding:14px 16px 120px}
   .slate td,.board td,.slate th,.board th{padding:9px 6px}
   .slate td:first-child,.board td:first-child,.slate th:first-child,.board th:first-child{padding-left:14px}
   .slate td:last-child,.board td:last-child,.slate th:last-child,.board th:last-child{padding-right:14px}
   .mu{gap:5px} .line{font-size:12.5px} .line .t{margin-right:3px;font-size:11px}
   .edge{min-width:0;padding:3px 7px;gap:4px;font-size:12.5px}
   .bar{display:none}
   .ph .pa{width:100%;justify-content:space-between}
 }

 /* side panels */
 .tiles{display:grid;gap:10px;padding:0 18px 18px}
 .tile{text-align:left;display:flex;flex-direction:column;gap:3px;padding:13px 14px;border-radius:10px;cursor:pointer;
   background:var(--s2);border:1px solid var(--line)}
 .tile:hover{border-color:var(--acc-line);background:var(--s3)}
 .tile .tt{font-weight:700;font-size:14px;display:flex;justify-content:space-between}
 .tile .tt::after{content:"→";color:var(--acc)}
 .tile .td{font-size:12px;color:var(--dim)}
 .trends{display:flex;flex-direction:column;padding:0 10px 6px}
 .trend{display:flex;align-items:center;gap:12px;width:100%;text-align:left;padding:10px 8px;border:0;border-bottom:1px solid var(--line);
   background:none;cursor:pointer;border-radius:0}
 .trend:last-child{border-bottom:0}
 .trend:hover{background:var(--s2);border-radius:8px}
 .trend .tx{flex:1;min-width:0}
 .trend .tl{font-weight:600;font-size:13.5px}
 .trend .tdsc{font-size:12px;color:var(--dim);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .trend .go-arrow{color:var(--faint);font-size:13px}
 .trend:hover .go-arrow{color:var(--acc)}
 details.sql{border-top:1px solid var(--line);padding:12px 18px 16px}
 details.sql summary{cursor:pointer;color:var(--dim);font-size:12.5px;font-weight:600}
 details.sql textarea{margin:10px 0 8px}

 /* more tools */
 details.more{background:var(--s1);border:1px solid var(--line);border-radius:14px}
 details.more>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:12px;padding:14px 18px;flex-wrap:wrap}
 details.more>summary::-webkit-details-marker{display:none}
 details.more>summary>span:first-child{font-weight:700;font-size:15px}
 details.more>summary::before{content:"+";width:22px;height:22px;border-radius:6px;display:grid;place-items:center;
   background:var(--s3);color:var(--dim);font-weight:700}
 details.more[open]>summary::before{content:"–"}
 .mgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr));gap:12px;padding:0 18px 18px}
 .mcard{background:var(--s2);border:1px solid var(--line);border-radius:11px;padding:14px 15px;display:flex;flex-direction:column;gap:8px;min-width:0}
 .mcard h3{margin:0;font-size:14px}
 .mcard>p{margin:0;font-size:12px;color:var(--dim)}

 /* output drawer */
 #out{position:fixed;left:0;right:0;bottom:0;z-index:30;background:var(--s1);border-top:1px solid var(--line2);
   box-shadow:0 -12px 40px rgba(0,0,0,.5);max-height:52vh;flex-direction:column}
 #outhead{padding:10px 18px;display:flex;gap:12px;align-items:center;border-bottom:1px solid var(--line);flex-wrap:wrap}
 #outhead .title{font-weight:700}
 #outhead .cmd{color:var(--faint);font-size:12px;font-family:var(--mono);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:40ch}
 .toggle{margin-left:auto;display:inline-flex;border:1px solid var(--line2);border-radius:8px;overflow:hidden}
 .toggle button{background:var(--s2);border:0;color:var(--dim);padding:5px 12px;cursor:pointer;font-size:12.5px}
 .toggle button.sel,.toggle button.act{background:var(--s3);color:var(--ink)}
 #outbody{overflow:auto;padding:14px 18px}
 pre{margin:0;white-space:pre-wrap;word-break:break-word;font:12.5px/1.55 var(--mono);color:#c9d4df}
 .rc-ok{color:var(--acc);font-size:12px} .rc-bad{color:var(--neg);font-size:12px}

 /* tables used inside dialogs / output */
 table.r{border-collapse:collapse;width:100%}
 table.r th,table.r td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
 table.r th:first-child,table.r td:first-child,table.r th.l,table.r td.l{text-align:left}
 table.r th{color:var(--faint);font-size:10.5px;text-transform:uppercase;letter-spacing:.07em}
 tr.flag td{background:var(--warn-soft)}
 .qbwrap{overflow:auto;max-height:66vh}
 .qbt{width:100%;border-collapse:collapse;font-size:12.5px}
 .qbt th,.qbt td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
 .qbt th{color:var(--faint);font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;position:sticky;top:0;background:var(--s1);z-index:1}
 .qbt td.rk{color:var(--faint);text-align:right;width:26px}
 .qbt td.num{text-align:right;font-family:var(--mono)}
 .qbt .dim{color:var(--dim)}
 .qbt tbody tr:hover{background:var(--s2)}
 .pill{display:inline-block;font-size:11.5px;padding:2px 9px;border-radius:999px;border:1px solid var(--line2);color:var(--dim)}
 .pill.warn{color:var(--warn);border-color:rgba(245,184,74,.35);background:var(--warn-soft)}

 /* dialogs */
 dialog{background:var(--s1);color:var(--ink);border:1px solid var(--line2);border-radius:14px;padding:20px;max-width:560px;width:94%;
   box-shadow:0 30px 80px rgba(0,0,0,.6)}
 dialog.wide{max-width:1040px}
 dialog::backdrop{background:rgba(2,4,8,.72)}
 dialog h3{margin:0 0 6px;font-size:17px}
 .wu-split{display:grid;grid-template-columns:1fr 1fr;gap:12px}
 @media(max-width:720px){.wu-split{grid-template-columns:1fr}}
 .wu-pane{display:flex;flex-direction:column;min-width:0}
 .wu-hd{font-size:10.5px;text-transform:uppercase;letter-spacing:.07em;color:var(--faint);font-weight:700;margin-bottom:6px}
 .wu-ta{width:100%;min-height:360px;resize:vertical;background:var(--bg);color:#c9d4df;border:1px solid var(--line2);
   border-radius:8px;padding:10px;font:12.5px/1.55 var(--mono)}
 .wu-prev{min-height:360px;max-height:60vh;overflow:auto;background:var(--bg);border:1px solid var(--line2);border-radius:8px;padding:12px 14px}
 .wu-prev h2{font-size:17px;margin:.2em 0 .3em} .wu-prev h3{font-size:15px;margin:.6em 0 .3em}
 .wu-prev h4{font-size:13px;margin:.6em 0 .2em;color:var(--dim)}
 .wu-prev p{margin:.4em 0} .wu-prev ul{margin:.3em 0 .5em;padding-left:1.2em} .wu-prev li{margin:.15em 0}
 .wu-prev .empty{color:var(--dim);font-style:italic;padding:0}
 .te-sec{border:1px solid var(--line);border-radius:10px;padding:14px;background:var(--s2)}
 .te-nums{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
 @media(max-width:640px){.te-nums{grid-template-columns:1fr}}
 .te-cell{display:flex;flex-direction:column;gap:3px}
 .te-cell label{font-size:11px;color:var(--dim)}
 .te-num{background:var(--bg);color:var(--ink);border:1px solid var(--line2);border-radius:8px;padding:8px 10px;font:15px var(--mono)}
 .te-ctx{font-size:10.5px;color:var(--faint)}
 .te-tot{margin-top:8px} .te-totv{font-weight:700;font-size:15px}
</style></head><body>
<header class="top">
  <div class="brand"><span class="logo">PR</span>
    <div><div class="bt">Power Ratings</div><div class="bs">McCabe Method</div></div></div>
  <div class="hstat">
    <span class="chip plain" id="p-week">Week —</span>
    <span class="chip" id="p-gate">gate…</span>
    <span class="chip warn" id="p-dirty" hidden>uncommitted data</span>
    <span class="chip warn" id="p-branch" hidden></span>
    <a class="btn pri livebtn" href="/suggestions" id="p-live" title="Live board: every suggested bet, scored live"><span class="ldot" id="p-ldot"></span><span id="p-ltxt">Live bets</span></a>
    <button class="icon" onclick="reloadAll(true)" title="Refresh lines and ratings" aria-label="Refresh">↻</button>
  </div>
</header>

<main class="wrap">
  <section class="panel">
    <div class="ph">
      <div><h2 id="sl-title">This week</h2><div class="sub" id="sl-sub">loading lines…</div></div>
      <div class="pa">
        <label class="tgl"><input type="checkbox" id="sl-edges" onchange="renderSlate()"> Edges ≥ 1.5 only</label>
        <button class="btn pri" onclick="launch('pick')">Open pick sheet →</button>
      </div>
    </div>
    <div class="tbl-wrap"><table class="slate" id="sl-tbl"></table></div>
  </section>

  <div class="cols">
    <section class="panel">
      <div class="ph">
        <div><h2>Power ratings</h2><div class="sub" id="rt-sub">QB + Off + Def · click a team to edit</div></div>
        <div class="pa">
          <button class="btn" onclick="openQbBoard()">QB rankings</button>
          <button class="btn" onclick="openEditions()">Editions</button>
        </div>
      </div>
      <div class="tbl-wrap tall"><table class="board" id="rt-tbl"></table></div>
    </section>

    <div class="side">
      <section class="panel">
        <div class="ph">
          <div><h2>Suggestions tracker</h2><div class="sub" id="sg-sub">every bet Claude suggested, graded</div></div>
          <div class="pa"><a class="btn pri livebtn" href="/suggestions">Live board &amp; tracker →</a></div>
        </div>
        <div class="tiles"><button class="tile" onclick="window.open('/suggestions','_blank')"><span class="tt" id="sg-rec">loading…</span>
          <span class="td" id="sg-det"></span></button></div>
      </section>

      <section class="panel">
        <div class="ph"><div><h2>Market</h2><div class="sub">where the market disagrees with you</div></div></div>
        <div class="tiles">
          <button class="tile" onclick="openMarketBoard()"><span class="tt">Market vs Mine</span>
            <span class="td">Market-implied rating for every team next to yours, with the gap</span></button>
          <button class="tile" onclick="launch('props')"><span class="tt">Prop Board</span>
            <span class="td">Check prop claims and compare Kalshi, Polymarket, DK and FD prices</span></button>
        </div>
      </section>

      <section class="panel">
        <div class="ph">
          <div><h2>Trends</h2><div class="sub" id="trend-label">from the knowledge base</div></div>
          <div class="pa"><button class="btn" onclick="launch('guru')">Open guru</button></div>
        </div>
        <div class="trends" id="trend-btns"><div class="empty">loading…</div></div>
        <details class="sql"><summary>Raw SQL</summary>
          <textarea id="kb-sql" placeholder="SELECT … (blank = show schema)"></textarea>
          <div class="row">
            <button class="btn pri" onclick="run({action:'kb',sql:document.getElementById('kb-sql').value},'KB query')">Run query</button>
            <button class="btn" onclick="openKbChat()">Chat (needs API key)</button>
          </div>
        </details>
      </section>
    </div>
  </div>

  <details class="more">
    <summary><span>More tools</span><span class="sub">ratings editor · game analysis · injuries &amp; depth · publish</span></summary>
    <div class="mgrid" id="more-grid"></div>
  </details>
</main>

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
const MORE = [
 {t:"Update ratings & write-up", d:"Edit QB/Off/Def (gated save) and the write-up with live preview. Or click any team on the board.",
   render:c=>teamEditorCard(c)},
 {t:"Game analysis", d:"Scores and graded picks, visual game reports, PFF player grades.",
   render:c=>{ sub(c,'Results & grading'); weekRun(c,'results',"Results & grading");
     sub(c,'Game reports'); btn(c,"Open game reports",()=>launch('game'));
     sub(c,'PFF player stats (local cache)'); pffCard(c); }},
 {t:"Injuries & depth", d:"Rating-relevant injuries (Sleeper) and depth-chart order (Ourlads).",
   render:c=>{ sub(c,'Injury report'); injuryCard(c); sub(c,'Depth charts'); depthCard(c); }},
 {t:"Publish center", d:"Preview, see what changed, run the gate. To go live, say “publish” to Claude Code.",
   render:c=>{ const r=el('div','row');
     const a=el('button','go','Build preview'); a.onclick=()=>run({action:'preview'},"Local preview");
     const b=el('button','go alt','What changed'); b.onclick=()=>run({action:'whatchanged'},"What changed");
     const p=el('button','go alt','Run preflight'); p.onclick=()=>publishCheck();
     [a,b,p].forEach(x=>r.appendChild(x)); c.appendChild(r); }},
];
function el(t,cls,txt){const e=document.createElement(t);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e;}
function btn(c,label,fn,cls){const b=el('button',(cls?'go '+cls:'go'),label);b.onclick=fn;
  const r=el('div','row');r.appendChild(b);c.appendChild(r);return b;}
function sub(c,label){const s=el('div','subhd',label);c.appendChild(s);return s;}

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
      +'<code>read -rs \"k?Anthropic key: \" && printf %s \"$k\" &gt; ~/Documents/Postgame_Outlet-hub/data/.anthropic_key '
      +'&amp;&amp; chmod 600 ~/Documents/Postgame_Outlet-hub/data/.anthropic_key &amp;&amp; unset k</code><br>then reopen this chat.</div>';
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
  [wk,yr,b].forEach(x=>r.appendChild(x));
  if(action==='results'){
    const bf=el('button','go alt','Full team stats');
    bf.title='Complete ESPN box score (24 stats/side) for every final game';
    bf.onclick=()=>run({action,week:wk.value,year:yr.value,full:true}, title+' — full team stats');
    r.appendChild(bf);
  }
  c.appendChild(r);
}

// ---- PFF player stats (reads local cache; fetch is a Claude Code browser step)
function pffCard(c){
  const r=el('div','row');
  const wk=el('input','sm'); wk.placeholder='week'; wk.value='1';
  const yr=el('input','sm'); yr.placeholder='year'; yr.value='2026';
  const gm=el('input'); gm.placeholder='game (team abbr, e.g. SF — blank = all)'; gm.style.width='150px';
  const b=el('button','go','Report'); b.onclick=()=>run({action:'pff',week:wk.value,year:yr.value,game:gm.value.trim()},'PFF player stats');
  const bf=el('button','go alt','Full (all fields)'); bf.onclick=()=>run({action:'pff',week:wk.value,year:yr.value,game:gm.value.trim(),full:true},'PFF player stats — full');
  [wk,yr,gm,b,bf].forEach(x=>r.appendChild(x)); c.appendChild(r);
  const note=el('div','note','PFF abbrs: BLT=BAL, CLV=CLE, HST=HOU, ARZ=ARI, LA=LAR. Grades+advanced included.');
  note.style.marginTop='4px'; c.appendChild(note);
}

// ---- previous ratings (snapshots / history)
function snapshotCard(c){
  const takeRow=el('div','row');
  const li=el('input'); li.placeholder='label (e.g. Week 2 2026)'; li.style.flex='1';
  const tb=el('button','go','📸 Take snapshot now'); tb.onclick=async()=>{
    const label=li.value.trim(); if(!label)return alert('enter a label');
    if(!confirm('Freeze the CURRENT ratings as “'+label+'”?\nSnapshots are immutable — the label can\'t be reused or edited.'))return;
    const res=await api('/api/snapshot',{label});
    if(!res.ok)return alert(res.message||'failed');
    showOut('Snapshot saved',label,res.message,0,{type:'text'}); li.value=''; loadSnaps(list);
  };
  takeRow.appendChild(li); takeRow.appendChild(tb); c.appendChild(takeRow);
  const lbl=el('div','note','Saved snapshots (newest first — click to view that board):'); lbl.style.marginTop='6px'; c.appendChild(lbl);
  const list=el('div','trendgrid'); list.textContent='loading…'; c.appendChild(list);
  loadSnaps(list);
}
async function loadSnaps(list){
  try{
    const j=await api('/api/snapshots'); list.innerHTML='';
    if(!j.snapshots || !j.snapshots.length){ list.textContent='(no snapshots yet — take one above)'; return; }
    j.snapshots.slice().reverse().forEach(s=>{
      const b=el('button','go alt',s.label);
      b.title=(s.published_at||'')+' · '+s.teams+' teams'+(s.corrections?(' · '+s.corrections+' correction(s)'):'');
      b.onclick=()=>openSnapshot(s.label); list.appendChild(b);
    });
  }catch(e){ list.textContent='(snapshots unavailable)'; }
}
async function openSnapshot(label){
  const j=await api('/api/snapshot?label='+encodeURIComponent(label));
  if(!j.ok)return alert(j.message||'load failed');
  const dlg=document.getElementById('dlg'); const b=document.getElementById('dlg-body'); b.innerHTML=''; dlg.classList.add('wide');
  b.appendChild(el('h3',null,'Previous ratings — '+label));
  b.appendChild(el('p','note',(j.published_at?('taken '+j.published_at+' · '):'')+j.rows.length+' teams · Δ = current − snapshot'));
  b.appendChild(snapBoard(j.rows));
  if(j.corrections && j.corrections.length){
    const cw=el('div'); cw.style.marginTop='10px'; cw.appendChild(el('div','wu-hd','Disclosed corrections'));
    j.corrections.forEach(x=>cw.appendChild(el('div','note',(x.at||'')+' — '+x.note))); b.appendChild(cw);
  }
  const foot=el('div','row'); foot.style.marginTop='12px';
  const close=el('button','go alt','Close'); close.onclick=()=>{dlg.classList.remove('wide');dlg.close();};
  foot.appendChild(close); b.appendChild(foot); dlg.showModal();
}
function snapBoard(rows){
  const t=el('table','r');
  t.innerHTML='<thead><tr><th class="l">#</th><th class="l">Team</th><th class="l">QB</th>'
    +'<th>qb</th><th>off</th><th>def</th><th>rating</th><th>now</th><th>Δ</th></tr></thead>';
  const tb=el('tbody');
  const f=v=>(Number(v)||0).toFixed(1);
  rows.forEach((r,i)=>{
    const tr=el('tr'); const d=r.delta;
    const dtxt=(d==null?'—':(d>0?'+'+f(d):f(d)));
    const dcol=(d==null||d===0)?'':(d>0?' style="color:var(--good)"':' style="color:var(--bad)"');
    tr.innerHTML=`<td class="l">${i+1}</td><td class="l">${r.team}</td><td class="l">${r.qb_name||''}</td>`
      +`<td>${f(r.qb)}</td><td>${f(r.off)}</td><td>${f(r.def)}</td><td><b>${f(r.rating)}</b></td>`
      +`<td>${r.current==null?'—':f(r.current)}</td><td${dcol}>${dtxt}</td>`;
    tb.appendChild(tr);
  });
  t.appendChild(tb); return t;
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
// minimal markdown -> HTML for the write-up preview (files use ##, ###, **, *, -)
function renderMd(src){
  const esc=s=>(s==null?'':(''+s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
  const inline=s=>esc(s)
    .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*]+)\*/g,'$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank">$1</a>');
  const lines=(src||'').split(/\r?\n/); let html='', inList=false;
  const closeList=()=>{ if(inList){html+='</ul>';inList=false;} };
  for(const raw of lines){
    const line=raw.replace(/\s+$/,'');
    if(/^###\s+/.test(line)){closeList();html+='<h4>'+inline(line.replace(/^###\s+/,''))+'</h4>';}
    else if(/^##\s+/.test(line)){closeList();html+='<h3>'+inline(line.replace(/^##\s+/,''))+'</h3>';}
    else if(/^#\s+/.test(line)){closeList();html+='<h2>'+inline(line.replace(/^#\s+/,''))+'</h2>';}
    else if(/^\s*[-*]\s+/.test(line)){ if(!inList){html+='<ul>';inList=true;} html+='<li>'+inline(line.replace(/^\s*[-*]\s+/,''))+'</li>'; }
    else if(line.trim()===''){closeList();}
    else {closeList();html+='<p>'+inline(line)+'</p>';}
  }
  closeList();
  return html || '<p class="empty">— empty —</p>';
}
function teamEditorCard(c){
  const r=el('div','row'); const i=el('input'); i.placeholder='team (e.g. Bills / BUF)'; i.style.flex='1';
  const b=el('button','go','Open editor'); const go=async()=>{ const q=i.value.trim(); if(!q)return alert('enter a team');
    const j=await api('/api/team?q='+encodeURIComponent(q)); if(!j.ok)return alert(j.message||'load failed'); openTeamEditor(j); };
  b.onclick=go; i.addEventListener('keydown',e=>{if(e.key==='Enter')go();});
  const wk=el('button','go alt','Full workspace'); wk.onclick=()=>{ if(!i.value.trim())return alert('enter a team'); launch('team',{team:i.value.trim()}); };
  r.appendChild(i); r.appendChild(b); r.appendChild(wk); c.appendChild(r);
}
function ctxLine(lg,k){ const x=lg&&lg[k]; if(!x)return ''; return 'league '+x.min+' / '+x.med+' / '+x.max; }
function openTeamEditor(j){
  const dlg=document.getElementById('dlg'); const b=document.getElementById('dlg-body'); b.innerHTML=''; dlg.classList.add('wide');
  b.appendChild(el('h3',null,'Team editor — '+(j.abbr||'')+' · '+(j.team||'')));
  const flag=el('p','note', (j.needs_review==='Y'?'⚠ this row is already needs_review=Y. ':'')+
    'Numbers save to ratings.csv (gated: sets needs_review=Y, reason → notes). Or hand the change to Claude Code for the method check. Write-up saves directly.');
  b.appendChild(flag);

  // ---- ratings block
  const rs=el('div','te-sec'); rs.appendChild(el('div','wu-hd','Ratings — QB / Off / Def'));
  const grid=el('div','te-nums');
  function numcell(key,label){ const w=el('div','te-cell');
    const lab=el('label',null,label); const inp=el('input','te-num'); inp.type='number'; inp.step='0.1';
    inp.value=(j[key]!=null?j[key]:0); inp.id='te-'+key;
    const ctx=el('div','te-ctx',ctxLine(j.league,key));
    w.appendChild(lab); w.appendChild(inp); w.appendChild(ctx); return {w,inp}; }
  const cQb=numcell('qb','QB'+(j.qb_name?' ('+j.qb_name+')':'')), cOff=numcell('off','Offense'), cDef=numcell('def','Defense');
  [cQb,cOff,cDef].forEach(x=>grid.appendChild(x.w));
  rs.appendChild(grid);
  const totRow=el('div','te-tot'); const cur='Current on file: QB '+j.qb+' · Off '+j.off+' · Def '+j.def+' = '+j.rating;
  const totEl=el('span','te-totv'); const refEl=el('span','note',cur);
  function recompute(){ const t=(parseFloat(cQb.inp.value)||0)+(parseFloat(cOff.inp.value)||0)+(parseFloat(cDef.inp.value)||0);
    totEl.textContent='New total: '+(Math.round(t*100)/100); }
  [cQb,cOff,cDef].forEach(x=>x.inp.addEventListener('input',recompute)); recompute();
  totRow.appendChild(totEl); rs.appendChild(totRow); rs.appendChild(refEl);
  const reason=el('input'); reason.placeholder='reason (required for a numbers save → becomes notes)'; reason.style.width='100%'; reason.style.marginTop='8px';
  rs.appendChild(reason);
  const rbtns=el('div','row'); rbtns.style.marginTop='8px';
  const saveNum=el('button','go','Save numbers (gated)'); saveNum.onclick=async()=>{
    const res=await api('/api/rating',{team:j.team,qb:cQb.inp.value,off:cOff.inp.value,def:cDef.inp.value,reason:reason.value.trim()});
    if(res.ok){ refEl.textContent='Current on file: '+res.new+' = '+res.total+'  (needs_review=Y)'; j.qb=parseFloat(cQb.inp.value);j.off=parseFloat(cOff.inp.value);j.def=parseFloat(cDef.inp.value);j.rating=res.total;
      showOut('Rating saved',res.new,res.message,0,{type:'text'}); refresh(); }
    else alert(res.message||'save failed'); };
  const toCC=el('button','go alt','Send to Claude Code'); toCC.onclick=()=>{
    const p='update ratings mode: '+j.team+' — set QB '+cQb.inp.value+', Off '+cOff.inp.value+', Def '+cDef.inp.value+
      (reason.value.trim()?('. Reason: '+reason.value.trim()):'')+'. Check it against the method, then draft/update the write-up.';
    if(navigator.clipboard)navigator.clipboard.writeText(p);
    showOut('Send to Claude Code','copied to clipboard — paste into the Claude Code chat:',p,0,{type:'text'}); };
  rbtns.appendChild(saveNum); rbtns.appendChild(toCC); rs.appendChild(rbtns);
  b.appendChild(rs);

  // ---- write-up block (markdown + live preview)
  const ws=el('div','te-sec'); ws.style.marginTop='14px';
  ws.appendChild(el('div','wu-hd','Write-up — data/writeups/'+(j.abbr||'')+'.md'+(j.writeup_exists?'':' (new)')));
  const split=el('div','wu-split');
  const lw=el('div','wu-pane'); lw.appendChild(el('div','wu-hd','Markdown (editable)'));
  const ta=el('textarea','wu-ta'); ta.value=j.writeup||''; lw.appendChild(ta);
  const rw=el('div','wu-pane'); const rhd=el('div','wu-hd', j.writeup_exists?'Preview — current on file':'Preview'); rw.appendChild(rhd);
  const prev=el('div','wu-prev'); prev.innerHTML=renderMd(j.writeup||''); rw.appendChild(prev);
  split.appendChild(lw); split.appendChild(rw); ws.appendChild(split);
  let dirty=false; ta.addEventListener('input',()=>{ prev.innerHTML=renderMd(ta.value); if(!dirty){dirty=true;rhd.textContent='Preview — your edits (unsaved)';} });
  const wbtns=el('div','row'); wbtns.style.marginTop='8px';
  const saveWu=el('button','go','Save write-up'); saveWu.onclick=async()=>{
    if(!j.abbr)return alert('no team abbr'); const res=await api('/api/writeup',{abbr:j.abbr,content:ta.value});
    if(res.ok){ j.writeup=ta.value; j.writeup_exists=true; dirty=false; rhd.textContent='Preview — current on file';
      showOut('Write-up saved',res.path,res.message,0,{type:'text'}); refresh(); } else alert(res.message||'save failed'); };
  const revWu=el('button','go alt','Revert write-up'); revWu.onclick=()=>{ ta.value=j.writeup||''; prev.innerHTML=renderMd(j.writeup||''); dirty=false; rhd.textContent=j.writeup_exists?'Preview — current on file':'Preview'; };
  wbtns.appendChild(saveWu); wbtns.appendChild(revWu); ws.appendChild(wbtns);
  b.appendChild(ws);

  const foot=el('div','row'); foot.style.marginTop='12px';
  const close=el('button','go alt','Close'); close.onclick=()=>{ dlg.classList.remove('wide'); dlg.close(); };
  foot.appendChild(close); b.appendChild(foot);
  dlg.showModal();
}
async function openQbBoard(){
  const dlg=document.getElementById('dlg'); const b=document.getElementById('dlg-body');
  b.innerHTML=''; dlg.classList.add('wide');
  b.appendChild(el('h3',null,'QB rankings'));
  const note=el('p','note','Ranked by each team’s ACTIVE starter (injured starters sit as backups). Toggle for week-to-week.');
  b.appendChild(note);
  const tg=el('div','toggle'); const bBoard=el('button',null,'Board (1–32)'); const bHist=el('button',null,'Week to week');
  tg.appendChild(bBoard); tg.appendChild(bHist); b.appendChild(tg);
  const wrap=el('div','qbwrap'); wrap.style.marginTop='10px'; b.appendChild(wrap);
  const foot=el('div','row'); foot.style.marginTop='10px';
  const close=el('span','close','Close'); close.onclick=()=>{dlg.classList.remove('wide');dlg.close();};
  foot.appendChild(close); b.appendChild(foot);
  const esc=s=>String(s==null?'':s).replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));
  const val=v=>{ if(v==null||v==='')return '—'; const n=Number(v); return (n>=0?'+':'')+n.toFixed(1); };
  const vcls=v=>v==null?'':(Number(v)>=0?'pos':'neg');
  async function showBoard(){
    bBoard.className='act'; bHist.className='';
    const j=await api('/api/qbboard'); if(!j.ok){wrap.textContent='load failed';return;}
    let h='<table class="qbt"><thead><tr><th>#</th><th>Team</th><th>Starter</th><th>Rtg</th><th>Backup</th><th>Rtg</th><th>3rd string</th><th>Rtg</th></tr></thead><tbody>';
    for(const r of j.board){ const s=r.starter,bk=r.backup,th=r.third;
      h+=`<tr><td class="rk">${r.rank}</td><td>${esc(r.team)}</td>`+
         `<td>${esc(s.name)}${s.review?' <span title="needs_review">⚠</span>':''}</td><td class="num ${vcls(s.v)}">${val(s.v)}</td>`+
         `<td class="dim">${bk?esc(bk.name):'—'}</td><td class="num dim ${bk?vcls(bk.v):''}">${bk?val(bk.v):'—'}</td>`+
         `<td class="dim">${th?esc(th.name):'—'}</td><td class="num dim ${th?vcls(th.v):''}">${th?val(th.v):'—'}</td></tr>`;
    }
    wrap.innerHTML=h+'</tbody></table>';
  }
  async function showHist(){
    bHist.className='act'; bBoard.className='';
    const j=await api('/api/qbhistory'); if(!j.ok){wrap.textContent='load failed';return;}
    let h='<table class="qbt"><thead><tr><th>Team · QB</th>';
    for(const l of j.labels) h+=`<th>${esc(l)}</th>`;
    h+='</tr></thead><tbody>';
    for(const t of j.teams){ h+=`<tr><td>${esc(t.team)} <span class="dim">${esc(t.current_qb)}</span></td>`; let prev=null;
      for(const c of t.cells){ if(c==null){h+='<td class="dim">—</td>';prev=null;continue;}
        const d=(prev!=null&&c.v!=null)?(c.v-prev):null;
        const arr=d?(d>0?` <span class="pos">▲${Math.abs(d).toFixed(1)}</span>`:(d<0?` <span class="neg">▼${Math.abs(d).toFixed(1)}</span>`:'')):'';
        h+=`<td class="num" title="${esc(c.name)}">${val(c.v)}${arr}</td>`; prev=c.v;
      }
      h+='</tr>';
    }
    wrap.innerHTML=h+'</tbody></table>';
  }
  bBoard.onclick=showBoard; bHist.onclick=showHist;
  await showBoard(); dlg.showModal();
}
async function openMarketBoard(refresh){
  const dlg=document.getElementById('dlg'); const b=document.getElementById('dlg-body');
  b.innerHTML=''; dlg.classList.add('wide');
  const hd=el('h3',null,'Market vs Mine'); b.appendChild(hd);
  const note=el('p','note','Loading market lines…'); b.appendChild(note);
  const wrap=el('div','qbwrap'); wrap.style.marginTop='8px'; b.appendChild(wrap);
  const adj=el('details'); adj.style.marginTop='10px'; b.appendChild(adj);
  const foot=el('div','row'); foot.style.marginTop='10px';
  const rf=el('button','go alt','↻ Refresh lines'); rf.onclick=()=>openMarketBoard(true);
  const close=el('span','close','Close'); close.onclick=()=>{dlg.classList.remove('wide');dlg.close();};
  foot.appendChild(rf); foot.appendChild(close); b.appendChild(foot);
  if(!dlg.open) dlg.showModal();
  const esc=s=>String(s==null?'':s).replace(/[&<>]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));
  const val=v=>{ if(v==null||v==='')return '—'; const n=Number(v); return (n>=0?'+':'')+n.toFixed(1); };
  const vcls=v=>v==null?'':(Number(v)>=0?'pos':'neg');
  const j=await api('/api/market'+(refresh?'?refresh=1':''));
  if(!j.ok){ note.textContent='Load failed: '+(j.message||'unknown'); return; }
  if(j.draft){ const d=el('span','pill','DRAFT — '+j.teams.filter(t=>t.needs_review).length+' rows needs_review=Y');
    d.style.cssText='margin-left:8px;background:#3a2a0e;color:#e3b341;border-color:#5a4212'; hd.appendChild(d); }
  const wk=j.weeks.map(u=>`Wk${u.week}×${u.weight} (${u.games})`).join(', ');
  note.innerHTML=`${j.season} through Week ${j.through_week} · ${j.games_used} games (${esc(wk)}). `+
    `Closing lines for played games, live ESPN odds for the upcoming week; your HFA (+0.5 primetime, 0 neutral). `+
    `Older lines re-based to today’s starting QB using your QB values. Ridge fit (λ ${j.lam}) centered on your mean (${val(j.mean)}) — `+
    `it shrinks the extremes a bit, so gaps under ~1 pt are noise. <span style="background:#12301c;padding:0 4px">green</span> = you’re ≥1.5 higher than the market, `+
    `<span style="background:#3a1616;padding:0 4px">red</span> = you’re ≥1.5 lower. Updated ${esc(j.generated_at)}.`;
  const hasPff=!!j.pff;
  const gcls=g=>g==null?'':(g>=1.5?' style="background:#12301c"':(g<=-1.5?' style="background:#3a1616"':''));
  let h='<table class="qbt"><thead><tr><th>#</th><th>Team</th><th>QB</th><th>Market</th>'+
    (hasPff?'<th title="PFF unit grades on your scale, around YOUR QB value">PFF</th>':'')+
    '<th>Mine</th><th>Gap (mine − mkt)</th>'+(hasPff?'<th>Gap (mine − PFF)</th><th>Read</th>':'')+'</tr></thead><tbody>';
  for(const r of j.teams){
    const hl=r.gap>=1.5?' style="background:#12301c"':(r.gap<=-1.5?' style="background:#3a1616"':'');
    const tag=r.consensus==='high'?'<span class="pill" style="background:#12301c;color:#7ee2a8">others agree: you’re high</span>'
      :(r.consensus==='low'?'<span class="pill" style="background:#3a1616;color:#ff9b9b">others agree: you’re low</span>':'');
    const u=r.pff_units;
    const ul=u?`<details><summary class="dim" style="cursor:pointer;font-size:11px">units</summary><div style="font-size:11px;white-space:nowrap">`+
      `OFF ${u.off} · pass ${u.pass} · pblk ${u.pblk} · recv ${u.recv} · run ${u.run} · rblk ${u.rblk}<br>`+
      `DEF ${u.def} · rdef ${u.rdef} · tack ${u.tack} · prsh ${u.prsh} · cov ${u.cov} · ST ${u.spec}<br>`+
      `PFF O ${val(r.pff_off)} / D ${val(r.pff_def)} vs yours O ${val(r.mine_off)} / D ${val(r.mine_def)} · PFF QB grade ${val(r.pff_qb)}${r.pff_qb_comparable===false?' (different QB — not comparable)':''}</div></details>`:'';
    h+=`<tr${hl}><td class="rk">${r.rank}</td><td>${esc(r.team)}${r.needs_review?' <span title="needs_review">⚠</span>':''}${ul}</td>`+
       `<td class="dim">${esc(r.qb)}</td><td class="num ${vcls(r.market)}">${val(r.market)}</td>`+
       (hasPff?`<td class="num ${vcls(r.pff_total)}">${val(r.pff_total)}</td>`:'')+
       `<td class="num ${vcls(r.mine)}">${val(r.mine)}</td><td class="num"><b>${val(r.gap)}</b></td>`+
       (hasPff?`<td class="num"${gcls(r.gap_pff)}><b>${val(r.gap_pff)}</b></td><td>${tag}</td>`:'')+`</tr>`;
  }
  wrap.innerHTML=h+'</tbody></table>'+(hasPff?
    `<p class="note" style="margin-top:6px">PFF column: PFF season unit grades (through Week ${esc(j.pff.through_week)}, fetched ${esc(j.pff.fetched)}) z-scored onto your Off/Def spread and added to <b>your</b> QB value — i.e. PFF’s read of the roster around your quarterback. PFF components use your QB value; PFF QB grade shown separately; not comparable where the starter changed. “Others agree” = Market and PFF both ≥1.0 on the same side of yours.</p>`
    :'<p class="note" style="margin-top:6px">No PFF team-grade cache found (data/pff/&lt;season&gt;/team_overview_wk&lt;N&gt;.json) — ask Claude to pull it.</p>');
  adj.innerHTML='<summary class="dim" style="cursor:pointer">QB re-basing applied ('+j.adjustments.length+')</summary>'+
    (j.adjustments.length?'<ul style="margin:6px 0 0;padding-left:18px;font-size:12px">'+j.adjustments.map(a=>
      `<li>Wk${a.week} ${esc(a.team)}: ${esc(a.from)} → ${esc(a.to)} ${a.shift==null?'(skipped: '+esc(a.note)+')':val(a.shift)}</li>`).join('')+'</ul>'
      :'<p class="note">none</p>');
}
function openWriteupEditor(j){
  const dlg=document.getElementById('dlg'); const b=document.getElementById('dlg-body'); b.innerHTML='';
  dlg.classList.add('wide');
  b.appendChild(el('h3',null,'Write-up — data/writeups/'+j.abbr+'.md'+(j.exists?'':' (new — file will be created)')));
  const note=el('p','note', j.exists
    ? 'Left = raw markdown you edit · Right = live preview (starts showing what’s currently on the site, so you see what you’re changing). Save writes the file directly; for a drafted rewrite from your take, use Claude Code.'
    : 'No write-up on file yet — the right pane previews what you type. Save creates the file.');
  b.appendChild(note);

  const split=el('div','wu-split');
  const leftWrap=el('div','wu-pane'); leftWrap.appendChild(el('div','wu-hd','Markdown (editable)'));
  const ta=el('textarea','wu-ta'); ta.value=j.content; leftWrap.appendChild(ta);
  const rightWrap=el('div','wu-pane');
  const rhd=el('div','wu-hd'); rhd.textContent = j.exists ? 'Preview — current on file' : 'Preview';
  rightWrap.appendChild(rhd);
  const prev=el('div','wu-prev'); prev.innerHTML=renderMd(j.content); rightWrap.appendChild(prev);
  split.appendChild(leftWrap); split.appendChild(rightWrap); b.appendChild(split);

  let dirty=false;
  ta.addEventListener('input',()=>{ prev.innerHTML=renderMd(ta.value);
    if(!dirty){dirty=true; rhd.textContent='Preview — your edits (unsaved)';} });

  const r=el('div','row'); r.style.marginTop='10px';
  const save=el('button','go','Save'); save.onclick=async()=>{
    const res=await api('/api/writeup',{abbr:j.abbr,content:ta.value});
    if(res.ok){ dlg.classList.remove('wide'); dlg.close(); showOut("Write-up saved",res.path,res.message,0,{type:'text'}); refresh(); }
    else alert(res.message||'save failed');
  };
  const revert=el('button','go alt','Revert'); revert.onclick=()=>{ ta.value=j.content; prev.innerHTML=renderMd(j.content);
    dirty=false; rhd.textContent = j.exists ? 'Preview — current on file' : 'Preview'; };
  const cancel=el('button','go alt','Close'); cancel.onclick=()=>{ dlg.classList.remove('wide'); dlg.close(); };
  r.appendChild(save); r.appendChild(revert); r.appendChild(cancel); b.appendChild(r);
  dlg.showModal();
}

// ---- layout builders (new hub)
const escH=s=>String(s==null?'':s).replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
const sgn=v=>{ const n=Number(v); if(!isFinite(n))return '—'; return (n>0?'+':'')+n.toFixed(1); };
const vcl=v=>{ const n=Number(v); return n>0?'pos':(n<0?'neg':'zero'); };

function buildMore(){
  const g=document.getElementById('more-grid'); g.innerHTML='';
  for(const cd of MORE){
    const box=el('div','mcard'); box.appendChild(el('h3',null,cd.t)); box.appendChild(el('p',null,cd.d));
    cd.render(box); g.appendChild(box);
  }
}

// ---- week board (market vs my line, same numbers as the pick sheet)
let SLATE=null;
function favLine(v,home,away){ // home-relative: negative = home favored
  if(v==null) return '<span class="zero">—</span>';
  const n=Number(v); if(n===0) return '<span class="t">PK</span>';
  const team=n<0?home:away; return `<span class="t">${escH(team)}</span>−${Math.abs(n).toFixed(1).replace(/\.0$/,'')}`;
}
function kickoffCell(g){
  if(g.final) return `<span class="when"><b>Final</b> ${g.away_score??''}–${g.home_score??''}</span>`;
  if(g.locked) return '<span class="when"><b style="color:var(--neg)">Live</b></span>';
  const d=new Date(g.kickoff); if(isNaN(d)) return '<span class="when">TBD</span>';
  const day=d.toLocaleDateString([], {weekday:'short'});
  const t=d.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'});
  return `<span class="when"><b>${day}</b> ${t}</span>`;
}
async function loadSlate(force){
  try{ SLATE=await api('/api/slate'+(force?'?refresh=1':'')); }catch(e){ SLATE={ok:false,message:String(e)}; }
  renderSlate();
}
function renderSlate(){
  const t=document.getElementById('sl-tbl'), sub=document.getElementById('sl-sub');
  if(!SLATE || !SLATE.ok){ t.innerHTML=`<tbody><tr><td class="empty l">${escH((SLATE&&SLATE.message)||'Lines unavailable.')}</td></tr></tbody>`;
    sub.textContent='lines unavailable'; return; }
  document.getElementById('sl-title').textContent=`Week ${SLATE.week} board`;
  const wk=document.getElementById('p-week'); wk.textContent=`Week ${SLATE.week} · ${SLATE.season}`;
  const games=SLATE.games.slice().sort((a,b)=>(a.kickoff||'').localeCompare(b.kickoff||''));
  const hot=games.filter(g=>g.edge!=null && Math.abs(g.edge)>=1.5);
  const onlyEdges=document.getElementById('sl-edges').checked;
  const gen=SLATE.generated?new Date(SLATE.generated.replace('Z',':00Z')):null;
  sub.textContent=`${games.length} games · ${hot.length} edge${hot.length===1?'':'s'} ≥ 1.5 · picks ${SLATE.picked_count}/${SLATE.max_picks}`
    +(gen&&!isNaN(gen)?` · lines ${gen.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'})}`:'');
  const rows=(onlyEdges?hot:games);
  let h='<thead><tr><th class="l hide-sm">Kickoff</th><th class="l">Matchup</th><th>Market</th><th>Mine</th><th>Edge</th><th class="hide-sm">Pick</th></tr></thead><tbody>';
  if(!rows.length) h+=`<tr><td class="empty l" colspan="6">No games with an edge of 1.5 or more.</td></tr>`;
  for(const g of rows){
    const e=g.edge, lean=e==null||e===0?null:(e>0?'home':'away');
    const leanAbbr=lean==='home'?g.home_abbr:(lean==='away'?g.away_abbr:'');
    const isHot=e!=null && Math.abs(e)>=1.5;
    const edgeHtml=e==null?'<span class="edge none">—</span>'
      :(e===0?'<span class="edge none">0.0</span>'
      :`<span class="edge${isHot?' hot':''}"><span class="t">${escH(leanAbbr)}</span>${Math.abs(e).toFixed(1)}</span>`);
    const pk=g.pick_side?`<span class="pk">★${g.pick_confidence??''} ${escH(g.pick_side==='home'?g.home_abbr:g.away_abbr)}</span>`:'<span class="zero">—</span>';
    h+=`<tr><td class="l hide-sm">${kickoffCell(g)}</td>`
      +`<td class="l"><span class="mu"><span class="${lean==='away'?'lean':''}" title="${escH(g.away)}">${escH(g.away_abbr)}</span>`
      +`<span class="at">@</span><span class="${lean==='home'?'lean':''}" title="${escH(g.home)}">${escH(g.home_abbr)}</span></span></td>`
      +`<td><span class="line">${favLine(g.market,g.home_abbr,g.away_abbr)}</span></td>`
      +`<td><span class="line">${favLine(g.my_spread,g.home_abbr,g.away_abbr)}</span></td>`
      +`<td>${edgeHtml}</td><td class="hide-sm">${pk}</td></tr>`;
  }
  t.innerHTML=h+'</tbody>';
}

// ---- ratings board
async function loadBoard(){
  const t=document.getElementById('rt-tbl');
  let j; try{ j=await api('/api/board'); }catch(e){ t.innerHTML='<tbody><tr><td class="empty l">Ratings unavailable.</td></tr></tbody>'; return; }
  const rows=j.rows||[]; const mx=Math.max(1,...rows.map(r=>Math.abs(r.rating)));
  const flagged=rows.filter(r=>r.needs_review==='Y').length;
  document.getElementById('rt-sub').textContent=`${rows.length} teams · QB + Off + Def · click a team to edit`+(flagged?` · ${flagged} need review`:'');
  let h='<thead><tr><th class="l">#</th><th class="l">Team</th><th class="l hide-sm">QB</th><th>QB</th><th>Off</th><th>Def</th><th>Total</th></tr></thead><tbody>';
  rows.forEach((r,i)=>{
    const w=Math.min(50,Math.abs(r.rating)/mx*50);
    const nick=r.team.split(' ').slice(-1)[0];
    h+=`<tr data-abbr="${escH(r.abbr||r.team)}"><td class="l rk">${i+1}</td>`
      +`<td class="l"><span class="tm"><b>${escH(r.abbr||r.team)}${r.needs_review==='Y'?'<span class="flagd" title="needs review">⚠</span>':''}</b><span>${escH(nick)}</span></span></td>`
      +`<td class="l hide-sm qbn">${escH(r.qb_name||'')}</td>`
      +`<td class="n ${vcl(r.qb)}">${sgn(r.qb)}</td><td class="n ${vcl(r.off)}">${sgn(r.off)}</td><td class="n ${vcl(r.def)}">${sgn(r.def)}</td>`
      +`<td><span class="tot"><span class="bar"><i class="${r.rating>=0?'p':'m'}" style="width:${w}%"></i></span><span class="v ${vcl(r.rating)}">${sgn(r.rating)}</span></span></td></tr>`;
  });
  t.innerHTML=h+'</tbody>';
  t.querySelectorAll('tbody tr').forEach(tr=>tr.onclick=async()=>{
    const q=tr.dataset.abbr; const jj=await api('/api/team?q='+encodeURIComponent(q));
    if(!jj.ok) return alert(jj.message||'load failed'); openTeamEditor(jj);
  });
}

// ---- editions (snapshots) in a dialog
function openEditions(){
  const dlg=document.getElementById('dlg'); const b=document.getElementById('dlg-body'); b.innerHTML=''; dlg.classList.remove('wide');
  b.appendChild(el('h3',null,'Editions'));
  b.appendChild(el('p','note','Freeze the current board as a named edition, or open a past one to compare.'));
  snapshotCard(b);
  const foot=el('div','row'); foot.style.marginTop='14px';
  const close=el('button','go alt','Close'); close.onclick=()=>dlg.close(); foot.appendChild(close); b.appendChild(foot);
  dlg.showModal();
}

// ---- trends (KB, no key needed)
async function loadTrends(row){
  row=row||document.getElementById('trend-btns');
  try{
    const j=await api('/api/trends');
    row.innerHTML='';
    const wk = j.week!=null ? ` · Wk${j.week} ${j.season}` : '';
    const lbl=document.getElementById('trend-label');
    if(lbl && j.week!=null) lbl.textContent=`Week ${j.week} angles from history · no API key needed`;
    (j.trends||[]).forEach(t=>{
      const b=el('button','trend');
      const label=t.label.replace(/^\W+\s*/,'');
      const desc=t.desc.replace(/^This week #:\s*/,'');
      b.innerHTML=`<span class="tx"><div class="tl">${escH(label)}</div><div class="tdsc" title="${escH(desc)}">${escH(desc)}</div></span><span class="go-arrow">Run →</span>`;
      b.onclick=()=>run({action:'trend',trend:t.id}, label+wk);
      row.appendChild(b);
    });
  }catch(e){ row.innerHTML='<div class="empty">Trends unavailable — build the knowledge base first.</div>'; }
}

// ---- status chips
async function refresh(){
  let s; try{ s=await api('/api/status'); }catch(e){ return; }
  const gate=document.getElementById('p-gate');
  if(s.needs_review.count){ gate.textContent=s.needs_review.count+' need review'; gate.className='chip bad';
    gate.title=s.needs_review.teams.join(', '); }
  else { gate.textContent='Gate clear'; gate.className='chip ok'; gate.title='No rows need review'; }
  const d=document.getElementById('p-dirty'); d.hidden=!s.dirty; d.title=s.dirty_files||'';
  const br=document.getElementById('p-branch'); br.hidden=(s.branch==='testing'); br.textContent='branch: '+s.branch;
}
function reloadAll(force){ refresh(); loadSlate(force); loadBoard(); }

async function loadSuggestions(){try{const j=await api('/api/suggestions');const S=j.summary,r=S.record;
  const u=x=>(x>0?'+':'')+(+x).toFixed(2)+'u';
  document.getElementById('sg-rec').textContent=(r.win+r.loss+r.push)?`${r.win}-${r.loss}${r.push?'-'+r.push:''} · ${u(S.units_pl)}`+(S.roi!=null?` · ROI ${(S.roi*100).toFixed(1)}%`:''):'No graded bets yet';
  document.getElementById('sg-det').textContent=`${S.pending} pending (expected ${u(S.expected_pl_pending)}) · ${S.total} suggestions logged · avg edge ${S.avg_edge!=null?'+'+(S.avg_edge*100).toFixed(1)+'¢':'—'}`;
}catch(e){document.getElementById('sg-rec').textContent='tracker unavailable';}}
loadSuggestions();
async function loadLiveChip(){try{const j=await api('/api/suggestions/live');const g=j.games||[];
  const inG=g.filter(x=>x.state==='in'), bets=inG.flatMap(x=>x.rows).filter(r=>r.size_u);
  const on=bets.filter(r=>['on','hit'].includes(r.state)).length;
  document.getElementById('p-ldot').classList.toggle('on',inG.length>0);
  document.getElementById('p-ltxt').textContent=inG.length?`Live bets · ${inG.length} game${inG.length>1?'s':''}${bets.length?` · ${on}/${bets.length} on track`:''}`:'Live bets';
  setTimeout(loadLiveChip,inG.length?45e3:180e3);}catch(e){setTimeout(loadLiveChip,180e3);}}
loadLiveChip();
buildMore(); loadTrends(); reloadAll(false);
setInterval(refresh, 15000); setInterval(()=>loadSlate(false), 300000);
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
        if u.path == "/api/team":
            return self._send(200, json.dumps(act_team_get((q.get("q") or q.get("abbr") or [""])[0])))
        if u.path == "/api/kbstatus":
            return self._send(200, json.dumps(act_kbstatus()))
        if u.path == "/api/trends":
            return self._send(200, json.dumps(act_trends_catalog()))
        if u.path == "/api/qbboard":
            return self._send(200, json.dumps(act_qb_board()))
        if u.path == "/api/qbhistory":
            return self._send(200, json.dumps(act_qb_history()))
        if u.path == "/api/market":
            return self._send(200, json.dumps(act_market(
                (q.get("week") or [None])[0], (q.get("year") or [None])[0],
                refresh=bool((q.get("refresh") or [""])[0]))))
        if u.path == "/api/slate":
            return self._send(200, json.dumps(act_slate(
                refresh=bool((q.get("refresh") or [""])[0]))))
        if u.path == "/api/board":
            return self._send(200, json.dumps(act_board()))
        if u.path == "/api/snapshots":
            return self._send(200, json.dumps(act_snapshots_list()))
        if u.path == "/api/snapshot":
            return self._send(200, json.dumps(act_snapshot_get((q.get("label") or [""])[0])))
        if u.path == "/suggestions":
            with open(os.path.join(REPO, "suggestions_page.html"), encoding="utf-8") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if u.path == "/api/suggestions":
            import suggestions
            return self._send(200, json.dumps(suggestions.api_payload()))
        if u.path == "/api/suggestions/live":
            import suggestions
            return self._send(200, json.dumps(suggestions.live()))
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
            if u.path == "/api/rating":
                return self._send(200, json.dumps(act_rating_save(body)))
            if u.path == "/api/snapshot":
                return self._send(200, json.dumps(act_snapshot_create(body)))
            if u.path == "/api/kbchat":
                return self._send(200, json.dumps(act_kbchat(body)))
            if u.path == "/api/suggestions/grade":
                import suggestions
                ch = suggestions.grade_all()
                return self._send(200, json.dumps({"ok": True, "changes": ch}))
            if u.path == "/api/suggestions/update":
                import suggestions
                sid = body.pop("id", "")
                return self._send(200, json.dumps({"ok": True, "suggestion": suggestions.update(sid, body)}))
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
