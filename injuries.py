"""NFL injury scanner for the McCabe Method — who's hurt that actually matters.

Reads Sleeper's player feed (injury status + body part + severity + depth order)
and surfaces the injuries that could move a rating, not the noise:

  - Starters first, plus EFFECTIVE STARTERS (a backup promoted because the man
    ahead of him is out — flagged if he then gets hurt too).
  - All O-line and all defense are in scope, not just skill positions.
  - CLUSTER flags when 2+ starters in the same position group are hurt (e.g. both
    starting safeties = a DB-group cluster).
  - Severity from Sleeper (IR/PUP/Out/Doubtful = severe; Questionable = watch),
    with body part + notes.
  - Depth is corroborated against the Ourlads cache; disagreements are flagged for
    Sean's judgment rather than trusting one source (every depth source has holes).

Read-only: never edits ratings. Findings are evidence for the Update-ratings flow,
exactly like results.py signals. Stdlib only.

CLI:
    python3 injuries.py                 # all 32 teams, worst first
    python3 injuries.py 49ers           # one team (name/city/nickname/abbr)
    python3 injuries.py --all           # include backups (folded by default)
    python3 injuries.py --refresh       # force a fresh Sleeper pull first
    python3 injuries.py --json          # machine-readable (for the agent / a future page)

Return-timeline estimates (recovery.py + data/injury_recovery.csv) attach a projected
return window per injury — typical recovery for the diagnosis, anchored to the last
report; a planning aid (ranges, not a diagnosis), never auto-applied to a rating.
"""

import json
import os
import re
import sys

import sleeper

try:
    import recovery as _recovery
except Exception:  # noqa: BLE001
    _recovery = None
try:
    import team_view as _tv
except Exception:  # noqa: BLE001
    _tv = None
try:
    import depthchart as _depthchart
except Exception:  # noqa: BLE001
    _depthchart = None

# --- position taxonomy -------------------------------------------------------

# Map a base position (Sleeper `position`) to a coarse group, used for clusters
# and for the "all OL + all defense" scope.
POSITION_GROUP = {
    "QB": "QB", "RB": "RB", "FB": "RB",
    "WR": "WR", "TE": "TE",
    "OL": "OL", "OT": "OL", "OG": "OL", "T": "OL", "G": "OL", "C": "OL", "LT": "OL",
    "RT": "OL", "LG": "OL", "RG": "OL",
    "DL": "DL", "DE": "DL", "DT": "DL", "NT": "DL", "EDGE": "DL",
    "LB": "LB", "OLB": "LB", "ILB": "LB", "MLB": "LB",
    "DB": "DB", "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "NB": "DB",
    "K": "ST", "P": "ST", "LS": "ST",
}
DEF_GROUPS = {"DL", "LB", "DB"}

# Starter slots per Sleeper depth_chart_position. Sleeper gives slot-precise codes
# for most spots (one starter each) but lumps the O-line as "OL" (~5 starters) and
# occasionally lumps a defensive front/secondary.
STARTER_SLOTS = {"OL": 5, "DL": 4, "LB": 3, "DB": 4, "WR": 3}

# Severity: rank + whether it's "severe" (out/likely-out) vs a "watch" (Questionable).
_SEVERITY = {
    "IR": 5, "PUP": 5, "NFI": 5, "SUS": 4, "SUSPENSION": 4, "OUT": 4,
    "DOUBTFUL": 3, "DNR": 3, "NA": 3, "COV": 2, "QUESTIONABLE": 1, "PROBABLE": 1,
}
SEVERE_MIN = 3  # severity >= this is "severe" (out / likely out)


def _sev(status):
    return _SEVERITY.get((status or "").strip().upper(), 1 if status else 0)


def _group(position):
    return POSITION_GROUP.get((position or "").upper(), (position or "").upper() or "?")


def _slots(dcp):
    return STARTER_SLOTS.get((dcp or "").upper(), 1)


# --- name matching for Ourlads corroboration ---------------------------------

_SUFFIXES = (" jr", " sr", " ii", " iii", " iv", " v")


def _norm(name):
    s = (name or "").lower().replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]", "", s).strip()
    for suf in _SUFFIXES:
        if s.endswith(suf):
            s = s[: -len(suf)]
    return " ".join(s.split())


# --- Ourlads depth corroboration ---------------------------------------------

_RESERVE_POS = {"IR", "PUP", "NFI"}


