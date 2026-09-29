"""Game-day injury news check (McCabe Method, Lane-2 WIP — `testing` branch).

Pulls the latest RotoWire NFL player news (the same notes @RotoWireNFL posts on X,
read from RotoWire's public news page, per team) for the teams kicking off in the
next window, maps each item to role (starter / backup, via the Sleeper cache), flags
the injury-relevant ones, and pairs every game with MY line (draft ratings) vs the
live market line. Evidence only — never edits ratings. The scheduled game-day runs
(Thu 4:15p, Sun 5:30a/9a/12:30p/4p, Mon 4p PT) call this, then Claude adds
the web context + suggested rating moves in the session.

CLI:
    python3 injury_news.py                 # games kicking off in the next 6h
    python3 injury_news.py --hours 4       # custom window
    python3 injury_news.py --week 4        # every unplayed game of week 4
    python3 injury_news.py --json          # machine-readable
Stdlib only. Seen-item cache: data/injury_news/seen.json (gitignored).
"""

import csv
import html
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import picks
from espn_api import fetch_json

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE_DIR = os.path.join(DATA, "injury_news")
SEEN = os.path.join(CACHE_DIR, "seen.json")
NEWS_URL = "https://www.rotowire.com/football/news.php?team={abbr}"
UA = "Mozilla/5.0 (McCabe power-ratings game-day check; low volume)"
ESPN_TO_RW = {"WSH": "WAS"}

INJURY_WORDS = re.compile(
    r"\b(out|inactive|ruled out|questionable|doubtful|injur\w*|IR\b|injured reserve|"
    r"game-time|won't play|will not play|will play|expected to play|active|limited|"
    r"did not practice|DNP|full participant|concussion|hamstring|ankle|knee|groin|"
    r"calf|shoulder|back|foot|toe|quad|pectoral|elbow|thumb|wrist|hip|neck|illness|"
    r"start(s|ing)?|benched|suspend\w*|designated to return|activated|placed)\b", re.I)

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "ignore")


def _text(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment or "")).strip()


def parse_news(page):
    """RotoWire news.php HTML → list of items (newest first)."""
    out = []
    for block in page.split('<div class="news-update">')[1:]:
        def grab(cls):
            m = re.search(rf'class="{cls}"[^>]*>(.*?)</(?:div|a|b)>', block, re.S)
            return _text(m.group(1)) if m else ""
        link = re.search(r'news-update__headline" href="([^"]+)"', block)
        nid = re.search(r"-(\d+)$", link.group(1)) if link else None
        team = re.search(r'news-update__logo"[^>]*alt="([A-Z]+)"', block)
        out.append({
            "id": int(nid.group(1)) if nid else 0,
            "team": team.group(1) if team else "",
            "player": grab("news-update__player-link"),
            "headline": grab("news-update__headline"),
            "pos": grab("news-update__pos"),
            "date": grab("news-update__timestamp"),
            "news": _text((re.search(r'class="news-update__news"[^>]*>(.*?)</div>', block, re.S)
                           or re.search(r"()", "")).group(1)),
            "url": ("https://www.rotowire.com" + link.group(1)) if link else "",
        })
    return out


def team_news(espn_abbr):
    return parse_news(_get(NEWS_URL.format(abbr=ESPN_TO_RW.get(espn_abbr, espn_abbr))))


def _load_seen():
    try:
        with open(SEEN) as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def _save_seen(ids):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(SEEN, "w") as f:
        json.dump(sorted(ids)[-5000:], f)


def _roles():
    """{(team_abbr, normalized name): role} from the Sleeper cache."""
    path = os.path.join(DATA, "sleeper_cache", "players.json")
    try:
        d = json.load(open(path))
    except (OSError, ValueError):
        return {}
    players = d.get("players", d)
    it = players.values() if isinstance(players, dict) else players
    roles = {}
    for p in it:
        t, name = p.get("team"), p.get("full_name")
        if not t or not name:
            continue
        order = p.get("depth_chart_order")
        pos = p.get("position") or ""
        if order == 1 or (pos in ("OL", "T", "G", "C") and order and order <= 5):
            role = "starter"
        elif order:
            role = f"depth {order}"
        else:
            role = "reserve/unknown"
        status = p.get("injury_status") or ""
        roles[(t, _norm(name))] = (role, status, p.get("injury_body_part") or "")
    return roles


def _norm(name):
    return re.sub(r"[^a-z]", "", (name or "").lower().replace("jr", "").replace("sr", ""))


def _draft_ratings():
    with open(os.path.join(DATA, "ratings.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    return {r["team"]: round(float(r["qb_value"] or 0) + float(r["off_value"] or 0)
                             + float(r["def_value"] or 0), 1) for r in rows}, \
        any((r.get("needs_review") or "").strip().upper() == "Y" for r in rows)


