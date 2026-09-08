"""Research-only non-QB skill efficiency features for PGO.

The hook adds four predeclared roster features to existing team views.  It does
not fit a model, alter availability, or claim offensive-line/defensive quality.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from pathlib import Path

import pgo_sources


ROOT = Path(__file__).resolve().parent
CHARTER_PATH = ROOT / "research/pgo_current_strength/charter.md"
EXPECTED_CHARTER_SHA256 = "edf1328d2dc1a7d047f75d40cffa6ba3eb1d4e0a2b5858e8de5ef0b74aafa157"
SEASON_WEIGHTS = (1.0, 0.5, 0.25)
FEATURE_NAMES = (
    "quality_wr_receiving",
    "quality_te_receiving",
    "quality_rb_receiving",
    "quality_rb_rushing",
)
PRIOR_OPPORTUNITIES = {
    "quality_wr_receiving": 50.0,
    "quality_te_receiving": 50.0,
    "quality_rb_receiving": 30.0,
    "quality_rb_rushing": 75.0,
}
FEATURE_SPECS = {
    "quality_wr_receiving": (frozenset(("WR",)), "receiving_epa", "targets"),
    "quality_te_receiving": (frozenset(("TE",)), "receiving_epa", "targets"),
    "quality_rb_receiving": (frozenset(("RB", "FB")), "receiving_epa", "targets"),
    "quality_rb_rushing": (frozenset(("RB", "FB")), "rushing_epa", "carries"),
}


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _number(row, name):
    raw = row.get(name)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid player statistic {name}") from error
    if not math.isfinite(value):
        raise ValueError(f"Nonfinite player statistic {name}")
    return value


def _load_history(paths):
    records = []
    seen = set()
    source_receipt = []
    for (name, source_season), path in sorted(
        paths.items(), key=lambda item: (item[0][0], item[0][1] or -1)
    ):
        if name != "player_weekly_stats":
            continue
        path = Path(path)
        raw = path.read_bytes()
        source_receipt.append({
            "season": source_season,
            "path": str(path.resolve()),
            "sha256": _hash(raw),
            "bytes": len(raw),
        })
        for row in pgo_sources.open_csv(path):
            if (row.get("season_type") or "REG").strip().upper() != "REG":
                continue
            player_id = (row.get("player_id") or "").strip()
            position = (row.get("position") or "").strip().upper()
            if not player_id or not position:
                continue
            try:
                season = int(row.get("season") or source_season)
            except (TypeError, ValueError) as error:
                raise ValueError("Invalid player-stat season") from error
            if source_season is not None and season != source_season:
                raise ValueError("Player-stat row differs from its source season")
            try:
                week = int(row.get("week"))
            except (TypeError, ValueError) as error:
                raise ValueError("Invalid player-stat week") from error
            identity = (season, week, player_id)
            if identity in seen:
                raise ValueError("Duplicate player-stat season/week/player identity")
            seen.add(identity)
            records.append((season, player_id, position, row))
    if not source_receipt:
        raise ValueError("Player weekly history is required")
    return records, source_receipt


def _profiles(records, target_season):
    seasons = [target_season - offset for offset in (1, 2, 3)]
    weights = dict(zip(seasons, SEASON_WEIGHTS))
    player_totals = {name: defaultdict(lambda: [0.0, 0.0]) for name in FEATURE_NAMES}
    population = {name: [0.0, 0.0] for name in FEATURE_NAMES}
    for season, player_id, position, row in records:
        weight = weights.get(season)
        if weight is None:
            continue
        for name, (positions, numerator_name, denominator_name) in FEATURE_SPECS.items():
            if position not in positions:
                continue
            numerator = _number(row, numerator_name)
            denominator = _number(row, denominator_name)
            if denominator is None or denominator <= 0 or numerator is None:
                continue
            weighted_numerator = weight * numerator
            weighted_denominator = weight * denominator
            player_totals[name][player_id][0] += weighted_numerator
            player_totals[name][player_id][1] += weighted_denominator
            population[name][0] += weighted_numerator
            population[name][1] += weighted_denominator
    output = {}
    means = {}
    for name in FEATURE_NAMES:
        pop_numerator, pop_denominator = population[name]
        mean = pop_numerator / pop_denominator if pop_denominator > 0 else None
        means[name] = mean
        prior = PRIOR_OPPORTUNITIES[name]
        output[name] = {
            player_id: {
                "value": (
                    (numerator + prior * mean) / (denominator + prior)
                    if mean is not None else None
                ),
                "observed_opportunities": denominator,
            }
            for player_id, (numerator, denominator) in player_totals[name].items()
        }
    return output, means, seasons


def build_roster_hook(paths):
    """Return the chartered team-view hook; no fitting or availability changes."""
    if _hash(CHARTER_PATH.read_bytes()) != EXPECTED_CHARTER_SHA256:
        raise ValueError("Current-strength charter hash differs")
    records, sources = _load_history(paths)
    cache = {}

    def hook(full, current, metadata, *, team, season, week, kickoff, context, inputs):
        del week, kickoff, context
        if season not in cache:
            cache[season] = _profiles(records, season)
        profiles, means, seasons = cache[season]
        roster = metadata.get("roster")
        if not isinstance(roster, dict):
            raise ValueError(f"Roster metadata is unavailable for {team}")
        audit = {}
        for name, (positions, _numerator, _denominator) in FEATURE_SPECS.items():
            weighted_value = 0.0
            total_weight = 0.0
            observed_weight = 0.0
            group_players = 0
            missing_role = 0
            using_prior = 0
            unavailable_value = 0
            ambiguous_ids = 0
            colliding = set(inputs.get("colliding_gsis", ()))
            for internal_id, player in roster.items():
                if (player.get("position") or "").strip().upper() not in positions:
                    continue
                group_players += 1
                role = player.get("offense_snap_share")
                if role is None:
                    missing_role += 1
                    continue
                try:
                    role = float(role)
                except (TypeError, ValueError) as error:
                    raise ValueError(f"Invalid offense snap-share role for {team}") from error
                if not math.isfinite(role) or not 0.0 <= role <= 1.0:
                    raise ValueError(f"Invalid offense snap-share role for {team}")
                if role == 0.0:
                    continue
                player_id = (player.get("gsis_id") or internal_id or "").strip()
                ambiguous = player_id in colliding
                profile = None if ambiguous else profiles[name].get(player_id)
                value = profile["value"] if profile is not None else means[name]
                if value is None:
                    unavailable_value += 1
                    continue
                if profile is None:
                    using_prior += 1
                    ambiguous_ids += int(ambiguous)
                else:
                    observed_weight += role
                weighted_value += role * value
                total_weight += role
            value = weighted_value / total_weight if total_weight > 0 else None
            full[name] = value
            current[name] = value
            audit[name] = {
                "team": team,
                "position_group": "/".join(sorted(positions)),
                "population_mean": means[name],
                "prior_opportunities": PRIOR_OPPORTUNITIES[name],
                "players_on_roster": group_players,
                "players_without_role_weight": missing_role,
                "players_using_position_prior": using_prior,
                "players_with_unavailable_value": unavailable_value,
                "ambiguous_player_ids": ambiguous_ids,
                "total_role_weight": total_weight,
                "observed_history_role_weight": observed_weight,
                "observed_role_weight_coverage": (
                    observed_weight / total_weight if total_weight > 0 else None
                ),
            }
        metadata["roster_strength"] = audit
        metadata["roster_strength_window"] = {
            "seasons": seasons,
            "weights": list(SEASON_WEIGHTS),
        }
        metadata["unavailable_player_quality"] = ["offensive_line", "defense"]
        return full, current, metadata

    hook.receipt = {
        "charter_sha256": EXPECTED_CHARTER_SHA256,
        "features": list(FEATURE_NAMES),
        "prior_opportunities": dict(PRIOR_OPPORTUNITIES),
        "season_weights": list(SEASON_WEIGHTS),
        "sources": sources,
        "limitations": [
            "Skill-player EPA rates are role- and context-dependent efficiency proxies, not player WAR.",
            "Offensive-line and defensive player quality are unavailable from the admitted inputs.",
            "Availability remains in the incumbent availability features and is not multiplied into quality.",
        ],
    }
    return hook
