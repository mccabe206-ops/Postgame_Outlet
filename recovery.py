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


def estimate(inj, today=None):
    """Return-timeline estimate for one injury dict, or None if not estimable."""
    status = (inj.get("status") or "").strip().upper()
    if not status:
        return None
    text = ((inj.get("body_part") or "") + " " + (inj.get("notes") or "")).lower()
    surgery_flag = "surger" in text
    today = today or datetime.now(timezone.utc).date()
    anchor, kind = _anchor(inj)
    anchor = anchor or today

    row = _match(text, surgery_flag)
    confidence = "est"
    reserve = status in ("IR", "PUP", "NFI")  # reserve list = out a minimum of 4 games
    if row and row["weeks_min"] is not None:
        wmin, wmax, label = row["weeks_min"], row["weeks_max"], row["label"]
        matched = True
        if surgery_flag and wmax is not None and "surg" not in label.lower():
            label += " (surgery)"
    else:
        fb = _STATUS_FALLBACK.get(status)
        if not fb:
            return None
        wmin, wmax, label = fb
        matched = False
        confidence = "rough"  # no body-part signal — status-only

    ret_low = anchor + timedelta(weeks=wmin)
    ret_high = anchor + timedelta(weeks=wmax) if wmax is not None else None
    # NFL reserve list is a MINIMUM of 4 games counted from Week 1 (not the injury
    # date), so the body-part recovery can only push the return LATER, never earlier
    # than ~Week 5. Floor the return dates accordingly.
    if reserve:
        floor = _week1() + timedelta(weeks=4)  # ~Week 5 kickoff
        ret_low = max(ret_low, floor)
        if ret_high is not None:
            ret_high = max(ret_high, floor)
    week_low = _to_week(ret_low)
    week_high = _to_week(ret_high) if ret_high else None
    season_ending = week_low is not None and week_low > _LAST_REG_WEEK
    target = ret_high or ret_low  # the "should be back by" date
    duration = _duration(wmin, wmax)

    if reserve and not matched:
        # on IR/PUP with an undisclosed body part — don't fake a precise week.
        eta = "out ≥4 games (min)"
        duration = "≥4 games"
        text_out = (f"On {status} — body part undisclosed; out a minimum of 4 games, "
                    "may be season-ending · rough")
    elif season_ending:
        eta = "out for the season"
        text_out = f"{eta} · typical {duration} ({label})"
    else:
        if target <= today:
            eta = "likely available"        # typical recovery has already elapsed
        elif (week_low or 1) <= 1 and (week_high is None or week_high <= 1):
            eta = "by ~Week 1"              # heals before the season opens
        elif wmax is None:
            eta = f"~Week {week_low}+ ({_month_word(target)})"
        elif week_high and week_high != week_low:
            eta = f"~Weeks {week_low}–{week_high} ({_month_word(target)})"
        else:
            eta = f"~Week {week_low} ({_month_word(target)})"
        text_out = f"{eta} · typical {duration} ({label})"
        if reserve:
            text_out += " · on reserve (min 4 games)"
        if confidence == "rough":
            text_out += " · rough"

    return {
        "label": label, "weeks_min": wmin, "weeks_max": wmax,
        "anchor": anchor.isoformat(), "anchor_kind": kind or "assumed-today",
        "return_low": ret_low.isoformat(),
        "return_high": ret_high.isoformat() if ret_high else None,
        "week_low": week_low, "week_high": week_high,
        "season_ending": season_ending, "confidence": confidence,
        "duration": duration, "eta": eta, "text": text_out,
    }