def _ourlads_depth(abbr):
    """Cached Ourlads depth for a team, or {} — never scrapes (cache-only)."""
    if not _depthchart or not abbr:
        return {}
    try:
        if not os.path.exists(_depthchart.cache_path(abbr)):
            return {}
        return _depthchart.get_depth(abbr).get("depth", {})
    except Exception:  # noqa: BLE001
        return {}


def _ourlads_rank(depth, name):
    """(position, 1-based index) of a player in Ourlads' real depth rows, or None.

    Reserve buckets (IR/PUP/NFI) are ignored — a name found only there is treated as
    'not on the active chart'.
    """
    target = _norm(name)
    if not target:
        return None
    for pos, players in depth.items():
        if pos in _RESERVE_POS:
            continue
        for i, pl in enumerate(players):
            if _norm(pl.get("name", "")) == target:
                return (pos, i + 1)
    return None


# --- core analysis -----------------------------------------------------------

def analyze_team(abbr, players, ourlads):
    """Return {clusters, injuries} for one team from its normalized player list."""
    # Group players by slot (depth_chart_position) for starter/promotion logic.
    slots = {}
    for p in players:
        if p.get("dcp") and p.get("order") is not None:
            slots.setdefault(p["dcp"], []).append(p)
    for lst in slots.values():
        lst.sort(key=lambda p: p["order"])

    def role_of(p):
        """STARTER / EFFECTIVE / BACKUP / SHELVED for an injured player."""
        dcp, order = p.get("dcp"), p.get("order")
        if not dcp or order is None:
            return "SHELVED"  # IR usually drops depth order — role can't be read
        group = slots.get(dcp, [])
        s = _slots(dcp)
        rank = 1 + sum(1 for q in group if q["order"] < order)  # 1-based by order
        if rank <= s:
            return "STARTER"
        ahead_healthy = sum(
            1 for q in group if q["order"] < order and _sev(q.get("status")) < SEVERE_MIN
        )
        if ahead_healthy < s:
            return "EFFECTIVE"  # promoted into a starter slot because those ahead are out
        return "BACKUP"

    injuries = []
    for p in players:
        if not p.get("status"):
            continue
        role = role_of(p)
        rank = None
        odepth = _ourlads_rank(ourlads, p["name"])
        if role in ("STARTER", "EFFECTIVE"):
            # corroborate: does Ourlads also see a starter?
            if odepth is None:
                agree = "absent"      # not on Ourlads active chart
            elif odepth[1] == 1:
                agree = "agrees"
            else:
                agree = "differs"     # Ourlads has them as a backup
        else:
            agree = None
        injuries.append({
            "name": p["name"], "position": p.get("position"), "dcp": p.get("dcp"),
            "order": p.get("order"), "group": _group(p.get("position")),
            "status": p.get("status"), "body_part": p.get("body_part"),
            "notes": p.get("notes"), "role": role, "severity": _sev(p.get("status")),
            "practice": p.get("practice"), "start": p.get("start"),
            "updated": p.get("updated"),
            "return_est": _recovery.estimate(p) if _recovery else None,
            "ourlads": (f"{odepth[0]} {odepth[1]}" if odepth else None),
            "ourlads_agree": agree,
        })

    # Clusters: 2+ severe injuries to (effective) starters in the same group.
    by_group = {}
    for inj in injuries:
        if inj["role"] in ("STARTER", "EFFECTIVE") and inj["severity"] >= SEVERE_MIN:
            by_group.setdefault(inj["group"], []).append(inj["name"])
    clusters = [
        {"group": g, "count": len(names), "players": names}
        for g, names in by_group.items() if len(names) >= 2
    ]
    clusters.sort(key=lambda c: -c["count"])

    injuries.sort(key=lambda i: (-i["severity"], i["role"] != "STARTER", i["group"]))
    return {"clusters": clusters, "injuries": injuries}


def build_report(bundle, only_team=None, include_backups=False):
    players = sleeper.nfl_players(bundle)
    by_team = {}
    for p in players:
        by_team.setdefault(p["team"], []).append(p)

    teams = {}
    for abbr, roster in by_team.items():
        if only_team and abbr != only_team:
            continue
        res = analyze_team(abbr, roster, _ourlads_depth(abbr))
        shown = [i for i in res["injuries"] if _keep(i, include_backups)]
        if shown or res["clusters"]:
            teams[abbr] = {"clusters": res["clusters"], "injuries": shown}

    total_inj = sum(len(t["injuries"]) for t in teams.values())
    total_clusters = sum(len(t["clusters"]) for t in teams.values())
    return {
        "generated": bundle.get("fetched_at"),
        "source_fetched_at": bundle.get("fetched_at"),
        "from_cache": bundle.get("from_cache"),
        "summary": {"teams": len(teams), "injuries": total_inj, "clusters": total_clusters},
        "teams": teams,
    }


