"""Player-prop prices from free sources, normalized to one row shape.

Sources:
  kalshi      — public trade API (no key). "N+" ladders per player; strike = line.
  polymarket  — gamma API (no key). "<A> vs. <B> - Player Props" events. The
                headline outcomePrices is often the midpoint of an EMPTY book, so only
                bestBid/bestAsk are used and thin markets are flagged unusable.
  oddsapi     — the-odds-api.com v4 (DraftKings / FanDuel). Needs a key from
                $ODDS_API_KEY or data/props/.odds_api_key (gitignored, never logged).
                Credit-guarded: refuses to call when remaining credits < reserve.

Normalized row (dict):
  source, book, event_key ("AWAY@HOME", ESPN abbrs), player, market, line,
  p_bid, p_ask, p_fair (prob of OVER/YES), liquidity, spread, usable, raw_id, fetched_at

Markets: pass_yds rush_yds rec_yds receptions anytime_td pass_tds pass_ints
p_* are probabilities of the OVER (or YES for anytime_td) side.

CLI:
    python3 props_markets.py                  # pull kalshi+polymarket (+oddsapi if keyed)
    python3 props_markets.py --sources kalshi
    python3 props_markets.py --player "Tyler Shough"
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PROPS_DIR = os.path.join(HERE, "data", "props")
CACHE_DIR = os.path.join(PROPS_DIR, "markets")
KEY_PATH = os.path.join(PROPS_DIR, ".odds_api_key")

MARKETS = ("pass_yds", "rush_yds", "rec_yds", "receptions", "anytime_td",
           "pass_tds", "pass_ints")

# Kalshi/Polymarket/Odds API team codes -> ESPN abbreviations used everywhere else
TEAM_ALIASES = {"JAC": "JAX", "LA": "LAR", "WAS": "WSH", "ARZ": "ARI", "LVR": "LV",
                "GNB": "GB", "KAN": "KC", "NWE": "NE", "NOR": "NO", "SFO": "SF",
                "TAM": "TB"}
NFL_TEAMS = ("ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
             "DET", "GB", "HOU", "IND", "JAX", "JAC", "KC", "LAC", "LAR", "LA", "LV",
             "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB",
             "TEN", "WAS", "WSH")

# usable-market thresholds (probability units / dollars)
MAX_SPREAD = 0.05
MIN_POLY_LIQUIDITY = 500.0
MIN_KALSHI_OI = 100.0
ODDS_API_RESERVE = 50  # never spend the last N monthly credits


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _team(code):
    c = (code or "").upper()
    return TEAM_ALIASES.get(c, c)


def _f(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=dict({"User-Agent": "Mozilla/5.0"},
                                                   **(headers or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r), dict(r.headers)


def _row(source, book, event_key, player, market, line, bid, ask, liquidity,
         raw_id, fetched_at, fair=None, min_liq=0.0):
    spread = (ask - bid) if (bid is not None and ask is not None) else None
    if fair is None and bid is not None and ask is not None:
        fair = (bid + ask) / 2.0
    usable = bool(fair is not None and 0.0 < fair < 1.0
                  and (spread is None or spread <= MAX_SPREAD)
                  and (liquidity is None or liquidity >= min_liq))
    return {"source": source, "book": book, "event_key": event_key, "player": player,
            "market": market, "line": line, "p_bid": bid, "p_ask": ask,
            "p_fair": fair, "liquidity": liquidity, "spread": spread,
            "usable": usable, "raw_id": raw_id, "fetched_at": fetched_at}


# --------------------------------------------------------------------- Kalshi
KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_SERIES = {"KXNFLPASSYDS": "pass_yds", "KXNFLRSHYDS": "rush_yds",
                 "KXNFLRECYDS": "rec_yds", "KXNFLREC": "receptions",
                 "KXNFLTD": "anytime_td", "KXNFLPASSTDS": "pass_tds",
                 "KXNFLPASSINT": "pass_ints"}
_KALSHI_TITLE = re.compile(r"^(?P<player>.+?):\s*(?P<n>\d+)\+")


def kalshi_event_key(event_ticker):
    """'KXNFLREC-26OCT11BALATL' -> 'BAL@ATL' (teams are 2-3 letter codes)."""
    tail = event_ticker.rsplit("-", 1)[-1]
    m = re.match(r"^\d{2}[A-Z]{3}\d{2}(?P<teams>[A-Z]+)$", tail)
    if not m:
        return None
    t = m.group("teams")
    for i in (2, 3):
        a, h = t[:i], t[i:]
        if a in NFL_TEAMS and h in NFL_TEAMS:
            return f"{_team(a)}@{_team(h)}"
    return None


def parse_kalshi(markets, market_key, fetched_at):
    rows = []
    for x in markets:
        if x.get("status") not in (None, "active", "open", "initialized"):
            continue
        m = _KALSHI_TITLE.match(x.get("title") or "")
        line = _f(x.get("floor_strike"))
        if not m or line is None:
            continue
        if market_key == "anytime_td" and line != 0.5:
            continue  # 2+/3+ TD ladders are a different market
        bid, ask = _f(x.get("yes_bid_dollars")), _f(x.get("yes_ask_dollars"))
        if bid == 0.0:
            bid = None if ask is None else 0.0
        rows.append(_row("kalshi", "kalshi", kalshi_event_key(x.get("event_ticker", "")),
                         m.group("player").strip(), market_key, line, bid, ask,
                         _f(x.get("open_interest_fp")), x.get("ticker"), fetched_at,
                         min_liq=MIN_KALSHI_OI))
    return rows


def fetch_kalshi(get=_get_json, fetched_at=None):
    fetched_at = fetched_at or _now()
    out = []
    for series, key in KALSHI_SERIES.items():
        cursor = ""
        for _ in range(20):  # pagination guard
            q = {"series_ticker": series, "status": "open", "limit": 1000}
            if cursor:
                q["cursor"] = cursor
            d, _h = get(KALSHI_BASE + "/markets?" + urllib.parse.urlencode(q))
            out.extend(parse_kalshi(d.get("markets", []), key, fetched_at))
            cursor = d.get("cursor") or ""
            if not cursor:
                break
    return out


# ----------------------------------------------------------------- Polymarket
POLY_BASE = "https://gamma-api.polymarket.com"
POLY_TYPES = {"passing_yards": "pass_yds", "rushing_yards": "rush_yds",
              "receiving_yards": "rec_yds", "receptions": "receptions",
              "anytime_touchdowns": "anytime_td", "passing_touchdowns": "pass_tds"}


def poly_event_key(slug):
    """'nfl-buf-la-2026-10-13-player-props' -> 'BUF@LAR'."""
    m = re.match(r"^nfl-([a-z]+)-([a-z]+)-\d{4}-\d{2}-\d{2}", slug or "")
    return f"{_team(m.group(1))}@{_team(m.group(2))}" if m else None


def parse_polymarket(events, fetched_at):
    rows = []
    for e in events:
        if "Player Props" not in (e.get("title") or ""):
            continue
        ek = poly_event_key(e.get("slug"))
        for m in e.get("markets", []):
            key = POLY_TYPES.get(m.get("sportsMarketType"))
            if not key or m.get("closed"):
                continue
            q = m.get("question") or ""
            player = q.split(":", 1)[0].strip()
            line = _f(m.get("line"))
            if key == "anytime_td":
                line = 0.5
            if line is None or not player:
                continue
            try:
                outcomes = json.loads(m.get("outcomes") or "[]")
            except ValueError:
                outcomes = []
            first = (outcomes[0] if outcomes else "").lower()
            bid, ask = _f(m.get("bestBid")), _f(m.get("bestAsk"))
            if first in ("under", "no"):  # book quotes the other side: flip
                bid, ask = ((1 - ask) if ask is not None else None,
                            (1 - bid) if bid is not None else None)
            rows.append(_row("polymarket", "polymarket", ek, player, key, line, bid, ask,
                             _f(m.get("liquidityNum")), m.get("id"), fetched_at,
                             min_liq=MIN_POLY_LIQUIDITY))
    return rows


def fetch_polymarket(get=_get_json, fetched_at=None):
    fetched_at = fetched_at or _now()
    events = []
    for off in range(0, 3000, 100):
        d, _h = get(POLY_BASE + "/events?" + urllib.parse.urlencode(
            {"tag_slug": "nfl", "closed": "false", "limit": 100, "offset": off}))
        if not d:
            break
        events.extend(d)
    return parse_polymarket(events, fetched_at)


# ------------------------------------------------------------------ Odds API
ODDS_BASE = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
ODDS_MARKETS = {"player_pass_yds": "pass_yds", "player_rush_yds": "rush_yds",
                "player_reception_yds": "rec_yds", "player_receptions": "receptions",
                "player_anytime_td": "anytime_td", "player_pass_tds": "pass_tds",
                "player_pass_interceptions": "pass_ints"}
ODDS_BOOKS = ("draftkings", "fanduel")
NAME_TO_ABBR = {}  # filled lazily from ESPN team names when needed


def american_to_prob(price):
    p = _f(price)
    if p is None or p == 0:
        return None
    return 100.0 / (p + 100.0) if p > 0 else -p / (-p + 100.0)


def devig_two_way(p_over, p_under):
    """Multiplicative de-vig; returns fair P(over) or None."""
    if p_over is None or p_under is None or (p_over + p_under) <= 0:
        return None
    return p_over / (p_over + p_under)


def odds_api_key():
    k = os.environ.get("ODDS_API_KEY", "").strip()
    if k:
        return k
    try:
        with open(KEY_PATH) as f:
            return f.read().strip() or None
    except OSError:
        return None


class CreditGuardError(RuntimeError):
    pass


def _team_abbr(full_name):
    if not NAME_TO_ABBR:
        try:
            import spreads  # ESPN displayName -> abbreviation via the current schedule
            p = spreads.fetch_week(*_current_week())
            for e in p.get("events", []):
                for c in e["competitions"][0]["competitors"]:
                    NAME_TO_ABBR[c["team"]["displayName"]] = c["team"]["abbreviation"]
        except Exception:  # noqa: BLE001
            pass
    return NAME_TO_ABBR.get(full_name)


def _current_week():
    import picks
    return picks.current_week_year()


def parse_oddsapi_event(ev, fetched_at, abbr=None):
    abbr = abbr or _team_abbr
    a, h = abbr(ev.get("away_team")), abbr(ev.get("home_team"))
    ek = f"{a}@{h}" if a and h else None
    rows = []
    for bk in ev.get("bookmakers", []):
        for mk in bk.get("markets", []):
            key = ODDS_MARKETS.get(mk.get("key"))
            if not key:
                continue
            sides = {}
            for o in mk.get("outcomes", []):
                player = (o.get("description") or "").strip()
                line = 0.5 if key == "anytime_td" else _f(o.get("point"))
                if not player or line is None:
                    continue
                sides.setdefault((player, line), {})[(o.get("name") or "").lower()] = \
                    american_to_prob(o.get("price"))
            for (player, line), s in sides.items():
                p_over = s.get("over", s.get("yes"))
                p_under = s.get("under", s.get("no"))
                fair = devig_two_way(p_over, p_under)
                one_sided = fair is None
                if one_sided:
                    fair = p_over  # anytime TD is usually Yes-only: vig left in
                r = _row("oddsapi", bk.get("key"), ek, player, key, line, None, None, None,
                         ev.get("id"), fetched_at, fair=fair)
                r["vig_included"] = one_sided
                r["p_over_raw"] = p_over
                rows.append(r)
    return rows


def fetch_oddsapi(get=_get_json, fetched_at=None, key=None, reserve=ODDS_API_RESERVE,
                  markets=tuple(ODDS_MARKETS), books=ODDS_BOOKS, log=print):
    """One events call (free) + one odds call per event (len(markets) credits each)."""
    key = key or odds_api_key()
    if not key:
        log("  oddsapi: no key (set ODDS_API_KEY or data/props/.odds_api_key) — skipped")
        return []
    fetched_at = fetched_at or _now()
    events, hdr = get(ODDS_BASE + "/events?" + urllib.parse.urlencode({"apiKey": key}))
    remaining = _f(hdr.get("x-requests-remaining") or hdr.get("X-Requests-Remaining"))
    cost_each = len(markets)
    rows = []
    for ev in events:
        if remaining is not None and remaining - cost_each < reserve:
            raise CreditGuardError(
                f"Odds API credits {remaining:.0f} would drop below reserve {reserve}")
        q = {"apiKey": key, "regions": "us", "markets": ",".join(markets),
             "oddsFormat": "american", "bookmakers": ",".join(books)}
        try:
            d, hdr = get(f"{ODDS_BASE}/events/{ev['id']}/odds?" + urllib.parse.urlencode(q))
        except urllib.error.HTTPError as e:
            log(f"  oddsapi {ev.get('id')}: HTTP {e.code} (props may not be on this plan)")
            if e.code in (401, 403, 422):
                break
            continue
        remaining = _f(hdr.get("x-requests-remaining") or hdr.get("X-Requests-Remaining"))
        rows.extend(parse_oddsapi_event(d, fetched_at))
    if remaining is not None:
        log(f"  oddsapi: {remaining:.0f} credits remaining")
    return rows


# --------------------------------------------------------------------- pulls
FETCHERS = {"kalshi": fetch_kalshi, "polymarket": fetch_polymarket,
            "oddsapi": fetch_oddsapi}


def pull(sources=("kalshi", "polymarket", "oddsapi"), log=print, save=True):
    fetched_at = _now()
    rows, status = [], {}
    for s in sources:
        try:
            got = FETCHERS[s](fetched_at=fetched_at)
            status[s] = {"ok": True, "rows": len(got),
                         "usable": sum(1 for r in got if r["usable"])}
            rows.extend(got)
            log(f"  {s}: {len(got)} rows ({status[s]['usable']} usable)")
        except Exception as e:  # noqa: BLE001 — one dead source never blocks the others
            status[s] = {"ok": False, "error": str(e)[:200]}
            log(f"  {s}: FAILED ({str(e)[:120]})")
    snap = {"fetched_at": fetched_at, "status": status, "rows": rows}
    if save:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, fetched_at[:10] + ".json")
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(snap, f)
        os.replace(tmp, path)
    return snap


def latest_snapshot():
    try:
        files = sorted(f for f in os.listdir(CACHE_DIR) if f.endswith(".json"))
    except OSError:
        return None
    if not files:
        return None
    with open(os.path.join(CACHE_DIR, files[-1])) as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pull player-prop prices (free sources).")
    ap.add_argument("--sources", default="kalshi,polymarket,oddsapi")
    ap.add_argument("--player", default="")
    a = ap.parse_args(argv)
    snap = pull([s.strip() for s in a.sources.split(",") if s.strip()])
    if a.player:
        want = a.player.lower()
        for r in sorted(snap["rows"], key=lambda r: (r["market"], r["line"], r["source"])):
            if want in r["player"].lower():
                fair = "—" if r["p_fair"] is None else f"{r['p_fair']:.2f}"
                print(f"  {r['source']:10} {r['book']:10} {r['market']:10} "
                      f"o{r['line']:<6} fair {fair}  {'ok' if r['usable'] else 'thin'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
