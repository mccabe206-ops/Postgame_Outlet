#!/usr/bin/env python3
"""Render the frozen 2026 PGO Forecast Lab without fetching or grading."""

import argparse
import csv
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import generate_site
from pgo_challenger import PERFORMANCE_FEATURES, QB_FEATURES
import pgo_forecast_snapshot
import pgo_forecast_weekly
import pgo_prospective
from release_ratings import atomic_write_text


HERE = Path(__file__).resolve().parent
ARCHIVE_DIR = HERE / "docs" / "evidence" / "forecast-lab-2026"
LOCK_PATH = ARCHIVE_DIR / "prospective_lock.json"
PREDICTIONS_PATH = ARCHIVE_DIR / "prospective_predictions.csv"
ATTESTATION_PATH = HERE / "research" / "pgo_stability_blend" / "prospective_attestation.json"
CAPTURE_ROOT = ARCHIVE_DIR / "results"
SNAPSHOT_DIR = ARCHIVE_DIR / "september-07"
WEEKLY_DIR = ARCHIVE_DIR / "weekly"
OUTPUT_PATH = HERE / "docs" / "forecast-lab.html"
ATTESTATION_COMMIT = "8aae9438d251c645509d3df15a31bb86d50059b9"
ATTESTED_AT = "2026-08-26T16:07:24-04:00"
EXPECTED_ATTESTATION_SHA256 = "b89fe9c50f6c9d351aecc1820c573625ef11dd17bca1650ce3327abc8e3fadcd"
EXPECTED_SNAPSHOT_MANIFEST_SHA256 = "43bdeee73a2d3301eedbcecc7d291dc9ebe68cf196860e7217326570e4fe2f42"
RESULT_COLUMNS = (
    "game_id", "season", "week", "kickoff", "game_type", "home_team",
    "away_team", "home_score", "away_score", "finalized_at",
)
_RESULT_REQUIRED = {
    "game_id", "kickoff", "game_type", "home_team", "away_team",
    "home_score", "away_score", "finalized_at",
}
_CAPTURE_KEYS = {
    "schema_version", "kind", "captured_at", "source_url", "results_file",
    "results_file_sha256", "rows",
}
_CAPTURE_NAME = re.compile(r"^\d{8}T\d{6}Z$")


def _sha256(value):
    return hashlib.sha256(value).hexdigest()


def _utc(value):
    return pgo_prospective._parse_datetime(value).astimezone(UTC)


def _capture_name(value):
    return _utc(value).strftime("%Y%m%dT%H%M%SZ")


def _current_utc():
    return datetime.now(UTC)


def _https_url(value):
    parsed = urlparse(str(value).strip())
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Result provenance requires an HTTPS source URL")
    return parsed.geturl()


def load_archive(lock_path, csv_path, attestation_path):
    """Verify the exact derived lock and its review CSV against the attestation."""
    try:
        lock_bytes = Path(lock_path).read_bytes()
        prediction_bytes = Path(csv_path).read_bytes()
        attestation_bytes = Path(attestation_path).read_bytes()
        if _sha256(attestation_bytes) != EXPECTED_ATTESTATION_SHA256:
            raise ValueError("published attestation hash mismatch")
        attestation = json.loads(attestation_bytes)
        lock = json.loads(lock_bytes)
        pgo_prospective._verify_lock(lock)
        pgo_prospective._verify_grade_attestation(lock, lock_bytes, attestation)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"Forecast archive verification failed: {error}") from error
    expected = attestation["derived"]["predictions_file_sha256"]
    if _sha256(prediction_bytes) != expected:
        raise ValueError("Forecast prediction CSV hash mismatch")
    if prediction_bytes != pgo_prospective._prediction_csv(lock).encode("utf-8"):
        raise ValueError("Forecast prediction CSV does not match the lock")
    if len(lock["games"]) != 272:
        raise ValueError("Forecast archive must contain exactly 272 games")
    return lock


def _load_snapshot(directory):
    directory = Path(directory)
    is_default = directory.absolute() == SNAPSHOT_DIR.absolute()
    if not directory.exists() and not directory.is_symlink():
        if is_default and EXPECTED_SNAPSHOT_MANIFEST_SHA256:
            raise ValueError("The pinned default snapshot is missing")
        return None
    if is_default and EXPECTED_SNAPSHOT_MANIFEST_SHA256:
        try:
            manifest = (directory / "manifest.json").read_bytes()
        except OSError as error:
            raise ValueError("The pinned default snapshot manifest is missing") from error
        if _sha256(manifest) != EXPECTED_SNAPSHOT_MANIFEST_SHA256:
            raise ValueError("The pinned default snapshot manifest hash changed")
    return pgo_forecast_snapshot.load_snapshot(directory)


def _parse_results(raw, label):
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        fieldnames = reader.fieldnames or ()
        if len(fieldnames) != len(set(fieldnames)):
            raise ValueError("duplicate result CSV columns")
        fields = set(fieldnames)
        if not _RESULT_REQUIRED <= fields or fields - set(RESULT_COLUMNS):
            raise ValueError("result CSV columns are invalid")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError("result CSV field count mismatch")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label} is not UTF-8") from error
    except csv.Error as error:
        raise ValueError(f"{label} is not valid CSV") from error
    if not rows:
        raise ValueError(f"{label} has no result rows")
    return rows


def _accepted_results(raw, lock, captured_at, label):
    locked = {game["game_id"]: game for game in lock.get("games", ())}
    accepted = []
    seen = set()
    capture_time = _utc(captured_at)
    for row in _parse_results(raw, label):
        normalized = pgo_prospective._normalize_result(row)
        game_id = normalized["game_id"]
        if game_id in seen:
            raise ValueError(f"duplicate result in capture: {game_id}")
        seen.add(game_id)
        game = locked.get(game_id)
        if game is None:
            raise ValueError(f"unexpected result: {game_id}")
        for field, actual, expected in (
            ("home team", normalized["home_team"], game["home"]),
            ("away team", normalized["away_team"], game["away"]),
            ("kickoff", _utc(normalized["kickoff"]), _utc(game["kickoff"])),
            ("game type", normalized["game_type"], game["game_type"]),
        ):
            if actual != expected:
                raise ValueError(f"locked {field} mismatch: {game_id}")
        for field in ("season", "week"):
            if field in normalized and normalized[field] != game[field]:
                raise ValueError(f"locked {field} mismatch: {game_id}")
        if any(not isinstance(normalized[field], int) for field in ("home_score", "away_score")):
            raise ValueError(f"Result requires nonnegative integer scores: {game_id}")
        finalized = _utc(normalized["finalized_at"])
        if finalized <= _utc(game["kickoff"]):
            raise ValueError(f"Result finalized before kickoff: {game_id}")
        if finalized > capture_time:
            raise ValueError(f"Result finalized after capture: {game_id}")
        normalized.update({
            "season": game["season"],
            "week": game["week"],
            "actual_margin": normalized["home_score"] - normalized["away_score"],
        })
        accepted.append(normalized)
    return accepted


