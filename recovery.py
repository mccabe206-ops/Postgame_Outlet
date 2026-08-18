"""Injury return-timeline estimates for the injury scanner (Lane-2, testing).

Turns "he's on PUP with an Achilles" into "typical Achilles recovery ~6-11 months,
so realistically out for the season." Purely a planning aid built from a curated
table of GENERAL recovery norms (`data/injury_recovery.csv`) — NOT a diagnosis and
NOT a player-specific medical read. Everything is a range.

Data reality: Sleeper rarely fills `injury_start_date`, so we anchor the clock to the
last-report date (`news_updated`) and label it as such — the estimate is "as of last
report," which is fine for fresh injuries and clearly rough for chronic ones.

Public API:
    estimate(injury_dict, today=None) -> dict | None
      injury_dict needs: status, body_part, notes, start (opt), updated (ms, opt).
      Returns {label, weeks_min, weeks_max, anchor, anchor_kind, return_low,
               return_high, week_low, week_high, season_ending, confidence,
               duration, eta, text} or None when nothing is estimable.

Stdlib only.
"""

import csv
import os
import re
from datetime import datetime, timezone, timedelta, date

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(HERE, "data", "injury_recovery.csv")

# NFL Week 1 (Thursday) per season — for mapping a return date to a week number.
_WEEK1 = {2024: date(2024, 9, 5), 2025: date(2025, 9, 4), 2026: date(2026, 9, 10)}
_LAST_REG_WEEK = 18  # regular season length; a return past this = "out for the season"


def _season_year():
    try:
        p = os.path.join(HERE, "data", "config.csv")
        for r in csv.DictReader(open(p, newline="")):
            if r.get("key") == "season":
                return int(r["value"])
    except Exception:  # noqa: BLE001
        pass
    return 2026


def _week1():
    y = _season_year()
    return _WEEK1.get(y, date(y, 9, 10))


_ROWS = None


def _load():
    global _ROWS
    if _ROWS is None:
        rows = []
        if os.path.exists(TABLE):
            with open(TABLE, newline="") as f:
                for r in csv.DictReader(f):
                    try:
                        rows.append({
                            "keywords": [k.strip().lower()
                                         for k in (r.get("match") or "").split("|") if k.strip()],
                            "surgery": (r.get("surgery") or "").strip().lower() in ("y", "yes", "1", "true"),
                            "priority": int(r.get("priority") or 1),
                            "weeks_min": float(r["weeks_min"]) if r.get("weeks_min") else None,
                            "weeks_max": float(r["weeks_max"]) if r.get("weeks_max") else None,
                            "label": (r.get("label") or "injury").strip(),
                        })
                    except (ValueError, KeyError):
                        continue
        _ROWS = rows
    return _ROWS


def _match(text, surgery_flag):
    """Best recovery-table row for the combined body_part+notes text.

    Ranks by (priority, surgery-preference when surgery is mentioned, keyword length),
    so 'Knee - ACL' matches ACL (specific) not 'knee' (generic)."""
    best, best_score = None, (-1, -1, -1)
    for r in _load():
        if r["surgery"] and not surgery_flag:
            continue
        for kw in r["keywords"]:
            # word-boundary PREFIX match: catches plurals ("rib"->"ribs") but not
            # mid-word hits ("disc" must not fire inside "undisclosed").
            if kw and re.search(r"\b" + re.escape(kw), text):
                score = (r["priority"], 1 if (r["surgery"] and surgery_flag) else 0, len(kw))
                if score > best_score:
                    best_score, best = score, r
    return best


# status-only fallback when the body part is unknown/undisclosed
_STATUS_FALLBACK = {
    "IR": (4, None, "IR — out ≥4 games"),
    "PUP": (4, None, "PUP — out ≥4 games"),
    "NFI": (4, None, "NFI — out ≥4 games"),
    "DOUBTFUL": (1, 1, "doubtful this week"),
    "OUT": (1, 1, "out this week"),
    "DNR": (1, 1, "did not report"),
    "QUESTIONABLE": (0, 1, "game-time decision"),
    "PROBABLE": (0, 0, "expected to play"),
}


def _anchor(inj):
    """(date, kind) the recovery clock is anchored to: injury start if present,
    else the last Sleeper update, else None."""
    s = inj.get("start")
    if s:
        try:
            return datetime.strptime(str(s)[:10], "%Y-%m-%d").date(), "start"
        except ValueError:
            pass
    u = inj.get("updated")
    if u:
        try:
            return datetime.fromtimestamp(int(u) / 1000, tz=timezone.utc).date(), "report"
        except (ValueError, OSError, OverflowError):
            pass
    return None, None


