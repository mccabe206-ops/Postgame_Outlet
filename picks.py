"""Weekly pick-sheet data layer for the McCabe Method.

Fetches the week's NFL matchups + market spread from ESPN, computes Sean's
predicted spread from the current power ratings, and persists his picks (side +
confidence) to a PRIVATE, gitignored file — one per week.

Lock rule: each game locks individually at kickoff. A pick for a game can be
changed freely until that game's kickoff; after kickoff it is frozen.

Picks are stored per week at:  data/picks/week_<season>_<week>.json  (gitignored)

Stdlib only. Reuses espn_api + the same ratings/HFA math as spreads.py/results.py.
"""

import json
import os
from datetime import datetime, timezone

from espn_api import fetch_json
from release_ratings import load_release_rows

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PICKS_DIR = os.path.join(DATA, "picks")
LINE_OVERRIDES = os.path.join(DATA, "line_overrides.json")
RECORDS_JSON = os.path.join(DATA, "records.json")

SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
              "scoreboard?dates={year}&seasontype=2&week={week}")
SCOREBOARD_NOW = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
                  "scoreboard")
SUMMARY = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
           "summary?event={eid}")

REVEAL_LEAD_SECONDS = 3600  # picks become public 1 hour before kickoff (phase 2)
MAX_PICKS = 5               # confidence pool: pick exactly 5 games
CONF_WEIGHTS = (1, 2, 3, 4, 5)  # each used at most once across the 5 picks


# ---- ratings math (mirror spreads.py) ---------------------------------------

def load_ratings():
    out = {}
    for r in load_release_rows(os.path.join(DATA, "ratings.csv")):
        out[r["team"]] = round(
            float(r["qb_value"] or 0)
            + float(r["off_value"] or 0)
            + float(r["def_value"] or 0), 1)
    return out


def load_hfa():
    import csv
    hfa, default = {}, 1.5
    path = os.path.join(DATA, "hfa.csv")
    if os.path.exists(path):
        for r in csv.DictReader(open(path, newline="")):
            if r["team"] == "DEFAULT":
                default = float(r["home_field"])
            else:
                hfa[r["team"]] = float(r["home_field"])
    return hfa, default


def load_line_overrides():
    """Manual per-game line overrides, keyed by ESPN game_id (string).

    Two purposes:
      - "market": a home-relative market spread (neg = home favored) to use when
        ESPN drops its odds after kickoff, or to freeze a closing/kickoff line.
      - "neutral": force neutral-site (HFA = 0) when ESPN's own neutralSite flag
        is missing. (ESPN usually sets it, in which case no override is needed.)

    File: data/line_overrides.json — { "<game_id>": {"market": -3.5, "neutral": true, ...} }
    Returns {} if the file is absent or unreadable.
    """
    if not os.path.exists(LINE_OVERRIDES):
        return {}
    try:
        with open(LINE_OVERRIDES) as f:
            raw = json.load(f)
    except (ValueError, OSError):
        return {}
    # drop any documentation keys (leading underscore)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def load_config():
    import csv
    cfg = {}
    path = os.path.join(DATA, "config.csv")
    if os.path.exists(path):
        for r in csv.DictReader(open(path, newline="")):
            cfg[r["key"]] = r["value"]
    return cfg


def _is_primetime(iso_utc):
    try:
        return int(iso_utc[11:13]) >= 23 or int(iso_utc[11:13]) <= 4
    except (ValueError, IndexError):
        return False


def _round_half(x):
    return round(x * 2) / 2


def _now():
    return datetime.now(timezone.utc)


