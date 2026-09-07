#!/usr/bin/env python3
"""Build a private McCabe-versus-PGO ratings comparison preview."""

import argparse
import csv
import hashlib
import html
import json
import math
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import generate_site
import pgo_challenger
import pgo_fantasy_prospective as fantasy_prospective
import pgo_model
import snapshot
from release_ratings import atomic_write_text, load_release_rows, rating_total


HERE = Path(__file__).resolve().parent
MCCABE_PATH = HERE / "data" / "ratings.csv"
MODEL_PATH = HERE / "research" / "pgo_v1" / "ratings_2026_preseason.csv"
BACKTEST_PATH = HERE / "research" / "pgo_v1" / "backtest.json"
SNAPSHOTS_PATH = HERE / "data" / "snapshots.json"
PUBLIC_OUTPUT = HERE / "docs" / "index.html"
MCCABE_SNAPSHOT_LABEL = "Preseason 2026"
MODEL_NUMBER_FIELDS = (
    "full_strength_rating",
    "availability_adjustment",
    "current_lineup_rating",
    "headline_rating",
)


def default_preview_path(today=None):
    today = today or datetime.now().astimezone().date()
    return HERE / "output" / "pgo-comparison-preview" / today.isoformat() / "index.html"


def _finite(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {label}: {value!r}") from error
    if not math.isfinite(number):
        raise ValueError(f"Invalid {label}: {value!r}")
    return number


def load_mccabe_rows(path):
    parsed = []
    for row in load_release_rows(path):
        team = row.get("team", "")
        if team not in generate_site.TEAM:
            raise ValueError(f"Unknown McCabe team: {team!r}")
        components = {
            name: _finite(row.get(name), f"{team} {name}")
            for name in ("qb_value", "off_value", "def_value")
        }
        rating = round(rating_total(components), 1)
        parsed.append({
            "team": team,
            "abbr": generate_site.TEAM[team][0],
            "rating": rating,
        })
    expected = set(pgo_model.CURRENT_TEAMS)
    if len(parsed) != 32 or {row["abbr"] for row in parsed} != expected:
        raise ValueError("McCabe comparison requires exactly the 32 current teams")
    parsed.sort(key=lambda row: -row["rating"])
    for rank, row in enumerate(parsed, 1):
        row["rank"] = rank
    return parsed


def load_mccabe_snapshot(path, rows):
    snaps = snapshot.load_snaps(path)
    if MCCABE_SNAPSHOT_LABEL not in snaps:
        raise ValueError(f"Missing McCabe snapshot: {MCCABE_SNAPSHOT_LABEL}")
    entry = snapshot.normalize_snapshot_entry(snaps[MCCABE_SNAPSHOT_LABEL])
    if not entry["published_at"]:
        raise ValueError("McCabe comparison snapshot has no published_at")
    current = {row["team"]: row["rating"] for row in rows}
    frozen = {
        row["team"]: _finite(row.get("rating"), f"{row.get('team')} rating")
        for row in entry["rows"]
    }
    if frozen != current:
        raise ValueError("Reviewed McCabe ratings do not match the frozen snapshot")
    return {
        "mccabe_edition": MCCABE_SNAPSHOT_LABEL,
        "mccabe_published_at": entry["published_at"],
    }


def validate_receipt(receipt):
    status = receipt.get("status")
    expected_publication = pgo_challenger.PUBLICATION_STATUS.get(status)
    if (
        status not in {"HOLD", "PASS"}
        or receipt.get("publication_status") != expected_publication
    ):
        raise ValueError("PGO model receipt is not eligible for comparison")
    checks = receipt.get("checks")
    if pgo_challenger.classify_release(checks) != status:
        raise ValueError("PGO model receipt status contradicts its checks")
    if not all(checks[name] for name in pgo_challenger.INTEGRITY_GATE_NAMES):
        raise ValueError("PGO model integrity gates did not pass")
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed != receipt.get("failed_checks"):
        raise ValueError("PGO model failed-check receipt is inconsistent")
    return receipt


def load_model_rows(path, receipt):
    expected_label = pgo_challenger.PUBLICATION_STATUS[receipt["status"]]
    expected_reason = (
        "All historical gates passed"
        if receipt["status"] == "PASS"
        else "Historical HOLD: " + ", ".join(receipt["failed_checks"])
    )
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != pgo_challenger.RATING_COLUMNS:
            raise ValueError("PGO ratings schema does not match the release contract")
        rows = list(reader)
    if len(rows) != 32 or {row["team"] for row in rows} != set(pgo_model.CURRENT_TEAMS):
        raise ValueError("PGO comparison requires exactly the 32 current teams")
    if {row["validation_status"] for row in rows} != {expected_label}:
        raise ValueError("PGO ratings label contradicts the receipt")
    if {row["status_reason"] for row in rows} != {expected_reason}:
        raise ValueError("PGO ratings reason contradicts the receipt")
    if {row["as_of"] for row in rows} != {str(receipt["as_of"])}:
        raise ValueError("PGO ratings as-of time contradicts the receipt")

    parsed = []
    for row in rows:
        item = dict(row)
        try:
            item["rank"] = int(row["rank"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid PGO rank for {row['team']}") from error
        for name in MODEL_NUMBER_FIELDS:
            item[name] = _finite(row.get(name), f"{row['team']} {name}")
        if not math.isclose(
            item["full_strength_rating"] + item["availability_adjustment"],
            item["current_lineup_rating"],
            abs_tol=1e-6,
        ):
            raise ValueError(f"PGO rating algebra failed for {row['team']}")
        if item["headline_view"] not in {"full_strength", "current_lineup"}:
            raise ValueError(f"Invalid PGO headline view for {row['team']}")
        expected_headline = item[
            "full_strength_rating"
            if item["headline_view"] == "full_strength"
            else "current_lineup_rating"
        ]
        if not math.isclose(item["headline_rating"], expected_headline, abs_tol=1e-6):
            raise ValueError(f"PGO headline rating failed for {row['team']}")
        parsed.append(item)
    if sorted(row["rank"] for row in parsed) != list(range(1, 33)):
        raise ValueError("PGO full-strength ranks must be 1 through 32")
    return parsed


def build_comparison_rows(mccabe_rows, model_rows):
    mccabe_by_abbr = {row["abbr"]: row for row in mccabe_rows}
    model_by_abbr = {row["team"]: row for row in model_rows}
    if set(mccabe_by_abbr) != set(model_by_abbr):
        raise ValueError("McCabe and PGO team sets do not match")
    current_ranks = {
        row["team"]: rank
        for rank, row in enumerate(
            sorted(
                model_rows,
                key=lambda row: (-row["current_lineup_rating"], row["team"]),
            ),
            1,
        )
    }
    output = []
    for mccabe in sorted(mccabe_rows, key=lambda row: row["rank"]):
        model = model_by_abbr[mccabe["abbr"]]
        current_rank = current_ranks[model["team"]]
        headline_rank = (
            model["rank"]
            if model["headline_view"] == "full_strength"
            else current_rank
        )
        output.append({
            "team": mccabe["team"],
            "abbr": mccabe["abbr"],
            "mccabe_rank": mccabe["rank"],
            "mccabe_rating": mccabe["rating"],
            "full_strength_rank": model["rank"],
            "full_strength_rating": model["full_strength_rating"],
            "availability_adjustment": model["availability_adjustment"],
            "current_lineup_rank": current_rank,
            "current_lineup_rating": model["current_lineup_rating"],
            "rank_disagreement": headline_rank - mccabe["rank"],
            "rating_disagreement": model["headline_rating"] - mccabe["rating"],
        })
    return output


def load_comparison_rows(
    mccabe_path,
    model_path,
    backtest_path,
    snapshots_path=SNAPSHOTS_PATH,
    require_immutable=False,
):
    receipt = validate_receipt(
        json.loads(Path(backtest_path).read_text(encoding="utf-8"))
    )
    mccabe_rows = load_mccabe_rows(mccabe_path)
    receipt = {
        **receipt,
        **load_mccabe_snapshot(snapshots_path, mccabe_rows),
    }
    if require_immutable:
        receipt["receipt_ref"] = require_immutable_artifacts(
            backtest_path, model_path
        )
    return build_comparison_rows(
        mccabe_rows,
        load_model_rows(model_path, receipt),
    ), receipt


def immutable_git_ref(path):
    try:
        relative = Path(path).resolve().relative_to(HERE.resolve()).as_posix()
        subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", relative],
            cwd=HERE,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", relative],
            cwd=HERE,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        raise ValueError(
            "PGO publication artifact must be committed and unmodified"
        ) from error
    receipt_ref = result.stdout.strip()
    if len(receipt_ref) != 40 or any(
        character not in "0123456789abcdef" for character in receipt_ref.lower()
    ):
        raise ValueError("PGO receipt has no immutable Git commit reference")
    return receipt_ref


def require_immutable_artifacts(backtest_path, model_path):
    receipt_ref = immutable_git_ref(backtest_path)
    ratings_ref = immutable_git_ref(model_path)
    if receipt_ref != ratings_ref:
        raise ValueError(
            "PGO receipt and ratings artifact must be from the same Git commit"
        )
    return receipt_ref


MODEL_CSS = """
#panel-comparison .model-status {
  display:inline-block; margin:0 0 12px; padding:6px 10px;
  border:1px solid var(--orange); border-radius:999px;
  color:var(--ink); font-weight:700;
}
#panel-comparison .comparison-summary { color:var(--mut); max-width:78ch; }
#panel-comparison .comparison-table th:first-child,
#panel-comparison .comparison-table td:first-child { text-align:left; }
#panel-comparison .comparison-table thead th:first-child,
#panel-comparison .comparison-table tbody th:first-child {
  position:sticky; left:0; z-index:1;
}
#panel-comparison .comparison-table thead th:first-child {
  background:var(--ink);
}
#panel-comparison .comparison-table tbody th:first-child {
  background:var(--panel); color:var(--ink);
}
#panel-comparison .comparison-links { margin-top:16px; }
@media (max-width:680px) {
  #panel-comparison .comparison-table { font-size:12px; }
  #panel-comparison .comparison-table th,
  #panel-comparison .comparison-table td { padding:8px 7px; }
}
"""


FANTASY_CSS = """
#panel-fantasy .fantasy-status {
  display:inline-block; margin:0 0 10px; padding:6px 10px;
  border:1px solid var(--orange); border-radius:999px;
  color:var(--ink); font-weight:700;
}
#panel-fantasy .fantasy-warning {
  max-width:78ch; margin:0 0 16px; color:var(--mut);
}
#panel-fantasy .fantasy-controls {
  display:flex; flex-wrap:wrap; gap:10px 14px; align-items:end;
  margin:16px 0 10px;
}
#panel-fantasy .fantasy-field {
  display:grid; gap:4px; color:var(--mut); font-size:12px; font-weight:600;
}
#panel-fantasy .fantasy-field input[type="search"],
#panel-fantasy .fantasy-field select {
  min-height:38px; border:1px solid var(--border); border-radius:8px;
  background:var(--panel); color:var(--ink); font:inherit; padding:7px 9px;
}
#panel-fantasy .fantasy-view-buttons {
  display:flex; flex-wrap:wrap; gap:7px; margin:0 0 12px;
}
#panel-fantasy .fantasy-view-button {
  border:1px solid var(--border); border-radius:999px; background:var(--panel);
  color:var(--ink); cursor:pointer; font:inherit; font-size:12px;
  font-weight:700; padding:7px 11px;
}
#panel-fantasy .fantasy-view-button[aria-pressed="true"] {
  border-color:var(--orange); background:var(--orange); color:#1e2a3c;
}
#panel-fantasy .fantasy-result-count {
  margin:8px 0; color:var(--mut); font-size:13px;
}
#panel-fantasy .fantasy-table th:nth-child(2),
#panel-fantasy .fantasy-table td:nth-child(2) { text-align:left; }
#panel-fantasy .fantasy-table tbody .fantasy-player {
  background:transparent; border-bottom:0; color:inherit; font:inherit;
  letter-spacing:normal; text-transform:none; user-select:text;
  text-align:left; white-space:normal; overflow-wrap:anywhere;
}
#panel-fantasy .fantasy-table tbody .fantasy-player:hover {
  background:transparent; color:inherit;
}
#panel-fantasy .fantasy-technical { display:none; }
#panel-fantasy.show-technical .fantasy-technical { display:table-cell; }
#panel-fantasy.show-technical .fantasy-table { min-width:1080px; }
#panel-fantasy .fantasy-details {
  margin-top:16px; color:var(--mut); font-size:12px;
}
#panel-fantasy .fantasy-details summary {
  color:var(--ink); cursor:pointer; font-weight:700;
}
#panel-fantasy .fantasy-details code { overflow-wrap:anywhere; }
#panel-fantasy .fantasy-league {
  margin:16px 0; padding:14px; border:1px solid var(--border);
  border-radius:10px; background:var(--panel);
}
#panel-fantasy .fantasy-league summary { cursor:pointer; font-weight:700; color:var(--ink); }
#panel-fantasy .fantasy-league p { font-size:13px; line-height:1.5; }
#panel-fantasy .fantasy-league-grid {
  display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:12px;
}
#panel-fantasy .fantasy-league fieldset { border:0; margin:14px 0; padding:0; min-width:0; }
#panel-fantasy .fantasy-league legend { font-weight:700; margin-bottom:8px; }
#panel-fantasy .fantasy-league input,
#panel-fantasy .fantasy-league select {
  box-sizing:border-box; min-width:0; width:100%; min-height:40px;
  border:1px solid var(--border); border-radius:7px; padding:8px;
  background:var(--panel); color:var(--ink); font:inherit;
}
#panel-fantasy .fantasy-league-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
#panel-fantasy .fantasy-league-actions button {
  min-height:40px; padding:8px 12px; border:1px solid var(--ink); border-radius:7px;
  color:var(--ink); background:var(--panel); cursor:pointer; font:inherit; font-weight:600;
}
#panel-fantasy .fantasy-league-actions button[type="submit"] { background:var(--ink); color:white; }
#panel-fantasy .fantasy-league-status { min-height:1.5em; color:var(--ink); }
#panel-fantasy .fantasy-league-summary { font-size:13px; line-height:1.5; margin:8px 0; }
#panel-fantasy .fantasy-league-explanation { font-size:12px; color:var(--mut); line-height:1.5; }
#panel-fantasy .fantasy-league-value { font-weight:700; white-space:nowrap; }
@media (max-width:480px) {
  #panel-fantasy .fantasy-controls { display:grid; grid-template-columns:1fr 1fr; }
  #panel-fantasy .fantasy-field:first-child { grid-column:1 / -1; }
  #panel-fantasy:not(.show-technical) .fantasy-table {
    table-layout:fixed; font-size:11px;
  }
  #panel-fantasy:not(.show-technical) .fantasy-table th,
  #panel-fantasy:not(.show-technical) .fantasy-table td { padding:6px 3px; }
  #panel-fantasy:not(.show-technical) .fantasy-table th:nth-child(1) { width:9%; }
  #panel-fantasy:not(.show-technical) .fantasy-table th:nth-child(2) { width:36%; }
  #panel-fantasy:not(.show-technical) .fantasy-table th:nth-child(3) { width:10%; }
  #panel-fantasy:not(.show-technical) .fantasy-table th:nth-child(4),
  #panel-fantasy:not(.show-technical) .fantasy-table td:nth-child(4),
  #panel-fantasy:not(.show-technical) .fantasy-table th:nth-child(5),
  #panel-fantasy:not(.show-technical) .fantasy-table td:nth-child(5) { display:none; }
  #panel-fantasy:not(.show-technical) .fantasy-table th:nth-child(6) { width:21%; }
  #panel-fantasy:not(.show-technical) .fantasy-table th:last-child { width:24%; }
}
"""


FANTASY_AVAILABILITY_CSS = """
#panel-fantasy .fantasy-availability {
  display:flex; flex-wrap:wrap; gap:4px 6px; align-items:center;
  max-width:100%; margin-top:4px; color:var(--mut); font-size:11px;
  font-weight:600; line-height:1.35;
}
#panel-fantasy .fantasy-source-badge,
#panel-fantasy .fantasy-game-state {
  display:inline-block; max-width:100%; padding:2px 6px;
  border:1px solid var(--border); border-radius:999px;
  overflow-wrap:anywhere;
}
#panel-fantasy .fantasy-source-badge { color:var(--ink); }
#panel-fantasy .fantasy-source-badge:focus-visible,
#panel-fantasy .fantasy-details summary:focus-visible {
  outline:3px solid var(--orange); outline-offset:2px;
}
#panel-fantasy .fantasy-availability-note,
#panel-fantasy .fantasy-source-time,
#panel-fantasy .fantasy-inactives li { overflow-wrap:anywhere; }
#panel-fantasy .fantasy-inactives { padding-left:20px; }
@media (max-width:480px) {
  #panel-fantasy .fantasy-availability { align-items:flex-start; }
  #panel-fantasy .fantasy-source-badge,
  #panel-fantasy .fantasy-game-state { border-radius:6px; }
}
"""


def _signed(value):
    return f"{value:+.1f}"


def _optional_rank(value):
    return ("", "&mdash;") if value is None else (str(value), str(value))


def _league_controls():
    slots = "".join(
        f'<label class="fantasy-field">{label}<input type="number" '
        f'name="slot_{position}" min="0" max="{maximum}" step="1" required></label>'
        for position, label, maximum in (
            ("QB", "QB starters", 2), ("RB", "RB starters", 4),
            ("WR", "WR starters", 4), ("TE", "TE starters", 4),
            ("FLEX", "FLEX starters", 4), ("SUPERFLEX", "Superflex starters", 2),
        )
    )
    scoring = "".join(
        f'<label class="fantasy-field">{label}<input type="number" '
        f'name="score_{key}" min="{minimum}" max="{maximum}" step="any" required></label>'
        for key, label, minimum, maximum in (
            ("passing_yards", "Per passing yard", 0, 1),
            ("passing_tds", "Passing touchdown", 0, 12),
            ("passing_interceptions", "Interception thrown", -10, 0),
            ("rushing_yards", "Per rushing yard", 0, 1),
            ("rushing_tds", "Rushing touchdown", 0, 12),
            ("receptions", "Reception", 0, 3),
            ("receiving_yards", "Per receiving yard", 0, 1),
            ("receiving_tds", "Receiving touchdown", 0, 12),
            ("fumbles_lost_total", "Fumble lost", -10, 0),
            ("passing_2pt_conversions", "Passing two-point conversion", 0, 6),
            ("rushing_2pt_conversions", "Rushing two-point conversion", 0, 6),
            ("receiving_2pt_conversions", "Receiving two-point conversion", 0, 6),
            ("special_teams_tds", "Return touchdown", 0, 12),
            ("te_reception_bonus", "Extra points per TE reception", 0, 3),
        )
    )
    return f'''<details class="fantasy-league" id="fantasy-league-settings">
      <summary>League settings <span id="fantasy-profile-label">12 teams · Half-PPR</span></summary>
      <p>Set your scoring and starting lineup. Profiles are saved only in this browser.</p>
      <form id="fantasy-league-form">
        <div class="fantasy-league-grid">
          <label class="fantasy-field">Saved league<select id="fantasy-profile-select"></select></label>
          <label class="fantasy-field">League name<input name="league_name" maxlength="60" required></label>
          <label class="fantasy-field">Number of teams<input name="teams" type="number" min="2" max="32" step="1" required></label>
          <label class="fantasy-field">Scoring preset<select id="fantasy-scoring-preset">
            <option value="STANDARD">Standard (no PPR)</option><option value="HALF_PPR" selected>Half-PPR</option>
            <option value="PPR">Full PPR</option><option value="CUSTOM">Custom scoring</option>
          </select></label>
        </div>
        <fieldset><legend>Starting lineup per team</legend><div class="fantasy-league-grid">{slots}</div></fieldset>
        <details><summary>Scoring points and TE premium</summary>
          <fieldset><legend>Points awarded or deducted</legend><div class="fantasy-league-grid">{scoring}</div></fieldset>
          <p>Supports the listed scoring categories. Threshold bonuses, first downs, kickers and team defenses are not included.</p>
        </details>
        <div class="fantasy-league-actions">
          <button type="submit">Apply &amp; save</button><button type="button" id="fantasy-profile-new">Save as new league</button>
          <button type="button" id="fantasy-profile-reset">Reset settings</button><button type="button" id="fantasy-profile-delete">Delete league</button>
        </div>
      </form>
      <p id="fantasy-league-status" class="fantasy-league-status" role="status" aria-live="polite"></p>
    </details>
    <p id="fantasy-league-summary" class="fantasy-league-summary"></p>
    <p id="fantasy-scoring-summary" class="fantasy-league-explanation"></p>
    <details class="fantasy-details"><summary>How league value works</summary>
      <p>Value is projected points above an estimated replacement at the same position. We fill every team's starting positions, then FLEX, then Superflex. The best player left at each position sets its baseline. This starting-lineup estimate does not include benches or identify actual free agents. Search and team filters do not change the baseline.</p>
      <p id="fantasy-replacement-summary"></p>
    </details>
    <noscript><p>JavaScript is needed for league settings. The table below shows the original half-PPR projections, ordered by points across all positions.</p></noscript>
    '''


def add_fantasy_leagues(panel, players, scoring=None):
    """Add league controls to a reviewed panel without rebuilding its source cells."""
    if 'id="fantasy-league-form"' in panel:
        raise ValueError("Fantasy league controls already exist")
    eligible = [row for row in players if row["ranking_eligible"]]
    identities = {(row["team"], row["player_name"].lower(), row["position"]): row for row in eligible}
    if len(identities) != len(eligible):
        raise ValueError("Fantasy league player identities are ambiguous")
    seen = set()

    def enrich(match):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', match[1]))
        key = tuple(html.unescape(attrs[name]) for name in ("data-team", "data-player", "data-position"))
        row = identities.get(key)
        cells = re.findall(r'<(?:td|th)\b[^>]*data-sort="([^"]*)"[^>]*>', match[2])
        if row is None or key in seen or len(cells) != 14 or float(cells[5]) != row["strong_prediction"]:
            raise ValueError("Fantasy league source projection or identity changed")
        seen.add(key)
        identifier = html.escape(row["gsis_id"], quote=True)
        inactive = str(row["availability_status"] == "INACTIVE").lower()
        return (f'<tr class="fantasy-row"{match[1]} data-player-id="{identifier}" '
                f'data-base-points="{cells[5]}" data-inactive="{inactive}">{match[2]}'
                '<td class="fantasy-league-value" data-sort="">&mdash;</td></tr>')

    panel = re.sub(r'<tr class="fantasy-row"([^>]*)>(.*?)</tr>', enrich, panel, flags=re.S)
    if len(seen) != len(eligible):
        raise ValueError("Fantasy league source population changed")
    payload = scoring or {"schema_version": 1, "available": False, "players": {}}
    if payload.get("available"):
        if set(payload["players"]) != {row["gsis_id"] for row in eligible}:
            raise ValueError("Fantasy scoring component population changed")
        for row in eligible:
            projected = payload["players"][row["gsis_id"]]
            if projected["position"] != row["position"] or projected["points"] != row["strong_prediction"]:
                raise ValueError("Fantasy scoring source projection changed")
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")
    digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
    panel = panel.replace('id="panel-fantasy"', 'id="panel-fantasy" data-league-version="1"', 1)
    marker = '<div class="fantasy-view-buttons"'
    if panel.count(marker) != 1 or panel.count('</tr></thead>') != 1:
        raise ValueError("Fantasy league panel structure changed")
    panel, captions = re.subn(r'<caption\b[^>]*>',
        '<caption class="visually-hidden" id="fantasy-table-caption">', panel)
    if captions != 1:
        raise ValueError("Fantasy league table caption changed")
    for column, label in enumerate(("Pos #", "FLEX #", "SF #", "Baseline", "Delta"), 6):
        panel, labels = re.subn(rf'(data-column="{column}" data-kind="number">)[^<]+',
            rf'\g<1>Original half-PPR {label}', panel)
        if labels != 1:
            raise ValueError("Fantasy league source columns changed")
    panel = re.sub(r'(<p class="fantasy-warning">)(.*?)</p>',
        lambda match: match[1] + match[2].replace("half-PPR projections", "half-PPR base forecasts")
            + ' League profiles can score-adjust the displayed Proj. column.</p>', panel, count=1, flags=re.S)
    panel = panel.replace(marker, _league_controls() + marker, 1)
    panel = panel.replace('aria-label="Fantasy ranking view">', 'aria-label="Fantasy ranking view">'
        '<button type="button" class="fantasy-view-button" data-view="LEAGUE" '
        'aria-pressed="false" aria-controls="fantasy-table">League value</button>', 1)
    panel = panel.replace('>SUPERFLEX</button>', '>All positions</button>', 1)
    panel = panel.replace('</tr></thead>', '<th scope="col" aria-sort="none" class="fantasy-league-value">'
        '<button type="button" class="sort-button fantasy-sort" data-column="14" data-kind="number" '
        'title="Projected points above the estimated replacement player">Value</button></th></tr></thead>', 1)
    return panel.replace('</section>', f'<script type="application/json" id="fantasy-scoring-data" '
        f'data-sha256="{digest}">{data}</script>\n</section>', 1)


def render_fantasy_panel(preview):
    eligible = sorted(
        (
            row for row in preview["rows"]
            if row["ranking_eligible"]
        ),
        key=lambda row: row["superflex_rank"],
    )
    if not eligible:
        raise ValueError("Fantasy Week 1 preview has no eligible rows")

    teams = sorted({row["team"] for row in eligible})
    options = "\n".join(
        f'<option value="{html.escape(team, quote=True)}">'
        f"{html.escape(team)}</option>"
        for team in teams
    )
    body = []
    for row in eligible:
        position_sort, position_text = _optional_rank(row["position_rank"])
        flex_sort, flex_text = _optional_rank(row["flex_rank"])
        superflex_sort, superflex_text = _optional_rank(
            row["superflex_rank"]
        )
        player = html.escape(row["player_name"])
        player_sort = html.escape(row["player_name"].lower(), quote=True)
        position = html.escape(row["position"], quote=True)
        team = html.escape(row["team"], quote=True)
        opponent = html.escape(row["opponent"], quote=True)
        initialization = html.escape(row["initialization_reason"])
        availability = html.escape(row["availability_status"])
        delta = row["strong_prediction"] - row["null_prediction"]
        body.append(
            f'<tr class="fantasy-row" data-position="{position}" '
            f'data-team="{team}" data-player="{player_sort}" '
            f'data-position-rank="{position_sort}" '
            f'data-flex-rank="{flex_sort}" '
            f'data-superflex-rank="{superflex_sort}">'
            f'<td class="fantasy-rank" data-sort="{superflex_sort}">'
            f"{superflex_text}</td>"
            f'<th scope="row" class="fantasy-player" data-sort="{player_sort}">'
            f"{player}</th>"
            f'<td data-sort="{position}">{position}</td>'
            f'<td data-sort="{team}">{team}</td>'
            f'<td data-sort="{opponent}">{opponent}</td>'
            f'<td data-sort="{row["strong_prediction"]}">'
            f'{row["strong_prediction"]:.1f}</td>'
            f'<td class="fantasy-technical" data-sort="{position_sort}">'
            f"{position_text}</td>"
            f'<td class="fantasy-technical" data-sort="{flex_sort}">'
            f"{flex_text}</td>"
            f'<td class="fantasy-technical" data-sort="{superflex_sort}">'
            f"{superflex_text}</td>"
            f'<td class="fantasy-technical" data-sort="{row["null_prediction"]}">'
            f'{row["null_prediction"]:.1f}</td>'
            f'<td class="fantasy-technical" data-sort="{delta}">'
            f"{delta:+.1f}</td>"
            f'<td class="fantasy-technical" data-sort="{row["history_count"]}">'
            f'{row["history_count"]}</td>'
            f'<td class="fantasy-technical" '
            f'data-sort="{html.escape(row["initialization_reason"].lower(), quote=True)}">'
            f"{initialization}</td>"
            f'<td class="fantasy-technical" '
            f'data-sort="{html.escape(row["availability_status"].lower(), quote=True)}">'
            f"{availability}</td>"
            "</tr>"
        )

    generated = html.escape(preview["generated_at"], quote=True)
    model = html.escape(preview["model_version"])
    artifact_sha = html.escape(preview["artifact_sha256"])
    config_sha = html.escape(preview["config_sha256"])
    coverage = preview["source_coverage"]
    total = len(preview["rows"])
    visible = len(eligible)
    panel = f"""
  <section class="panel active" id="panel-fantasy" role="tabpanel"
    aria-labelledby="tab-fantasy">
    <div class="fantasy-status">PREVIEW / HOLD</div>
    <h2>2026 Week 1 Fantasy Rankings</h2>
    <p class="fantasy-warning">These are pre-lock half-PPR projections.
      Player availability is unverified, rankings may change before lock,
      and this artifact is not gradeable. Generated
      <time datetime="{generated}">{generated}</time>.</p>
    <div class="fantasy-view-buttons" role="group"
      aria-label="Fantasy ranking view">
      <button type="button" class="fantasy-view-button"
        data-view="SUPERFLEX" aria-pressed="true"
        aria-controls="fantasy-table">SUPERFLEX</button>
      <button type="button" class="fantasy-view-button"
        data-view="QB" aria-pressed="false"
        aria-controls="fantasy-table">QB</button>
      <button type="button" class="fantasy-view-button"
        data-view="RB" aria-pressed="false"
        aria-controls="fantasy-table">RB</button>
      <button type="button" class="fantasy-view-button"
        data-view="WR" aria-pressed="false"
        aria-controls="fantasy-table">WR</button>
      <button type="button" class="fantasy-view-button"
        data-view="TE" aria-pressed="false"
        aria-controls="fantasy-table">TE</button>
      <button type="button" class="fantasy-view-button"
        data-view="FLEX" aria-pressed="false"
        aria-controls="fantasy-table">FLEX</button>
    </div>
    <div class="fantasy-controls">
      <label class="fantasy-field" for="fantasy-player-search">
        Player
        <input id="fantasy-player-search" type="search"
          autocomplete="off" placeholder="Search player">
      </label>
      <label class="fantasy-field" for="fantasy-team">
        Team
        <select id="fantasy-team">
          <option value="">All teams</option>
          {options}
        </select>
      </label>
      <label class="fantasy-field" for="fantasy-columns">
        Columns
        <span><input id="fantasy-columns" type="checkbox">
          Show all columns</span>
      </label>
    </div>
    <p class="fantasy-result-count" id="fantasy-result-count"
      role="status" aria-live="polite">{visible} players shown</p>
    <p class="visually-hidden fantasy-sort-status"
      role="status" aria-live="polite"></p>
    <div class="table-shell">
      <table class="fantasy-table" id="fantasy-table">
        <caption class="visually-hidden">
          Eligible 2026 Week 1 half-PPR fantasy projections
        </caption>
        <thead><tr>
          <th scope="col" aria-sort="ascending">
            <button type="button" class="sort-button fantasy-sort"
              data-column="0" data-kind="number">SF#</button></th>
          <th scope="col" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="1" data-kind="text">Player</button></th>
          <th scope="col" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="2" data-kind="text">Pos</button></th>
          <th scope="col" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="3" data-kind="text">Team</button></th>
          <th scope="col" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="4" data-kind="text">Opp.</button></th>
          <th scope="col" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="5" data-kind="number">Proj.</button></th>
          <th scope="col" class="fantasy-technical" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="6" data-kind="number">Pos #</button></th>
          <th scope="col" class="fantasy-technical" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="7" data-kind="number">FLEX #</button></th>
          <th scope="col" class="fantasy-technical" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="8" data-kind="number">SF #</button></th>
          <th scope="col" class="fantasy-technical" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="9" data-kind="number">Baseline</button></th>
          <th scope="col" class="fantasy-technical" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="10" data-kind="number">Delta</button></th>
          <th scope="col" class="fantasy-technical" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="11" data-kind="number">History</button></th>
          <th scope="col" class="fantasy-technical" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="12" data-kind="text">Init</button></th>
          <th scope="col" class="fantasy-technical" aria-sort="none">
            <button type="button" class="sort-button fantasy-sort"
              data-column="13" data-kind="text">Availability</button></th>
        </tr></thead>
        <tbody id="fantasy-rows">{"".join(body)}</tbody>
      </table>
    </div>
    <details class="fantasy-details">
      <summary>Preview details</summary>
      <p>Model <code>{model}</code>; generated
        <time datetime="{generated}">{generated}</time>.<br>
        Artifact SHA-256 <code>{artifact_sha}</code>.<br>
        Config SHA-256 <code>{config_sha}</code>.<br>
        Rows: {total} total, {visible} ranking-eligible.<br>
        Coverage: roster {len(coverage["roster"]["processed"])}/32;
        depth {len(coverage["depth"]["processed"])}/32;
        availability {len(coverage["availability"]["processed"])}/32.
        Status: PREVIEW / HOLD, EXPERIMENTAL, non-gradeable.
        Availability remains unverified.</p>
    </details>
  </section>
"""
    return add_fantasy_leagues(panel, eligible)


def render_comparison_panel(rows, receipt):
    rows = sorted(
        rows,
        key=lambda row: (row["full_strength_rank"], row["team"]),
    )
    receipt_ref = receipt.get("receipt_ref")
    receipt_link = (
        f'<a href="https://github.com/walshja9/Postgame_Outlet/blob/'
        f'{html.escape(str(receipt_ref), quote=True)}'
        '/research/pgo_v1/backtest.json" target="_blank" '
        'rel="noopener noreferrer">Backtest receipt</a>'
        if receipt_ref
        else "<span>Backtest receipt available on publish</span>"
    )
    interval = receipt["aggregate_interval"]
    metrics = receipt["metrics"]
    label = (
        "Validated model \N{EM DASH} PASS"
        if receipt["status"] == "PASS"
        else "Experimental model \N{EM DASH} HOLD"
    )
    reason = (
        "All historical gates passed"
        if not receipt["failed_checks"]
        else "Hold reason: " + ", ".join(
            name.replace("_", " ") for name in receipt["failed_checks"]
        )
    )
    body = "\n".join(
        "<tr>"
        f'<th scope="row" data-sort="{html.escape(row["team"].casefold())}">'
        f'{html.escape(row["team"])}</th>'
        f'<td data-sort="{row["full_strength_rank"]}">{row["full_strength_rank"]}</td>'
        f'<td data-sort="{row["full_strength_rating"]}">{_signed(row["full_strength_rating"])}</td>'
        f'<td data-sort="{row["availability_adjustment"]}">{_signed(row["availability_adjustment"])}</td>'
        f'<td data-sort="{row["current_lineup_rank"]}">{row["current_lineup_rank"]}</td>'
        f'<td data-sort="{row["current_lineup_rating"]}">{_signed(row["current_lineup_rating"])}</td>'
        f'<td data-sort="{row["mccabe_rank"]}">{row["mccabe_rank"]}</td>'
        f'<td data-sort="{row["mccabe_rating"]}">{_signed(row["mccabe_rating"])}</td>'
        f'<td data-sort="{row["rank_disagreement"]}">{row["rank_disagreement"]:+d}</td>'
        f'<td data-sort="{row["rating_disagreement"]}">{_signed(row["rating_disagreement"])}</td>'
        "</tr>"
        for row in rows
    )
    summary = (
        f'Backtest: v1 MAE {metrics["challenger"]["mae"]:.3f} vs '
        f'v0 {metrics["pgo_v0"]["mae"]:.3f}; improvement '
        f'{interval["mean"]:+.3f}, 95% CI '
        f'{interval["lower"]:+.3f} to {interval["upper"]:+.3f}.'
    )
    return f"""
  <section class="panel active" id="panel-comparison" role="tabpanel"
    aria-labelledby="tab-comparison">
    <div class="model-status">{html.escape(label)}</div>
    <h2>PGO v1 Power Ratings</h2>
    <p>Postgame Outlet's independent statistical rating, compared with McCabe's human rating and never blended.</p>
    <p class="comparison-summary">{html.escape(summary)}<br>
      McCabe {html.escape(receipt["mccabe_edition"])} locked
      {html.escape(receipt["mccabe_published_at"])}.<br>
      PGO {html.escape(receipt["version"])} as of
      {html.escape(str(receipt["as_of"]))}. {html.escape(reason)}.</p>
    <p class="visually-hidden comparison-sort-status" role="status" aria-live="polite"></p>
    <div class="table-shell">
      <table class="comparison-table">
        <caption class="visually-hidden">All 32 NFL teams comparing McCabe and PGO ratings</caption>
        <thead><tr>
          <th scope="col" aria-sort="none"><button type="button" class="sort-button" data-column="0">Team</button></th>
          <th scope="col" aria-sort="ascending"><button type="button" class="sort-button" data-column="1">PGO full #</button></th>
          <th scope="col" aria-sort="none"><button type="button" class="sort-button" data-column="2">PGO full</button></th>
          <th scope="col" aria-sort="none"><button type="button" class="sort-button" data-column="3">Avail.</button></th>
          <th scope="col" aria-sort="none"><button type="button" class="sort-button" data-column="4">PGO today #</button></th>
          <th scope="col" aria-sort="none"><button type="button" class="sort-button" data-column="5">PGO today</button></th>
          <th scope="col" aria-sort="none"><button type="button" class="sort-button" data-column="6">McCabe #</button></th>
          <th scope="col" aria-sort="none"><button type="button" class="sort-button" data-column="7">McCabe</button></th>
          <th scope="col" aria-sort="none"><button type="button" class="sort-button" data-column="8">Rank gap</button></th>
          <th scope="col" aria-sort="none"><button type="button" class="sort-button" data-column="9">Rating gap</button></th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table>
    </div>
    <p class="legend">Positive rank gap means PGO ranks the team lower.
      Positive rating gap means PGO rates the team higher.</p>
    <p class="comparison-links">
      {receipt_link}
      &middot;
      <a href="https://github.com/walshja9/Postgame_Outlet/blob/main/docs/superpowers/specs/2026-07-21-independent-forward-looking-pgo-model-design.md" target="_blank" rel="noopener noreferrer">Methodology and release rules</a>
    </p>
  </section>
"""


COMPARISON_TAB = """
    <button type="button" class="tab active" id="tab-comparison" role="tab"
      aria-selected="true" aria-controls="panel-comparison" tabindex="0"
      data-panel="comparison">PGO Model</button>
"""


FANTASY_TAB = """
    <button type="button" class="tab active" id="tab-fantasy" role="tab"
      aria-selected="true" aria-controls="panel-fantasy" tabindex="0"
      data-panel="fantasy">Fantasy Week 1</button>
"""


COMPARISON_SCRIPT = """
<script>
  (() => {
    const panel = document.querySelector('#panel-comparison');
    const body = panel && panel.querySelector('.comparison-table tbody');
    const status = panel && panel.querySelector('.comparison-sort-status');
    const buttons = panel ? [...panel.querySelectorAll('.comparison-table .sort-button')] : [];
    if (!body || !status || buttons.length === 0) return;

    let activeColumn = 1;
    let ascending = true;

    function value(row, index) {
      const raw = row.children[index].dataset.sort;
      const numeric = index !== 0;
      return numeric ? Number(raw) : raw;
    }

    buttons.forEach(button => {
      button.addEventListener('click', () => {
        const column = Number(button.dataset.column);
        ascending = column === activeColumn ? !ascending : true;
        activeColumn = column;
        [...body.rows].sort((a, b) => {
          const left = value(a, column);
          const right = value(b, column);
          const order = typeof left === 'number'
            ? left - right
            : left.localeCompare(right);
          const directed = ascending ? order : -order;
          return directed || a.children[0].dataset.sort.localeCompare(
            b.children[0].dataset.sort
          );
        }).forEach(row => body.appendChild(row));
        buttons.forEach(candidate => {
          candidate.closest('th').setAttribute('aria-sort', 'none');
        });
        button.closest('th').setAttribute(
          'aria-sort', ascending ? 'ascending' : 'descending'
        );
        status.textContent = button.textContent.trim() + ' sorted '
          + (ascending ? 'ascending' : 'descending');
      });
    });
  })();
</script>
"""


FANTASY_SCRIPT = "\n<script>\n" + "\n".join(
    (HERE / name).read_text(encoding="utf-8")
    for name in ("fantasy_league.js", "fantasy_league_ui.js")
) + "\n</script>\n"


def inject_comparison(base_html, panel_html):
    rating_tab = (
        '    <button type="button" class="tab active" id="tab-ratings"'
    )
    rating_panel = (
        '  <section class="panel active" id="panel-ratings"'
    )
    fixed_replacements = (
        (
            '<meta name="description" content="Sean McCabe’s',
            '<meta name="description" content="Postgame Outlet’s independent PGO v1',
        ),
        (
            '<div class="updated">By Sean McCabe &middot;',
            '<div class="updated">By Postgame Outlet Model &middot;',
        ),
        (
            'aria-selected="true" aria-controls="panel-ratings" tabindex="0"',
            'aria-selected="false" aria-controls="panel-ratings" tabindex="-1"',
        ),
        (
            'data-panel="ratings">Power Ratings</button>',
            'data-panel="ratings">McCabe Ratings</button>',
        ),
        (">QB Ratings</button>", ">McCabe QBs</button>"),
        (">Methodology</button>", ">McCabe Method</button>"),
    )
    markers = (
        "</style>",
        "</body>",
        rating_tab,
        rating_panel,
        *(old for old, _new in fixed_replacements),
    )
    if any(base_html.count(marker) != 1 for marker in markers):
        raise ValueError("Base ratings template markers changed")
    output = base_html.replace(
        "</style>", MODEL_CSS + '\n</style>\n<link rel="icon" href="data:,">', 1
    )
    for old, new in fixed_replacements:
        output = output.replace(old, new, 1)
    output = output.replace(
        rating_tab,
        COMPARISON_TAB
        + '    <button type="button" class="tab" id="tab-ratings"',
        1,
    )
    output = output.replace(
        rating_panel,
        panel_html
        + '\n  <section class="panel" id="panel-ratings" hidden',
        1,
    )
    output = output.replace("</body>", COMPARISON_SCRIPT + "\n</body>", 1)
    return output


def inject_fantasy_preview(existing_html, panel_html):
    if (
        'id="tab-fantasy"' in existing_html
        or 'id="panel-fantasy"' in existing_html
    ):
        raise ValueError("Existing ratings page already has a fantasy preview")

    comparison_panel = extract_comparison_panel(existing_html)
    panel_class = '<section class="panel active" id="panel-comparison"'
    panel_label = 'aria-labelledby="tab-comparison">'
    markers = ("</style>", "</body>", COMPARISON_TAB, comparison_panel)
    if (
        any(existing_html.count(marker) != 1 for marker in markers)
        or existing_html.count(FANTASY_AVAILABILITY_CSS) != 0
        or comparison_panel.count(panel_class) != 1
        or comparison_panel.count(panel_label) != 1
        or panel_html.count('id="panel-fantasy"') != 1
    ):
        raise ValueError("Fantasy preview page markers changed")

    inactive_tab = (
        COMPARISON_TAB
        .replace('class="tab active"', 'class="tab"', 1)
        .replace('aria-selected="true"', 'aria-selected="false"', 1)
        .replace('tabindex="0"', 'tabindex="-1"', 1)
    )
    inactive_panel = (
        comparison_panel
        .replace(panel_class, '<section class="panel" id="panel-comparison"', 1)
        .replace(panel_label, 'aria-labelledby="tab-comparison" hidden>', 1)
    )
    fantasy_css = FANTASY_CSS
    if 'class="fantasy-availability"' in panel_html:
        fantasy_css += "\n" + FANTASY_AVAILABILITY_CSS
    output = existing_html.replace("</style>", fantasy_css + "\n</style>", 1)
    output = output.replace(COMPARISON_TAB, inactive_tab + FANTASY_TAB, 1)
    output = output.replace(
        comparison_panel, inactive_panel + "\n" + panel_html, 1
    )
    output = output.replace("</body>", FANTASY_SCRIPT + "\n</body>", 1)
    return output


def extract_comparison_panel(existing_html):
    identifier = 'id="panel-comparison"'
    if existing_html.count(identifier) == 0:
        raise ValueError(
            "Existing public board has no PGO comparison panel; publish an approved PGO release first"
        )
    start_markers = (
        '<section class="panel active" id="panel-comparison"',
        '<section class="panel" id="panel-comparison"',
    )
    matches = [marker for marker in start_markers if existing_html.count(marker) == 1]
    if existing_html.count(identifier) != 1 or len(matches) != 1:
        raise ValueError("Existing PGO comparison panel markers changed")
    start = existing_html.find(matches[0])
    end_marker = "</section>"
    end = existing_html.find(end_marker, start)
    if end < 0:
        raise ValueError("Existing PGO comparison panel is incomplete")
    return existing_html[start:end + len(end_marker)]


def _extract_published_fantasy_panel(existing_html):
    tab_count = existing_html.count('id="tab-fantasy"')
    panel_count = existing_html.count('id="panel-fantasy"')
    css_count = existing_html.count(FANTASY_CSS)
    availability_css_count = existing_html.count(FANTASY_AVAILABILITY_CSS)
    script_count = existing_html.count(FANTASY_SCRIPT)
    if (
        tab_count == panel_count == css_count == availability_css_count
        == script_count == 0
    ):
        if any(marker in existing_html for marker in (
                'id="fantasy-league-form"', 'id="fantasy-scoring-data"',
                'data-league-version="1"')):
            raise ValueError("Existing fantasy league assets are orphaned")
        return None
    if (
        tab_count != 1
        or panel_count != 1
        or existing_html.count(FANTASY_TAB) != 1
        or css_count != 1
        or script_count != 1
    ):
        raise ValueError("Existing fantasy preview markers are incomplete or duplicated")
    start_marker = '<section class="panel active" id="panel-fantasy"'
    start = existing_html.find(start_marker)
    end_marker = "</section>"
    end = existing_html.find(end_marker, start)
    if start < 0 or end < 0:
        raise ValueError("Existing fantasy preview markers are incomplete or duplicated")
    if start >= 2 and existing_html[start - 2:start] == "  ":
        start -= 2
    panel = existing_html[start:end + len(end_marker)]
    _validate_fantasy_leagues(panel, existing_html)
    if availability_css_count != int(
        'class="fantasy-availability"' in panel
    ):
        raise ValueError(
            "Existing fantasy availability CSS is missing, duplicated, or orphaned"
        )
    return panel


def _validate_fantasy_leagues(panel, page):
    for marker in ('id="fantasy-league-form"', 'id="fantasy-scoring-data"',
                   'id="fantasy-table-caption"', 'data-league-version="1"'):
        if page.count(marker) != 1 or panel.count(marker) != 1:
            raise ValueError("Existing fantasy league controls or scoring data are incomplete or duplicated")
    match = re.search(r'<script type="application/json" id="fantasy-scoring-data" '
                      r'data-sha256="([0-9a-f]{64})">(.*?)</script>', panel, re.S)
    if match is None or hashlib.sha256(match[2].encode("utf-8")).hexdigest() != match[1]:
        raise ValueError("Existing fantasy scoring data integrity changed")
    try:
        data = json.loads(match[2])
        if (type(data["schema_version"]) is not int or data["schema_version"] != 1
                or type(data["available"]) is not bool or not isinstance(data["players"], dict)):
            raise ValueError("Invalid fantasy scoring data")
        if not data["available"] and data["players"]:
            raise ValueError("Unavailable fantasy scoring data has player projections")
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid fantasy scoring data") from error

    rows = re.findall(r'<tr class="fantasy-row"([^>]*)>(.*?)</tr>', panel, re.S)
    if not rows or len(rows) != panel.count('class="fantasy-row"'):
        raise ValueError("Fantasy league row population is incomplete")
    dom_players = {}
    for attributes, cells_html in rows:
        pairs = re.findall(r'([\w-]+)="([^"]*)"', attributes)
        attrs = dict(pairs)
        if any(sum(name == key for name, _ in pairs) != 1 for key in (
                "data-player-id", "data-position", "data-base-points", "data-inactive")):
            raise ValueError("Fantasy league player fields are malformed")
        identifier = html.unescape(attrs["data-player-id"])
        position = html.unescape(attrs["data-position"])
        if not identifier or identifier in dom_players or position not in {"QB", "RB", "WR", "TE"}:
            raise ValueError("Fantasy league player population is duplicated or malformed")
        cells = re.findall(r'<(?:td|th)\b[^>]*data-sort="([^"]*)"[^>]*>', cells_html)
        try:
            points = float(html.unescape(attrs["data-base-points"]))
            source_points = float(html.unescape(cells[5]))
        except (IndexError, TypeError, ValueError) as error:
            raise ValueError("Fantasy league source projection is malformed") from error
        if len(cells) != 15 or not math.isfinite(points) or source_points != points:
            raise ValueError("Fantasy league source projection changed")
        if attrs["data-inactive"] != str(html.unescape(cells[13]).lower() == "inactive").lower():
            raise ValueError("Fantasy league source availability changed")
        dom_players[identifier] = (position, points)

    if not data["available"]:
        return
    if set(data["players"]) != set(dom_players):
        raise ValueError("Fantasy scoring player population changed")
    component_names = {
        "passing_yards", "passing_tds", "passing_interceptions",
        "passing_2pt_conversions", "rushing_yards", "rushing_tds",
        "rushing_2pt_conversions", "receptions", "receiving_yards",
        "receiving_tds", "receiving_2pt_conversions", "special_teams_tds",
        "fumbles_lost_total",
    }
    for identifier, projected in data["players"].items():
        if not isinstance(projected, dict) or set(projected) != {"position", "points", "components"}:
            raise ValueError("Fantasy scoring player fields are malformed")
        position, points = dom_players[identifier]
        projected_points = projected["points"]
        components = projected["components"]
        if (projected["position"] != position
                or type(projected_points) not in (int, float)
                or not math.isfinite(projected_points)
                or projected_points != points
                or not isinstance(components, dict)
                or set(components) != component_names
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       for value in components.values())):
            raise ValueError("Fantasy scoring player projection is malformed")


def mccabe_source_timestamp(path):
    try:
        relative = Path(path).resolve().relative_to(HERE.resolve()).as_posix()
        history = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=HERE,
            check=True,
            capture_output=True,
            text=True,
        )
        if history.stdout.strip().lower() == "true":
            raise ValueError(
                "Current McCabe source timestamp requires full Git history"
            )
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", relative],
            cwd=HERE,
            check=True,
            capture_output=True,
            text=True,
        )
    except ValueError:
        raise
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("Could not determine the current McCabe source timestamp") from error
    timestamp = result.stdout.strip()
    if not timestamp:
        raise ValueError("Current McCabe source has no Git timestamp")
    return timestamp