def _to_week(d):
    if not d:
        return None
    wk = 1 + (d - _week1()).days // 7
    return max(1, wk)


def _month_word(d):
    return d.strftime("%b %-d") if hasattr(d, "strftime") else ""


def _duration(wmin, wmax):
    if wmin is None:
        return "unknown"
    if wmax is None:
        return f"{int(wmin)}+ wks"
    # express longer recoveries in months for readability
    if wmax >= 13:
        mlo, mhi = round(wmin / 4.345), round(wmax / 4.345)
        return f"{mlo}–{mhi} mo" if mhi != mlo else f"~{mlo} mo"
    lo, hi = int(round(wmin)), int(round(wmax))
    return f"{lo}–{hi} wks" if hi != lo else f"~{lo} wks"


def _ago(d, today):
    """Human 'how long ago' for a report date."""
    if not d:
        return ""
    days = (today - d).days
    if days < 0:
        return "upcoming"
    if days < 1:
        return "today"
    if days < 14:
        return f"{days}d ago"
    if days < 75:
        return f"{days // 7}w ago"
    mo = round(days / 30.4)
    if mo >= 12:
        y = round(days / 365, 1)
        return (f"{int(y)}y ago" if y == int(y) else f"{y}y ago")
    return f"{mo}mo ago"


def estimate(inj, today=None):
    """Return-timeline READ for one injury dict, or None if not estimable.

    Honest by design: Sleeper gives no injury/surgery date (only a last-REPORT
    timestamp), so we do NOT fabricate a precise return date. We LEAD with status +
    the injury type's typical recovery (context) + WHEN it was last reported, and let
    the roster rules drive availability:
      - Preseason PUP/NFI is a *recovering* designation — never 'out for the season'
        (that was the bug: a carryover injury reported recently was projected as if
        the recovery clock started now).
      - In-season reserve/PUP or IR = out a minimum of 4 games (earliest ~Week 5).
      - Only an IN-SEASON IR with a season-length injury reads as likely season-ending.
    A stale report (>45 days) is flagged so an 'out' verdict is always time-anchored.
    """
    status = (inj.get("status") or "").strip().upper()
    if not status:
        return None
    src = ((inj.get("body_part") or "") + " " + (inj.get("notes") or "")).lower()
    surgery_flag = "surger" in src
    today = today or datetime.now(timezone.utc).date()
    report_date, kind = _anchor(inj)
    reported = report_date.strftime("%b %-d, %Y") if report_date else ""
    reported_ago = _ago(report_date, today) if report_date else ""
    stale = bool(report_date and (today - report_date).days > 45)

    row = _match(src, surgery_flag)
    matched = bool(row and row["weeks_min"] is not None)
    if matched:
        wmin, wmax, label = row["weeks_min"], row["weeks_max"], row["label"]
        if surgery_flag and wmax is not None and "surg" not in label.lower():
            label += " (surgery)"
        duration = _duration(wmin, wmax)
        typical = f"typical {label} recovery {duration}"
    else:
        wmin = wmax = None
        label, duration, typical = "", "", ""

    preseason = today < _week1()
    long_injury = matched and wmax is not None and wmax >= 26  # season-length type
    season_ending = False

    if status in ("QUESTIONABLE", "PROBABLE"):
        eta = "game-time decision"
    elif status in ("OUT", "DOUBTFUL", "DNR", "NA"):
        eta = "out (week-to-week)"
    elif status in ("SUS", "SUSPENSION"):
        eta = "suspended"
    elif status in ("PUP", "NFI"):
        eta = ("on PUP — recovering, back TBD" if preseason
               else "reserve/PUP — out ≥4 games (earliest ~Wk 5)")
    elif status == "IR":
        if preseason:
            eta = "on IR — timeline uncertain (camp)"
        elif long_injury:
            eta, season_ending = "likely out for the season", True
        else:
            eta = "on IR — out ≥4 games (earliest ~Wk 5)"
    else:
        eta = status.title()

    parts = [eta]
    if typical:
        parts.append(typical)
    if reported_ago:
        parts.append(f"reported {reported_ago}")
    text_out = " · ".join(parts)
    if stale:
        text_out += " · ⚠ may be outdated"

    return {
        "eta": eta, "typical": typical, "label": label, "duration": duration,
        "weeks_min": wmin, "weeks_max": wmax,
        "reported": reported, "reported_ago": reported_ago, "stale": stale,
        "anchor_kind": kind or "assumed-today",
        "season_ending": season_ending,
        "confidence": "est" if matched else "rough",
        "text": text_out,
    }