def _parse_iso(iso_utc):
    """ESPN gives e.g. '2024-09-06T00:40Z'. Return aware datetime or None."""
    if not iso_utc:
        return None
    try:
        return datetime.strptime(iso_utc, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        except ValueError:
            return None


# ---- week + picks ------------------------------------------------------------

def current_week_year():
    """Ask ESPN what week/season it is right now.

    Only the REGULAR season (season.type == 2) maps 1:1 to this sheet's weeks. In
    the preseason/offseason ESPN's `week.number` is a PRESEASON week — feeding it
    into the regular-season URL would silently skip Week 1 (e.g. preseason wk 2 ->
    regular wk 2). So outside the regular season we default to regular Week 1.
    """
    sb = fetch_json(SCOREBOARD_NOW)
    wk = sb.get("week", {}).get("number")
    yr = sb.get("season", {}).get("year")
    stype = sb.get("season", {}).get("type")
    if stype != 2:
        wk = 1
    return wk, yr


def picks_path(season, week):
    return os.path.join(PICKS_DIR, f"week_{season}_{week}.json")


def load_picks(season, week):
    """Return {game_id: {"side": "home"/"away", "confidence": 1-5}} or {}."""
    path = picks_path(season, week)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get("picks", {})
    return {}


def save_pick(season, week, game_id, side, confidence, games_index, snapshot=None):
    """Persist one pick under the confidence-pool rules.

    Rules enforced here (server-side — the source of truth):
      - A game locked at kickoff cannot be added, changed, or cleared.
      - At most MAX_PICKS (5) games may be picked at once.
      - Each confidence weight in CONF_WEIGHTS (1..5) is used at most once —
        no two picks share the same star rating.

    games_index: {game_id: kickoff_iso} used to enforce the per-game lock.
    snapshot: optional {"market", "my_line", "edge"} captured live at save time so
        each pick records the market line (and edge) it was made against. Captured
        when a game is first picked or its SIDE changes; preserved across a pure
        confidence change so it stays the line you actually committed to.
    Returns (ok, message).
    """
    kickoff = _parse_iso(games_index.get(game_id))
    locked_now = bool(kickoff and _now() >= kickoff)

    os.makedirs(PICKS_DIR, exist_ok=True)
    path = picks_path(season, week)
    doc = {"season": season, "week": week, "picks": {}}
    if os.path.exists(path):
        with open(path) as f:
            doc = json.load(f)
    doc.setdefault("picks", {})
    picks = doc["picks"]

    # --- clearing a pick ---
    if side is None:
        if game_id in picks and locked_now:
            return False, "Game has kicked off — pick is locked."
        picks.pop(game_id, None)
        return _write(path, doc)

    # --- adding / changing a pick ---
    if locked_now:
        return False, "Game has kicked off — pick is locked."

    conf = int(confidence) if confidence else None
    if conf is not None and conf not in CONF_WEIGHTS:
        return False, f"Confidence must be one of {CONF_WEIGHTS}."

    is_new_game = game_id not in picks
    if is_new_game and len(picks) >= MAX_PICKS:
        return False, (f"You've already picked {MAX_PICKS} games. "
                       f"Clear one before adding another.")

    # Unique-weight rule: a confidence value can't be shared by two games.
    if conf is not None:
        for gid, p in picks.items():
            if gid != game_id and p.get("confidence") == conf:
                other = games_index_label(games_index, gid)
                return False, (f"Confidence {conf} is already used"
                               + (f" on {other}" if other else "")
                               + ". Each of your 5 picks needs a different star rating.")

    prev = picks.get(game_id, {})
    entry = {
        "side": side,
        # keep prior confidence if a side-only toggle came in without one
        "confidence": conf if conf is not None else prev.get("confidence"),
    }
    # Snapshot the market line + edge at pick time. Set on first pick or when the
    # side changes (a new pick decision); otherwise carry the existing snapshot
    # forward so a confidence tweak doesn't rewrite the line you committed to.
    side_changed = prev.get("side") != side
    if snapshot and (side_changed or "market_at_pick" not in prev):
        entry["market_at_pick"] = snapshot.get("market")
        entry["my_line_at_pick"] = snapshot.get("my_line")
        entry["edge_at_pick"] = snapshot.get("edge")
        entry["picked_at"] = _now().strftime("%Y-%m-%dT%H:%MZ")
    else:
        for k in ("market_at_pick", "my_line_at_pick", "edge_at_pick", "picked_at"):
            if k in prev:
                entry[k] = prev[k]
    picks[game_id] = entry
    return _write(path, doc)


def games_index_label(games_index, gid):
    """Best-effort human label for a game id (games_index only has kickoff);
    returns None — labels are added by the caller when available."""
    return None


def _write(path, doc):
    doc["updated"] = _now().strftime("%Y-%m-%dT%H:%MZ")
    with open(path, "w") as f:
        json.dump(doc, f, indent=2)
    return True, "saved"


def _num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _line_for_event(e, ratings, hfa, default_hfa, overrides, now):
    """One per-event line computation, shared by the live sheet AND grading, so
    the model line that gets graded is exactly the line the sheet displayed
    (including neutral-site / manual-override handling). Also reads the final
    score + completed flag so grading can reuse the same fetch.

    Returns a dict, or None if the event isn't a usable home/away matchup.
    """
    c = e["competitions"][0]
    comp = {t["homeAway"]: t for t in c["competitors"]}
    if "home" not in comp or "away" not in comp:
        return None
    home = comp["home"]["team"]["displayName"]
    away = comp["away"]["team"]["displayName"]
    gid = e.get("id")
    ov = overrides.get(gid, {})
    kickoff_iso = e.get("date", "")
    kickoff = _parse_iso(kickoff_iso)
    locked = bool(kickoff and now >= kickoff)

    # Neutral-site games get NO home-field edge. ESPN flags most of them
    # (neutralSite); the override can force it when ESPN doesn't.
    neutral = bool(c.get("neutralSite") or ov.get("neutral"))
    prime = _is_primetime(kickoff_iso)
    eff_hfa = 0.0 if neutral else hfa.get(home, default_hfa) + (0.5 if prime else 0.0)
    rh, ra = ratings.get(home), ratings.get(away)
    my_spread = None
    if rh is not None and ra is not None:
        my_spread = _round_half(-(rh - ra + eff_hfa))  # home-relative, neg = home fav

    odds = c.get("odds") or []
    market = odds[0].get("spread") if odds else None
    details = odds[0].get("details") if odds else None
    market_source = "espn" if market is not None else None
    # A manual override wins — used to freeze a kickoff/closing line once ESPN
    # drops its odds after a game starts (post-kickoff ESPN returns no spread).
    if ov.get("market") is not None:
        market = ov["market"]
        details = ov.get("market_note", details)
        market_source = "manual"

    edge = None
    if my_spread is not None and market is not None:
        edge = round(market - my_spread, 1)

    # opening line (home-relative) if we've stored one — used for the "vs open" record
    market_open = ov.get("market_open")
    # frozen model line (home-relative) captured at kickoff from the ratings AS THEY
    # STOOD THEN — grading must use this, not the live (post-hoc adjusted) ratings,
    # so a week is never graded with hindsight. Absent => fall back to live my_spread.
    model_spread = ov.get("model_spread")

    status = c.get("status", {}).get("type", {})
    final = bool(status.get("completed", False))
    hs, as_ = _num(comp["home"].get("score")), _num(comp["away"].get("score"))
    actual_margin = (hs - as_) if (final and hs is not None and as_ is not None) else None

    return {
        "game_id": gid, "kickoff_iso": kickoff_iso, "kickoff": kickoff,
        "locked": locked, "neutral": neutral, "prime": prime,
        "home": home, "away": away,
        "home_score": hs, "away_score": as_, "final": final,
        "my_spread": my_spread, "market": market, "market_details": details,
        "market_source": market_source, "edge": edge, "actual_margin": actual_margin,
        "market_open": market_open, "model_spread": model_spread,
    }


def build_sheet(week=None, year=None):
    """Return the full sheet: matchups + market + my predicted spread + lock state
    + any saved pick. This is what the web page renders."""
    cfg = load_config()
    if week is None or year is None:
        cw, cy = current_week_year()
        week = week or cw
        year = year or cy or int(cfg.get("season", "2026"))
    ratings = load_ratings()
    hfa, default_hfa = load_hfa()

    payload = fetch_json(SCOREBOARD.format(year=year, week=week))
    saved = load_picks(year, week)
    overrides = load_line_overrides()
    now = _now()
    games = []
    for e in payload.get("events", []):
        L = _line_for_event(e, ratings, hfa, default_hfa, overrides, now)
        if not L:
            continue
        pick = saved.get(L["game_id"]) or {}
        # per-game ATS grade for final games: did the model's edge side cover, and
        # did Sean's pick cover (vs the line he had when he picked it)?
        am = L["actual_margin"]
        model_side = _model_side(L["my_spread"], L["market"]) if L["final"] else None
        model_result = _grade_side(model_side, L["market"], am) if L["final"] else None
        his_mkt = pick.get("market_at_pick")
        if his_mkt is None:
            his_mkt = L["market"]
        pick_result = (_grade_side(pick.get("side"), his_mkt, am)
                       if (L["final"] and pick.get("side")) else None)
        games.append({
            "game_id": L["game_id"],
            "kickoff": L["kickoff_iso"],
            "kickoff_local": _fmt_local(L["kickoff"]),
            "locked": L["locked"],
            "neutral": L["neutral"],
            "home": L["home"], "away": L["away"],
            "my_spread": L["my_spread"],       # home-relative
            "market": L["market"], "market_details": L["market_details"],
            "market_source": L["market_source"],  # "espn" | "manual" | None
            "edge": L["edge"],                 # market - mine; sign shows lean
            "final": L["final"],
            "home_score": L["home_score"], "away_score": L["away_score"],
            "pick_side": pick.get("side"),
            "pick_confidence": pick.get("confidence"),
            # market line + edge captured when the pick was made (may lag the live line)
            "pick_market_at_pick": pick.get("market_at_pick"),
            "pick_edge_at_pick": pick.get("edge_at_pick"),
            # per-game ATS grade once final: 'win'/'loss'/'push'/None
            "model_side": model_side,
            "model_result": model_result,
            "pick_result": pick_result,
        })
    used_conf = sorted(g["pick_confidence"] for g in games if g["pick_confidence"])
    return {"season": year, "week": week, "games": games,
            "max_picks": MAX_PICKS,
            "conf_weights": list(CONF_WEIGHTS),
            "picked_count": sum(1 for g in games if g["pick_side"]),
            "used_confidence": used_conf,
            "generated": now.strftime("%Y-%m-%dT%H:%MZ")}


def _fmt_local(dt):
    """Kickoff in US Eastern-ish label for display (no tz lib; ET ~ UTC-4/-5)."""
    if not dt:
        return "TBD"
    # Display in UTC with a note; the page also shows the raw time.
    return dt.strftime("%a %m/%d %H:%MZ")


# ---- grading + records -------------------------------------------------------
#
# Two records, both ATS (against the spread):
#   * "mine"  — Sean's saved picks, each graded vs the market line captured at the
#               time he picked (falls back to the game's closing market if a pick
#               predates snapshotting).
#   * "model" — "blindly follow the power ratings": bet the edge side of EVERY game
#               that has an edge, graded vs the market. This is the benchmark.

def _model_side(my_spread, market):
    """Side the ratings favor vs the market (home-relative, neg = home fav).
    I lean home when my number is more home-friendly than the market. None = no edge."""
    if my_spread is None or market is None or abs(my_spread - market) < 1e-9:
        return None
    return "home" if my_spread < market else "away"


def _grade_side(side, market, actual_margin):
    """ATS grade ('win'/'loss'/'push') for a picked side vs a home-relative market
    line. None if it can't be graded."""
    if side not in ("home", "away") or market is None or actual_margin is None:
        return None
    home_cover_margin = actual_margin + market  # >0 => home covered
    if abs(home_cover_margin) < 1e-9:
        return "push"
    home_covered = home_cover_margin > 0
    return "win" if ((side == "home") == home_covered) else "loss"


def _tally():
    # np = "no play": the model had no edge (its number matched the market), so it
    # didn't bet that game. Not a win/loss/push — excluded from the W-L record.
    return {"win": 0, "loss": 0, "push": 0, "np": 0}


def _bump(t, result):
    if result in t:
        t[result] += 1


def _add_tally(dst, src):
    for k in ("win", "loss", "push", "np"):
        dst[k] += src.get(k, 0)


def _record_model(t, side, line, am):
    """Fold one model game into a tally: a None side is a no-play (no edge)."""
    if side is None:
        t["np"] += 1
    else:
        _bump(t, _grade_side(side, line, am))


TOP_EDGE_N = 5  # "top edge plays" = the N largest-|edge| model plays per week


def grade_week(week, year, ratings=None, hfa=None, default_hfa=None):
    """Grade one week's completed games against BOTH the opening and closing line.
    Returns {week, season, mine:{open,close}, model:{open,close}, top5:{open,close}}
    where each open/close is a {win,loss,push,np} tally (np = no-play / no edge).
    `top5` grades only the week's TOP_EDGE_N largest-edge model plays. Only FINAL
    games count; a game with no stored opening line falls back to its closing line."""
    if ratings is None:
        ratings = load_ratings()
    if hfa is None:
        hfa, default_hfa = load_hfa()
    overrides = load_line_overrides()
    saved = load_picks(year, week)
    now = _now()
    payload = fetch_json(SCOREBOARD.format(year=year, week=week))
    mine = {"open": _tally(), "close": _tally()}
    model = {"open": _tally(), "close": _tally()}
    # collect the model's edge plays so we can rank the biggest ones for top5
    plays = {"open": [], "close": []}   # each: (abs_edge, side, line, am)
    for e in payload.get("events", []):
        L = _line_for_event(e, ratings, hfa, default_hfa, overrides, now)
        if not L or not L["final"]:
            continue
        am = L["actual_margin"]
        close = L["market"]
        opn = L["market_open"] if L["market_open"] is not None else close
        # model line frozen at kickoff (no hindsight); fall back to live only if unfrozen
        my = L["model_spread"] if L["model_spread"] is not None else L["my_spread"]
        for key, line in (("open", opn), ("close", close)):
            side = _model_side(my, line)
            _record_model(model[key], side, line, am)
            if side is not None and my is not None and line is not None:
                plays[key].append((abs(line - my), side, line, am))
        # mine: the side I picked, graded vs each line
        side_me = (saved.get(L["game_id"]) or {}).get("side")
        if side_me:
            _bump(mine["open"], _grade_side(side_me, opn, am))
            _bump(mine["close"], _grade_side(side_me, close, am))
    top5 = {"open": _tally(), "close": _tally()}
    for key in ("open", "close"):
        for _edge, side, line, am in sorted(plays[key], key=lambda x: -x[0])[:TOP_EDGE_N]:
            _bump(top5[key], _grade_side(side, line, am))
    return {"week": week, "season": year, "mine": mine, "model": model, "top5": top5}


def _summary_market(event_id):
    """Home-relative market spread (+ details) from ESPN's per-event summary
    `pickcenter`, which RETAINS odds after a game is final (the scoreboard drops
    them). Returns (spread, details) or (None, None). ESPN's pickcenter spread is
    already home-team-relative (negative = home favored)."""
    try:
        s = fetch_json(SUMMARY.format(eid=event_id))
    except Exception:  # noqa: BLE001
        return None, None
    for p in (s.get("pickcenter") or []):
        sp = p.get("spread")
        if sp is not None:
            try:
                return round(float(sp), 1), p.get("details")
            except (TypeError, ValueError):
                continue
    return None, None


def freeze_week_lines(week, year, overwrite=False):
    """Persist the real ESPN market line for each game of a week into
    data/line_overrides.json (keyed by ESPN game_id), so the blind-model record
    has a stable line to grade against. Source order per game:
      1. the live scoreboard odds (present pre-game / near kickoff), then
      2. the per-event summary `pickcenter` (present even AFTER the game is final).
    Because of (2) this works retroactively for completed weeks, not just at
    kickoff. It ALSO freezes the model line (`model_spread`) from the ratings as they
    stand right now, so the blind-model record is graded on the pre-game model line,
    never on later (hindsight) rating adjustments. `overwrite=True` replaces existing
    entries (e.g. to swap a proxy line for the real one); otherwise frozen lines are
    left untouched. Sean's own picks still capture their line at pick time via
    save_pick. Returns count written.
    """
    now = _now()
    ratings = load_ratings()
    hfa, default_hfa = load_hfa()
    payload = fetch_json(SCOREBOARD.format(year=year, week=week))
    raw = {}
    if os.path.exists(LINE_OVERRIDES):
        try:
            with open(LINE_OVERRIDES) as f:
                raw = json.load(f)
        except (ValueError, OSError):
            raw = {}
    written = 0
    for e in payload.get("events", []):
        c = e["competitions"][0]
        comp = {t["homeAway"]: t for t in c["competitors"]}
        if "home" not in comp or "away" not in comp:
            continue
        gid = e.get("id")
        existing = raw.get(gid, {})
        # freeze the current model line once (never overwrite a frozen one — the
        # pre-game line must not be rewritten by later rating changes)
        if existing.get("model_spread") is None:
            Lm = _line_for_event(e, ratings, hfa, default_hfa, {}, now)
            if Lm and Lm["my_spread"] is not None:
                existing["model_spread"] = Lm["my_spread"]
                raw[gid] = existing
        if existing.get("market") is not None and not overwrite:
            continue
        odds = c.get("odds") or []
        mkt = odds[0].get("spread") if odds else None
        det = odds[0].get("details") if odds else None
        src = "scoreboard"
        if mkt is None:
            mkt, det = _summary_market(gid)
            src = "summary"
        if mkt is None:
            continue
        existing["market"] = round(float(mkt), 1)
        existing["market_note"] = (f"{det or ''} (ESPN {src}, frozen "
                                   f"{now.strftime('%Y-%m-%dT%H:%MZ')})").strip()
        raw[gid] = existing
        written += 1
    if written:
        with open(LINE_OVERRIDES, "w") as f:
            json.dump(raw, f, indent=2)
    return written


def records(view_week, view_year):
    """Season-to-date + this-week records for Sean's picks vs the blind-model
    benchmark. Season-to-date spans weeks 1..(current week) for the live season, or
    the full 18 for a completed past season. One ESPN fetch per week — call this on
    load/navigation, not on the 60s auto-refresh."""
    ratings = load_ratings()
    hfa, default_hfa = load_hfa()
    cw, cy = current_week_year()
    bound = 18 if (cy and view_year < cy) else (cw or view_week or 1)
    season = {"mine": {"open": _tally(), "close": _tally()},
              "model": {"open": _tally(), "close": _tally()},
              "top5": {"open": _tally(), "close": _tally()}}
    week_cache = {}
    for w in range(1, bound + 1):
        try:
            gw = grade_week(w, view_year, ratings, hfa, default_hfa)
        except Exception:  # noqa: BLE001 — a bad week shouldn't sink the record
            continue
        week_cache[w] = gw
        for who in ("mine", "model", "top5"):
            for line in ("open", "close"):
                _add_tally(season[who][line], gw[who][line])
    empty = {"mine": {"open": _tally(), "close": _tally()},
             "model": {"open": _tally(), "close": _tally()},
             "top5": {"open": _tally(), "close": _tally()}}
    vw = week_cache.get(view_week) or empty
    return {
        "season": view_year, "week": view_week, "through_week": bound,
        "season_record": season,
        "week_record": {"mine": vw["mine"], "model": vw["model"], "top5": vw["top5"]},
    }


def write_records_json(year=None, path=None):
    """Compute the season records and write a compact PUBLIC JSON the board renders.

    Aggregate W-L-P(-NP) only — no individual pick selections, so Sean's picks stay
    private while the tallies go public. Model + mine + top-5, each vs opening and
    closing line, season-to-date. Run this locally (needs the gitignored picks +
    frozen lines); the committed file is what CI renders. Returns the payload.
    """
    if path is None:
        path = RECORDS_JSON
    cw, cy = current_week_year()
    if year is None:
        year = cy or 2026
    rec = records(cw or 1, year)
    payload = {
        "season_year": year,
        "through_week": rec["through_week"],
        "generated": _now().strftime("%Y-%m-%dT%H:%MZ"),
        "season_record": rec["season_record"],   # mine/model/top5 -> open/close tallies
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return payload