def _cell_sort_value(cell, label):
    match = re.search(r'data-sort="([^"]+)"', cell)
    if not match:
        raise ValueError(f"Existing PGO comparison cell has no sort value: {label}")
    try:
        return float(match.group(1))
    except ValueError as error:
        raise ValueError(
            f"Existing PGO comparison cell has an invalid sort value: {label}"
        ) from error


def _replace_comparison_cell(cell, sort_value, display):
    cell = re.sub(
        r'data-sort="[^"]+"',
        f'data-sort="{html.escape(str(sort_value), quote=True)}"',
        cell,
        count=1,
    )
    return re.sub(r">[^<>]*</td>\Z", f">{display}</td>", cell, count=1)


def _refresh_comparison_metadata(panel_html, source_timestamp):
    old_pattern = re.compile(
        r"McCabe (?P<edition>[^<\r\n]+?) locked\s+"
        r"(?P<published>\d{4}-\d{2}-\d{2}T[^\s<]+)\.<br>"
    )
    current_pattern = re.compile(
        r"Current McCabe ratings from data/ratings\.csv as of\s+"
        r"(?P<source>\d{4}-\d{2}-\d{2}T[^\s<]+)\.\s+"
        r"Historical (?P<edition>[^<\r\n]+?) snapshot locked\s+"
        r"(?P<published>\d{4}-\d{2}-\d{2}T[^\s<]+)\.<br>"
    )
    match = old_pattern.search(panel_html) or current_pattern.search(panel_html)
    if not match:
        raise ValueError("Existing PGO comparison panel has no McCabe metadata")
    edition = match.group("edition")
    published = match.group("published")
    replacement = (
        "Current McCabe ratings from data/ratings.csv as of\n"
        f"      {html.escape(source_timestamp)}. Historical {html.escape(edition)} "
        "snapshot locked\n"
        f"      {html.escape(published)}.<br>"
    )
    return panel_html[:match.start()] + replacement + panel_html[match.end():]


