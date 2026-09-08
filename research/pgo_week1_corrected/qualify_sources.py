"""Qualify the immutable September 8 Week 1 source capture."""

import csv
import gzip
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SOURCE = OUT / "sources-20260908T150137Z"
CHARTER = ROOT / "research/pgo_week1_corrected/charter.md"
OLD_SNAPSHOT = ROOT / "docs/evidence/forecast-lab-2026/september-07/snapshot.json"
WEEKLY = ROOT / "docs/evidence/forecast-lab-2026/weekly/20260907T223412922311Z.json"
TEAMS = set("ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS".split())
CHECKS = {}


def check(name, condition):
    CHECKS[name] = bool(condition)


def stamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must have a timezone")
    return result.astimezone(timezone.utc)


def team(value):
    return {"LA": "LAR", "AZ": "ARI", "JAC": "JAX", "WSH": "WAS"}.get(value, value)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(name):
    with gzip.open(SOURCE / name, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def official_games(page):
    chunks = []
    for script in re.findall(r"<script[^>]*>(.*?)</script>", page, re.S):
        match = re.fullmatch(r"self\.__next_f\.push\((.*)\)", script, re.S)
        if match:
            value = json.loads(match[1])
            if len(value) == 2 and value[0] == 1:
                chunks.append(value[1])
    text = "".join(chunks)
    games, conflicts = {}, []
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{"id":', text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except ValueError:
            continue
        if not isinstance(value, dict) or not {"id", "homeTeam", "awayTeam", "date", "week", "season"} <= value.keys():
            continue
        if value["week"] != 1 or value["season"] != 2026 or value.get("seasonType") != "REG" or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value["date"]):
            continue
        def code(entry):
            return team(entry.get("abbreviation") or entry["currentLogo"].rsplit("/", 1)[-1])
        row = {"away": code(value["awayTeam"]), "home": code(value["homeTeam"]),
               "kickoff": stamp(value["date"]).isoformat(), "official_id": value["id"],
               "neutral_site": value.get("neutralSite")}
        if value["id"] in games and games[value["id"]] != row:
            conflicts.append(value["id"])
        games[value["id"]] = row
    check("official_html_no_conflicting_games", not conflicts)
    return list(games.values())


INJURY_ROWS = {
    "NE": [
        ("00-0036981", "Christian Barmore", "DT", "Knee", "Full Participation", None),
        ("00-0037413", "Ben Brown", "OL", "Knee", "Did Not Participate", "Out"),
        ("00-0040734", "TreVeyon Henderson", "RB", "Ankle", "Did Not Participate", None),
    ],
    "SEA": [
        ("00-0039793", "AJ Barner", "TE", "Oblique", "Full Participation", None),
        ("00-0039020", "Anthony Bradford", "G", "Knee", "Full Participation", None),
        ("00-0040733", "Nick Emmanwori", "S", "Ankle", "Limited Participation", None),
        ("00-0040648", "Tory Horton", "WR", "Hamstring", "Limited Participation", None),
        ("00-0036363", "Josh Jones", "T", "Knee", "Limited Participation", None),
        ("00-0040873", "Julian Neal", "CB", "Quadricep", "Full Participation", None),
        ("00-0038765", "Ty Okada", "S", "Hamstring", "Did Not Participate", None),
        ("00-0038797", "Emanuel Wilson", "RB", "Hamstring", "Full Participation", None),
    ],
}
TEAM_PAGE = {
    "NE": ("patriots-week1-injury.html", "https://www.patriots.com/news/week-1-injury-report-patriots-at-seahawks"),
    "SEA": ("seahawks-week1-injury.html", "https://www.seahawks.com/news/2026-week-1-injury-report-seahawks-vs-patriots"),
}


def qualify():
    issued_at = datetime.now(timezone.utc)
    capture_path = SOURCE / "capture.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    captured = stamp(capture["captured_at"])
    sources = {row["file"]: row for row in capture["sources"]}
    check("thirteen_unique_capture_entries", len(sources) == len(capture["sources"]) == 13)
    raw_sources = []
    for name, row in sources.items():
        path = SOURCE / name
        check("https_source:" + name, row["url"].startswith("https://"))
        check("hash_size_status:" + name, row["status"] == 200 and sha(path) == row["sha256"] and path.stat().st_size == row["bytes"])
        check("capture_chronology:" + name, stamp(row["started_at"]) <= stamp(row["captured_at"]) <= captured <= issued_at)
        if row.get("last_modified"):
            check("last_modified_before_capture:" + name, parsedate_to_datetime(row["last_modified"]) <= stamp(row["captured_at"]))
        raw_sources.append({key: row.get(key) for key in ("file", "url", "status", "bytes", "sha256", "started_at", "captured_at", "last_modified")})

    provider_metadata = []
    for tag, filename, asset_name in (("rosters", "roster.csv.gz", "roster_2026.csv.gz"),
                                      ("depth_charts", "depth.csv.gz", "depth_charts_2026.csv.gz"),
                                      ("schedules", "schedule.csv.gz", "games.csv.gz")):
        release = json.loads((SOURCE / (tag + "-release.json")).read_text(encoding="utf-8"))
        provider_text = json.loads((SOURCE / (tag + "-timestamp.json")).read_text(encoding="utf-8"))["last_updated"]
        local_time, zone = provider_text.rsplit(" ", 1)
        provider = datetime.fromisoformat(local_time).replace(tzinfo=ZoneInfo("America/New_York"))
        check("provider_timestamp:" + tag, provider.tzname() == zone and provider <= stamp(sources[filename]["captured_at"]))
        check("release_metadata:" + tag, release["tag_name"] == tag and not release["draft"] and not release["prerelease"])
        for asset_name2, target in ((asset_name, filename), ("timestamp.json", tag + "-timestamp.json")):
            assets = [asset for asset in release["assets"] if asset["name"] == asset_name2]
            check("one_release_asset:" + tag + ":" + asset_name2, len(assets) == 1)
            if len(assets) == 1:
                asset = assets[0]
                check("release_digest_size:" + tag + ":" + asset_name2,
                      asset["digest"] == "sha256:" + sources[target]["sha256"] and asset["size"] == sources[target]["bytes"])
        provider_metadata.append({"tag": tag, "provider_timestamp": provider.isoformat(), "release_sha256": sources[tag + "-release.json"]["sha256"]})

    roster = read_csv("roster.csv.gz")
    depth = read_csv("depth.csv.gz")
    check("roster_2026_week1_regular", all(row["season"] == "2026" and row["week"] == "1" and row["game_type"] == "REG" for row in roster))
    roster_index = defaultdict(list)
    for row in roster:
        roster_index[team(row["team"]), row["gsis_id"]].append(row)
    check("roster_32_teams", {team(row["team"]) for row in roster} == TEAMS)
    check("no_roster_team_gsis_duplicates", all(len(rows) == 1 for rows in roster_index.values()))

    latest = max(row["dt"] for row in depth if stamp(row["dt"]) <= stamp(sources["depth.csv.gz"]["captured_at"]))
    current = [row for row in depth if row["dt"] == latest]
    qbs = [row for row in current if row["pos_abb"] == "QB"]
    check("coherent_depth_all_32", {team(row["team"]) for row in current} == {team(row["team"]) for row in qbs} == TEAMS)
    chosen_qbs = []
    for club in sorted(TEAMS):
        club_qbs = sorted((row for row in qbs if team(row["team"]) == club), key=lambda row: int(row["pos_rank"]))
        check("contiguous_qb_depth:" + club, [int(row["pos_rank"]) for row in club_qbs] == list(range(1, len(club_qbs) + 1)))
        starter = club_qbs[0]
        matches = roster_index[club, starter["gsis_id"]]
        check("starter_unique_active:" + club, len(matches) == 1 and matches[0]["position"] == "QB" and matches[0]["status"] == "ACT" and matches[0]["espn_id"] == starter["espn_id"])
        if len(matches) == 1:
            chosen_qbs.append({"team": club, "gsis_id": starter["gsis_id"], "player_name": matches[0]["full_name"],
                               "roster_status": matches[0]["status"], "depth_rank": 1})
    check("exactly_32_unique_expected_qbs", len(chosen_qbs) == len({row["gsis_id"] for row in chosen_qbs}) == 32)
    old = json.loads(OLD_SNAPSHOT.read_text(encoding="utf-8"))
    old_qbs = {row["team"]: (row["qb_gsis_id"], row["qb_name"]) for row in old["teams"]}
    starter_changes = [{"team": row["team"], "old_gsis_id": old_qbs[row["team"]][0], "old_player_name": old_qbs[row["team"]][1],
                        "fresh_gsis_id": row["gsis_id"], "fresh_player_name": row["player_name"]}
                       for row in chosen_qbs if old_qbs[row["team"]] != (row["gsis_id"], row["player_name"])]

    schedule = [row for row in read_csv("schedule.csv.gz") if row["season"] == "2026" and row["game_type"] == "REG" and row["week"] == "1"]
    check("sixteen_unique_week1_games", len(schedule) == len({row["game_id"] for row in schedule}) == 16)
    games = []
    for row in schedule:
        kickoff = datetime.fromisoformat(row["gameday"] + "T" + row["gametime"]).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        games.append({"game_id": row["game_id"], "away": team(row["away_team"]), "home": team(row["home_team"]),
                      "kickoff": kickoff.isoformat(), "lock_at": (kickoff - timedelta(minutes=60)).isoformat(),
                      "location": row["location"], "away_rest": int(row["away_rest"]), "home_rest": int(row["home_rest"])})
    official = official_games((SOURCE / "nfl-week-1.html").read_text(encoding="utf-8"))
    key = lambda row: (row["away"], row["home"], stamp(row["kickoff"]))
    check("official_week1_exact", len(official) == 16 and {key(row) for row in official} == {key(row) for row in games})
    registered = json.loads(WEEKLY.read_text(encoding="utf-8"))["games"]
    registered_by_id = {row["game_id"]: row for row in registered}
    schedule_changes = []
    for row in games:
        prior = registered_by_id.get(row["game_id"])
        changed = {} if prior else {"identity": {"registered": None, "fresh": row}}
        if prior:
            for field in ("away", "home", "location", "away_rest", "home_rest"):
                if prior[field] != row[field]: changed[field] = {"registered": prior[field], "fresh": row[field]}
            if stamp(prior["kickoff"]) != stamp(row["kickoff"]): changed["kickoff"] = {"registered": prior["kickoff"], "fresh": row["kickoff"]}
        if changed: schedule_changes.append({"game_id": row["game_id"], "changes": changed})
    check("registered_week1_identity_unchanged", len(registered_by_id) == 16 and not schedule_changes)
    check("all_cutoffs_after_qualification", all(stamp(row["lock_at"]) > issued_at for row in games))

    raw_injury_sources = []
    for filename in ("nfl-injuries.html", "patriots-week1-injury.html", "seahawks-week1-injury.html"):
        row = sources[filename]
        raw_injury_sources.append({"file": filename, "url": row["url"], "status": row["status"], "bytes": row["bytes"],
                                   "sha256": row["sha256"], "captured_at": row["captured_at"]})
    coverage = {}
    roster_status_counts = Counter(row["status"] for row in roster)
    for club in sorted(TEAMS):
        if club in TEAM_PAGE:
            filename, url = TEAM_PAGE[club]
            page_text = html.unescape((SOURCE / filename).read_text(encoding="utf-8", errors="strict"))
            observations = []
            for gsis_id, name, position, injury, practice, game_status in INJURY_ROWS[club]:
                matches = roster_index[club, gsis_id]
                check("injury_roster_identity:" + gsis_id, len(matches) == 1 and matches[0]["full_name"] == name)
                check("injury_page_name:" + gsis_id, name in page_text)
                observations.append({"gsis_id": gsis_id, "player_name": name, "report_position": position,
                                     "roster_position": matches[0]["position"] if len(matches) == 1 else None, "injury": injury,
                                     "practice_status": practice, "game_status": game_status, "report_date": "2026-09-07",
                                     "source_url": url, "model_treatment": "unadjusted" if game_status != "Out" else "known_unavailable_unpriced"})
            known = [dict(row) for row in observations if row["game_status"] == "Out"]
            coverage[club] = {"source_kind": "formal_injury_report", "report_date": "2026-09-07", "source_url": url,
                              "source_file": filename, "captured_at": sources[filename]["captured_at"],
                              "notes": ["Monday practice report; later final game designations were not yet available at capture.",
                                        "The corrected base forecast does not numerically adjust non-QB availability."],
                              "known_unavailable": known, "observations": observations}
        else:
            coverage[club] = {"source_kind": "no_formal_report", "report_date": None,
                              "source_url": sources["nfl-injuries.html"]["url"], "source_file": "nfl-injuries.html",
                              "captured_at": sources["nfl-injuries.html"]["captured_at"],
                              "notes": ["No formal team report appeared in the captured NFL injury overview at this point in the Week 1 reporting cycle.",
                                        "Unknown coverage is not evidence that the roster is healthy."],
                              "known_unavailable": [], "observations": []}
    known_unavailable = [row for item in coverage.values() for row in item["known_unavailable"]]
    check("formal_two_unknown_thirty", Counter(row["source_kind"] for row in coverage.values()) == {"formal_injury_report": 2, "no_formal_report": 30})
    check("one_confirmed_unavailable", len(known_unavailable) == 1 and known_unavailable[0]["gsis_id"] == "00-0037413")
    check("no_expected_qb_confirmed_unavailable", not ({row["gsis_id"] for row in chosen_qbs} & {row["gsis_id"] for row in known_unavailable}))

    reserve_exempt = [{"team": team(row["team"]), "gsis_id": row["gsis_id"], "player_name": row["full_name"],
                       "position": row["position"], "raw_status": row["status"], "raw_status_description": row["status_description_abbr"],
                       "model_treatment": "excluded_from_ACT_eligibility_unpriced"}
                      for row in roster if row["status"] in {"RES", "EXE"}]
    return {
        "schema_version": 1, "artifact_kind": "PGO_WEEK1_CORRECTED_SOURCE_QUALIFICATION", "status": "PASS",
        "issued_at": issued_at.isoformat(), "charter_sha256": sha(CHARTER),
        "capture_manifest_sha256": sha(capture_path), "capture_status_field": "status",
        "raw_sources": raw_sources, "provider_metadata": provider_metadata,
        "depth_snapshot": latest, "chosen_qbs": chosen_qbs, "starter_changes_from_september_07": starter_changes,
        "week1_games": sorted(games, key=lambda row: (row["kickoff"], row["game_id"])),
        "registered_weekly_revision_sha256": sha(WEEKLY), "registered_schedule_changes": schedule_changes,
        "raw_injury_sources": raw_injury_sources, "coverage": coverage,
        "injury_coverage_summary": {"formal_reports": 2, "no_formal_report": 30, "observations": sum(len(row["observations"]) for row in coverage.values()),
                                    "known_unavailable": len(known_unavailable), "expected_qb_blocks": 0},
        "roster_status_counts": dict(sorted(roster_status_counts.items())),
        "reserve_exempt_roster_exclusions": reserve_exempt,
        "reserve_exempt_note": "Raw RES/EXE codes establish non-ACT eligibility only; they are not decoded here as injury, PUP, suspension, or health claims and they receive no numerical availability adjustment.",
        "limitations": ["Engineering source qualification only; all predictions remain experimental HOLD.",
                        "ACT is roster eligibility, not a claim of health or final game-day availability.",
                        "The corrected base forecast is explicitly unadjusted for non-QB injury and availability.",
                        "Thirty teams had no formal report in the captured NFL overview and remain unknown pending later pre-cutoff refresh.",
                        "No questionable/doubtful practice-status probability or numerical availability mapping is admitted."],
    }


if __name__ == "__main__":
    path = SOURCE / "qualification.json"
    if path.exists():
        raise SystemExit("Refusing to overwrite existing qualification.json")
    try:
        receipt = qualify()
    except Exception as error:
        CHECKS["completed_without_error"] = False
        receipt = {"schema_version": 1, "artifact_kind": "PGO_WEEK1_CORRECTED_SOURCE_QUALIFICATION",
                   "status": "BLOCKED", "error": f"{type(error).__name__}: {error}"}
    receipt["script_sha256"] = sha(Path(__file__))
    receipt["checks"] = CHECKS
    receipt["failed_checks"] = [name for name, passed in CHECKS.items() if not passed]
    if not CHECKS or not all(CHECKS.values()):
        receipt["status"] = "BLOCKED"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(receipt["status"], "checks", len(CHECKS), "failed", receipt["failed_checks"])
    raise SystemExit(0 if receipt["status"] == "PASS" else 1)
