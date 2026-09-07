#!/usr/bin/env python3
"""Render the frozen 2026 PGO Forecast Lab without fetching or grading."""

import argparse
import csv
from datetime import UTC, datetime
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

import generate_site
import pgo_prospective
from release_ratings import atomic_write_text


HERE = Path(__file__).resolve().parent
ARCHIVE_DIR = HERE / "docs" / "evidence" / "forecast-lab-2026"
LOCK_PATH = ARCHIVE_DIR / "prospective_lock.json"
PREDICTIONS_PATH = ARCHIVE_DIR / "prospective_predictions.csv"
ATTESTATION_PATH = HERE / "research" / "pgo_stability_blend" / "prospective_attestation.json"
CAPTURE_ROOT = ARCHIVE_DIR / "results"
OUTPUT_PATH = HERE / "docs" / "forecast-lab.html"
ATTESTATION_COMMIT = "8aae9438d251c645509d3df15a31bb86d50059b9"
ATTESTED_AT = "2026-08-26T16:07:24-04:00"
EXPECTED_ATTESTATION_SHA256 = "b89fe9c50f6c9d351aecc1820c573625ef11dd17bca1650ce3327abc8e3fadcd"
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


def render_lab(lock, results, provenance):
    """Render a standalone, escaped, no-fetch Forecast Lab page."""
    css = _shared_css()
    font_links = _shared_font_links()
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
    recorded = len(results)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PGO Forecast Lab</title>{font_links}<style>{css}
.lab-wrap{{max-width:1180px;margin:0 auto;padding:24px 18px 60px}}.lab-hero{{padding:26px;border:1px solid var(--border);border-radius:14px;background:var(--panel)}}
.status{{display:inline-block;padding:6px 10px;border:1px solid var(--orange);border-radius:999px;font-weight:800}}.metric-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:16px 0}}.metric{{padding:14px;border:1px solid var(--border);border-radius:10px;background:var(--panel)}}.metric h3{{margin-top:0}}.forecast-week{{margin:12px 0;border:1px solid var(--border);border-radius:10px;padding:12px}}.forecast-week summary{{cursor:pointer;font-weight:800}}.forecast-week summary span{{color:var(--mut);font-weight:500}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap}}th:first-child{{text-align:left}}.notice{{padding:14px;border-left:4px solid var(--orange);background:var(--panel)}}code{{overflow-wrap:anywhere}}
</style></head><body><main class="lab-wrap">
<section class="lab-hero"><div class="status">Experimental &middot; frozen archive</div>
<h1>PGO Forecast Lab</h1><h2>Can PGO predict football?</h2>
<p>This page tracks one frozen 2026 experiment. Each forecast is an estimated scoring margin: positive favors the home team; negative favors the away team.</p>
<p><strong>{recorded} of {len(lock["games"])} finalized results recorded.</strong> Interim tracking &mdash; not a validation result.</p>
<p><a href="index.html">Back to McCabe Ratings</a></p></section>
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
</main></body></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    parser.add_argument("--predictions", type=Path, default=PREDICTIONS_PATH)
    parser.add_argument("--attestation", type=Path, default=ATTESTATION_PATH)
    parser.add_argument("--captures", type=Path, default=CAPTURE_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--record-results", type=Path)
    parser.add_argument("--source-url")
    args = parser.parse_args(argv)
    try:
        args.output = _validate_output_path(
            args.output,
            (args.lock, args.predictions, args.attestation, args.record_results),
            (ARCHIVE_DIR, args.captures),
        )
        lock = load_archive(args.lock, args.predictions, args.attestation)
        if args.record_results:
            if not args.source_url:
                raise ValueError("--source-url is required with --record-results")
            record_results(
                args.record_results, args.source_url, args.captures, lock,
            )
        elif args.source_url:
            raise ValueError("capture metadata requires --record-results")
        results, provenance = load_results(args.captures, lock)
        atomic_write_text(args.output, render_lab(lock, results, provenance))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Forecast Lab failed: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output.resolve()} ({len(results)} of {len(lock['games'])} results)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