# --- per-team detail + formation (for the dashboard field diagram) -----------

OFFENSE_GROUPS = {"QB", "RB", "WR", "TE", "OL"}
DEFENSE_GROUPS = {"DL", "LB", "DB"}
# Sleeper lumps the O-line as "OL" with order 1..5 — map those to line slots L→R.
_OL_ORDER_SLOTS = ["LT", "LG", "C", "RG", "RT"]


def team_detail(bundle, abbr, include_backups=True):
    """Everything the per-team dashboard view needs: the injuries list plus, per
    position slot, the FULL depth (starter → backups) with injury info attached, so
    the field diagram can show every player in depth order and highlight the hurt ones."""
    players = [p for p in sleeper.nfl_players(bundle) if p["team"] == abbr]
    odepth = _ourlads_depth(abbr)
    res = analyze_team(abbr, players, odepth)
    inj_by_norm = {_norm(i["name"]): i for i in res["injuries"]}
    rec_by_norm = {_norm(p["name"]): p for p in players}  # Sleeper record by name

    def _update(rec):
        """The latest Sleeper injury info for a player (or None if no record)."""
        if not rec:
            return None
        return {"status": rec.get("status"), "body_part": rec.get("body_part"),
                "notes": rec.get("notes"), "practice": rec.get("practice"),
                "start": rec.get("start"), "updated": rec.get("updated")}

    def entry(name, ourlads=None):
        disp = name.title() if name.isupper() else name  # Ourlads sometimes ALL-CAPS
        e = {"name": disp, "injury": inj_by_norm.get(_norm(name)),
             "update": _update(rec_by_norm.get(_norm(name)))}
        if ourlads is not None:  # O-line comes from Ourlads; keep its note as a fallback
            e["ourlads_note"] = (ourlads.get("note") or ourlads.get("status") or "").strip()
        return e

    # Sleeper gives slot-precise order for every spot EXCEPT the O-line (dcp "OL",
    # order null). So take skill + defense depth from Sleeper, and the 5 O-line slots
    # from the Ourlads cache (slot-precise, in depth order there), matching injuries by name.
    slots = {}
    for p in players:
        if p.get("dcp") and p.get("order") is not None:
            slots.setdefault(p["dcp"], []).append(p)
    for lst in slots.values():
        lst.sort(key=lambda p: p["order"])

    offense, defense = [], []
    for dcp, lst in slots.items():
        if dcp.upper() == "OL":
            continue  # sourced from Ourlads below
        grp = _group(lst[0].get("position"))  # group by the starter's position
        item = {"slot": dcp, "group": grp, "players": [entry(p["name"]) for p in lst]}
        if grp in OFFENSE_GROUPS:
            offense.append(item)
        elif grp in DEFENSE_GROUPS:
            defense.append(item)

    for slot in _OL_ORDER_SLOTS:  # LT LG C RG RT — Ourlads list is in depth order
        row = odepth.get(slot) or []
        players_out = [entry(pl["name"], ourlads=pl) for pl in row if pl.get("name")]
        if players_out:
            offense.append({"slot": slot, "group": "OL", "players": players_out})

    return {
        "abbr": abbr, "name": _team_name(abbr),
        "clusters": res["clusters"],
        "injuries": [i for i in res["injuries"] if _keep(i, include_backups)],
        "offense": offense, "defense": defense,
    }


def league_grid(bundle):
    """One row per NFL team (all 32) with injury counts — for the landing grid."""
    players = sleeper.nfl_players(bundle)
    by_team = {}
    for p in players:
        by_team.setdefault(p["team"], []).append(p)
    rows = []
    for abbr in sorted(sleeper.NFL_ABBRS):
        res = analyze_team(abbr, by_team.get(abbr, []), _ourlads_depth(abbr))
        severe_starters = sum(
            1 for i in res["injuries"]
            if i["role"] in ("STARTER", "EFFECTIVE") and i["severity"] >= SEVERE_MIN)
        rows.append({
            "abbr": abbr, "name": _team_name(abbr),
            "severe_starters": severe_starters,
            "clusters": len(res["clusters"]),
            "total": len(res["injuries"]),
        })
    return rows


