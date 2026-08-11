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

SCOREBOARD = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
              "scoreboard?dates={year}&seasontype=2&week={week}")
SCOREBOARD_NOW = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
                  "scoreboard")

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
    """Ask ESPN what week/season it is right now."""
    sb = fetch_json(SCOREBOARD_NOW)
    wk = sb.get("week", {}).get("number")
    yr = sb.get("season", {}).get("year")
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


def save_pick(season, week, game_id, side, confidence, games_index):
    """Persist one pick under the confidence-pool rules.

    Rules enforced here (server-side — the source of truth):
      - A game locked at kickoff cannot be added, changed, or cleared.
      - At most MAX_PICKS (5) games may be picked at once.
      - Each confidence weight in CONF_WEIGHTS (1..5) is used at most once —
        no two picks share the same star rating.

    games_index: {game_id: kickoff_iso} used to enforce the per-game lock.
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
    picks[game_id] = {
        "side": side,
        # keep prior confidence if a side-only toggle came in without one
        "confidence": conf if conf is not None else prev.get("confidence"),
    }
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
    now = _now()
    games = []
    for e in payload.get("events", []):
        c = e["competitions"][0]
        comp = {t["homeAway"]: t["team"]["displayName"] for t in c["competitors"]}
        home, away = comp.get("home"), comp.get("away")
        if not home or not away:
            continue
        kickoff_iso = e.get("date", "")
        kickoff = _parse_iso(kickoff_iso)
        locked = bool(kickoff and now >= kickoff)

        prime = _is_primetime(kickoff_iso)
        eff_hfa = hfa.get(home, default_hfa) + (0.5 if prime else 0.0)
        rh, ra = ratings.get(home), ratings.get(away)
        my_spread = None
        if rh is not None and ra is not None:
            my_spread = _round_half(-(rh - ra + eff_hfa))  # home-relative, neg = home fav

        odds = c.get("odds") or []
        market = odds[0].get("spread") if odds else None
        details = odds[0].get("details") if odds else None

        edge = None
        if my_spread is not None and market is not None:
            edge = round(market - my_spread, 1)

        gid = e.get("id")
        pick = saved.get(gid)

        games.append({
            "game_id": gid,
            "kickoff": kickoff_iso,
            "kickoff_local": _fmt_local(kickoff),
            "locked": locked,
            "home": home, "away": away,
            "my_spread": my_spread,       # home-relative
            "market": market, "market_details": details,
            "edge": edge,                 # market - mine; sign shows lean
            "pick_side": (pick or {}).get("side"),
            "pick_confidence": (pick or {}).get("confidence"),
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
