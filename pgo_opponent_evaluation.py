"""Frozen, retrospective evaluation for the opponent-EPA research charter.

This module is deliberately separate from forecast production.  It reads the
locked July/September evidence, fits the three chartered arms, and writes a new
research directory exactly once.  It never updates a public lock or snapshot.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import io
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import pgo_challenger as challenger
import pgo_forecast_snapshot
import pgo_sources


ROOT = Path(__file__).resolve().parent
CHARTER_PATH = ROOT / "research/pgo_opponent_adjustment/charter.md"
EXPECTED_CHARTER_SHA256 = "22e7c00e9bc5b1dc96664fe445c0954699d58b700acb23a98618e96440e2a578"
RECOVERY_DIR = ROOT / "output/pgo-snapshot-review-20260907/public-fit-recovery"
RECOVERED_FIT_PATH = RECOVERY_DIR / "recovered-fit.json"
EXPECTED_RECOVERED_FIT_SHA256 = "1b960834b33cdda08bf69b792fa24ee2bb57ff738b1153aa1c1d833914af2036"
SOURCE_LOCK_PATH = ROOT / "research/pgo_v1/sources.lock.json"
EXPECTED_SOURCE_LOCK_SHA256 = "3a7673ac4617d57954cb56954f2216226a358c7b187b1e3ce62994a6f2b3fd29"
CACHE_DIR = Path("D:/Postgame_Outlet-pgo-model/.cache/pgo_v1")
SNAPSHOT_DIR = ROOT / "docs/evidence/forecast-lab-2026/september-07"
EXPECTED_SNAPSHOT_MANIFEST_SHA256 = "43bdeee73a2d3301eedbcecc7d291dc9ebe68cf196860e7217326570e4fe2f42"
DEFAULT_OUTPUT = ROOT / "research/pgo_opponent_adjustment/run-20260907"

ARMS = ("raw", "team_epa", "team_qb_epa")
EVALUATION_SEASONS = tuple(range(2018, 2026))
HALF_LIFE_GAMES = 4
ALPHA = 100.0
DELTA = 1.0
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20260907
CODE_PATHS = (
    "pgo_opponent_evaluation.py",
    "pgo_opponent_adjustment.py",
    "tests/test_pgo_opponent_evaluation.py",
    "tests/test_pgo_opponent_adjustment.py",
    "pgo_challenger.py",
    "pgo_sources.py",
    "pgo_forecast_snapshot.py",
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_protected(expected: dict[str, str]) -> dict[str, str]:
    for name, digest in expected.items():
        path = Path(name)
        try:
            actual = sha256(path.read_bytes())
        except OSError as error:
            raise ValueError(f"Protected artifact is unavailable: {path}") from error
        if actual != digest:
            raise ValueError(f"Protected artifact changed: {path}")
    return dict(expected)


def _row_identity(row):
    return (
        row.game_id,
        int(row.season),
        int(row.week),
        str(row.kickoff),
        float(row.actual_margin),
    )


def validate_matching_arms(arms) -> None:
    if set(arms) != set(ARMS):
        raise ValueError("Evaluation arms do not match the charter")
    reference = [_row_identity(row) for row in arms[ARMS[0]]]
    if len({row[0] for row in reference}) != len(reference):
        raise ValueError("Evaluation arm identity contains duplicate games")
    for arm in ARMS[1:]:
        current = [_row_identity(row) for row in arms[arm]]
        if current != reference:
            raise ValueError(f"Evaluation arm identity or target differs: {arm}")


def expanding_folds(rows, seasons=EVALUATION_SEASONS):
    for season in seasons:
        training = [row for row in rows if row.season < season]
        validation = [row for row in rows if row.season == season]
        if not training or not validation:
            raise ValueError(f"Expanding fold {season} is empty")
        if max(row.season for row in training) >= season:
            raise ValueError(f"Expanding fold {season} crosses its boundary")
        yield season, training, validation


def _metric_summary(rows, prediction_key):
    if not rows:
        raise ValueError("Metric rows must not be empty")
    try:
        actual = np.asarray([float(row["actual_margin"]) for row in rows])
        predicted = np.asarray([float(row[prediction_key]) for row in rows])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Metric rows are invalid") from error
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Metric values must be finite")
    errors = actual - predicted
    decisions = (actual != 0.0) & (predicted != 0.0)
    correct = int(np.sum((actual[decisions] > 0.0) == (predicted[decisions] > 0.0)))
    denominator = int(np.sum(decisions))
    return {
        "count": len(rows),
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors ** 2))),
        "winner": {
            "correct": correct,
            "denominator": denominator,
            "accuracy": correct / denominator if denominator else None,
            "actual_ties": int(np.sum(actual == 0.0)),
            "predicted_ties": int(np.sum(predicted == 0.0)),
        },
    }


def metric_views(rows, prediction_key):
    seasons = sorted({int(row["season"]) for row in rows})
    return {
        "overall": _metric_summary(rows, prediction_key),
        "seasons": [
            {"season": season, **_metric_summary(
                [row for row in rows if int(row["season"]) == season], prediction_key
            )}
            for season in seasons
        ],
        "weeks_1_4": _metric_summary(
            [row for row in rows if 1 <= int(row["week"]) <= 4], prediction_key
        ),
        "weeks_5_18": _metric_summary(
            [row for row in rows if 5 <= int(row["week"]) <= 18], prediction_key
        ),
    }


def season_block_bootstrap(
    rows, candidate_key, baseline_key, *, samples=BOOTSTRAP_SAMPLES, seed=BOOTSTRAP_SEED,
):
    if not isinstance(samples, int) or samples <= 0:
        raise ValueError("samples must be a positive integer")
    blocks = defaultdict(list)
    for row in rows:
        try:
            actual = float(row["actual_margin"])
            candidate = float(row[candidate_key])
            baseline = float(row[baseline_key])
            season = int(row["season"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Bootstrap rows are invalid") from error
        if not all(math.isfinite(value) for value in (actual, candidate, baseline)):
            raise ValueError("Bootstrap values must be finite")
        blocks[season].append(abs(actual - baseline) - abs(actual - candidate))
    if not blocks:
        raise ValueError("Bootstrap rows must not be empty")
    arrays = [np.asarray(blocks[key], dtype=float) for key in sorted(blocks)]
    sums = np.asarray([values.sum() for values in arrays])
    counts = np.asarray([len(values) for values in arrays])
    draws = np.random.default_rng(seed).integers(0, len(arrays), size=(samples, len(arrays)))
    distribution = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    return {
        "mean": float(sums.sum() / counts.sum()),
        "lower": float(np.percentile(distribution, 2.5)),
        "upper": float(np.percentile(distribution, 97.5)),
        "blocks": len(arrays),
        "samples": samples,
        "seed": seed,
    }


def _fit(rows):
    feature_names = tuple(sorted(rows[0].features))
    if any(tuple(sorted(row.features)) != feature_names for row in rows):
        raise ValueError("Feature row shapes do not align")
    preprocessor = challenger.fit_preprocessor(rows, feature_names)
    coefficients = challenger.fit_huber_ridge(
        preprocessor.transform(rows),
        np.asarray([row.actual_margin for row in rows], dtype=float),
        ALPHA,
        DELTA,
    )
    return preprocessor, coefficients


def _fit_receipt(preprocessor, coefficients, training, validation=()):
    return {
        "parameters": {
            "half_life_games": HALF_LIFE_GAMES,
            "alpha": ALPHA,
            "delta": DELTA,
        },
        "training": {
            "count": len(training),
            "season_min": min(row.season for row in training),
            "season_max": max(row.season for row in training),
            "game_ids": [row.game_id for row in training],
        },
        "validation": {
            "count": len(validation),
            "game_ids": [row.game_id for row in validation],
        },
        "preprocessor": {
            "feature_names": list(preprocessor.feature_names),
            "medians": preprocessor.medians.tolist(),
            "scales": preprocessor.scales.tolist(),
            "missing_features": list(preprocessor.missing_features),
        },
        "coefficients": coefficients.tolist(),
    }


def _predict_rows(rows, preprocessor, coefficients):
    return challenger.predict(preprocessor.transform(rows), coefficients).tolist()


def _frozen_v0_predictions(paths):
    """Reproduce the fixed v0 baseline without invoking parameter selection."""
    schedule = list(pgo_sources.open_csv(paths[("schedule_results", None)]))
    if not schedule:
        raise ValueError("Schedule source must not be empty")
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=tuple(schedule[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(schedule)
    games = challenger.pgo_model.parse_games(text.getvalue())
    predictions, _ = challenger.pgo_model.walk_forward(games, challenger.V0_PARAMETERS)
    return [row for row in predictions if row.season in EVALUATION_SEASONS]


def _exact_raw_fit(preprocessor, coefficients, rows, frozen):
    expected = frozen["fit"]
    checks = {
        "parameters": expected["parameters"] == {
            "half_life_games": HALF_LIFE_GAMES, "alpha": ALPHA, "delta": DELTA,
        },
        "training_count": len(rows) == expected["training"]["count"],
        "training_seasons": sorted({row.season for row in rows}) == expected["training"]["seasons"],
        "feature_names": list(preprocessor.feature_names) == expected["preprocessor"]["feature_names"],
        "missing_features": list(preprocessor.missing_features) == expected["preprocessor"]["missing_features"],
        "medians_exact": np.array_equal(preprocessor.medians, np.asarray(expected["preprocessor"]["medians"])),
        "scales_exact": np.array_equal(preprocessor.scales, np.asarray(expected["preprocessor"]["scales"])),
        "coefficients_exact": np.array_equal(coefficients, np.asarray(expected["coefficients"])),
    }
    checks["passed"] = all(checks.values())
    if not checks["passed"]:
        failed = ", ".join(name for name, value in checks.items() if value is False)
        raise ValueError(f"Raw final fit does not reproduce frozen public fit: {failed}")
    return checks


def _tracked_hashes():
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True,
    )
    names = [name for name in result.stdout.decode("utf-8").split("\0") if name]
    return {name: sha256((ROOT / name).read_bytes()) for name in names}


def _source_inventory(recovered):
    inventory = {}
    for entry in recovered["original_raw_sources"]:
        path = Path(entry["path"])
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or sha256(raw) != entry["sha256"]:
            raise ValueError(f"Recovered raw source changed: {entry['source']}")
        inventory[entry["source"]] = {
            "path": str(path), "sha256": entry["sha256"], "bytes": entry["bytes"],
        }
    return inventory


def loaded_source_inventory(paths):
    inventory = {}
    for (name, season), path in sorted(paths.items()):
        raw = Path(path).read_bytes()
        label = f"{name}:{season}" if season is not None else name
        inventory[label] = {
            "path": str(Path(path).resolve()),
            "sha256": sha256(raw),
            "bytes": len(raw),
        }
    return inventory


def verify_loaded_sources(expected, paths):
    current = loaded_source_inventory(paths)
    if current != expected:
        raise ValueError("Loaded source cache changed during the experiment")
    return current


def _code_hashes():
    return {name: sha256((ROOT / name).read_bytes()) for name in CODE_PATHS}


def _opponent_coverage(context):
    weeks = context.get("opponent_epa", {}).get("weeks", ())
    if not weeks:
        return {"week_boundaries": 0, "first": None, "last": None,
                "fallback_team_features": 0, "weeks_with_fallback": 0,
                "maximum_fallback_team_features": 0}
    fallbacks = [int(row["fallback_team_features"]) for row in weeks]
    return {
        "week_boundaries": len(weeks),
        "first": {key: weeks[0][key] for key in ("season", "week")},
        "last": {key: weeks[-1][key] for key in ("season", "week")},
        "fallback_team_features": sum(fallbacks),
        "weeks_with_fallback": sum(value > 0 for value in fallbacks),
        "maximum_fallback_team_features": max(fallbacks),
        "by_season": [
            {
                "season": season,
                "week_boundaries": sum(row["season"] == season for row in weeks),
                "fallback_team_features": sum(
                    row["fallback_team_features"] for row in weeks if row["season"] == season
                ),
            }
            for season in sorted({row["season"] for row in weeks})
        ],
    }


def _rating_variants(snapshot, contexts, final_fits, adjustment):
    variants, details = {}, []
    team_metadata = {row["team"]: row for row in snapshot["teams"]}
    for arm in ARMS:
        preprocessor, coefficients = final_fits[arm]
        labels = list(preprocessor.feature_names) + [
            f"{name}_missing" for name in preprocessor.missing_features
        ]
        for apply_offseason in (False, True):
            key = f"{arm}__offseason_{'0.5' if apply_offseason else 'unchanged'}"
            features = adjustment.snapshot_features(
                snapshot, contexts[arm], arm, apply_offseason=apply_offseason,
            )
            teams = sorted(features)
            rows = [challenger._neutral_feature_row(team, features[team], preprocessor) for team in teams]
            transformed = preprocessor.transform(rows)
            scores = challenger.predict(transformed, coefficients)
            ratings = scores - scores.mean()
            centered_x = transformed - transformed.mean(axis=0)
            contributions = centered_x * coefficients[1:]
            ranked = sorted(range(len(teams)), key=lambda index: (-ratings[index], teams[index]))
            ranks = {teams[index]: rank for rank, index in enumerate(ranked, 1)}
            variants[key] = {
                team: {"rating": float(ratings[index]), "rank": ranks[team]}
                for index, team in enumerate(teams)
            }
            for index, team in enumerate(teams):
                contribution_map = {
                    name: float(value) for name, value in zip(labels, contributions[index])
                }
                if not math.isclose(sum(contribution_map.values()), ratings[index], abs_tol=1e-9):
                    raise ValueError(f"Centered contributions do not reproduce {team} {key}")
                metadata = team_metadata[team]
                details.append({
                    "variant": key,
                    "team": team,
                    "rank": ranks[team],
                    "rating": float(ratings[index]),
                    "qb_name": metadata["qb_name"],
                    "qb_gsis_id": metadata["qb_gsis_id"],
                    "features": features[team],
                    "standardized_features": {
                        name: float(value) for name, value in zip(labels, transformed[index])
                    },
                    "centered_contributions": contribution_map,
                })
    rating_rows = []
    for team in sorted(team_metadata):
        row = {
            "team": team,
            "qb_name": team_metadata[team]["qb_name"],
            "qb_gsis_id": team_metadata[team]["qb_gsis_id"],
        }
        for key in variants:
            row[f"{key}_rank"] = variants[key][team]["rank"]
            row[f"{key}_rating"] = variants[key][team]["rating"]
        rating_rows.append(row)
    return rating_rows, details


def _screening(metrics, bootstraps):
    raw = metrics["raw"]
    output = {}
    raw_seasons = {row["season"]: row for row in raw["seasons"]}
    for candidate in ("team_epa", "team_qb_epa"):
        current = metrics[candidate]
        season_wins = sum(
            row["mae"] < raw_seasons[row["season"]]["mae"] for row in current["seasons"]
        )
        checks = {
            "pooled_mae_improves": current["overall"]["mae"] < raw["overall"]["mae"],
            "season_block_interval_above_zero": bootstraps[candidate]["vs_raw"]["lower"] > 0.0,
            "at_least_five_seasons_improve": season_wins >= 5,
            "weeks_1_4_not_worse": current["weeks_1_4"]["mae"] <= raw["weeks_1_4"]["mae"],
        }
        output[candidate] = {
            "season_mae_wins": season_wins,
            "checks": checks,
            "merits_further_prospective_study": all(checks.values()),
        }
    return output


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _csv_bytes(rows):
    if not rows:
        raise ValueError("CSV rows must not be empty")
    from io import StringIO
    text = StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return text.getvalue().encode("utf-8")


def _write_exclusive(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()


def _report(metrics, screening, raw_check):
    lines = [
        "# Opponent EPA retrospective experiment",
        "",
        "Status: exploratory retrospective research; no promotion or forecast replacement.",
        "Leakage verdict: **REVIEW REQUIRED** for historical publication vintage.",
        "",
        f"The raw final fit reproduced the frozen public fit exactly: **{raw_check['passed']}**.",
        "",
        "## Matched expanding-season results",
        "",
        "| Arm | Games | MAE | RMSE | Winner accuracy |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in ("constant", "pgo_v0", *ARMS):
        overall = metrics[arm]["overall"]
        winner = overall["winner"]
        accuracy = "unavailable" if winner["accuracy"] is None else f"{winner['accuracy']:.3f}"
        lines.append(
            f"| {arm} | {overall['count']} | {overall['mae']:.4f} | "
            f"{overall['rmse']:.4f} | {accuracy} ({winner['correct']}/{winner['denominator']}) |"
        )
    lines.extend(["", "## Predeclared screening", ""])
    for arm, result in screening.items():
        verdict = "PASS" if result["merits_further_prospective_study"] else "HOLD"
        lines.append(f"- `{arm}`: **{verdict}**; {result['season_mae_wins']}/8 seasons improve.")
    lines.extend([
        "",
        "The intervals use only eight season blocks and all evaluation seasons were previously inspected.",
        "The frozen sources are final/backfilled historical releases without complete row-publication receipts.",
        "The all-team ratings are descriptive centered model-scale sensitivities, not calibrated neutral-point forecasts.",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


def run_experiment(
    output=DEFAULT_OUTPUT, *, cache_dir=CACHE_DIR, snapshot_dir=SNAPSHOT_DIR,
    recovery_path=RECOVERED_FIT_PATH,
):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Research output directory must be new")
    started_at = datetime.now(timezone.utc).isoformat()
    if sha256(CHARTER_PATH.read_bytes()) != EXPECTED_CHARTER_SHA256:
        raise ValueError("Research charter hash differs")
    if sha256(Path(recovery_path).read_bytes()) != EXPECTED_RECOVERED_FIT_SHA256:
        raise ValueError("Recovered fit hash differs")
    if sha256(SOURCE_LOCK_PATH.read_bytes()) != EXPECTED_SOURCE_LOCK_SHA256:
        raise ValueError("Locked source manifest hash differs")
    if sha256((Path(snapshot_dir) / "manifest.json").read_bytes()) != EXPECTED_SNAPSHOT_MANIFEST_SHA256:
        raise ValueError("September snapshot manifest hash differs")

    recovered = json.loads(Path(recovery_path).read_bytes())
    protected = dict(recovered["original_artifacts_sha256"])
    protected.update({
        str(CHARTER_PATH): EXPECTED_CHARTER_SHA256,
        str(Path(recovery_path)): EXPECTED_RECOVERED_FIT_SHA256,
        str(Path(snapshot_dir) / "manifest.json"): EXPECTED_SNAPSHOT_MANIFEST_SHA256,
    })
    verify_protected(protected)
    tracked_before = _tracked_hashes()
    source_inventory = _source_inventory(recovered)
    code_before = _code_hashes()
    run_start = {
        "schema_version": 1,
        "identity": "pgo-opponent-epa-retrospective-20260907",
        "status": "STARTED_INCOMPLETE_UNTIL_MANIFEST_EXISTS",
        "started_at": started_at,
        "charter_sha256": EXPECTED_CHARTER_SHA256,
        "recovered_fit_sha256": EXPECTED_RECOVERED_FIT_SHA256,
        "snapshot_manifest_sha256": EXPECTED_SNAPSHOT_MANIFEST_SHA256,
        "code_sha256": code_before,
    }
    run_start_raw = _json_bytes(run_start)
    output.mkdir(parents=True, exist_ok=False)
    _write_exclusive(output / "run-start.json", run_start_raw)

    all_paths = pgo_sources.load_locked_sources(SOURCE_LOCK_PATH, cache_dir)
    loaded_sources_before = loaded_source_inventory(all_paths)
    paths = {key: path for key, path in all_paths.items() if key != ("current_roster", 2026)}
    if len(all_paths) != 67 or len(paths) != 66 or ("current_roster", 2026) in paths:
        raise ValueError("Historical walker source selection differs from the charter")
    adjustment = importlib.import_module("pgo_opponent_adjustment")

    arms, contexts, input_receipts = {}, {}, {}
    for arm in ARMS:
        print(f"building arm {arm}", flush=True)
        rows, context, inputs = adjustment.build_rows(paths, arm)
        print(f"built arm {arm}: {len(rows)} rows", flush=True)
        arms[arm] = rows
        contexts[arm] = {key: context[key] for key in
                         ("season", "colliding_gsis", "opponent_epa") if key in context}
        input_receipts[arm] = {
            "rows": len(rows),
            "colliding_gsis": sorted(context.get("colliding_gsis", ())),
            "opponent_history": _opponent_coverage(context),
            "loaded_input_keys": sorted(str(key) for key in inputs),
        }
        del context
    validate_matching_arms(arms)

    incumbent = challenger._unique_predictions(
        _frozen_v0_predictions(paths), "pgo_v0",
    )
    matched = {
        row.game_id: {
            "game_id": row.game_id,
            "season": row.season,
            "week": row.week,
            "kickoff": row.kickoff,
            "actual_margin": row.actual_margin,
        }
        for row in arms["raw"] if row.season in EVALUATION_SEASONS
    }
    if set(matched) != set(incumbent):
        raise ValueError("PGO v0 and candidate evaluation game IDs differ")
    for game_id, prediction in incumbent.items():
        row = matched[game_id]
        if prediction.season != row["season"] or prediction.actual != row["actual_margin"]:
            raise ValueError("PGO v0 identity or target differs")
        row["pgo_v0"] = prediction.predicted

    fold_fits = {arm: [] for arm in ARMS}
    for arm in ARMS:
        for season, training, validation in expanding_folds(arms[arm]):
            print(f"fitting {arm} validation season {season}", flush=True)
            preprocessor, coefficients = _fit(training)
            predictions = _predict_rows(validation, preprocessor, coefficients)
            constant = float(np.mean([row.actual_margin for row in training]))
            for row, prediction in zip(validation, predictions):
                matched[row.game_id][arm] = prediction
                if "constant" in matched[row.game_id] and matched[row.game_id]["constant"] != constant:
                    raise ValueError("Fold constant differs across matched arms")
                matched[row.game_id]["constant"] = constant
            receipt = _fit_receipt(preprocessor, coefficients, training, validation)
            receipt["evaluation_season"] = season
            receipt["constant_training_mean"] = constant
            fold_fits[arm].append(receipt)

    matched_rows = sorted(matched.values(), key=lambda row: (row["season"], row["week"], row["kickoff"], row["game_id"]))
    metrics = {
        name: metric_views(matched_rows, name)
        for name in ("constant", "pgo_v0", *ARMS)
    }
    bootstraps = {}
    for arm in ("team_epa", "team_qb_epa"):
        sensitivity_rows = [
            {**row, "pgo_v0_prediction": row["raw"], "challenger_prediction": row[arm]}
            for row in matched_rows
        ]
        bootstraps[arm] = {
            "vs_raw": season_block_bootstrap(matched_rows, arm, "raw"),
            "vs_pgo_v0": season_block_bootstrap(matched_rows, arm, "pgo_v0"),
            "season_week_vs_raw": challenger.paired_block_bootstrap(
                sensitivity_rows, samples=BOOTSTRAP_SAMPLES, seed=BOOTSTRAP_SEED,
            ),
        }
    screening = _screening(metrics, bootstraps)

    final_fits = {}
    for arm in ARMS:
        print(f"fitting {arm} final 2013-2025", flush=True)
        preprocessor, coefficients = _fit(arms[arm])
        final_fits[arm] = preprocessor, coefficients
        fold_fits[arm].append({
            "fit": "final_2013_2025",
            **_fit_receipt(preprocessor, coefficients, arms[arm]),
        })
    snapshot = pgo_forecast_snapshot.load_snapshot(snapshot_dir)
    raw_check = _exact_raw_fit(*final_fits["raw"], arms["raw"], snapshot)
    rating_rows, rating_details = _rating_variants(snapshot, contexts, final_fits, adjustment)

    verify_protected(protected)
    source_inventory_after = _source_inventory(recovered)
    if source_inventory_after != source_inventory:
        raise ValueError("Raw source inventory changed during the experiment")
    verify_loaded_sources(
        loaded_sources_before,
        pgo_sources.load_locked_sources(SOURCE_LOCK_PATH, cache_dir),
    )
    code_after = _code_hashes()
    if code_after != code_before:
        raise ValueError("Research code changed during the experiment")
    tracked_after = _tracked_hashes()
    if tracked_after != tracked_before:
        raise ValueError("Tracked repository files changed during the experiment")

    metrics_artifact = {
        "metrics": metrics,
        "paired_bootstrap": bootstraps,
        "screening": screening,
        "winner_convention": "Actual ties and exact-zero predicted ties are excluded from the winner denominator.",
        "leakage_verdict": "REVIEW REQUIRED",
    }
    receipt = {
        "schema_version": 1,
        "identity": "pgo-opponent-epa-retrospective-20260907",
        "status": "EXPLORATORY_RETROSPECTIVE_RESEARCH",
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "charter_sha256": EXPECTED_CHARTER_SHA256,
        "parameters": {"half_life_games": HALF_LIFE_GAMES, "alpha": ALPHA, "delta": DELTA},
        "arms": list(ARMS),
        "evaluation_seasons": list(EVALUATION_SEASONS),
        "source_inventory": source_inventory,
        "loaded_source_inventory_before_after": loaded_sources_before,
        "source_lock": {"path": str(SOURCE_LOCK_PATH), "sha256": EXPECTED_SOURCE_LOCK_SHA256},
        "snapshot_manifest_sha256": EXPECTED_SNAPSHOT_MANIFEST_SHA256,
        "protected_artifacts_before_after": protected,
        "tracked_files_before_after": tracked_before,
        "code_sha256_before_after": code_before,
        "arm_inputs": input_receipts,
        "raw_final_fit_reproduction": raw_check,
        "limits": [
            "Historical seasonal sources are final/backfilled releases without complete row-publication receipts.",
            "The operator-declared frozen_at time does not prove original acquisition or public availability.",
            "The experiment has no untouched historical holdout and does not authorize forecast replacement.",
        ],
    }
    artifacts = {
        "run-start.json": run_start_raw,
        "matched-predictions.csv": _csv_bytes(matched_rows),
        "fold-fits.json": _json_bytes(fold_fits),
        "metrics.json": _json_bytes(metrics_artifact),
        "ratings.csv": _csv_bytes(rating_rows),
        "rating-details.json": _json_bytes(rating_details),
        "run-receipt.json": _json_bytes(receipt),
        "report.md": _report(metrics, screening, raw_check),
    }
    for name, raw in artifacts.items():
        if name == "run-start.json":
            continue
        _write_exclusive(output / name, raw)
    manifest = {
        "schema_version": 1,
        "identity": receipt["identity"],
        "files": {
            name: {"sha256": sha256(raw), "bytes": len(raw)}
            for name, raw in artifacts.items()
        },
    }
    _write_exclusive(output / "manifest.json", _json_bytes(manifest))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_DIR)
    parser.add_argument("--recovered-fit", type=Path, default=RECOVERED_FIT_PATH)
    args = parser.parse_args(argv)
    receipt = run_experiment(
        args.output, cache_dir=args.cache_dir, snapshot_dir=args.snapshot,
        recovery_path=args.recovered_fit,
    )
    print(json.dumps({"status": receipt["status"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
