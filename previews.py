"""Game Previews — a write-up for every game explaining why our number is what it is.

Lane-2 WIP (testing) until Sean signs off; pgo_comparison imports this optionally.

One markdown file per game at data/previews/<year>_wk<W>/<AWAY>-<HOME>.md:

    ---
    game_id: 401873100
    status: draft            # draft | ready  (only `ready` previews are published)
    written_at: 2026-11-18T15:00Z
    market_at_write: -4.5    # home-relative, negative = home favored (frozen)
    our_line_at_write: -6.5  # our number when written (frozen)
    ...rating snapshot per side...
    ---
    ## Why the number
    ## Assumptions
    ## Situational
    ## Updates

The frozen `*_at_write` fields are what the "at pick" records grade the model on, so
the Tuesday number stays honest even after ratings move later in the week. Drafts
are never published and never fail the build. Existing files are never overwritten.

Bets are entered once on the pick sheet (data/picks, gitignored); `export-bets`
writes the public data/previews/<wk>/bets.json the board renders (Sean chose to show
bets as soon as the preview publishes — previews tab only).

CLI:
    python3 previews.py draft <week> [year]        # write draft files for the slate
    python3 previews.py export-bets <week> [year]  # pick sheet -> public bets.json
    python3 previews.py check <week> [year]        # list status / gate problems
    python3 previews.py grade <week> [year]        # stamp finals + ATS results (after games)
"""

import csv
import html
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PREVIEWS_DIR = os.path.join(HERE, "data", "previews")
DRAFT_MARKER = "<!-- DRAFT"
SECTIONS = ("Why the number", "Assumptions", "Situational", "Psychological", "Trends & systems", "Updates")
ORD = {1: "1st", 2: "2nd", 3: "3rd"}


# ---- file format --------------------------------------------------------------

def week_dir(year, week):
    return os.path.join(PREVIEWS_DIR, f"{year}_wk{week}")


def _coerce(v):
    v = v.strip()
    if v in ("", "null", "None"):
        return None
    try:
        return float(v) if re.fullmatch(r"-?\d+(\.\d+)?", v) else v
    except ValueError:
        return v


def parse(text):
    """Return {meta: {...}, sections: {name: body}}; tolerant of missing sections."""
    meta, body = {}, text
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.lstrip().startswith("#"):
                k, v = line.split(":", 1)
                meta[k.strip()] = _coerce(v.split(" #", 1)[0])
        body = m.group(2)
    sections = {}
    for chunk in re.split(r"^## ", body, flags=re.M)[1:]:
        name, _, rest = chunk.partition("\n")
        sections[name.strip()] = rest.strip()
    return {"meta": meta, "sections": sections}


def load_week(year, week):
    """All previews for a week (drafts included), sorted by kickoff."""
    d = week_dir(year, week)
    out = []
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".md"):
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                p = parse(f.read())
            p["file"] = fn
            out.append(p)
    out.sort(key=lambda p: str(p["meta"].get("kickoff") or ""))
    return out


def gate_problems(p):
    """Why a `ready` preview can't publish (empty list = OK). Drafts aren't gated —
    they are simply left off the page."""
    probs = []
    s = p["sections"]
    why = s.get("Why the number", "")
    if not why or DRAFT_MARKER in why:
        probs.append("write-up still a draft")
    if not s.get("Assumptions"):
        probs.append("no assumptions listed")
    if "CHECK:" in s.get("Assumptions", ""):
        probs.append("unresolved CHECK in assumptions")
    for k in ("game_id", "market_at_write", "our_line_at_write", "written_at"):
        if p["meta"].get(k) is None:
            probs.append(f"missing {k}")
    return probs


def is_ready(p):
    return p["meta"].get("status") == "ready" and not gate_problems(p)


def at_write_lines(year, week):
    """{game_id: (market_at_write, our_line_at_write)} for READY previews — the
    model's 'at pick' line for grading."""
    out = {}
    for p in load_week(year, week):
        if is_ready(p):
            m = p["meta"]
            out[str(m["game_id"]).split(".")[0]] = (m["market_at_write"], m["our_line_at_write"])
    return out


# ---- line display -----------------------------------------------------------------

def fmt_line(home_rel, home_abbr, away_abbr):
    """Home-relative spread (neg = home fav) -> 'HOU -6.5' / 'PK'."""
    if home_rel is None:
        return "—"
    if abs(home_rel) < 1e-9:
        return "PK"
    fav, n = (home_abbr, -home_rel) if home_rel < 0 else (away_abbr, home_rel)
    return f"{fav} -{n:g}"


# ---- drafting -----------------------------------------------------------------------

