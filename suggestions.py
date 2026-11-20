"""Suggestions tracker — every bet/lean/model pick Claude suggests to Sean, auto-graded.

Private, local-only (data/suggestions.json is gitignored). Served by hub_server.py at
/suggestions (full dashboard) and summarized on the hub's front page.

Each suggestion:
  id, created (UTC ISO), source (what produced it), season, week,
  game: {espn_id, away, home, kickoff}          (ESPN abbreviations)
  category: spread | moneyline | total | team_total | player_prop | anytime_td | multi_td | combo
  bet: human label, e.g. "Patriots +2.5"
  grade: machine spec used to settle it (see _grade_leg), or {"legs": [...]} for a combo
  venue, price_prob (implied prob of the suggested buy, 0-1), price_note,
  our_prob (our model's probability), size_u (units; 0 = informational model pick),
  status: bet | conditional | info | void,  condition (text, for conditional)
  result: pending | win | loss | push | void,  actual (text), graded_at
  sean: {placed: bool, amount, fill_prob, notes}   (Sean's own tracking, editable in the UI)
  notes      short one-liner
  reasoning  full pre-game thesis: the inputs, the numbers, what would make it wrong
  review     post-game: what actually happened vs the thesis (filled in after grading)

CLI:  python3 suggestions.py grade        # settle finished games from ESPN
      python3 suggestions.py summary
      python3 suggestions.py add '<json>'  # append one suggestion
"""
import json
import os
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "data", "suggestions.json")
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={eid}"
UA = {"User-Agent": "Mozilla/5.0 (power-ratings-hub)"}


# ------------------------------------------------------------------ storage
def load():
    try:
        with open(PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"version": 1, "suggestions": []}


def save(doc):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(PATH), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(doc, f, indent=2)
    os.replace(tmp, PATH)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def add(s):
    doc = load()
    ids = {x["id"] for x in doc["suggestions"]}
    if s.get("id") in ids:
        raise ValueError(f"duplicate id {s['id']}")
    s.setdefault("created", _now())
    s.setdefault("result", "pending")
    s.setdefault("sean", {"placed": False, "amount": None, "fill_prob": None, "notes": ""})
    doc["suggestions"].append(s)
    save(doc)
    return s


def update(sid, fields):
    """Edit Sean-owned fields (sean.*, status, notes, manual result override)."""
    doc = load()
    for s in doc["suggestions"]:
        if s["id"] == sid:
            if "sean" in fields:
                s.setdefault("sean", {}).update({k: v for k, v in fields["sean"].items()
                                                 if k in ("placed", "amount", "fill_prob", "notes")})
            for k in ("status", "notes", "reasoning", "review"):
                if k in fields:
                    s[k] = fields[k]
            if "condition_met" in fields:
                s["condition_met"] = fields["condition_met"]  # True / False / None (unknown)
            if fields.get("result") in ("pending", "win", "loss", "push", "void"):
                s["result"] = fields["result"]
                s["manual_result"] = fields["result"] != "pending"
                s["graded_at"] = _now()
            save(doc)
            return s
    raise KeyError(sid)


