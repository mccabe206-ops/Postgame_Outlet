"""Ourlads NFL depth-chart scraper (depth ORDER — starter → backups).

ESPN gives rosters but not who starts; Ourlads publishes true position-by-position
depth order. This fetches ONE team's depth chart, parses the position rows, and
caches it. Ourlads updates ~weekly, so we cache and only re-fetch when stale.

Politeness / compliance:
  - Ourlads robots.txt does NOT disallow /nfldepthcharts/ (checked 2026-08).
  - We send a real browser User-Agent, cache aggressively, and (in bulk mode)
    sleep between teams so we never hammer the site.

Color classes on Ourlads encode status:
  lc_red = injured/inactive · lc_gold = FA/trade add · lc_aqua = UDFA · (purple = rookie)

Cache: data/depthcharts/<ABBR>.json  (gitignored)
Stdlib only (urllib + regex; no bs4 dependency).
"""

import html as _html
import json
import os
import re
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(DATA, "depthcharts")

URL = "https://www.ourlads.com/nfldepthcharts/depthchart/{abbr}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
STALE_DAYS = 7

# Ourlads uses a few abbreviations that differ from ESPN's. Map ESPN->Ourlads.
ESPN_TO_OURLADS = {"ARI": "ARZ", "LAR": "LAR", "LAC": "LAC", "LV": "LV",
                   "WSH": "WAS", "JAX": "JAX"}

_CLASS_MEAN = {"lc_red": "injured/inactive", "lc_gold": "FA/trade add",
               "lc_aqua": "UDFA", "lc_purple": "rookie"}


def _ourlads_abbr(espn_abbr):
    return ESPN_TO_OURLADS.get(espn_abbr, espn_abbr)


def cache_path(abbr):
    return os.path.join(CACHE, f"{abbr}.json")


def _clean_name(raw):
    """'Moore, DJ T/Chi' -> ('DJ Moore', 'T/Chi'). Ourlads shows 'Last, First <note>'."""
    txt = _html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
    # trailing note is usually an ALLCAPS/short token after the first name; keep it separate
    m = re.match(r"^([^,]+),\s+(.+)$", txt)
    if not m:
        return txt, ""
    last, rest = m.group(1).strip(), m.group(2).strip()
    # split a trailing transaction note (e.g. 'DJ T/Chi', 'Keon 24/2') — heuristic:
    # the first token(s) are the first name; a note often contains a slash or digits.
    parts = rest.split()
    first_tokens, note_tokens = [], []
    for i, tok in enumerate(parts):
        if ("/" in tok or any(c.isdigit() for c in tok)) and first_tokens:
            note_tokens = parts[i:]
            break
        first_tokens.append(tok)
    first = " ".join(first_tokens)
    note = " ".join(note_tokens)
    return f"{first} {last}".strip(), note


def parse_depth(html_text):
    """Parse Ourlads HTML into {position: [ {name, note, status} in depth order ]}."""
    depth = {}
    # each position is a <tr> ... first <td> is the position label; then repeating
    # (jersey <td>) (player <td> with an <a class=...>Name</a>)
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if not tds:
            continue
        pos = _html.unescape(re.sub(r"<[^>]+>", "", tds[0])).strip()
        if not pos or len(pos) > 6 or not re.match(r"^[A-Z/]+$", pos):
            continue  # not a position row
        players = []
        for cell in tds[1:]:
            a = re.search(r'<a[^>]*class=[\'"]([^\'"]*)[\'"][^>]*>(.*?)</a>', cell, re.S)
            if not a:
                continue
            cls = a.group(1)
            name, note = _clean_name(a.group(2))
            status = next((v for k, v in _CLASS_MEAN.items() if k in cls), "")
            if name:
                players.append({"name": name, "note": note, "status": status})
        if players:
            depth[pos] = players
    return depth


def fetch_depth(espn_abbr):
    """Live fetch + parse one team's depth chart. Returns {abbr, depth, source}."""
    o_abbr = _ourlads_abbr(espn_abbr)
    req = urllib.request.Request(URL.format(abbr=o_abbr), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as resp:
        html_text = resp.read().decode("utf-8", errors="ignore")
    depth = parse_depth(html_text)
    return {"abbr": espn_abbr, "ourlads_abbr": o_abbr, "depth": depth,
            "source": "ourlads"}


def _age_days(iso, now_iso):
    """Whole days between two 'YYYY-MM-DD...' strings; large if unknown."""
    try:
        from datetime import date
        a = date.fromisoformat(iso[:10])
        b = date.fromisoformat(now_iso[:10])
        return abs((b - a).days)
    except Exception:  # noqa: BLE001
        return 9999


def get_depth(espn_abbr, now_iso="", force=False):
    """Cached read: use the cache unless it's >STALE_DAYS old, missing, or forced."""
    p = cache_path(espn_abbr)
    if not force and os.path.exists(p):
        with open(p) as f:
            cached = json.load(f)
        if now_iso and _age_days(cached.get("fetched_at", ""), now_iso) <= STALE_DAYS:
            cached["from_cache"] = True
            return cached
        if not now_iso:  # can't judge age without a clock — prefer cache, note it
            cached["from_cache"] = True
            return cached
    d = fetch_depth(espn_abbr)
    d["fetched_at"] = now_iso
    os.makedirs(CACHE, exist_ok=True)
    with open(p, "w") as f:
        json.dump(d, f, indent=2)
    d["from_cache"] = False
    return d


def refresh_all(all_espn_abbrs, now_iso="", sleep_between=2.0):
    """Weekly bulk refresh — polite: real UA + a delay between teams."""
    done = []
    for ab in all_espn_abbrs:
        try:
            get_depth(ab, now_iso=now_iso, force=True)
            done.append(ab)
        except Exception as e:  # noqa: BLE001
            done.append(f"{ab}:ERR")
        time.sleep(sleep_between)
    return done