def _team_rows():
    with open(os.path.join(HERE, "data", "ratings.csv"), newline="", encoding="utf-8") as f:
        return {r["team"]: r for r in csv.DictReader(f)}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _last_game_dates(year, week):
    """{team displayName: (last kickoff datetime, weeks back)} from the 2 prior weeks."""
    import picks
    from espn_api import fetch_json
    out = {}
    for back in (1, 2):
        w = week - back
        if w < 1:
            break
        sb = fetch_json(picks.SCOREBOARD.format(year=year, week=w))
        for e in sb.get("events", []):
            ko = picks._parse_iso(e.get("date", ""))
            for t in e["competitions"][0]["competitors"]:
                name = t["team"]["displayName"]
                if name not in out:
                    out[name] = (ko, back)
    return out


def situational(L, rows, last):
    """Plain-language situational factors for the draft (Sean's standing checklist:
    rest/bye, short week, divisional, primetime, neutral). Qualitative — the number
    only carries what the ratings + HFA carry."""
    items = []
    h, a = rows.get(L["home"], {}), rows.get(L["away"], {})
    if h.get("division") and h.get("division") == a.get("division") and h.get("conf") == a.get("conf"):
        items.append("Divisional game.")
    if L["neutral"]:
        items.append("Neutral site: no home-field edge in the number.")
    if L["prime"] and not L["neutral"]:
        items.append("Primetime: +0.5 home field in the number.")
    elif L["prime"]:
        items.append("Primetime.")
    ko = L["kickoff"]
    for side in ("away", "home"):
        name, abbr = L[side], L[f"{side}_abbr"]
        prev = last.get(name)
        if not prev or not ko:
            continue
        pko, back = prev
        days = (ko - pko).days
        if back == 2:
            items.append(f"{abbr} off a bye ({days} days rest).")
        elif days <= 5:
            items.append(f"{abbr} on a short week ({days} days rest).")
        elif days >= 9:
            items.append(f"{abbr} on extra rest ({days} days).")
    return items


def _snapshot(L, rows, hfa, default_hfa):
    snap = {}
    for side in ("away", "home"):
        r = rows.get(L[side], {})
        snap[f"{side}_qb"] = r.get("qb_name")
        snap[f"{side}_qb_value"] = _f(r.get("qb_value"))
        snap[f"{side}_off"] = _f(r.get("off_value"))
        snap[f"{side}_def"] = _f(r.get("def_value"))
        snap[f"{side}_total"] = round(snap[f"{side}_qb_value"] + snap[f"{side}_off"] + snap[f"{side}_def"], 1)
    snap["hfa"] = 0.0 if L["neutral"] else hfa.get(L["home"], default_hfa) + (0.5 if L["prime"] else 0.0)
    return snap


PRICED_CSV = os.path.join(HERE, "data", "priced_injuries.csv")
LONG_TERM = ("IR", "PUP", "NA", "DNR", "Suspended")