def load_results(capture_root, lock):
    """Load immutable incremental result transcriptions, rejecting corrections."""
    root = Path(capture_root)
    if not root.exists():
        return [], []
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Result capture root must be a real directory")
    accepted = {}
    provenance = []
    for directory in sorted(root.iterdir(), key=lambda path: path.name):
        if directory.is_symlink() or not directory.is_dir() or not _CAPTURE_NAME.fullmatch(directory.name):
            raise ValueError(f"Invalid result capture directory: {directory.name}")
        metadata_path = directory / "capture.json"
        results_path = directory / "results.csv"
        if metadata_path.is_symlink() or results_path.is_symlink():
            raise ValueError(f"Invalid result capture path: {directory.name}")
        if set(path.name for path in directory.iterdir()) != {"capture.json", "results.csv"}:
            raise ValueError(f"Invalid result capture contents: {directory.name}")
        try:
            metadata = json.loads(metadata_path.read_bytes())
            raw = results_path.read_bytes()
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid result capture: {directory.name}") from error
        if not isinstance(metadata, dict) or set(metadata) != _CAPTURE_KEYS:
            raise ValueError(f"Invalid result capture metadata: {directory.name}")
        if (
            metadata["schema_version"] != 1
            or metadata["kind"] != "pgo_forecast_lab_result_transcription"
            or metadata["results_file"] != "results.csv"
            or isinstance(metadata["rows"], bool)
            or not isinstance(metadata["rows"], int)
            or metadata["rows"] <= 0
        ):
            raise ValueError(f"Invalid result capture metadata: {directory.name}")
        if _capture_name(metadata["captured_at"]) != directory.name:
            raise ValueError(f"Result capture timestamp mismatch: {directory.name}")
        metadata["source_url"] = _https_url(metadata["source_url"])
        if _sha256(raw) != metadata["results_file_sha256"]:
            raise ValueError(f"Result capture hash mismatch: {directory.name}")
        rows = _accepted_results(raw, lock, metadata["captured_at"], directory.name)
        if len(rows) != metadata["rows"]:
            raise ValueError(f"Result capture row count mismatch: {directory.name}")
        for row in rows:
            if row["game_id"] in accepted:
                raise ValueError(f"duplicate result across captures: {row['game_id']}")
            accepted[row["game_id"]] = row
        provenance.append(metadata)
    order = {game["game_id"]: index for index, game in enumerate(lock.get("games", ()))}
    return sorted(accepted.values(), key=lambda row: order[row["game_id"]]), provenance


def record_results(results_path, source_url, capture_root, lock):
    """Archive one reviewed, incremental UTF-8 result transcription once."""
    source_url = _https_url(source_url)
    capture_time = _current_utc().astimezone(UTC)
    name = _capture_name(capture_time)
    destination = Path(capture_root) / name
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Result capture already exists: {name}")
    try:
        raw = Path(results_path).read_bytes()
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Reviewed result CSV is not UTF-8") from error
    except OSError as error:
        raise ValueError(f"Cannot read reviewed result CSV: {error}") from error
    if text.encode("utf-8") != raw:
        raise ValueError("Reviewed result CSV does not round-trip as UTF-8")
    rows = _accepted_results(raw, lock, capture_time, str(results_path))
    existing, _ = load_results(capture_root, lock)
    duplicate = {row["game_id"] for row in rows} & {row["game_id"] for row in existing}
    if duplicate:
        raise ValueError(f"Result already captured: {sorted(duplicate)[0]}")
    captured_text = capture_time.isoformat().replace("+00:00", "Z")
    metadata = {
        "schema_version": 1,
        "kind": "pgo_forecast_lab_result_transcription",
        "captured_at": captured_text,
        "source_url": source_url,
        "results_file": "results.csv",
        "results_file_sha256": _sha256(raw),
        "rows": len(rows),
    }
    outputs = (
        (destination / "results.csv", text),
        (destination / "capture.json", pgo_prospective._canonical(metadata) + "\n"),
    )
    if not pgo_prospective._write_new_outputs(destination, outputs):
        raise ValueError("Result capture could not reserve new output paths")
    return destination


def _validate_output_path(output, protected_paths, protected_roots):
    output = Path(output).resolve()
    if output.suffix.lower() != ".html":
        raise ValueError("Forecast Lab output must be an HTML file")
    protected = {Path(path).resolve() for path in protected_paths if path is not None}
    if output in protected:
        raise ValueError("Forecast Lab output conflicts with a protected input")
    for root in protected_roots:
        root = Path(root).resolve()
        if output == root or root in output.parents:
            raise ValueError("Forecast Lab output cannot be inside immutable evidence")
    return output


def _summary(values, actuals, *, winner=False):
    errors = [actual - predicted for actual, predicted in zip(actuals, values)]
    result = {
        "count": len(errors),
        "mae": math.fsum(abs(error) for error in errors) / len(errors) if errors else None,
        "rmse": math.sqrt(math.fsum(error * error for error in errors) / len(errors)) if errors else None,
    }
    if winner:
        decisions = [
            (actual, predicted) for actual, predicted in zip(actuals, values)
            if actual != 0 and predicted != 0
        ]
        correct = sum((actual > 0) == (predicted > 0) for actual, predicted in decisions)
        result["winner"] = {
            "correct": correct,
            "denominator": len(decisions),
            "accuracy": correct / len(decisions) if decisions else None,
        }
    return result


def interim_metrics(lock, results):
    """Calculate descriptive subset metrics without invoking the canonical grader."""
    games = {game["game_id"]: game for game in lock.get("games", ())}
    actuals = [float(row["actual_margin"]) for row in results]
    predictions = {
        "blend": [float(games[row["game_id"]]["candidate_prediction"]) for row in results],
        "pgo_v0": [float(games[row["game_id"]]["pgo_v0_prediction"]) for row in results],
        "zero": [0.0 for _row in results],
        "venue": [
            2.5 if games[row["game_id"]]["location"] == "Home" else 0.0
            for row in results
        ],
    }
    return {
        name: _summary(values, actuals, winner=name in {"blend", "pgo_v0"})
        for name, values in predictions.items()
    }