def _refresh_comparison_panel(panel_html, mccabe_rows, source_timestamp):
    mccabe_by_team = {row["team"].casefold(): row for row in mccabe_rows}
    seen = set()
    row_pattern = re.compile(r"<tr\b[^>]*>.*?</tr>", re.DOTALL)
    cell_pattern = re.compile(r"<td\b[^>]*>.*?</td>", re.DOTALL)
    team_pattern = re.compile(r'<th\b[^>]*data-sort="([^"]+)"', re.DOTALL)

    def refresh_row(match):
        row_html = match.group(0)
        team_match = team_pattern.search(row_html)
        if not team_match:
            return row_html
        team_key = html.unescape(team_match.group(1)).casefold()
        if team_key not in mccabe_by_team:
            raise ValueError(f"Existing PGO comparison has unknown team: {team_key}")
        cells = cell_pattern.findall(row_html)
        if len(cells) != 9:
            raise ValueError(f"Existing PGO comparison row is incomplete: {team_key}")

        old_rank = int(_cell_sort_value(cells[5], f"{team_key} McCabe rank"))
        old_rating = _cell_sort_value(cells[6], f"{team_key} McCabe rating")
        headline_rank = old_rank + int(
            _cell_sort_value(cells[7], f"{team_key} rank gap")
        )
        headline_rating = old_rating + _cell_sort_value(
            cells[8], f"{team_key} rating gap"
        )
        current = mccabe_by_team[team_key]
        updates = {
            5: (current["rank"], str(current["rank"])),
            6: (current["rating"], _signed(current["rating"])),
            7: (
                headline_rank - current["rank"],
                f"{headline_rank - current['rank']:+d}",
            ),
            8: (
                headline_rating - current["rating"],
                _signed(headline_rating - current["rating"]),
            ),
        }

        cell_index = 0

        def replace_cell(cell_match):
            nonlocal cell_index
            current_index = cell_index
            cell_index += 1
            if current_index not in updates:
                return cell_match.group(0)
            sort_value, display = updates[current_index]
            return _replace_comparison_cell(
                cell_match.group(0), sort_value, display
            )

        seen.add(team_key)
        return cell_pattern.sub(replace_cell, row_html)

    refreshed = row_pattern.sub(refresh_row, panel_html)
    if seen != set(mccabe_by_team):
        missing = sorted(set(mccabe_by_team) - seen)
        raise ValueError(f"Existing PGO comparison is missing teams: {missing}")
    return _refresh_comparison_metadata(refreshed, source_timestamp)