def load_priced(year, week):
    """{team abbr: [rows]} — our availability calls for the week (the source of truth
    for previews; Sleeper only fills gaps and flags conflicts)."""
    out = defaultdict(list)
    if not os.path.exists(PRICED_CSV):
        return out
    with open(PRICED_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if str(r.get("season")) == str(year) and str(r.get("week")) == str(week):
                out[r["team"]].append(r)
    return out


def _norm(n):
    return re.sub(r"[^a-z]", "", (n or "").lower().replace("jr.", "").replace("iii", ""))


def _round_half(x):
    import math
    return math.floor(x * 2 + 0.5) / 2


def _line_if(snap, team_side, swing):
    raw = -(snap["home_total"] - snap["away_total"] + snap["hfa"])
    raw = raw - swing if team_side == "home" else raw + swing
    return _round_half(raw)


def assumptions_for(L, snap, priced, report):
    """Assumption bullets written as OUR calls: priced in or not, and what the
    number becomes if the call is wrong. Unpriced Sleeper starters become CHECK
    items (which block `ready`) until we make a call."""
    ha, aa = L["home_abbr"], L["away_abbr"]
    out, long_term = [], []
    for side in ("away", "home"):
        abbr = L[f"{side}_abbr"]
        calls = priced.get(abbr, [])
        covered = set()
        for r in calls:
            for nm in r["player"].split(" + "):
                covered.add(_norm(nm))
        sl = {}
        for inj in ((report.get("teams") or {}).get(abbr) or {}).get("injuries", []):
            sl[_norm(inj["name"])] = inj
        for r in calls:
            who = f'{abbr} {r["string"]} string {r["position"]} {r["player"]}'
            status_note = f' ({r["note"]})' if r.get("note") else ""
            if r["priced"].upper() == "OUT":
                head = f"Priced OUT: {who}{status_note}. In the number: {r['impact']}."
                verb = "plays" if " + " not in r["player"] else "play"
            else:
                head = f"Priced PLAYING: {who}{status_note}. {r['impact'][:1].upper() + r['impact'][1:]}."
                verb = "sits" if " + " not in r["player"] else "sit"
            sw = r.get("swing_if_wrong")
            if sw not in (None, ""):
                sw = float(sw)
                if abs(sw) >= 0.05:
                    nl = _line_if(snap, side, sw)
                    moved = (f"our line moves to {fmt_line(nl, ha, aa)}"
                             if L["my_spread"] is None or abs(nl - L["my_spread"]) > 1e-9
                             else f"our line stays {fmt_line(nl, ha, aa)} after rounding")
                    head += (f" If he {verb}: {abbr} {sw:+g}, {moved}."
                             ).replace("If he play:", "If they play:").replace("If he sit:", "If they sit:")
            # conflicts with Sleeper
            for nm in r["player"].split(" + "):
                inj = sl.get(_norm(nm))
                if r.get("sleeper_ack") == "Y":
                    continue   # we've seen Sleeper's status and made our call anyway
                if r["priced"].upper() == "PLAYING" and inj and inj.get("status") in ("Out", "IR", "Doubtful") + LONG_TERM:
                    head += f" CHECK: Sleeper lists {nm} {inj['status']}."
            out.append(head)
        for key, inj in sl.items():
            if key in covered or inj.get("role") not in ("STARTER", "EFFECTIVE"):
                continue
            if inj.get("role") == "STARTER" and inj.get("order") not in (1, None) \
                    and inj.get("status") not in LONG_TERM:
                continue   # Sleeper tags some deep backups STARTER (returners etc.)
            string = ORD.get(inj.get("order"), f"{inj.get('order')}th") + " string"
            if inj.get("role") == "EFFECTIVE":
                string += " (starting for an injured starter)"
            who = (f"{abbr} {string} {inj.get('position')} {inj['name']} "
                   f"({(inj.get('body_part') or '?').lower()})")
            if inj.get("status") in LONG_TERM:
                long_term.append(f"{who}, {inj['status']}")
            else:
                out.append(f"CHECK: {who} is {inj.get('status')} on Sleeper and we haven't made a call yet.")
    if long_term:
        out.append("Long-term absences already in the ratings: " + "; ".join(long_term) + ".")
    return out


def _espn_prev(year, week, overrides):
    """{espn abbr: {opp, score, upset_win, blowout_loss_as_fav}} from LAST week only
    (a bye in between resets the spot)."""
    import picks
    from espn_api import fetch_json
    out = {}
    if week <= 1:
        return out
    for e in fetch_json(picks.SCOREBOARD.format(year=year, week=week - 1)).get("events", []):
        c = e["competitions"][0]
        comp = {t["homeAway"]: t for t in c["competitors"]}
        if "home" not in comp or not c.get("status", {}).get("type", {}).get("completed"):
            continue
        ov = overrides.get(e.get("id"), {})
        odds = c.get("odds") or []
        m = ov.get("market", odds[0].get("spread") if odds else None)
        hs, as_ = picks._num(comp["home"].get("score")), picks._num(comp["away"].get("score"))
        if hs is None or as_ is None:
            continue
        for side, t in comp.items():
            ab = t["team"]["abbreviation"]
            opp = comp["away" if side == "home" else "home"]["team"]["abbreviation"]
            mine, theirs = (hs, as_) if side == "home" else (as_, hs)
            d = {"opp": opp, "score": f"{'W' if mine > theirs else 'L' if mine < theirs else 'T'} {mine}-{theirs}"}
            if m is not None:
                dog_pts = m if side == "home" else -m   # >0 => this team was the dog
                d["upset_win"] = dog_pts >= 3 and mine > theirs
                d["blowout_loss_as_fav"] = dog_pts < 0 and (mine - theirs) <= -14
            out[ab] = d
    return out


def build_context(L, e, year, week, kbrow, team_ratings, prev):
    """Game dict for preview_context.trends / psych_flags."""
    import preview_context as PC
    a, h = PC.kb_abbr(L["away_abbr"]), PC.kb_abbr(L["home_abbr"])
    odds = (e["competitions"][0].get("odds") or [{}])[0]
    recs = {}
    for t in e["competitions"][0]["competitors"]:
        summ = ((t.get("records") or [{}])[0] or {}).get("summary", "")
        m = re.match(r"(\d+)-(\d+)", summ)
        if m:
            recs[PC.kb_abbr(t["team"]["abbreviation"])] = (int(m.group(1)), int(m.group(2)))
    sched = [g for g in PC._games() if g["season"] == year]

    def nxt(team):
        for g in sched:
            if g["week"] > week and team in (g["away"], g["home"]):
                opp = g["home"] if g["away"] == team else g["away"]
                return {"opp": opp, "prime": (g["gametime"] or "") >= "19:00",
                        "strong": (team_ratings.get(opp) or 0) >= 3.0}
        return {}

    def road_streak(team):
        streak = 1 if team == a else 0
        if not streak:
            return 0
        for g in sorted((g for g in sched if g["week"] < week and team in (g["away"], g["home"])),
                        key=lambda g: -g["week"]):
            if g["away"] == team or g["location"] == "Neutral":
                streak += 1
            else:
                break
        return streak

    ko = L["kickoff"]
    return {
        "season": year, "week": week, "away": a, "home": h,
        "market": L["market"], "total": odds.get("overUnder"),
        "div": bool((kbrow or {}).get("div")), "neutral": L["neutral"],
        "gametime": (kbrow or {}).get("gametime"), "weekday": (kbrow or {}).get("weekday"),
        "away_rest": (kbrow or {}).get("away_rest"), "home_rest": (kbrow or {}).get("home_rest"),
        "away_coach": (kbrow or {}).get("away_coach"), "home_coach": (kbrow or {}).get("home_coach"),
        "month": ko.month if ko else None,
        "away_prev": prev.get(L["away_abbr"]), "home_prev": prev.get(L["home_abbr"]),
        "away_next": nxt(a), "home_next": nxt(h),
        "records": recs, "team_ratings": team_ratings, "away_road_streak": road_streak(a),
    }


def render_draft(L, snap, assumptions, sit, psych, trend_lines, now_iso, year, week):
    ha, aa = L["home_abbr"], L["away_abbr"]
    meta = {
        "game_id": L["game_id"], "season": year, "week": week,
        "away": L["away"], "home": L["home"], "away_abbr": aa, "home_abbr": ha,
        "kickoff": L["kickoff_iso"], "status": "draft", "written_at": now_iso,
        "market_at_write": L["market"], "our_line_at_write": L["my_spread"],
        "edge_at_write": L["edge"], **snap,
    }
    gap = round(snap["home_total"] - snap["away_total"], 1)
    qb_gap = round(snap["home_qb_value"] - snap["away_qb_value"], 1)
    why = (
        f"{DRAFT_MARKER}: replace with the real write-up, then set status: ready -->\n"
        f"Our number is **{fmt_line(L['my_spread'], ha, aa)}** against a market of "
        f"**{fmt_line(L['market'], ha, aa)}**. {ha} rates {snap['home_total']:+g} and {aa} "
        f"{snap['away_total']:+g}, a {abs(gap):g}-point gap to "
        f"{ha if gap >= 0 else aa}, plus {snap['hfa']:g} for home field. "
        f"At QB it's {snap['home_qb']} ({snap['home_qb_value']:+g}) vs "
        f"{snap['away_qb']} ({snap['away_qb_value']:+g}), {abs(qb_gap):g} to "
        f"{ha if qb_gap >= 0 else aa}."
    )
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {'' if v is None else v}")
    lines += ["---", "## Why the number", why, "", "## Assumptions"]
    lines += [f"- {x}" for x in assumptions] or ["- (none yet)"]
    lines += ["", "## Situational"]
    lines += [f"- {x}" for x in sit] or ["- Nothing notable."]
    lines += ["", "## Psychological"]
    lines += [f"- {x}" for x in psych] or ["- Nothing flagged."]
    lines += ["", "## Trends & systems"]
    lines += [f"- {x}" for x in trend_lines] or ["- No angle with a big enough sample."]
    lines += ["", "## Updates", ""]
    return "\n".join(lines)


def draft(week, year):
    """Write a draft for every game on the slate. Never overwrites."""
    import picks
    import injuries
    import sleeper
    import preview_context as PC
    from espn_api import fetch_json
    rows = _team_rows()
    ratings = picks.load_ratings()
    hfa, default_hfa = picks.load_hfa()
    overrides = picks.load_line_overrides()
    now = picks._now()
    now_iso = now.strftime("%Y-%m-%dT%H:%MZ")
    try:
        report = injuries.build_report(sleeper.get_players())
    except Exception as exc:  # noqa: BLE001 — drafts still useful without injuries
        print(f"  (injury feed unavailable: {exc})")
        report = {}
    priced = load_priced(year, week)
    last = _last_game_dates(year, week)
    prev = _espn_prev(year, week, overrides)
    kbweek = {(g["away"], g["home"]): g for g in PC._games() if g["season"] == year and g["week"] == week}
    team_ratings = {}
    d = week_dir(year, week)
    os.makedirs(d, exist_ok=True)
    events = fetch_json(picks.SCOREBOARD.format(year=year, week=week)).get("events", [])
    for e in events:
        for t in e["competitions"][0]["competitors"]:
            team_ratings[PC.kb_abbr(t["team"]["abbreviation"])] = ratings.get(t["team"]["displayName"])
    wrote = skipped = 0
    for e in events:
        L = picks._line_for_event(e, ratings, hfa, default_hfa, overrides, now)
        if not L:
            continue
        path = os.path.join(d, f"{L['away_abbr']}-{L['home_abbr']}.md")
        if os.path.exists(path):
            skipped += 1
            continue
        snap = _snapshot(L, rows, hfa, default_hfa)
        kbrow = kbweek.get((PC.kb_abbr(L["away_abbr"]), PC.kb_abbr(L["home_abbr"])))
        ctx = build_context(L, e, year, week, kbrow, team_ratings, prev)
        ctx["away_qb"], ctx["home_qb"] = snap["away_qb"], snap["home_qb"]
        psych = PC.psych_flags(ctx)
        trend_lines = [PC.fmt_trend(t) for t in PC.trends(ctx)]
        text = render_draft(L, snap, assumptions_for(L, snap, priced, report),
                            situational(L, rows, last), psych, trend_lines, now_iso, year, week)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        wrote += 1
    print(f"Week {week}: wrote {wrote} drafts, kept {skipped} existing -> {d}")


def export_bets(week, year):
    """Pick sheet -> public bets.json (side, confidence, line at pick)."""
    import picks
    saved = picks.load_picks(year, week)
    bets = {gid: {"side": p.get("side"), "confidence": p.get("confidence"),
                  "market_at_pick": p.get("market_at_pick")}
            for gid, p in saved.items() if p.get("side")}
    d = week_dir(year, week)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "bets.json"), "w", encoding="utf-8") as f:
        json.dump({"season": year, "week": week, "bets": bets}, f, indent=2)
    print(f"Week {week}: exported {len(bets)} bets")