def _target_summary(predicted, actual):
    errors = [observed - estimate for observed, estimate in zip(actual, predicted)]
    return {
        "count": len(errors),
        "mae": math.fsum(abs(error) for error in errors) / len(errors) if errors else None,
        "rmse": math.sqrt(math.fsum(error * error for error in errors) / len(errors)) if errors else None,
        "bias": math.fsum(errors) / len(errors) if errors else None,
    }


def snapshot_interim_metrics(snapshot, results):
    """Describe finalized results for the separately issued September snapshot."""
    games = {game["game_id"]: game for game in snapshot.get("games", ())}
    selected = []
    for result in results:
        game = games.get(result["game_id"])
        if game is None:
            raise ValueError(f'Unexpected September snapshot result: {result["game_id"]}')
        selected.append((game, result))
    predicted_margins = [float(game["margin"]) for game, _result in selected]
    actual_margins = [float(result["actual_margin"]) for _game, result in selected]
    predicted_totals = [float(game["total"]) for game, _result in selected]
    actual_totals = [
        float(result["home_score"] + result["away_score"])
        for _game, result in selected
    ]
    predicted_scores = [
        score for game, _result in selected
        for score in (float(game["home_points"]), float(game["away_points"]))
    ]
    actual_scores = [
        float(score) for _game, result in selected
        for score in (result["home_score"], result["away_score"])
    ]
    venue_margins = [
        2.5 if game["location"] == "Home" else 0.0
        for game, _result in selected
    ]
    league_total = float(snapshot["league_mean_total"])
    league_totals = [league_total for _item in selected]
    league_scores = [
        score for venue in venue_margins
        for score in ((league_total + venue) / 2, (league_total - venue) / 2)
    ]
    unavailable = {"total": None, "score": None}
    return {
        "count": len(selected),
        "margin": _target_summary(predicted_margins, actual_margins),
        "total": _target_summary(predicted_totals, actual_totals),
        "score": _target_summary(predicted_scores, actual_scores),
        "winner": _summary(predicted_margins, actual_margins, winner=True)["winner"],
        "ties": {
            "actual": actual_margins.count(0.0),
            "forecast": predicted_margins.count(0.0),
        },
        "baselines": {
            "pgo_v0": {
                "margin": _target_summary(
                    [float(game["pgo_v0_margin"]) for game, _result in selected],
                    actual_margins,
                ), **unavailable,
            },
            "legacy": {
                "margin": _target_summary(
                    [float(game["legacy_margin"]) for game, _result in selected],
                    actual_margins,
                ), **unavailable,
            },
            "zero": {
                "margin": _target_summary([0.0 for _item in selected], actual_margins),
                **unavailable,
            },
            "league_mean_venue": {
                "margin": _target_summary(venue_margins, actual_margins),
                "total": _target_summary(league_totals, actual_totals),
                "score": _target_summary(league_scores, actual_scores),
            },
        },
    }


def _shared_css():
    template = generate_site.TEMPLATE
    if template.count("<style>") != 1 or template.count("</style>") != 1:
        raise ValueError("Shared board style markers are missing or ambiguous")
    return template.split("<style>", 1)[1].split("</style>", 1)[0]


def _shared_font_links():
    template = generate_site.TEMPLATE
    marker = '<link rel="preconnect" href="https://fonts.googleapis.com">'
    if template.count(marker) != 1:
        raise ValueError("Shared board font markers are missing or ambiguous")
    start = template.index(marker)
    end = template.index("<style>", start)
    links = template[start:end].strip()
    if links.count("<link") != 2 or "{{" in links:
        raise ValueError("Shared board font links are invalid")
    return links


def _signed(value):
    return f"{float(value):+.1f}"


def _display_time(value, zone_label):
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )
    clock = moment.strftime("%I:%M %p").lstrip("0")
    return f"{moment.strftime('%B')} {moment.day}, {moment.year} at {clock} {zone_label}"


def _kickoff_time(value):
    source = str(value)
    display = _display_time(_utc(source), "UTC")
    return f'<time datetime="{html.escape(source, quote=True)}">{display}</time>'


def _snapshot_kickoff_time(value):
    source = str(value)
    moment = _utc(source).astimezone(ZoneInfo("America/New_York"))
    display = _display_time(moment, moment.tzname())
    return f'<time datetime="{html.escape(source, quote=True)}">{display}</time>'


