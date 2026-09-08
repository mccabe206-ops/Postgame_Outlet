"""Build the dated, research-only current availability sensitivity.

This consumes the completed current-strength fit and the separately captured
NFL report.  It never refits, ranks unknown teams, or writes a forecast lock.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pgo_challenger
import pgo_injury_source
import pgo_model


DEFAULT_RUN = ROOT / "research/pgo_current_strength/run-20260908"
EXPECTED_RUN_MANIFEST_SHA256 = "6682197b16fcc0974fef19e6c704ef238d4d2a30ba0db066e3e86a6bad35ee4a"
DEFAULT_SOURCE = ROOT / "output/pgo-current-strength-20260908"
EXPECTED_SOURCE_MANIFEST_SHA256 = "eaaf63ad755e85d4fabad05b5450dd1278b8fca8be0d04b9b9511dcb545be4ba"
DEFAULT_OUTPUT = ROOT / "research/pgo_current_strength/availability-20260908"
VARIANT = "starter_recency_roster"
COPIED_SOURCE_FILES = (
    "capture.json",
    "injury-source.json",
    "availability.csv",
    "availability-coverage.json",
    "availability-role-coverage.json",
    "report.md",
)


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _parse_time(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Scenario timestamps require timezones")
    return parsed


def _verified_manifest(directory, expected_hash):
    directory = Path(directory)
    raw = (directory / "manifest.json").read_bytes()
    if _hash(raw) != expected_hash:
        raise ValueError(f"Manifest hash differs: {directory}")
    manifest = json.loads(raw)
    for name, entry in manifest["files"].items():
        data = (directory / name).read_bytes()
        if len(data) != entry["bytes"] or _hash(data) != entry["sha256"]:
            raise ValueError(f"Manifest artifact differs: {name}")
    return manifest


def availability_adjustments(team, source_kind, roster_rows, overlay):
    """Return existing availability features or an explicit unknown state."""
    if source_kind == "no_formal_report":
        return {
            "status": "UNKNOWN_NO_FORMAL_REPORT",
            "offense_availability": None,
            "defense_availability": None,
            "matched_players": 0,
        }
    if source_kind != "formal_injury_report":
        raise ValueError(f"Unsupported current availability source for {team}")
    team_overlay = {key: value for key, value in overlay.items() if key[0] == team}
    roster = {}
    for row in roster_rows:
        if row["team"] != team or not row["gsis_id"]:
            raise ValueError(f"Invalid current role row for {team}")
        key = row["gsis_id"]
        if key in roster:
            raise ValueError(f"Duplicate current role row for {team} {key}")
        overlay_record = team_overlay.get((team, key))
        if overlay_record is None:
            raise ValueError(f"Current role row is absent from formal overlay for {team}")
        probability = float(overlay_record["availability_probability"])
        if probability != float(row["availability_probability"]):
            raise ValueError(f"Current role audit probability differs for {team}")
        if row["position"] == "QB" and probability < 1.0:
            raise ValueError("Reduced-QB availability requires the reviewed depth-aware policy")
        if probability < 1.0:
            group = pgo_challenger.ROLE_POSITION_GROUPS.get(row["position"])
            required = "defense_snap_share" if group == "defense" else "offense_snap_share"
            if row[required] is None:
                raise ValueError(f"Reduced player role share is unavailable for {team}")
        roster[key] = {
            "gsis_id": key,
            "position": row["position"],
            "probability": 1.0,
            "offense_snap_share": row["offense_snap_share"],
            "defense_snap_share": row["defense_snap_share"],
        }
    if set(team_overlay) != {(team, key) for key in roster}:
        raise ValueError(f"Current role rows do not match formal overlay for {team}")
    updated, matched = pgo_challenger.apply_availability_overlay(team, roster, team_overlay)
    if matched != set(team_overlay):
        raise ValueError(f"Current availability identities did not all match for {team}")
    offense = pgo_challenger._unavailable_share(updated.values(), "offense_snap_share")
    defense = pgo_challenger._unavailable_share(updated.values(), "defense_snap_share")
    if offense is None or defense is None:
        raise ValueError(f"Reduced player role share is unavailable for {team}")
    return {
        "status": "FORMAL_REPORT_CURRENT_SCENARIO",
        "offense_availability": -float(offense),
        "defense_availability": -float(defense),
        "matched_players": len(matched),
    }


def _preprocessor(fit):
    value = fit["preprocessor"]
    return pgo_challenger.Preprocessor(
        tuple(value["feature_names"]),
        __import__("numpy").asarray(value["medians"]),
        __import__("numpy").asarray(value["scales"]),
        tuple(value["missing_features"]),
    )


def _score(team, features, fit):
    preprocessor = _preprocessor(fit)
    row = pgo_challenger._neutral_feature_row(team, features, preprocessor)
    return float(pgo_challenger.predict(
        preprocessor.transform([row]), fit["coefficients"],
    )[0])


def _csv(rows):
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _json(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _write(path, raw):
    with Path(path).open("xb") as handle:
        handle.write(raw)


def build_scenario(run=DEFAULT_RUN, source=DEFAULT_SOURCE, output=DEFAULT_OUTPUT):
    run, source, output = Path(run), Path(source), Path(output)
    if output.exists():
        raise ValueError("Availability scenario output directory must be new")
    run_manifest = _verified_manifest(run, EXPECTED_RUN_MANIFEST_SHA256)
    source_manifest = _verified_manifest(source, EXPECTED_SOURCE_MANIFEST_SHA256)
    capture = json.loads((source / "capture.json").read_bytes())
    injury = pgo_injury_source.load_snapshot(source / "injury-source.json")
    if injury["source_as_of"] != capture["captured_at"]:
        raise ValueError("Normalized injury time differs from capture time")
    overlay, overlay_receipt = pgo_challenger.load_availability_overlay(
        source / "availability.csv", injury["source_as_of"],
        coverage_path=source / "availability-coverage.json",
    )
    role_audit = json.loads((source / "availability-role-coverage.json").read_bytes())
    if role_audit["overlay_receipt"]["sha256"] != overlay_receipt["sha256"]:
        raise ValueError("ACT role audit belongs to another overlay")

    run_receipt = json.loads((run / "run-receipt.json").read_bytes())
    if _parse_time(injury["source_as_of"]) <= _parse_time(run_receipt["snapshot_generated_at"]):
        raise ValueError("Availability capture is not distinct from the September baseline")
    folds = json.loads((run / "fold-fits.json").read_bytes())
    finals = [row for row in folds[VARIANT] if row.get("fit") == "final_2013_2025"]
    if len(finals) != 1:
        raise ValueError("Current-strength final fit is missing or ambiguous")
    fit = finals[0]
    details = json.loads((run / "rating-details.json").read_bytes())
    full = {row["team"]: row for row in details if row["variant"] == VARIANT}
    if set(full) != set(pgo_model.CURRENT_TEAMS):
        raise ValueError("Current-strength full features must cover all 32 teams")
    sources = {row["team"]: row for row in injury["team_sources"]}
    roles = {team: [] for team in pgo_model.CURRENT_TEAMS}
    for row in role_audit["players"]:
        roles[row["team"]].append(row)

    records = []
    for team in pgo_model.CURRENT_TEAMS:
        adjustment = availability_adjustments(
            team, sources[team]["source_kind"], roles[team], overlay,
        )
        record = {
            "team": team,
            "source_kind": sources[team]["source_kind"],
            "status": adjustment["status"],
            "formal_report_players": adjustment["matched_players"],
            "offense_availability": adjustment["offense_availability"],
            "defense_availability": adjustment["defense_availability"],
            "full_strength_centered_rating": None,
            "current_scenario_centered_rating": None,
            "model_output_delta": None,
        }
        if adjustment["status"] == "FORMAL_REPORT_CURRENT_SCENARIO":
            features = dict(full[team]["features"])
            baseline = _score(team, features, fit)
            features["offense_availability"] = adjustment["offense_availability"]
            features["defense_availability"] = adjustment["defense_availability"]
            candidate = _score(team, features, fit)
            if not all(math.isfinite(value) for value in (baseline, candidate)):
                raise ValueError(f"Nonfinite availability sensitivity for {team}")
            delta = candidate - baseline
            centered = float(full[team]["rating"])
            record.update(
                full_strength_centered_rating=centered,
                current_scenario_centered_rating=centered + delta,
                model_output_delta=delta,
            )
        records.append(record)
    if sum(row["model_output_delta"] is not None for row in records) != 2:
        raise ValueError("Only formally reported teams may receive model deltas")

    scenario = {
        "schema_version": 1,
        "identity": "pgo-current-availability-20260908",
        "status": "EXPERIMENTAL_RESEARCH_ONLY",
        "capture_as_of": injury["source_as_of"],
        "baseline_snapshot_generated_at": run_receipt["snapshot_generated_at"],
        "fit_variant": VARIANT,
        "fit_run_manifest_sha256": EXPECTED_RUN_MANIFEST_SHA256,
        "source_manifest_sha256": EXPECTED_SOURCE_MANIFEST_SHA256,
        "interpretation": "Model-scale artifact delta; not a calibrated spread or confidence interval.",
        "unknown_policy": "No formal report is unknown, not healthy; model delta remains unavailable.",
        "qb_policy": "Reduced-QB rows fail closed pending the reviewed depth-aware policy.",
        "teams": records,
    }
    report_rows = [row for row in records if row["model_output_delta"] is not None]
    report = [
        "# Current availability sensitivity — 2026-09-08",
        "",
        "Status: EXPERIMENTAL research only. No forecast or weekly lock was issued.",
        "",
        f"The official report capture at `{injury['source_as_of']}` is later than the frozen "
        f"September baseline at `{run_receipt['snapshot_generated_at']}` and is a distinct scenario.",
        "Thirty teams had no formal report and remain unknown with no model delta.",
        "",
        "| Team | Offense availability | Defense availability | Model output delta |",
        "|---|---:|---:|---:|",
        *[
            f"| {row['team']} | {row['offense_availability']:.6f} | "
            f"{row['defense_availability']:.6f} | {row['model_output_delta']:+.6f} |"
            for row in report_rows
        ],
        "",
        "The delta is on the fitted model's artifact scale. It is not a calibrated spread,",
        "confidence interval, ranking, or promotion result. The frozen full-strength scenario remains unchanged.",
        "",
    ]
    artifacts = {
        name: (source / name).read_bytes() for name in COPIED_SOURCE_FILES
    }
    artifacts.update({
        "availability-scenario.json": _json(scenario),
        "availability-scenario.csv": _csv(records),
        "scenario-report.md": "\n".join(report).encode("utf-8"),
    })
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in artifacts.items():
        _write(output / name, raw)
    manifest = {
        "schema_version": 1,
        "identity": scenario["identity"],
        "source_url": capture["url"],
        "raw_source_sha256": capture["sha256"],
        "raw_source_bytes": capture["bytes"],
        "raw_source_retention": "Exact NFL HTML remains in the local output capture; it is not copied here.",
        "fit_run_manifest_sha256": EXPECTED_RUN_MANIFEST_SHA256,
        "generator_sha256": _hash(Path(__file__).read_bytes()),
        "files": {
            name: {"sha256": _hash(raw), "bytes": len(raw)}
            for name, raw in artifacts.items()
        },
    }
    _write(output / "manifest.json", _json(manifest))
    return scenario


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = build_scenario(args.run, args.source, args.output)
    print(json.dumps({"teams": len(result["teams"]), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