def load_bets(year, week):
    try:
        with open(os.path.join(week_dir(year, week), "bets.json"), encoding="utf-8") as f:
            return json.load(f).get("bets", {})
    except (OSError, ValueError):
        return {}


def latest_week():
    """(year, week) of the newest week dir holding a READY preview, else None."""
    best = None
    if not os.path.isdir(PREVIEWS_DIR):
        return None
    for name in os.listdir(PREVIEWS_DIR):
        m = re.fullmatch(r"(\d{4})_wk(\d+)", name)
        if m:
            y, w = int(m.group(1)), int(m.group(2))
            if any(is_ready(p) for p in load_week(y, w)) and (best is None or (y, w) > best):
                best = (y, w)
    return best


# ---- board panel ------------------------------------------------------------------

TAB_START, TAB_END = "<!--previews-tab-start-->", "<!--previews-tab-end-->"
PANEL_START, PANEL_END = "<!--previews-panel-start-->", "<!--previews-panel-end-->"
TAB_ANCHOR = 'data-panel="comparison">PGO Model</button>'
PANEL_ANCHOR = "</section><!-- /panel-method -->"

PANEL_CSS = """<style>
#panel-previews .gp-records{width:100%;border-collapse:collapse;margin:8px 0 6px;font-size:14px}
#panel-previews .gp-records th,#panel-previews .gp-records td{padding:8px 10px;border-bottom:1px solid var(--border);text-align:center}
#panel-previews .gp-records th:first-child{text-align:left}
#panel-previews .gp-desc{display:block;color:var(--mut);font-weight:400;font-size:12px}
#panel-previews .gp-fine{color:var(--mut);font-size:12px;margin:4px 0 18px;max-width:78ch}
#panel-previews .gp-card{border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin:14px 0;background:var(--panel)}
#panel-previews .gp-head{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 14px;align-items:baseline}
#panel-previews .gp-head h3{margin:0;font-size:18px}
#panel-previews .gp-kick{color:var(--mut);font-size:13px}
#panel-previews .gp-lines{display:flex;flex-wrap:wrap;gap:6px 18px;margin:8px 0;font-size:14px}
#panel-previews .gp-lines b{font-variant-numeric:tabular-nums}
#panel-previews .gp-bet{display:inline-block;background:var(--accent,#1a7f37);color:#fff;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:700}
#panel-previews .gp-snap{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0 10px}
#panel-previews .gp-snap th,#panel-previews .gp-snap td{padding:4px 6px;border-bottom:1px solid var(--border);text-align:center}
#panel-previews .gp-snap th:first-child,#panel-previews .gp-snap td:first-child{text-align:left}
#panel-previews .gp-card h4{margin:12px 0 4px;font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
#panel-previews .gp-card ul{margin:0;padding-left:18px}
#panel-previews .gp-asof{color:var(--mut);font-size:12px}
#panel-previews .gp-weeknav{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 4px}
#panel-previews .gp-weekbtn{border:1px solid var(--border);border-radius:999px;background:var(--panel);color:var(--ink);padding:5px 12px;font:inherit;font-size:13px;cursor:pointer}
#panel-previews .gp-weekbtn[aria-pressed="true"]{background:var(--ink);color:var(--panel)}
#panel-previews .gp-result{margin:6px 0;font-size:14px}
#panel-previews .gp-win{color:#1a7f37;font-weight:700}
#panel-previews .gp-loss{color:#cf222e;font-weight:700}
@media (max-width:600px){#panel-previews .gp-records{font-size:12px}#panel-previews .gp-records th,#panel-previews .gp-records td{padding:6px 4px}}
</style>"""