def upcoming_games(hours=6.0, week=None, year=None):
    now = datetime.now(timezone.utc)
    cw, cy = picks.current_week_year()
    week, year = week or cw, year or cy
    payload = fetch_json(picks.SCOREBOARD.format(year=year, week=week))
    ratings, draft = _draft_ratings()
    hfa, dh = picks.load_hfa()
    ov = picks.load_line_overrides()
    games = []
    for e in payload.get("events", []):
        L = picks._line_for_event(e, ratings, hfa, dh, ov, now)
        if not L or L.get("final"):
            continue
        ko = L.get("kickoff")
        if isinstance(ko, str):
            ko = datetime.strptime(ko, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        if ko and ko < now:
            continue  # already started
        if hours is not None and ko and ko > now + timedelta(hours=hours):
            continue
        c = e["competitions"][0]
        comp = {t["homeAway"]: t["team"]["abbreviation"] for t in c["competitors"]}
        games.append({**L, "home_abbr": comp["home"], "away_abbr": comp["away"],
                      "kickoff_dt": ko})
    return games, draft, week, year


def build(hours=6.0, week=None, year=None, all_week=False):
    games, draft, week, year = upcoming_games(None if all_week else hours, week, year)
    roles = _roles()
    seen = _load_seen()
    today = datetime.now().date()
    keep_dates = {(today - timedelta(days=d)).strftime("%B %-d, %Y") for d in range(0, 3)}
    report = {"generated": datetime.now().strftime("%a %m/%d %I:%M %p"), "week": week,
              "season": year, "draft_ratings": draft, "games": []}
    new_ids = set()
    for g in sorted(games, key=lambda g: g["kickoff_dt"] or datetime.max.replace(tzinfo=timezone.utc)):
        entry = {k: g.get(k) for k in ("away", "home", "away_abbr", "home_abbr",
                                       "my_spread", "market", "market_details", "edge", "neutral")}
        entry["kickoff_local"] = picks._fmt_local(g["kickoff_dt"]) if g.get("kickoff_dt") else ""
        entry["items"] = []
        for ab in (g["away_abbr"], g["home_abbr"]):
            try:
                items = team_news(ab)
            except Exception as ex:  # noqa: BLE001 — one team's fetch shouldn't sink the run
                entry["items"].append({"team": ab, "error": str(ex)})
                continue
            time.sleep(0.7)
            for it in items:
                if it["date"] not in keep_dates:
                    continue
                if not INJURY_WORDS.search(it["headline"] + " " + it["news"]):
                    continue
                role, status, part = roles.get((ab, _norm(it["player"])), ("unknown", "", ""))
                it.update(team=ab, role=role, sleeper_status=status, body_part=part,
                          new=it["id"] not in seen)
                new_ids.add(it["id"])
                entry["items"].append(it)
        entry["items"].sort(key=lambda x: (x.get("role") != "starter", -x.get("id", 0)))
        report["games"].append(entry)
    _save_seen(seen | new_ids)
    return report


def print_report(rep):
    tag = " (DRAFT ratings — needs_review rows pending)" if rep["draft_ratings"] else ""
    print(f"=== Game-day injury check — Week {rep['week']} · {rep['generated']}{tag} ===")
    if not rep["games"]:
        print("No games kicking off in this window.")
        return
    for g in rep["games"]:
        mine = g["my_spread"]; mkt = g["market"]
        def side(v):
            if v is None: return "n/a"
            if v == 0: return "pick'em"
            return f"{g['home_abbr']} {v:.1f}" if v < 0 else f"{g['away_abbr']} {-v:.1f}"
        print(f"\n{g['away_abbr']} @ {g['home_abbr']}  ({g['kickoff_local']}){'  [neutral]' if g['neutral'] else ''}")
        print(f"  my line {side(mine)} | market {side(mkt)} ({g.get('market_details') or ''}) | edge {g['edge']}")
        if not g["items"]:
            print("  no injury-relevant RotoWire news in the last 3 days")
        for it in g["items"]:
            if it.get("error"):
                print(f"  ! {it['team']}: fetch failed ({it['error']})"); continue
            flag = "NEW " if it["new"] else "    "
            print(f"  {flag}{it['team']} {it['pos']} {it['player']} [{it['role']}"
                  f"{'; Sleeper ' + it['sleeper_status'] if it['sleeper_status'] else ''}]: "
                  f"{it['headline']} — {it['news'][:220]}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    hours = 6.0
    week = None
    if "--hours" in argv:
        hours = float(argv[argv.index("--hours") + 1])
    if "--week" in argv:
        week = int(argv[argv.index("--week") + 1])
    rep = build(hours=hours, week=week, all_week=week is not None)
    if "--json" in argv:
        print(json.dumps(rep, default=str, indent=1))
    else:
        print_report(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