# ------------------------------------------------------------------ grading
def _fetch(eid):
    req = urllib.request.Request(SUMMARY.format(eid=eid), headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _norm(name):
    parts = [w for w in (name or "").lower().replace(".", " ").replace("'", "").split()
             if w not in ("jr", "sr", "ii", "iii", "iv", "v")]
    return "".join(parts)


def _box(summary):
    """-> (final, {abbr: score}, {player_norm: {stat: value}})"""
    comp = summary["header"]["competitions"][0]
    final = bool(comp["status"]["type"].get("completed"))
    scores = {c["team"]["abbreviation"]: float(c.get("score") or 0) for c in comp["competitors"]}
    stats = {}
    for team in summary.get("boxscore", {}).get("players", []):
        for cat in team.get("statistics", []):
            keys = cat.get("keys") or []
            for a in cat.get("athletes", []):
                p = stats.setdefault(_norm(a["athlete"]["displayName"]),
                                     {"_name": a["athlete"]["displayName"], "_team": team["team"]["abbreviation"]})
                for k, v in zip(keys, a.get("stats", [])):
                    try:
                        p[f'{cat["name"]}.{k}'] = float(v)
                    except (TypeError, ValueError):
                        p[f'{cat["name"]}.{k}'] = v
    return final, scores, stats


STAT = {  # grade-spec stat name -> boxscore key
    "pass_td": "passing.passingTouchdowns", "pass_yds": "passing.passingYards",
    "rush_yds": "rushing.rushingYards", "rush_att": "rushing.rushingAttempts",
    "rush_td": "rushing.rushingTouchdowns", "rec_yds": "receiving.receivingYards",
    "receptions": "receiving.receptions", "rec_td": "receiving.receivingTouchdowns",
}


def _player_val(stats, player, stat):
    p = stats.get(_norm(player))
    if p is None:
        return None  # did not record a stat (DNP or no touches)
    if stat == "scrimmage_td":
        return (p.get("rushing.rushingTouchdowns") or 0) + (p.get("receiving.receivingTouchdowns") or 0)
    v = p.get(STAT[stat])
    return v if isinstance(v, float) else 0.0


def _ou(val, op, line):
    if val is None:
        return "void"
    if abs(val - line) < 1e-9:
        return "push"
    return "win" if (val > line) == (op == "over") else "loss"


def _grade_leg(g, game, box):
    final, scores, stats = box
    kind = g["kind"]
    if kind in ("spread", "moneyline"):
        team = g["team"]
        opp = game["home"] if team == game["away"] else game["away"]
        margin = scores[team] - scores[opp]
        if kind == "moneyline":
            return ("push" if margin == 0 else "win" if margin > 0 else "loss"), f"{team} {scores[team]:g}-{scores[opp]:g}"
        v = margin + g["line"]
        return ("push" if v == 0 else "win" if v > 0 else "loss"), f"{team} {scores[team]:g}-{scores[opp]:g}"
    if kind == "total":
        tot = sum(scores.values())
        return _ou(tot, g["op"], g["line"]), f"total {tot:g}"
    if kind == "team_total":
        return _ou(scores[g["team"]], g["op"], g["line"]), f'{g["team"]} {scores[g["team"]]:g}'
    if kind == "player":
        val = _player_val(stats, g["player"], g["stat"])
        if val is None and g["stat"] in ("scrimmage_td",):
            val = None
        res = _ou(val, g["op"], g["line"])
        return res, f'{g["player"]} {g["stat"]} {"DNP/none" if val is None else f"{val:g}"}'
    raise ValueError(kind)


def grade_all(force=False):
    """Settle every pending suggestion whose game is final. Returns list of changes."""
    doc = load()
    cache, changes = {}, []
    for s in doc["suggestions"]:
        if s.get("result") != "pending" and not force:
            continue
        if s.get("manual_result"):
            continue
        legs = s["grade"].get("legs") or [dict(s["grade"], game=s["game"])]
        results, actual, done = [], [], True
        for leg in legs:
            game = leg.get("game") or s["game"]
            eid = game["espn_id"]
            if eid not in cache:
                try:
                    cache[eid] = _box(_fetch(eid))
                except Exception as e:  # noqa: BLE001
                    cache[eid] = None
                    print(f"fetch failed {eid}: {e}", file=sys.stderr)
            box = cache[eid]
            if not box or not box[0]:
                done = False
                break
            r, a = _grade_leg(leg, game, box)
            results.append(r)
            actual.append(a)
        if not done:
            continue
        if s.get("status") == "conditional" and s.get("condition_met") is not True:
            res = "void"
        elif "loss" in results:
            res = "loss"
        elif all(r == "void" for r in results):
            res = "void"
        elif all(r in ("push", "void") for r in results):
            res = "push"
        elif "push" in results or "void" in results:
            res = "push" if len(results) == 1 else "win_reduced"
        else:
            res = "win"
        s["result"] = "win" if res == "win_reduced" else res
        s["actual"] = "; ".join(actual)
        s["graded_at"] = _now()
        changes.append((s["id"], s["result"], s["actual"]))
    save(doc)
    return changes


# ------------------------------------------------------------------ live view
import re as _re
import time as _time

_CACHE = {}           # key -> (fetched_at, value)
_AUTO_GRADED = set()  # espn ids we've already auto-graded this process
PM_EVENT = "https://gamma-api.polymarket.com/events?slug={slug}"
PM_ABBR = {"WSH": "was", "LAR": "la"}
PM_STAT = {"rec_yds": "Receiving Yards", "rush_yds": "Rushing Yards", "pass_yds": "Passing Yards",
           "pass_td": "Passing Touchdowns", "receptions": "Receptions", "rush_att": "Rushing Attempts"}


def _cached(key, ttl, fn):
    hit = _CACHE.get(key)
    if hit and _time.time() - hit[0] < ttl:
        return hit[1]
    try:
        val = fn()
    except Exception as e:  # noqa: BLE001
        print(f"live fetch failed {key}: {e}", file=sys.stderr)
        val = hit[1] if hit else None
    _CACHE[key] = (_time.time(), val)
    return val


def _get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def _pm_markets(game):
    """All Polymarket markets (game + player props) for a game, or []."""
    k = (game.get("kickoff") or "")[:10]
    if not k:
        return []
    a = PM_ABBR.get(game["away"], game["away"].lower())
    h = PM_ABBR.get(game["home"], game["home"].lower())
    slug = f"nfl-{a}-{h}-{k}"
    out = []
    for sl in (slug, slug + "-player-props"):
        ev = _cached("pm:" + sl, 60, lambda sl=sl: _get_json(PM_EVENT.format(slug=sl)))
        if ev:
            out.extend(ev[0].get("markets", []))
    return out


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _side(m, idx):
    """(buy price, mid) for outcome idx (0 = first) of a market."""
    ask, bid = _f(m.get("bestAsk")), _f(m.get("bestBid"))
    if ask is None and bid is None:
        return None
    mid = (ask + bid) / 2 if ask is not None and bid is not None else (ask if ask is not None else bid)
    wide = ask is None or bid is None or (ask - bid) > 0.10
    if idx == 0:
        buy, m_ = ask, mid
    else:
        buy, m_ = ((1 - bid) if bid is not None else None), 1 - mid
    # "now" = the market's current read on our side: midpoint when the book is tight,
    # otherwise what it would cost to buy (thin prop books have junk 0.01 bids).
    return {"buy": buy, "mid": m_, "now": buy if wide else m_, "wide": wide, "liq": _f(m.get("liquidity"))}


def _outs(m):
    o = m.get("outcomes")
    if isinstance(o, str):
        try:
            o = json.loads(o)
        except ValueError:
            o = []
    return o or []


def _pm_price(leg, markets, nick):
    """Current Polymarket price for OUR side of one grade leg."""
    kind = leg["kind"]
    for m in markets:
        q = (m.get("question") or "").strip()
        if kind == "player":
            if ":" not in q or _norm(q.split(":")[0]) != _norm(leg["player"]):
                continue
            rest = q.split(":", 1)[1].strip()
            if leg["stat"] == "scrimmage_td":
                want = "Anytime Touchdown" if leg["line"] < 1 else "2+ Touchdowns"
                if rest == want:
                    return _side(m, 0 if leg["op"] == "over" else 1)
                continue
            if rest == f'{PM_STAT.get(leg["stat"], "?")} O/U {leg["line"]:g}':
                return _side(m, 0 if leg["op"] == "over" else 1)
        elif kind == "spread":
            mm = _re.match(r"^Spread: (.+) \(-([\d.]+)\)$", q)
            if not mm or abs(float(mm.group(2)) - abs(leg["line"])) > 1e-9:
                continue
            fav = mm.group(1)
            mine = nick.get(leg["team"])
            if leg["line"] < 0 and fav == mine:
                return _side(m, 0)
            if leg["line"] > 0 and fav != mine and mine in _outs(m):
                return _side(m, 1)
        elif kind == "moneyline":
            if ":" in q or " vs. " not in q:
                continue
            o = _outs(m)
            if nick.get(leg["team"]) in o:
                return _side(m, o.index(nick[leg["team"]]))
        elif kind == "total":
            mm = _re.match(r"^[^:]+ vs\. [^:]+: O/U ([\d.]+)$", q)
            if mm and abs(float(mm.group(1)) - leg["line"]) < 1e-9:
                return _side(m, 0 if leg["op"] == "over" else 1)
    return None


def _clock(comp):
    st = comp["status"]
    period = st.get("period") or 0
    try:
        mm, ss = (st.get("displayClock") or "0:00").split(":")
        left = int(mm) * 60 + int(float(ss))
    except ValueError:
        left = 0
    frac = min(1.0, max(0.0, ((min(period, 4) - 1) * 900 + (900 - left)) / 3600)) if period else 0.0
    return st["type"].get("state", "pre"), st["type"].get("shortDetail", ""), frac


def _leg_live(leg, game, box, state, frac):
    final, scores, stats = box
    kind = leg["kind"]
    out = {"kind": kind}
    if state == "post":
        r, a = _grade_leg(leg, game, box)
        if kind == "player":
            v = _player_val(stats, leg["player"], leg["stat"])
            a = "did not play / no stats" if v is None else f'finished with {v:g} {_STAT_SHORT.get(leg["stat"], leg["stat"])}'
        out.update(state=r, text=a)
        return out
    if state == "pre":
        out.update(state="pre", text="not started")
        return out
    pace_ok = frac >= 0.05
    if kind in ("spread", "moneyline"):
        team = leg["team"]
        opp = game["home"] if team == game["away"] else game["away"]
        margin = scores.get(team, 0) - scores.get(opp, 0)
        v = margin + (leg.get("line") or 0)
        out["cur"] = margin
        if kind == "moneyline":
            out.update(state="on" if margin > 0 else "behind",
                       text=f"leading by {margin:g}" if margin > 0 else ("tied" if margin == 0 else f"trailing by {-margin:g}"))
        else:
            out.update(state="on" if v > 0 else "behind",
                       text=f"covering by {v:g}" if v > 0 else ("on the number" if v == 0 else f"needs {-v:g} more"))
        return out
    if kind in ("total", "team_total", "player"):
        if kind == "total":
            val = sum(scores.values())
        elif kind == "team_total":
            val = scores.get(leg["team"], 0)
        else:
            val = _player_val(stats, leg["player"], leg["stat"])
            val = 0.0 if val is None else val
        line, over = leg["line"], leg["op"] == "over"
        pace = val / frac if pace_ok else None
        out.update(cur=val, line=line, pace=round(pace, 1) if pace is not None else None)
        if over:
            if val > line:
                out.update(state="hit", text="cashed")
            else:
                need = line - val
                out.update(state="on" if pace is not None and pace > line else "behind",
                           text=f"needs {need:g}" if leg.get("stat") != "scrimmage_td" else "needs a TD")
        else:
            if val > line:
                out.update(state="dead", text="went over")
            else:
                out.update(state="on" if pace is None or pace <= line else "behind",
                           text=f"{line - val:g} to spare" if leg.get("stat") != "scrimmage_td" else "no TD yet")
        return out
    out.update(state="pre", text="?")
    return out


def _combine(states):
    if any(s in ("dead", "loss") for s in states):
        return "dead" if any(s == "dead" for s in states) else "loss"
    if all(s in ("hit", "win") for s in states):
        return "hit"
    if all(s in ("win", "push", "void") for s in states):
        return "win"
    if any(s == "pre" for s in states):
        return "pre"
    return "on" if all(s in ("on", "hit", "win") for s in states) else "behind"


def live(window_back_h=12, window_ahead_h=36):
    """Live state for every game with a pending suggestion (plus recent finals)."""
    doc = load()
    now = datetime.now(timezone.utc)
    games = {}
    for s in doc["suggestions"]:
        g = s.get("game") or {}
        k = g.get("kickoff")
        try:
            kt = datetime.strptime(k, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        hrs = (kt - now).total_seconds() / 3600
        if s.get("result") == "pending" and hrs > window_ahead_h:
            continue
        if s.get("result") != "pending" and not (-window_back_h <= hrs <= 0.5):
            continue
        games.setdefault(g["espn_id"], {"game": g, "kickoff": k, "items": []})["items"].append(s)

    newly_final = False
    out = []
    for eid, G in games.items():
        summ = _cached("espn:" + eid, 20, lambda eid=eid: _fetch(eid))
        if not summ:
            continue
        comp = summ["header"]["competitions"][0]
        state, detail, frac = _clock(comp)
        box = _box(summ)
        teams = {c["team"]["abbreviation"]: {"score": c.get("score") or "0", "name": c["team"].get("name"),
                                             "home": c.get("homeAway") == "home"} for c in comp["competitors"]}
        nick = {a: t["name"] for a, t in teams.items()}
        markets = _pm_markets(G["game"]) if state != "post" else []
        if state == "post" and eid not in _AUTO_GRADED and any(s.get("result") == "pending" for s in G["items"]):
            newly_final = True
            _AUTO_GRADED.add(eid)
        rows = []
        for s in G["items"]:
            legs = s["grade"].get("legs") or [dict(s["grade"])]
            ll = []
            for leg in legs:
                lg = leg.get("game") or s["game"]
                if lg["espn_id"] != eid:  # cross-game combo leg: not tracked live
                    ll.append({"kind": leg["kind"], "state": "pre", "text": "other game"})
                    continue
                d = _leg_live(leg, lg, box, state, frac)
                d["label"] = _leg_label(leg)
                d["pm"] = _pm_price(leg, markets, nick) if markets else None
                ll.append(d)
            st = s["result"] if s.get("result") != "pending" else _combine([x["state"] for x in ll])
            if s.get("status") == "conditional" and s.get("condition_met") is False:
                st = "void"
            pm = ll[0].get("pm") if len(ll) == 1 else None
            rows.append({"id": s["id"], "bet": s["bet"], "status": s.get("status"), "size_u": s.get("size_u"),
                         "price_prob": s.get("price_prob"), "our_prob": s.get("our_prob"), "result": s.get("result"),
                         "condition": s.get("condition"), "condition_met": s.get("condition_met"),
                         "placed": (s.get("sean") or {}).get("placed"), "venue": s.get("venue"), "state": st, "legs": ll, "pm": pm})
        order = {"bet": 0, "conditional": 1, "info": 2, "void": 3}
        rows.sort(key=lambda r: (order.get(r["status"], 9), -(r["size_u"] or 0)))
        out.append({"espn_id": eid, "away": G["game"]["away"], "home": G["game"]["home"], "kickoff": G["kickoff"],
                    "state": state, "detail": detail, "frac": round(frac, 3), "teams": teams, "rows": rows})
    out.sort(key=lambda g: ({"in": 0, "pre": 1, "post": 2}.get(g["state"], 3), g["kickoff"]))
    changes = grade_all() if newly_final else []
    return {"ok": True, "now": _now(), "games": out, "graded": changes}


_STAT_SHORT = {"scrimmage_td": "TD", "rec_yds": "rec yds", "rush_yds": "rush yds", "pass_yds": "pass yds",
               "pass_td": "pass TD", "receptions": "rec", "rush_att": "rush att", "rush_td": "rush TD", "rec_td": "rec TD"}


def _leg_label(leg):
    k = leg["kind"]
    if k == "spread":
        return f'{leg["team"]} {leg["line"]:+g}'
    if k == "moneyline":
        return f'{leg["team"]} ML'
    if k == "total":
        return f'{leg["op"]} {leg["line"]:g} total'
    if k == "team_total":
        return f'{leg["team"]} {leg["op"]} {leg["line"]:g}'
    st = {"scrimmage_td": "TD", "rec_yds": "rec yds", "rush_yds": "rush yds", "pass_yds": "pass yds",
          "pass_td": "pass TD", "receptions": "rec", "rush_att": "rush att", "rush_td": "rush TD", "rec_td": "rec TD"}
    return f'{leg["player"]} {leg["op"][0]}{leg["line"]:g} {st.get(leg["stat"], leg["stat"])}'


# ------------------------------------------------------------------ stats
def _profit(s):
    """Units won/lost at the suggested buy price (prob p pays 1/p per unit staked)."""
    size, p, r = s.get("size_u") or 0, s.get("price_prob"), s.get("result")
    if not size or not p or r not in ("win", "loss", "push"):
        return 0.0
    return size * (1 / p - 1) if r == "win" else (-size if r == "loss" else 0.0)


def summary():
    doc = load()
    S = doc["suggestions"]
    bets = [s for s in S if s.get("status") in ("bet", "conditional") and s.get("size_u")]
    graded = [s for s in bets if s.get("result") in ("win", "loss", "push")]
    rec = {k: sum(1 for s in graded if s["result"] == k) for k in ("win", "loss", "push")}
    risked = sum(s["size_u"] for s in graded if s["result"] != "push")
    pl = sum(_profit(s) for s in graded)
    by_cat = {}
    for s in graded:
        c = by_cat.setdefault(s["category"], {"win": 0, "loss": 0, "push": 0, "pl": 0.0, "n": 0})
        c[s["result"]] += 1
        c["pl"] += _profit(s)
        c["n"] += 1
    info = [s for s in S if s.get("status") == "info" and s.get("our_prob")]
    info_g = [s for s in info if s.get("result") in ("win", "loss")]
    cal = {"n": len(info_g), "expected": round(sum(s["our_prob"] for s in info_g), 2),
           "hits": sum(1 for s in info_g if s["result"] == "win"), "pending": len(info) - len(info_g)}
    edge = [s["our_prob"] - s["price_prob"] for s in bets if s.get("our_prob") and s.get("price_prob")]
    return {
        "record": rec, "units_pl": round(pl, 2), "risked_u": round(risked, 2),
        "roi": round(pl / risked, 3) if risked else None,
        "pending": sum(1 for s in bets if s.get("result") == "pending"),
        "total": len(S), "bets": len(bets), "avg_edge": round(sum(edge) / len(edge), 3) if edge else None,
        "by_category": by_cat, "model_calibration": cal,
        "expected_pl_pending": round(sum((s["our_prob"] / s["price_prob"] - 1) * s["size_u"]
                                         for s in bets if s.get("result") == "pending"
                                         and s.get("our_prob") and s.get("price_prob")), 2),
    }


def api_payload():
    doc = load()
    for s in doc["suggestions"]:
        s["profit_u"] = round(_profit(s), 2)
    return {"ok": True, "suggestions": doc["suggestions"], "summary": summary()}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "grade":
        for c in grade_all():
            print(*c)
        print(json.dumps(summary(), indent=2))
    elif cmd == "live":
        print(json.dumps(live(), indent=1)[:4000])
    elif cmd == "add":
        print(add(json.loads(sys.argv[2]))["id"])
    else:
        print(json.dumps(summary(), indent=2))