def _md_inline(s):
    s = html.escape(s)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)


def _md_block(s):
    """Paragraphs, '- ' lists and '### ' sub-heads; enough for these write-ups."""
    out, items = [], []
    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{_md_inline(i)}</li>" for i in items) + "</ul>")
            items.clear()
    for para in re.sub(r"<!--.*?-->", "", s, flags=re.S).split("\n"):
        line = para.strip()
        if line.startswith("- "):
            items.append(line[2:])
            continue
        flush()
        if line.startswith("### "):
            out.append(f"<p><b>{_md_inline(line[4:])}</b></p>")
        elif line:
            out.append(f"<p>{_md_inline(line)}</p>")
    flush()
    return "".join(out)


def _rec(t):
    if not isinstance(t, dict) or not (t.get("win") or t.get("loss") or t.get("push")):
        return "&mdash;"
    s = f'{t.get("win", 0)}-{t.get("loss", 0)}'
    return s + (f'-{t["push"]}' if t.get("push") else "")


def _records_html(records):
    sr = (records or {}).get("season_record") or {}
    rows = (("McCabe Bets", "mine", "my 5 weekly picks"),
            ("Strict model", "model", "the edge side of every game"),
            ("Biggest edge", "top5", "the model's 5 largest edges each week"))
    body = "".join(
        f'<tr><th scope="row">{lab}<span class="gp-desc">{desc}</span></th>'
        f'<td>{_rec((sr.get(k) or {}).get("open"))}</td>'
        f'<td>{_rec((sr.get(k) or {}).get("pick"))}</td>'
        f'<td>{_rec((sr.get(k) or {}).get("close"))}</td></tr>'
        for lab, k, desc in rows)
    year = html.escape(str((records or {}).get("season_year", "")))
    thru = html.escape(str((records or {}).get("through_week", "")))
    return (f'<h3>{year} ATS record <span class="gp-desc" style="display:inline">'
            f'&mdash; through Week {thru}</span></h3>'
            '<table class="gp-records"><thead><tr><th>Record</th><th>vs Open</th>'
            '<th>At pick</th><th>vs Close</th></tr></thead><tbody>' + body +
            '</tbody></table><p class="gp-fine">At pick = graded against the line '
            'available when the pick was made (for the model: when the preview was '
            'written). Tracked from Week 10 for McCabe Bets (earlier picks were logged after '
            'the fact) and from Week 11, when previews began, for the model.</p>')