def _whole_point(value):
    return str(int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def _spread(game):
    margin = float(game["margin"])
    if f"{abs(margin):.1f}" == "0.0":
        return "Pick'em"
    if margin > 0:
        return f'{html.escape(game["home"])} -{margin:.1f}'
    if margin < 0:
        return f'{html.escape(game["away"])} -{abs(margin):.1f}'


def _snapshot_metric_cards(metrics, label="September snapshot"):
    if metrics["count"] == 0:
        return f'<p class="empty">No finalized {html.escape(label)} results recorded yet.</p>'
    cards = []
    for name, label in (
        ("margin", "Margin error"),
        ("total", "Total-points error"),
        ("score", "Team-score error"),
    ):
        item = metrics[name]
        cards.append(
            f'<article class="metric"><h3>{label}</h3>'
            f'<div>Values <strong>{item["count"]}</strong></div>'
            f'<div>MAE <strong>{item["mae"]:.3f}</strong></div>'
            f'<div>RMSE <strong>{item["rmse"]:.3f}</strong></div>'
            f'<div>Bias <strong>{item["bias"]:+.3f}</strong></div></article>'
        )
    winner = metrics["winner"]
    accuracy = "Unavailable" if winner["accuracy"] is None else f'{winner["accuracy"]:.1%}'
    cards.append(
        '<article class="metric"><h3>Winner accuracy</h3>'
        f'<div><strong>{accuracy}</strong></div>'
        f'<small>{winner["correct"]}/{winner["denominator"]}; '
        f'{metrics["ties"]["actual"]} actual ties and '
        f'{metrics["ties"]["forecast"]} zero-margin forecasts excluded</small></article>'
    )
    baselines = metrics["baselines"]
    baseline_rows = []
    for key, label in (
        ("pgo_v0", "PGO v0 margin"),
        ("legacy", "Original archive margin"),
        ("zero", "Zero margin"),
        ("league_mean_venue", "League mean + venue"),
    ):
        item = baselines[key]
        values = [
            "Unavailable" if item[target] is None else f'{item[target]["mae"]:.3f}'
            for target in ("margin", "total", "score")
        ]
        baseline_rows.append(
            f'<tr><th scope="row">{label}</th>'
            + "".join(f"<td>{value}</td>" for value in values) + "</tr>"
        )
    return (
        '<div class="metric-grid">' + "".join(cards) + "</div>"
        '<h3>Same-game diagnostic baselines</h3>'
        f'<p>Every row uses the same {metrics["count"]} finalized games. '
        'PGO v0 and the original archive have no frozen total or score forecasts.</p>'
        '<div class="table-shell"><table><thead><tr><th>Baseline</th>'
        '<th>Margin MAE</th><th>Total MAE</th><th>Team-score MAE</th></tr></thead>'
        f'<tbody>{"".join(baseline_rows)}</tbody></table></div>'
    )


def _forecast_weeks(games, results, *, weekly=False):
    result_by_id = {row["game_id"]: row for row in results}
    weeks = []
    for week in sorted({game["week"] for game in games}):
        rows = []
        for game in (item for item in games if item["week"] == week):
            result = result_by_id.get(game["game_id"])
            actual = "&mdash;"
            if result:
                actual = (
                    f'{html.escape(game["away"])} {result["away_score"]}, '
                    f'{html.escape(game["home"])} {result["home_score"]}'
                )
            score = (
                f'{html.escape(game["away"])} {_whole_point(game["away_points"])}, '
                f'{html.escape(game["home"])} {_whole_point(game["home_points"])}'
            )
            timing = ""
            if weekly:
                cutoff = html.escape(game["lock_at"], quote=True)
                status = "Locked" if _current_utc() >= _utc(game["lock_at"]) else "Draft"
                timing = (
                    f'<td><span class="weekly-status" data-weekly-cutoff="{cutoff}">{status}</span>'
                    f'<br>{_snapshot_kickoff_time(game["lock_at"])}</td>'
                )
            kind = "weekly" if weekly else "snapshot"
            rows.append(
                f'<tr data-{kind}-game-id="{html.escape(game["game_id"], quote=True)}">'
                f'<th scope="row">{html.escape(game["away"])} @ {html.escape(game["home"])}</th>'
                f'<td>{_spread(game)}</td><td>{score}</td><td>{float(game["total"]):.1f}</td>'
                f'{timing}'
                f'<td>{_snapshot_kickoff_time(game["kickoff"])}</td>'
                f'<td>{actual}</td></tr>'
            )
        weeks.append(
            f'<details class="forecast-week {kind}-week"{" open" if week == min(game["week"] for game in games) else ""}>'
            f'<summary>Week {week} <span>{len(rows)} games</span></summary>'
            '<div class="table-shell"><table><thead><tr><th>Matchup</th><th>PGO spread</th>'
            '<th>Projected score</th><th>Projected total</th>'
            f'{"<th>Weekly lock (Eastern)</th>" if weekly else ""}'
            f'<th>Frozen kickoff</th><th>Actual</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></details>'
        )
    return "".join(weeks)


def _rating_explanations(snapshot):
    """Explain saved centered contributions without recomputing ratings."""
    labels = {
        "pgo_v0": "PGO v0 results-history input",
        "passing_epa_per_play_for": "Team passing efficiency (EPA per dropback)",
        "passing_epa_per_play_against": "Pass defense (opponent EPA prevented)",
        "rushing_epa_per_play_for": "Team rushing efficiency (EPA per carry)",
        "rushing_epa_per_play_against": "Run defense (opponent EPA prevented)",
        "explosive_play_rate_for": "Offensive explosive-play rate",
        "explosive_play_prevention_rate": "Explosive-play prevention",
        "sack_avoidance_rate": "Team sack avoidance",
        "sack_creation_rate": "Defensive sack creation",
        "giveaway_avoidance_rate": "Team giveaway avoidance",
        "takeaway_rate": "Defensive takeaway rate",
        "qb_epa_per_dropback": "QB passing efficiency (historical EPA)",
        "qb_cpoe": "QB completion rate above expectation",
        "qb_sack_avoidance": "QB historical sack avoidance",
        "qb_ball_security": "QB historical ball security",
        "qb_rushing_epa_per_carry": "QB historical rushing efficiency",
        "qb_log_dropbacks": "QB historical passing sample size",
        "qb_experience_prior": "QB experience prior",
        "qb_draft_prior": "QB draft-position prior",
        "returning_offense_snap_share": "Returning offensive snap share",
        "returning_defense_snap_share": "Returning defensive snap share",
        "incoming_prior_snap_share": "Incoming players' prior snap share",
        "rookie_draft_capital": "Rookie draft capital",
        "head_coach_continuity": "Head-coach continuity",
        "head_coach_tenure": "Head-coach tenure",
        "offense_availability": "Offensive availability adjustment",
        "defense_availability": "Defensive availability adjustment",
        "qb_current_minus_full": "QB lineup adjustment",
        "home_field": "Home-field adjustment",
        "rest_difference": "Rest adjustment",
    }
    teams = sorted(snapshot["teams"], key=lambda team: team["rank"])
    preprocessor = snapshot["fit"]["preprocessor"]
    names = [*preprocessor["feature_names"],
             *(name + "_missing" for name in preprocessor["missing_features"])]
    groups = (
        ("Results history", ("pgo_v0",)),
        ("Team passing efficiency", ("passing_epa_per_play_for",)),
        ("Other team efficiency", tuple(name for name in PERFORMANCE_FEATURES
                                        if name != "passing_epa_per_play_for")),
        ("QB history", QB_FEATURES),
        ("Roster composition", ("returning_offense_snap_share", "returning_defense_snap_share",
                                "incoming_prior_snap_share", "rookie_draft_capital")),
        ("Coaching", ("head_coach_continuity", "head_coach_tenure")),
    )
    grouped_names = {name for _, members in groups for name in members}
    groups += (("Other adjustments", tuple(name for name in names if name not in grouped_names)),)

    def contribution_row(label, value):
        number = f"{value:+.3f}".replace("-0.000", "+0.000")
        return f'<tr><th scope="row">{html.escape(label)}</th><td>{number}</td></tr>'

    cards = []
    for index, team in enumerate(teams):
        contributions = team["contributions"]
        if (not contributions or set(contributions) != set(names)
                or not all(math.isfinite(v) for v in contributions.values())
                or not math.isclose(math.fsum(contributions.values()), team["rating"],
                                    abs_tol=1e-8, rel_tol=0)):
            raise ValueError("Saved contributions must reconcile to the team rating")
        rows = [contribution_row(label, math.fsum(contributions.get(name, 0.0) for name in members))
                for label, members in groups]
        rows.append(contribution_row("Total model rating", team["rating"]))
        terms = []
        for name in names:
            label = labels.get(name.removesuffix("_missing"), name.replace("_", " "))
            if name.endswith("_missing"):
                label = "Missing-data adjustment: " + label
            terms.append(contribution_row(label, contributions[name]))
        gaps = []
        for neighbor, direction in ((index - 1, "below"), (index + 1, "above")):
            if 0 <= neighbor < len(teams):
                other = teams[neighbor]
                gap = abs(team["rating"] - other["rating"])
                gaps.append(f'{gap:.3f} {direction} #{other["rank"]} {html.escape(other["team"])}')
        cards.append(
            f'<details class="lab-detail rating-explanation" id="rating-{html.escape(team["team"], quote=True)}">'
            f'<summary>#{team["rank"]} {html.escape(team["team"])} &middot; {team["rating"]:+.3f}</summary>'
            f'<p>{"; ".join(gaps)}. Expected QB1: {html.escape(team["qb_name"])}.</p>'
            '<p>These are model contributions, not independent team grades. '
            '<a href="#rating-explanations">How to read them</a>.</p>'
            '<table class="rating-summary"><thead><tr><th>Input group</th><th>Contribution</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
            f'<details class="lab-detail"><summary>All {len(names)} fitted terms</summary>'
            '<p>The same input order for every team, including zero contributions. Group totals can hide offsetting positive and negative terms.</p>'
            '<table class="rating-terms"><thead><tr><th>Fitted input</th><th>Contribution</th></tr></thead>'
            f'<tbody>{"".join(terms)}</tbody></table></details></details>'
        )
    return '''<details class="lab-detail" id="rating-explanations">
<summary>Why teams rank here &middot; All 32 September ratings</summary>
<p>Open a team to see what raises and lowers its saved September 7 output. Higher totals rank higher; the gaps show how close neighboring teams are.</p>
<p><a href="#rating-NE">New England</a> &middot; <a href="#rating-JAX">Jacksonville</a> &middot; <a href="https://github.com/walshja9/Postgame_Outlet/blob/main/docs/model-audit-2026-09-07.md">Read the outlier audit</a></p>
<p>Every summary shows the same seven input groups in the same order, so you can compare teams row by row. All are centered against the 32-team average and sum to the rating before rounding. These are fitted adjustments, <strong>not independent football grades</strong>, player values, or calibrated point-spread prices.</p>
<p>Team passing efficiency is shown separately from the other nine team-efficiency inputs. QB history combines eight QB inputs; roster composition combines returning offensive and defensive snap shares, incoming snap share, and rookie draft capital; coaching combines continuity and tenure. Other adjustments include availability, the QB lineup adjustment, venue, rest, and missing-data indicators. A zero here does not establish comprehensive injury coverage. Open the full breakdown to see every term.</p>
<p>EPA means expected points added. Team efficiency uses games through 2025 with a four-game half-life; QB efficiency uses shrunk player history. The PGO v0 input carries the earlier results rating forward without a new offseason shrink, unlike the separate v0 game-forecast baseline.</p>
<p><strong>Audit concern:</strong> some learned directions run against football intuition. Lower returning offensive snap share raises this model's output, and head-coach continuity lowers it. Correlated inputs and these fitted relationships need testing; the arithmetic does not establish that roster turnover or coaching changes help a team. Returning snap share measures historical snap weight among currently eligible players, not the percentage of last season's roster retained.</p>
''' + "".join(cards) + '''<p>Full precision and all inputs: <a href="evidence/forecast-lab-2026/september-07/snapshot.json">saved snapshot JSON</a>. Ratings remain EXPERIMENTAL / HOLD.</p></details>'''


def _weekly_section(weekly, snapshot, results, provenance):
    games = weekly["games"]
    metrics = snapshot_interim_metrics({**snapshot, "games": games}, results)
    source_dates = sorted({game["source_generated_at"] for game in games})
    source_text = ", ".join(_snapshot_kickoff_time(value) for value in source_dates)
    sources = (
        f'<p>Source snapshot generated: {source_text}. '
        'The initial Week 1 draft uses the September 7 active-roster snapshot; '
        'it does not include a comprehensive game-day injury adjustment.</p>'
        if games else '<p>No weekly edition has been recorded yet.</p>'
    )
    revisions = "".join(
        f'<li>Saved {_snapshot_kickoff_time(item["registered_at"])}; '
        f'<a href="evidence/forecast-lab-2026/weekly/{html.escape(item["revision"], quote=True)}">'
        f'forecast revision</a></li>' for item in weekly.get("revisions", [])
    )
    result_sources = "".join(
        f'<li>{html.escape(str(item["captured_at"]))}: '
        f'<a href="{html.escape(_https_url(item["source_url"]), quote=True)}">'
        f'reviewed result source</a> ({item["rows"]} rows; CSV SHA-256 '
        f'<code>{html.escape(str(item["results_file_sha256"]))}</code>)</li>'
        for item in provenance
    ) or "<li>No weekly results recorded.</li>"
    return f'''
<header class="lab-hero hero"><div class="status">EXPERIMENTAL &mdash; HOLD</div>
<h1>PGO Forecast Lab</h1><h2>Weekly game forecasts</h2>
<p>Each matchup locks <strong>60 minutes before kickoff</strong>. Both teams' projected scores, the spread, and the total freeze together.</p>
<p>Drafts can change until their own cutoff. The last saved revision before that deadline becomes the locked forecast; earlier games do not lock the rest of the week.</p>
<p><a href="index.html">Back to McCabe Ratings</a> &middot; <a href="#rating-explanations">Why teams rank here</a> &middot; <a href="#preseason-baseline">Full-season preseason forecast</a></p></header>
<section><h2>Weekly predictions</h2>{sources}
<p>The PGO spread shows the favorite with a minus sign. Scores are rounded to whole points; spreads and totals to one decimal. Evaluation uses unrounded values.</p>
{_forecast_weeks(games, results, weekly=True)}</section>
<section><h2>Weekly forecast record</h2><p>{len(results)} of {len(games)} recorded weekly forecasts have finalized results. Interim tracking &mdash; not a validation result.</p>{_snapshot_metric_cards(metrics, "weekly")}</section>
<details class="lab-detail"><summary>Weekly revision history and rules</summary><ul>{revisions or "<li>No revisions yet.</li>"}</ul>
<p>Revisions are saved separately and cannot be submitted at or after the cutoff. A saved timestamp records local registration; the repository history records publication. A schedule change requires review and cannot silently extend an existing deadline.</p>
<p>Fresh weekly inputs require a separately reviewed source snapshot. Source refresh is not automated. Future weeks without a weekly edition remain available in the preseason baseline below.</p>
<h3>Weekly results provenance</h3><ul>{result_sources}</ul></details>'''


def _snapshot_section(snapshot, results, provenance):
    generated = _utc(snapshot["generated_at"])
    games = list(snapshot["games"])
    if any(generated >= _utc(game["kickoff"]) for game in games):
        raise ValueError("September snapshot must be generated before every kickoff")
    metrics = snapshot_interim_metrics(snapshot, results)
    ratings = "".join(
        f'<tr class="snapshot-team"><td>{team["rank"]}</td>'
        f'<th scope="row"><a href="#rating-{html.escape(team["team"], quote=True)}">{html.escape(team["team"])}</a></th><td>{_signed(team["rating"])}</td>'
        f'<td>{html.escape(team["qb_name"])}</td>'
        f'<td>{html.escape(team["old_selector_qb_name"])} ({_signed(team["old_selector_rating"])})</td></tr>'
        for team in sorted(snapshot["teams"], key=lambda item: item["rank"])
    )
    method = snapshot.get("method", {})
    method_items = "".join(
        f'<li><strong>{html.escape(label)}:</strong> {html.escape(str(method[key]))}</li>'
        for key, label in (
            ("roster_policy", "Roster policy"),
            ("injury_coverage", "Injury coverage"),
            ("history", "History"),
            ("totals", "Projected totals"),
            ("fit_recovery", "Fit recovery"),
            ("evaluation", "Evaluation boundary"),
            ("schedule", "Schedule"),
        ) if method.get(key)
    )
    source_items = "".join(
        f'<li>{html.escape(str(source["name"]))}: '
        f'<a href="{html.escape(_https_url(source["url"]), quote=True)}">source</a>; '
        f'captured {html.escape(str(source["captured_at"]))}; SHA-256 '
        f'<code>{html.escape(str(source["sha256"]))}</code></li>'
        for source in snapshot.get("sources", ())
    ) or "<li>See the verified snapshot manifest.</li>"
    result_sources = "".join(
        f'<li>{html.escape(str(item["captured_at"]))}: '
        f'<a href="{html.escape(_https_url(item["source_url"]), quote=True)}">'
        f'reviewed transcription source</a> ({item["rows"]} rows; CSV SHA-256 '
        f'<code>{html.escape(str(item["results_file_sha256"]))}</code>)</li>'
        for item in provenance
    ) or "<li>No September result transcriptions recorded.</li>"
    return f'''
<header class="lab-hero hero"><div class="status">{html.escape(str(method.get("status", "EXPERIMENTAL — HOLD")))}</div>
<h1>PGO Forecast Lab</h1><h2>September 7 preseason snapshot</h2>
<p><strong>{html.escape(str(method.get("name", "Active-roster preseason scenario")))}</strong>. Positive home margin means the home team is ahead; the PGO spread shows the favorite with a minus sign.</p>
<p>ACT is an administrative roster status, not proof of health or game-day availability. Week 1 and the full schedule use the same September 7 state; later weeks are not weekly lineup updates.</p>
<p><strong>{len(results)} of {len(games)} finalized results recorded.</strong> Interim tracking &mdash; not a validation result.</p>
<p><a href="index.html">Back to McCabe Ratings</a></p></header>
<section><h2>September snapshot record</h2>{_snapshot_metric_cards(metrics)}</section>
<section><h2>Week 1 and full-season forecasts</h2><p>Scores are rounded to whole points; spreads and totals to one decimal. Evaluation uses the original unrounded projections.</p>{_forecast_weeks(games, results)}</section>
<details class="lab-detail" open><summary>32-team active-roster ratings and QB assumptions</summary><div class="table-shell"><table><thead><tr><th>Rank</th><th>Team</th><th>PGO rating</th><th>Expected QB1</th><th>Old QB-selector comparison</th></tr></thead><tbody>{ratings}</tbody></table></div></details>
<details class="lab-detail"><summary>September method, sources, and downloads</summary><p>Generated {_display_time(generated, "UTC")}. This inference-policy change and the simple projected-score method remain experimental; through-2025 performance does not validate them.</p><ul>{method_items}</ul><p><a href="evidence/forecast-lab-2026/september-07/snapshot.json">Snapshot JSON</a> &middot; <a href="evidence/forecast-lab-2026/september-07/forecasts.csv">Forecast CSV</a> &middot; <a href="evidence/forecast-lab-2026/september-07/ratings.csv">Ratings CSV</a> &middot; <a href="evidence/forecast-lab-2026/september-07/manifest.json">Verification manifest</a></p><ul>{source_items}</ul><p>No calibrated probabilities, market claims, or retrospective promotion are attached to this snapshot.</p><h3>September results provenance</h3><ul>{result_sources}</ul></details>'''


def _metric_cards(metrics):
    if metrics["blend"]["count"] == 0:
        return '<p class="empty">No finalized results recorded yet.</p>'
    labels = {
        "blend": "Frozen 25% stability blend",
        "pgo_v0": "PGO v0 baseline",
        "zero": "Zero-margin diagnostic",
        "venue": "Venue-only diagnostic",
    }
    cards = []
    for name in ("blend", "pgo_v0", "zero", "venue"):
        metric = metrics[name]
        winner = ""
        if "winner" in metric:
            item = metric["winner"]
            value = "Unavailable" if item["accuracy"] is None else f'{item["accuracy"]:.1%}'
            winner = (
                f'<div>Winner accuracy <strong>{value}</strong> '
                f'<small>({item["correct"]}/{item["denominator"]}; ties and zero forecasts excluded)</small></div>'
            )
        cards.append(
            f'<article class="metric"><h3>{html.escape(labels[name])}</h3>'
            f'<div>Results <strong>{metric["count"]}</strong></div>'
            f'<div>MAE <strong>{metric["mae"]:.3f}</strong></div>'
            f'<div>RMSE <strong>{metric["rmse"]:.3f}</strong></div>{winner}</article>'
        )
    return '<div class="metric-grid">' + "".join(cards) + "</div>"


def render_lab(lock, results, provenance, *, snapshot=None,
               snapshot_results=(), snapshot_provenance=(), weekly=None,
               weekly_results=(), weekly_provenance=()):
    """Render a standalone, escaped, no-fetch Forecast Lab page."""
    css = _shared_css()
    font_links = _shared_font_links()
    if snapshot is None:
        lead = f'''<header class="lab-hero hero"><div class="status">Experimental &middot; frozen archive</div>
<h1>PGO Forecast Lab</h1><h2>Can PGO predict football?</h2>
<p>This page tracks one frozen 2026 experiment. Each forecast is an estimated scoring margin: positive favors the home team; negative favors the away team.</p>
<p><strong>{len(results)} of {len(lock["games"])} finalized results recorded.</strong> Interim tracking &mdash; not a validation result.</p>
<p><a href="index.html">Back to McCabe Ratings</a></p></header>'''
        archive_open = archive_close = archive_heading = ""
    else:
        lead = _snapshot_section(snapshot, snapshot_results, snapshot_provenance)
        if weekly is not None:
            lead = (
                _weekly_section(weekly, snapshot, weekly_results, weekly_provenance)
                + _rating_explanations(snapshot)
                + '<details class="preseason-archive" id="preseason-baseline">'
                '<summary>September 7 preseason baseline &middot; All 272 games and 32 team ratings</summary>'
                + lead.replace('<h1>PGO Forecast Lab</h1>', '') + '</details>'
            )
        else:
            lead += _rating_explanations(snapshot)
        archive_open = '<details class="original-archive"><summary>Original July/August archive &middot; Frozen 25% stability blend</summary>'
        archive_heading = '<section><h2>Original frozen forecast record</h2><p>This separate 272-game archive and its HOLD gate remain unchanged.</p></section>'
        archive_close = "</details>"
    result_by_id = {row["game_id"]: row for row in results}
    metrics = interim_metrics(lock, results)
    weeks = []
    for week in sorted({game["week"] for game in lock["games"]}):
        body = []
        for game in (item for item in lock["games"] if item["week"] == week):
            result = result_by_id.get(game["game_id"])
            actual = error = "&mdash;"
            if result:
                actual = (
                    f'{html.escape(game["away"])} {result["away_score"]}, '
                    f'{html.escape(game["home"])} {result["home_score"]}; '
                    f'home margin {_signed(result["actual_margin"])}'
                )
                error = f'{abs(result["actual_margin"] - game["candidate_prediction"]):.1f}'
            body.append(
                f'<tr data-game-id="{html.escape(game["game_id"], quote=True)}">'
                f'<th scope="row">{html.escape(game["away"])} @ {html.escape(game["home"])}</th>'
                f'<td>{_signed(game["candidate_prediction"])}</td>'
                f'<td>{_signed(game["pgo_v0_prediction"])}</td>'
                f'<td>{_kickoff_time(game["kickoff"])}</td>'
                f'<td>{actual}</td><td>{error}</td></tr>'
            )
        weeks.append(
            f'<details class="forecast-week"{" open" if week == 1 else ""}>'
            f'<summary>Week {week} <span>{len(body)} games</span></summary>'
            '<div class="table-shell"><table><thead><tr><th>Matchup</th>'
            '<th>Blend home margin</th><th>PGO v0 home margin</th><th>Frozen kickoff</th>'
            f'<th>Actual</th><th>Blend absolute error</th></tr></thead><tbody>{"".join(body)}</tbody></table></div></details>'
        )
    sources = []
    for item in provenance:
        source_url = _https_url(item.get("source_url", ""))
        sources.append(
            f'<li>{html.escape(item.get("captured_at", ""))}: '
            f'<a href="{html.escape(source_url, quote=True)}">reviewed transcription source</a> '
            f'({html.escape(str(item.get("rows", 0)))} rows; CSV SHA-256 '
            f'<code>{html.escape(item.get("results_file_sha256", ""))}</code>)</li>'
        )
    sources = "".join(sources) or "<li>No result transcriptions recorded.</li>"
    diagnostic_rows = "".join(
        f'<tr><th scope="row">{html.escape(game["away"])} @ {html.escape(game["home"])}</th>'
        f'<td>{_signed(game["challenger_prediction"])}</td>'
        f'<td>{_signed(game["challenger_full_strength_prediction"])}</td></tr>'
        for game in lock["games"]
    )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PGO Forecast Lab</title>{font_links}<style>{css}
.lab-wrap{{max-width:1180px;margin:0 auto;padding:24px 18px 60px}}.lab-wrap a{{color:var(--accent)}}.lab-hero{{max-width:none;padding:26px;border-radius:14px;color:#fff;text-align:left}}.lab-hero a{{color:var(--highlight)}}.lab-hero a:focus-visible{{outline-color:var(--highlight)}}.lab-hero .status{{border-color:var(--highlight);margin-bottom:22px}}
.status{{display:inline-block;padding:6px 10px;border:1px solid var(--orange);border-radius:999px;font-weight:800}}.metric-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:16px 0}}.metric{{padding:14px;border:1px solid var(--border);border-radius:10px;background:var(--panel)}}.metric h3{{margin-top:0}}.forecast-week,.lab-detail,.original-archive,.preseason-archive{{margin:12px 0;border:1px solid var(--border);border-radius:10px;padding:12px}}.forecast-week summary,.lab-detail summary,.original-archive>summary,.preseason-archive>summary{{cursor:pointer;font-weight:800}}.forecast-week summary span{{color:var(--mut);font-weight:500}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap}}th:first-child{{text-align:left}}.notice{{padding:14px;border-left:4px solid var(--orange);background:var(--panel)}}code{{overflow-wrap:anywhere}}.weekly-status{{font-weight:800}}
.rating-explanation table{{table-layout:fixed}}.rating-explanation th{{white-space:normal;user-select:text}}.rating-explanation tbody th{{background:transparent;color:inherit;font-size:inherit;letter-spacing:normal;text-transform:none}}.rating-explanation thead th:last-child{{width:110px}}.rating-summary tr:last-child{{font-weight:800}}
</style></head><body><main class="lab-wrap">
{lead}{archive_open}{archive_heading}
<section><h2>Record so far</h2>{_metric_cards(metrics)}
<p>The theoretical 50% winner benchmark is a reference only.</p></section>
<section class="notice"><h2>What was frozen</h2>
<p>The source cutoff was {_display_time(lock["as_of"], "EDT")}. The exact forecasts were publicly attested on {_display_time(ATTESTED_AT, "EDT")}, before the first kickoff. This track is 75% PGO v0 and 25% of an archived challenger fit; it is not the live ratings-table model.</p>
<p><a href="evidence/forecast-lab-2026/prospective_lock.json">Download exact lock</a> &middot; <a href="evidence/forecast-lab-2026/prospective_predictions.csv">Download exact prediction CSV</a> &middot; <a href="https://github.com/walshja9/Postgame_Outlet/blob/{ATTESTATION_COMMIT}/research/pgo_stability_blend/prospective_attestation.json">Immutable attestation</a></p>
</section>
<details><summary>Method, metrics, and scientific boundary</summary>
<p>These are model-estimated home-score margins, not market prices, final-score predictions, or calibrated probabilities. MAE is mean absolute margin error; RMSE gives larger misses more weight.</p>
<p>Winner accuracy is derived from frozen margin signs. It excludes actual ties and zero-margin abstentions, reports its denominator, and is separate from calibration and every promotion gate. The theoretical 50% benchmark is a reference; no observed coin-flip record is invented.</p>
<p>Constant zero and venue-only (+2.5 Home, 0 Neutral) are fixed diagnostic margin baselines outside the preregistered full-season gate. Market and McCabe game-pick comparisons are unavailable because they were not captured before kickoff.</p>
<p>Raw source cutoff: <code>{html.escape(lock["as_of"])}</code>. Raw attestation time: <code>{html.escape(ATTESTED_AT)}</code>.</p>
<p>Partial metrics are descriptive only. The unchanged canonical grade requires all 272 exact final results and is the only path to a prospective PASS, HOLD, or BLOCKED receipt.</p></details>
<section><h2>Frozen forecasts and observed results</h2><p>Kickoffs are the frozen schedule record and may differ from the current schedule. Original forecasts are never rewritten.</p>{"".join(weeks)}</section>
<details><summary>Archived challenger diagnostic</summary><p>These are outputs from the archived July-cutoff fit (delta 0.75 with QB-depth uncertainty), kept separate from the public ratings-table fit.</p><div class="table-shell"><table><thead><tr><th>Matchup</th><th>Current-lineup home margin</th><th>Full-strength home margin</th></tr></thead><tbody>{diagnostic_rows}</tbody></table></div></details>
<section><h2>Results provenance</h2><p>Each entry is a reviewed transcription. Its digest verifies the archived CSV, not the remote source contents.</p><ul>{sources}</ul></section>
<section><h2>Staff Picks</h2><p>No editorial picks are published in this model archive. Staff Picks remain a separate human product.</p></section>
{archive_close}
</main><script>
function updateWeeklyLocks() {{
  const now = Date.now();
  let next = now + 60000;
  document.querySelectorAll('[data-weekly-cutoff]').forEach(node => {{
    const cutoff = Date.parse(node.dataset.weeklyCutoff);
    node.textContent = now >= cutoff ? 'Locked' : 'Draft';
    if (cutoff > now) next = Math.min(next, cutoff);
  }});
  if (document.querySelector('[data-weekly-cutoff]')) setTimeout(updateWeeklyLocks, Math.max(1, next - now));
}}
updateWeeklyLocks();
function openFragment(hash) {{
  const target = document.getElementById(hash.slice(1));
  if (!target) return;
  for (let node = target; node; node = node.parentElement) {{
    if (node.tagName === 'DETAILS') node.open = true;
  }}
  target.scrollIntoView();
}}
document.addEventListener('click', event => {{
  const link = event.target.closest('a[href^="#"]');
  if (link) openFragment(link.hash);
}});
window.addEventListener('hashchange', () => openFragment(location.hash));
openFragment(location.hash);
</script></body></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    parser.add_argument("--predictions", type=Path, default=PREDICTIONS_PATH)
    parser.add_argument("--attestation", type=Path, default=ATTESTATION_PATH)
    parser.add_argument("--captures", type=Path, default=CAPTURE_ROOT)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_DIR)
    parser.add_argument("--weekly", type=Path, default=WEEKLY_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    records = parser.add_mutually_exclusive_group()
    records.add_argument("--record-results", type=Path)
    records.add_argument("--record-snapshot-results", type=Path)
    records.add_argument("--record-weekly-results", type=Path)
    parser.add_argument("--source-url")
    args = parser.parse_args(argv)
    try:
        args.output = _validate_output_path(
            args.output,
            (args.lock, args.predictions, args.attestation, args.record_results,
             args.record_snapshot_results, args.record_weekly_results),
            (ARCHIVE_DIR, args.captures, args.snapshot, args.weekly),
        )
        lock = load_archive(args.lock, args.predictions, args.attestation)
        snapshot = _load_snapshot(args.snapshot)
        weekly = pgo_forecast_weekly.load_weekly(args.weekly)
        weekly_lock = {"games": weekly["games"]}
        if args.record_results or args.record_snapshot_results or args.record_weekly_results:
            if not args.source_url:
                raise ValueError("--source-url is required when recording results")
            if args.record_weekly_results:
                if not weekly["games"]:
                    raise ValueError("Cannot record results without verified weekly forecasts")
                record_results(
                    args.record_weekly_results, args.source_url,
                    args.weekly / "results", weekly_lock,
                )
            elif args.record_snapshot_results:
                if snapshot is None:
                    raise ValueError("Cannot record results without a verified snapshot")
                record_results(
                    args.record_snapshot_results, args.source_url,
                    args.snapshot / "results", snapshot["lock"],
                )
            else:
                record_results(
                    args.record_results, args.source_url, args.captures, lock,
                )
        elif args.source_url:
            raise ValueError("capture metadata requires a result-recording option")
        results, provenance = load_results(args.captures, lock)
        snapshot_results, snapshot_provenance = [], []
        if snapshot is not None:
            snapshot_results, snapshot_provenance = load_results(
                args.snapshot / "results", snapshot["lock"]
            )
        weekly_results, weekly_provenance = load_results(args.weekly / "results", weekly_lock)
        atomic_write_text(args.output, render_lab(
            lock, results, provenance, snapshot=snapshot,
            snapshot_results=snapshot_results,
            snapshot_provenance=snapshot_provenance,
            weekly=weekly if snapshot is not None else None,
            weekly_results=weekly_results,
            weekly_provenance=weekly_provenance,
        ))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Forecast Lab failed: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output.resolve()} ({len(results)} of {len(lock['games'])} results)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