def _keep(inj, include_backups):
    """Default view: every (effective) starter with any active injury, plus SEVERE
    injuries to anyone else (backups and no-depth-slot players).

    --all also shows non-severe backups / depth pieces. This keeps every OL / defense /
    skill *starter* visible — including Questionable ones — while folding depth noise.
    A SHELVED player (no readable depth slot, e.g. dropped after going on IR) surfaces
    only when the injury is severe, since a Questionable no-slot player is almost always
    a depth piece.
    """
    if inj["role"] in ("STARTER", "EFFECTIVE"):
        return True
    if include_backups:
        return True
    return inj["severity"] >= SEVERE_MIN  # severe injuries surface even for backups/shelved


# --- rendering ---------------------------------------------------------------

_TEAM_NAME = {}  # abbr -> full name, filled lazily from ESPN when available


def _team_name(abbr):
    global _TEAM_NAME
    if not _TEAM_NAME and _tv:
        try:
            _TEAM_NAME = {m["abbr"]: n for n, m in _tv.espn_team_index().items()}
        except Exception:  # noqa: BLE001
            _TEAM_NAME = {"_": "_"}
    return _TEAM_NAME.get(abbr, "")


def _fmt_injury(inj):
    detail = inj["status"]
    extra = "; ".join(x for x in (inj.get("body_part"), inj.get("notes")) if x)
    if extra:
        detail += f" ({extra})"
    tag = inj["role"].lower()
    if inj["role"] == "EFFECTIVE":
        tag = "effective starter (promoted)"
    if inj["role"] == "SHELVED":
        # no readable depth slot — common when a starter goes on IR and gets dropped
        tag = "role unclear (off depth chart) — verify"
    if inj.get("ourlads_agree") == "differs":
        tag += f" · ⚠ Ourlads has him at {inj['ourlads']}"
    elif inj.get("ourlads_agree") == "absent":
        tag += " · not on Ourlads chart"
    pos = inj.get("position") or inj.get("dcp") or "?"
    line = f"    {pos:<3} {inj['name']} — {detail}   [{tag}]"
    est = inj.get("return_est")
    if est:
        line += f"\n        ⏱ {est['text']}"
    return line


def print_report(report):
    gen = report.get("generated") or "?"
    cache = " (cached)" if report.get("from_cache") else " (fresh)"
    s = report["summary"]
    print(f"\n=== NFL Injury Report — {gen}{cache} · source: Sleeper ===\n")
    print(f"{s['teams']} teams with rating-relevant injuries · "
          f"{s['injuries']} entries · {s['clusters']} position-group clusters")
    print("severity: IR/PUP/Out/Doubtful = severe · Questionable = watch\n")

    # worst teams first: by cluster count, then # severe starter injuries
    def team_key(item):
        abbr, t = item
        severe = sum(1 for i in t["injuries"]
                     if i["role"] in ("STARTER", "EFFECTIVE") and i["severity"] >= SEVERE_MIN)
        return (-len(t["clusters"]), -severe, abbr)

    for abbr, t in sorted(report["teams"].items(), key=team_key):
        name = _team_name(abbr)
        print(f"{abbr}" + (f" — {name}" if name else ""))
        for c in t["clusters"]:
            print(f"  ⚠ CLUSTER: {c['group']} — {c['count']} starters hurt "
                  f"({', '.join(c['players'])})")
        severe = [i for i in t["injuries"] if i["severity"] >= SEVERE_MIN]
        watch = [i for i in t["injuries"] if i["severity"] < SEVERE_MIN]
        if severe:
            print("  severe:")
            for inj in severe:
                print(_fmt_injury(inj))
        if watch:
            print("  watch:")
            for inj in watch:
                print(_fmt_injury(inj))
        print()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    include_backups = "--all" in argv
    refresh = "--refresh" in argv

    only_team = None
    if args:
        query = " ".join(args)
        name = _tv.resolve_team(query) if _tv else None
        only_team = (_tv.team_abbr(name) if (name and _tv) else None)
        if not only_team:
            # allow a raw abbr even if team_view can't resolve
            up = query.strip().upper()
            only_team = up if up in sleeper.NFL_ABBRS else None
        if not only_team:
            print(f"could not resolve team: {query!r}")
            return 1

    bundle = sleeper.get_players(force=refresh)
    report = build_report(bundle, only_team=only_team, include_backups=include_backups)
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