def _card(p, bet):
    m, s = p["meta"], p["sections"]
    ha, aa = m.get("home_abbr"), m.get("away_abbr")
    title = f'{html.escape(str(m.get("away")))} at {html.escape(str(m.get("home")))}'
    try:
        ko = datetime.strptime(str(m.get("kickoff")), "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        kick = ko.strftime("%a %b %-d, %H:%M UTC")
    except ValueError:
        kick = html.escape(str(m.get("kickoff") or ""))
    badge = ""
    if bet and bet.get("side") in ("home", "away"):
        team = ha if bet["side"] == "home" else aa
        line = bet.get("market_at_pick")
        if line is None:
            line = m.get("market_at_write")
        side_line = "" if line is None else f" {(line if bet['side'] == 'home' else -line):+g}"
        conf = f' &middot; confidence {int(bet["confidence"])}' if bet.get("confidence") else ""
        badge = f'<span class="gp-bet">McCabe Bet: {html.escape(str(team))}{side_line}{conf}</span>'
    edge = m.get("edge_at_write")
    snap = "".join(
        f'<tr><td>{html.escape(str(m.get(f"{sd}_abbr")))}</td>'
        f'<td>{html.escape(str(m.get(f"{sd}_qb") or ""))} ({(m.get(f"{sd}_qb_value") or 0):+g})</td>'
        f'<td>{(m.get(f"{sd}_off") or 0):+g}</td><td>{(m.get(f"{sd}_def") or 0):+g}</td>'
        f'<td><b>{(m.get(f"{sd}_total") or 0):+g}</b></td></tr>'
        for sd in ("away", "home"))
    parts = [
        f'<article class="gp-card" id="gp-{html.escape(str(aa))}-{html.escape(str(ha))}">',
        f'<div class="gp-head"><h3>{title}</h3><span class="gp-kick">{kick}</span></div>',
        '<div class="gp-lines">'
        f'<span>Market: <b>{fmt_line(m.get("market_at_write"), ha, aa)}</b></span>'
        f'<span>McCabe line: <b>{fmt_line(m.get("our_line_at_write"), ha, aa)}</b></span>'
        f'<span>Edge: <b>{"—" if edge is None else f"{abs(edge):g}"}</b></span>'
        f'{badge}</div>',
        _result_html(m),
        '<table class="gp-snap"><thead><tr><th>Team</th><th>QB</th><th>Off</th><th>Def</th>'
        f'<th>Total</th></tr></thead><tbody>{snap}</tbody></table>'
        f'<p class="gp-asof">Home field: {(m.get("hfa") or 0):g} &middot; written '
        f'{html.escape(str(m.get("written_at") or ""))}</p>',
        _md_block(s.get("Why the number", "")),
    ]
    for name, label in (("Assumptions", "What we're assuming"), ("Situational", "Situational"),
                        ("Psychological", "Psychological spots"),
                        ("Trends & systems", "Trends & systems (for interest, not endorsed)"),
                        ("Updates", "Updates")):
        if s.get(name):
            parts.append(f"<h4>{label}</h4>{_md_block(s[name])}")
    parts.append("</article>")
    return "".join(parts)


def published_weeks():
    """[(year, week)] holding at least one READY preview, newest first."""
    out = []
    if os.path.isdir(PREVIEWS_DIR):
        for name in os.listdir(PREVIEWS_DIR):
            m = re.fullmatch(r"(\d{4})_wk(\d+)", name)
            if m:
                y, w = int(m.group(1)), int(m.group(2))
                if any(is_ready(p) for p in load_week(y, w)):
                    out.append((y, w))
    return sorted(out, reverse=True)


FIRST_WEEK_NOTE = ("Game previews began in Week 11 of the 2026 season. "
                   "Earlier weeks have ratings and picks but no previews.")

WEEK_JS = """<script>(() => {
  const panel = document.getElementById('panel-previews');
  if (!panel) return;
  const btns = [...panel.querySelectorAll('.gp-weekbtn')];
  btns.forEach(b => b.addEventListener('click', () => {
    btns.forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    panel.querySelectorAll('.gp-week').forEach(w => { w.hidden = w.dataset.week !== b.dataset.week; });
  }));
})();</script>"""


def _result_html(m):
    """Final score + how the Tuesday number and the bet graded (set by `grade`)."""
    if m.get("final_score") is None:
        return ""
    def tag(r):
        r = str(r or "")
        cls = {"win": "gp-win", "loss": "gp-loss"}.get(r, "")
        return f'<span class="{cls}">{html.escape(r.upper() or "NO PLAY")}</span>'
    out = f'<p class="gp-result">Final: <b>{html.escape(str(m["final_score"]))}</b> &middot; Model side: {tag(m.get("model_result"))}'
    if m.get("bet_result"):
        out += f' &middot; McCabe Bet: {tag(m.get("bet_result"))}'
    return out + "</p>"


def render_panel(weeks, records):
    """Newest week shown first; older weeks one click away (graded once final)."""
    nav, blocks = [], []
    for i, (year, week) in enumerate(weeks):
        previews = [p for p in load_week(year, week) if is_ready(p)]
        bets = load_bets(year, week)
        cards = "".join(_card(p, bets.get(str(p["meta"].get("game_id")).split(".")[0]))
                        for p in previews)
        key = f"{year}-{week}"
        nav.append(f'<button type="button" class="gp-weekbtn" data-week="{key}" '
                   f'aria-pressed="{"true" if i == 0 else "false"}">Week {week}</button>')
        blocks.append(f'<div class="gp-week" data-week="{key}"{"" if i == 0 else " hidden"}>'
                      f'<h2>Week {week} Game Previews</h2>{cards}</div>')
    return (
        PANEL_START +
        '<section class="panel" id="panel-previews" role="tabpanel" '
        'aria-labelledby="tab-previews" hidden>' + PANEL_CSS +
        '<p class="gp-fine">Why our number is what it is, written early in the week. '
        'Each preview lists the injury assumptions it was written on; later changes '
        f'are added as dated updates. {FIRST_WEEK_NOTE}</p>' +
        _records_html(records) +
        (f'<div class="gp-weeknav" aria-label="Choose a week">{"".join(nav)}</div>'
         if len(weeks) > 1 else "") +
        "".join(blocks) + WEEK_JS +
        "</section>" + PANEL_END
    )


TAB_HTML = (TAB_START +
            '\n    <button type="button" class="tab" id="tab-previews" role="tab"\n'
            '      aria-selected="false" aria-controls="panel-previews" tabindex="-1"\n'
            '      data-panel="previews">Game Previews</button>' + TAB_END)


def strip_panel(page):
    """Remove a previously injected Game Previews tab + panel, so the board's own
    tab/panel validation sees the page exactly as pgo_comparison built it."""
    page = re.sub(re.escape(TAB_START) + ".*?" + re.escape(TAB_END), "", page, flags=re.S)
    return re.sub(r"\n?" + re.escape(PANEL_START) + ".*?" + re.escape(PANEL_END) + r"\n?", "", page, flags=re.S)


def inject_panel(page, records=None, which=None):
    """Add/replace the Game Previews tab + panel. Idempotent; no-op when there is no
    ready preview or the anchors are missing."""
    page = strip_panel(page)
    weeks = [which] if which else published_weeks()
    if not weeks or page.count(TAB_ANCHOR) != 1 or page.count(PANEL_ANCHOR) != 1:
        return page
    page = page.replace(TAB_ANCHOR, TAB_ANCHOR + TAB_HTML, 1)
    return page.replace(PANEL_ANCHOR, PANEL_ANCHOR + "\n" + render_panel(weeks, records) + "\n", 1)


def grade(week, year):
    """Stamp final score + ATS results into each READY preview (vs the frozen
    market_at_write for the model; vs market_at_pick for the bet)."""
    import picks
    from espn_api import fetch_json
    bets = load_bets(year, week)
    finals = {}
    for e in fetch_json(picks.SCOREBOARD.format(year=year, week=week)).get("events", []):
        c = e["competitions"][0]
        if not c.get("status", {}).get("type", {}).get("completed"):
            continue
        comp = {t["homeAway"]: t for t in c["competitors"]}
        hs, as_ = picks._num(comp["home"].get("score")), picks._num(comp["away"].get("score"))
        finals[str(e["id"])] = (comp["away"]["team"]["abbreviation"], as_,
                                comp["home"]["team"]["abbreviation"], hs)
    n = 0
    for p in load_week(year, week):
        m = p["meta"]
        gid = str(m.get("game_id")).split(".")[0]
        if not is_ready(p) or gid not in finals or m.get("final_score") is not None:
            continue
        aa, as_, ha, hs = finals[gid]
        am = hs - as_
        side = picks._model_side(m["our_line_at_write"], m["market_at_write"])
        extra = {"final_score": f"{aa} {as_}, {ha} {hs}",
                 "model_result": picks._grade_side(side, m["market_at_write"], am) or "no play"}
        b = bets.get(gid)
        if b and b.get("side"):
            line = b.get("market_at_pick") if b.get("market_at_pick") is not None else m["market_at_write"]
            extra["bet_result"] = picks._grade_side(b["side"], line, am)
        path = os.path.join(week_dir(year, week), p["file"])
        with open(path, encoding="utf-8") as f:
            text = f.read()
        add = "".join(f"{k}: {v}\n" for k, v in extra.items())
        text = text.replace("\n---\n", "\n" + add + "---\n", 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        n += 1
    print(f"Week {week}: graded {n} previews")


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 2 or a[0] not in ("draft", "export-bets", "check", "grade"):
        print(__doc__)
        return 1
    week = int(a[1])
    year = int(a[2]) if len(a) > 2 else 2026
    if a[0] == "draft":
        draft(week, year)
    elif a[0] == "export-bets":
        export_bets(week, year)
    elif a[0] == "grade":
        grade(week, year)
    else:
        for p in load_week(year, week):
            probs = gate_problems(p)
            st = p["meta"].get("status")
            print(f'{p["file"]:<14} {st:<6} {"OK" if not probs else "; ".join(probs)}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