def refresh_mccabe_page(base_html, existing_html, mccabe_path=MCCABE_PATH):
    mccabe_rows = load_mccabe_rows(mccabe_path)
    fantasy_panel = _extract_published_fantasy_panel(existing_html)
    comparison_panel = extract_comparison_panel(existing_html)
    if fantasy_panel is not None:
        inactive_start = '<section class="panel" id="panel-comparison"'
        hidden_label = 'aria-labelledby="tab-comparison" hidden>'
        if comparison_panel.count(inactive_start) != 1 or comparison_panel.count(hidden_label) != 1:
            raise ValueError("Existing fantasy preview comparison state changed")
        comparison_panel = (
            comparison_panel.replace(
                inactive_start,
                '<section class="panel active" id="panel-comparison"',
                1,
            ).replace(hidden_label, 'aria-labelledby="tab-comparison">', 1)
        )
    elif (
        comparison_panel.count('<section class="panel active" id="panel-comparison"') != 1
        or comparison_panel.count('aria-labelledby="tab-comparison">') != 1
    ):
        raise ValueError("Existing PGO comparison panel must be active")
    panel = _refresh_comparison_panel(
        comparison_panel,
        mccabe_rows,
        mccabe_source_timestamp(mccabe_path),
    )
    output = inject_comparison(base_html, panel)
    if fantasy_panel is not None:
        output = inject_fantasy_preview(output, fantasy_panel)
    return output


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument(
        "--output", type=Path, default=default_preview_path()
    )
    destination.add_argument(
        "--publish",
        action="store_true",
        help="write the reviewed combined page to docs/index.html",
    )
    destination.add_argument(
        "--refresh-mccabe",
        action="store_true",
        help="update the McCabe board while preserving the approved PGO panel",
    )
    parser.add_argument(
        "--fantasy-preview",
        type=Path,
        help="add a validated Week 1 fantasy tab to private output only",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        if args.fantasy_preview is not None and (
            args.publish or args.refresh_mccabe
        ):
            raise ValueError(
                "--fantasy-preview is private-only and cannot be combined "
                "with --publish or --refresh-mccabe"
            )

        output = (
            PUBLIC_OUTPUT if (args.publish or args.refresh_mccabe) else args.output
        ).resolve()
        preview_root = (HERE / "output").resolve()
        if not (args.publish or args.refresh_mccabe) and preview_root not in output.parents:
            raise ValueError("Comparison output must stay under output/")

        fantasy_preview = None
        comparison_rows = receipt = None
        if args.fantasy_preview is not None:
            fantasy_path = args.fantasy_preview.resolve()
            if fantasy_path == output:
                raise ValueError(
                    "Fantasy preview input and HTML output must be different files"
                )
            fantasy_preview = fantasy_prospective.load_week1_preview(
                fantasy_path
            )
            preview = inject_fantasy_preview(
                PUBLIC_OUTPUT.read_text(encoding="utf-8"),
                render_fantasy_panel(fantasy_preview),
            )
        else:
            config = generate_site.load_config()
            site_rows = generate_site.load_teams(generate_site.load_prior())
            team_ratings = {row["team"]: row["rating"] for row in site_rows}
            generate_site.build_html.qb_data = generate_site.load_qbs(
                team_ratings
            )
            base_html = generate_site.build_html(site_rows, config)
            if args.refresh_mccabe:
                preview = refresh_mccabe_page(
                    base_html, PUBLIC_OUTPUT.read_text(encoding="utf-8")
                )
            else:
                comparison_rows, receipt = load_comparison_rows(
                    MCCABE_PATH,
                    MODEL_PATH,
                    BACKTEST_PATH,
                    require_immutable=args.publish,
                )
                preview = inject_comparison(
                    base_html,
                    render_comparison_panel(comparison_rows, receipt),
                )
        atomic_write_text(output, preview)
    except (csv.Error, KeyError, OSError, TypeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {output}")
    if receipt:
        print(f"  {len(comparison_rows)} teams | {receipt['publication_status']}")
    else:
        print("  Preserved the existing approved PGO panel")
    if fantasy_preview is not None:
        eligible = sum(
            row["ranking_eligible"] for row in fantasy_preview["rows"]
        )
        print(f"  {eligible} fantasy players | PREVIEW / HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
