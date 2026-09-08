"""Record verified per-game forecast revisions before kickoff minus 60 minutes.

Sources use their separately reviewed September7 or corrected Week1 verifier.
Each edition retains its own model, source and arithmetic contract.
"""

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

import pgo_forecast_snapshot
import pgo_forecast_corrected

# Only the two explicitly reviewed source editions are accepted below.

HERE = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT = HERE / "docs" / "evidence" / "forecast-lab-2026" / "september-07"
DEFAULT_WEEKLY_ROOT = HERE / "docs" / "evidence" / "forecast-lab-2026" / "weekly"
KIND = "pgo_forecast_weekly_revision"
_REVISION_NAME = re.compile(r"^\d{8}T\d{12}Z\.json$")
_REVISION_KEYS = {
    "schema_version", "kind", "revision", "week", "registered_at",
    "source_directory", "source_manifest_sha256", "source_generated_at",
    "games", "artifact_sha256",
}
_IDENTITY_KEYS = (
    "game_id", "season", "week", "kickoff", "game_type", "location",
    "home", "away", "home_rest", "away_rest",
)


def _current_utc():
    return datetime.now(UTC)


def _checked_now():
    value = _current_utc()
    if value.tzinfo is None:
        raise ValueError("Registration clock must be timezone-aware")
    return value.astimezone(UTC)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _artifact_hash(value):
    payload = dict(value)
    payload.pop("artifact_sha256", None)
    return _sha256(_canonical(payload).encode("utf-8"))


def _utc(value):
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _timestamp(value):
    return _utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _revision_name(value):
    return _utc(value).strftime("%Y%m%dT%H%M%S%fZ.json")


def _manifest_bytes(directory):
    path = directory / "manifest.json"
    if path.is_symlink():
        raise ValueError("Snapshot manifest must be a real file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ValueError("Snapshot manifest is unavailable") from error


def _verified_source(directory, expected_manifest_sha256=None):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Snapshot source must be a real directory")
    before = _manifest_bytes(directory)
    manifest_sha256 = _sha256(before)
    if expected_manifest_sha256 is not None and manifest_sha256 != expected_manifest_sha256:
        raise ValueError("Snapshot source manifest hash changed")
    edition = json.loads(before).get('edition')
    if edition == pgo_forecast_corrected.EDITION:
        snapshot = pgo_forecast_corrected.load_snapshot(directory)
    elif edition in (None, pgo_forecast_snapshot.EDITION):
        # Missing edition reaches the strict legacy verifier, which rejects it.
        snapshot = pgo_forecast_snapshot.load_snapshot(directory)
    else:
        raise ValueError('Unknown weekly source edition')
    if _manifest_bytes(directory) != before:
        raise ValueError("Snapshot source manifest changed during verification")
    return snapshot, manifest_sha256


def _paths(snapshot_directory, weekly_root):
    weekly = Path(weekly_root).absolute()
    parent = weekly.parent
    if not parent.exists() or parent.is_symlink() or not parent.is_dir():
        raise ValueError("Weekly evidence parent must be a real directory")
    evidence = parent.resolve()
    source = Path(snapshot_directory).resolve()
    try:
        source.relative_to(evidence)
    except ValueError as error:
        raise ValueError("Snapshot source is outside the common evidence root") from error
    weekly_real = weekly.resolve()
    if source == weekly_real or source in weekly_real.parents or weekly_real in source.parents:
        raise ValueError("Snapshot source and weekly output must be separate")
    return source, weekly_real, evidence


def _source_reference(source, weekly):
    return Path(os.path.relpath(source, weekly)).as_posix()


def _source_from_reference(reference, weekly, evidence):
    if not isinstance(reference, str) or not reference or "\\" in reference or ":" in reference:
        raise ValueError("Invalid snapshot source directory")
    relative = PurePosixPath(reference)
    if relative.is_absolute():
        raise ValueError("Invalid snapshot source directory")
    source = (weekly / Path(*relative.parts)).resolve()
    try:
        source.relative_to(evidence)
    except ValueError as error:
        raise ValueError("Snapshot source is outside the common evidence root") from error
    if reference != _source_reference(source, weekly):
        raise ValueError("Snapshot source directory is not canonical")
    return source


def _game_map(snapshot):
    games = snapshot.get("games")
    if not isinstance(games, list):
        raise ValueError("Snapshot games are invalid")
    mapped = {}
    for game in games:
        if not isinstance(game, dict) or not isinstance(game.get("game_id"), str) or not game["game_id"]:
            raise ValueError("Snapshot game identity is invalid")
        if game["game_id"] in mapped:
            raise ValueError("Snapshot contains duplicate games")
        if "lock_at" in game:
            raise ValueError("Snapshot game collides with weekly metadata")
        mapped[game["game_id"]] = game
    return mapped


def _locked_game(game):
    locked = dict(game)
    locked["lock_at"] = _timestamp(_utc(game["kickoff"]) - timedelta(minutes=60))
    return locked


def _read_revision(path):
    if path.is_symlink() or not path.is_file() or not _REVISION_NAME.fullmatch(path.name):
        raise ValueError(f"Invalid weekly revision path: {path.name}")
    try:
        raw = path.read_bytes()
        revision = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Invalid weekly revision: {path.name}") from error
    if not isinstance(revision, dict) or set(revision) != _REVISION_KEYS:
        raise ValueError(f"Invalid weekly revision schema: {path.name}")
    if raw != (_canonical(revision) + "\n").encode("utf-8"):
        raise ValueError(f"Weekly revision is not canonical: {path.name}")
    if revision["artifact_sha256"] != _artifact_hash(revision):
        raise ValueError(f"Weekly revision artifact hash mismatch: {path.name}")
    if type(revision["schema_version"]) is not int or revision["schema_version"] != 1:
        raise ValueError(f"Invalid weekly revision schema: {path.name}")
    if revision["kind"] != KIND or revision["revision"] != path.name:
        raise ValueError(f"Invalid weekly revision identity: {path.name}")
    if _revision_name(revision["registered_at"]) != path.name:
        raise ValueError(f"Weekly revision timestamp mismatch: {path.name}")
    if isinstance(revision["week"], bool) or not isinstance(revision["week"], int) or not 1 <= revision["week"] <= 18:
        raise ValueError(f"Invalid weekly revision week: {path.name}")
    if not isinstance(revision["source_manifest_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", revision["source_manifest_sha256"]
    ):
        raise ValueError(f"Invalid source manifest hash: {path.name}")
    if not isinstance(revision["games"], list) or not revision["games"]:
        raise ValueError(f"Weekly revision has no games: {path.name}")
    return revision


def load_weekly(weekly_root):
    """Verify the append-only series and return the latest revision per game."""
    weekly = Path(weekly_root).absolute()
    if not weekly.exists():
        return {"schema_version": 1, "games": [], "revisions": [], "count": 0}
    if weekly.is_symlink() or not weekly.is_dir() or weekly.parent.is_symlink():
        raise ValueError("Weekly evidence root must be a real directory")
    evidence = weekly.parent.resolve()
    weekly = weekly.resolve()
    paths = []
    for path in weekly.iterdir():
        if path.name == "results" and path.is_dir() and not path.is_symlink():
            continue
        if not path.is_file() or path.is_symlink() or not _REVISION_NAME.fullmatch(path.name):
            raise ValueError(f"Invalid weekly evidence entry: {path.name}")
        paths.append(path)
    revisions = [_read_revision(path) for path in sorted(paths, key=lambda item: item.name)]
    sources = {}
    latest = {}
    identities = {}
    seen_source_games = set()
    previous_registration = None
    metadata = []
    for revision in revisions:
        registered = _utc(revision["registered_at"])
        if previous_registration is not None and registered <= previous_registration:
            raise ValueError("Weekly revisions must have strictly increasing registration times")
        previous_registration = registered
        source = _source_from_reference(revision["source_directory"], weekly, evidence)
        cache_key = (str(source), revision["source_manifest_sha256"])
        if cache_key not in sources:
            sources[cache_key] = _verified_source(source, revision["source_manifest_sha256"])[0]
        snapshot = sources[cache_key]
        if revision["source_generated_at"] != snapshot.get("generated_at"):
            raise ValueError("Weekly revision source generation time changed")
        if _utc(revision["source_generated_at"]) > registered:
            raise ValueError("Snapshot source was issued after registration")
        source_games = _game_map(snapshot)
        seen = set()
        expected_rows = []
        for row in revision["games"]:
            if not isinstance(row, dict) or not isinstance(row.get("game_id"), str):
                raise ValueError("Weekly revision game is invalid")
            game_id = row["game_id"]
            if game_id in seen:
                raise ValueError(f"Weekly revision contains duplicate game: {game_id}")
            seen.add(game_id)
            if game_id not in source_games or source_games[game_id].get("week") != revision["week"]:
                raise ValueError(f"Weekly revision has an unknown game: {game_id}")
            expected = _locked_game(source_games[game_id])
            expected_rows.append(expected)
            if row != expected:
                raise ValueError(f"Weekly game differs from its source snapshot: {game_id}")
            if registered >= _utc(expected["lock_at"]):
                raise ValueError(f"Weekly revision was registered at or after cutoff: {game_id}")
            identity = tuple(expected.get(key) for key in _IDENTITY_KEYS)
            if game_id in identities and identities[game_id] != identity:
                raise ValueError(f"Weekly game identity changed: {game_id}")
            identities[game_id] = identity
            source_game = (revision["source_manifest_sha256"], game_id)
            if source_game in seen_source_games:
                raise ValueError(f"Weekly series already records this source and game: {game_id}")
            seen_source_games.add(source_game)
            latest[game_id] = {
                **row,
                "registered_at": revision["registered_at"],
                "source_generated_at": revision["source_generated_at"],
                "revision": revision["revision"],
                "source_manifest_sha256": revision["source_manifest_sha256"],
                "source_edition": snapshot["edition"],
                **({"league_mean_total": snapshot["league_mean_total"]}
                   if "league_mean_total" in snapshot else {}),
            }
        if revision["games"] != sorted(expected_rows, key=lambda row: (row["kickoff"], row["game_id"])):
            raise ValueError(f"Weekly revision games are not canonically ordered: {revision['revision']}")
        metadata.append({key: revision[key] for key in (
            "revision", "week", "registered_at", "source_directory",
            "source_manifest_sha256", "source_generated_at", "artifact_sha256",
        )} | {"game_ids": [row["game_id"] for row in revision["games"]],
              "source_edition": snapshot["edition"]})
    games = sorted(latest.values(), key=lambda row: (row["kickoff"], row["game_id"]))
    return {"schema_version": 1, "games": games, "revisions": metadata, "count": len(games)}


def record_week(snapshot_directory, weekly_root, week: int, game_ids=None):
    """Append one verified revision, using the real UTC registration time."""
    if isinstance(week, bool) or not isinstance(week, int) or not 1 <= week <= 18:
        raise ValueError("Week must be an integer from 1 through 18")
    source, weekly, _ = _paths(snapshot_directory, weekly_root)
    snapshot, manifest_sha256 = _verified_source(source)
    source_games = _game_map(snapshot)
    week_games = {game_id: game for game_id, game in source_games.items() if game.get("week") == week}
    if game_ids is None:
        selected_ids = list(week_games)
    else:
        selected_ids = list(game_ids)
        if any(not isinstance(game_id, str) or not game_id for game_id in selected_ids):
            raise ValueError("Selected game ids must be nonempty strings")
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError("Selected game ids must be unique")
    if not selected_ids or any(game_id not in week_games for game_id in selected_ids):
        raise ValueError("Selected game id is not in the requested week")
    selected = sorted((_locked_game(week_games[game_id]) for game_id in selected_ids),
                      key=lambda row: (row["kickoff"], row["game_id"]))

    series = load_weekly(weekly)
    prior_games = {game["game_id"]: game for game in series["games"]}
    for game in selected:
        prior = prior_games.get(game["game_id"])
        if prior and tuple(prior.get(key) for key in _IDENTITY_KEYS) != tuple(
            game.get(key) for key in _IDENTITY_KEYS
        ):
            raise ValueError(f"Weekly game identity changed: {game['game_id']}")
        if any(
            game["game_id"] in revision["game_ids"]
            and revision["source_manifest_sha256"] == manifest_sha256
            for revision in series["revisions"]
        ):
            raise ValueError(f"Weekly series already records this source and game: {game['game_id']}")

    registered = _checked_now()
    if _utc(snapshot["generated_at"]) > registered:
        raise ValueError("Snapshot source was issued after registration")
    if series["revisions"] and registered <= _utc(series["revisions"][-1]["registered_at"]):
        raise ValueError("Registration must be later than the latest weekly revision")
    for game in selected:
        if registered >= _utc(game["lock_at"]):
            raise ValueError(f"Selected game is at or after its cutoff: {game['game_id']}")

    registered_at = _timestamp(registered)
    revision_name = _revision_name(registered)
    revision = {
        "schema_version": 1,
        "kind": KIND,
        "revision": revision_name,
        "week": week,
        "registered_at": registered_at,
        "source_directory": _source_reference(source, weekly),
        "source_manifest_sha256": manifest_sha256,
        "source_generated_at": snapshot["generated_at"],
        "games": selected,
    }
    revision["artifact_sha256"] = _artifact_hash(revision)
    raw = (_canonical(revision) + "\n").encode("utf-8")
    durable_check = _checked_now()
    if durable_check < registered:
        raise ValueError("Registration clock moved backwards before write")
    for game in selected:
        if durable_check >= _utc(game["lock_at"]):
            raise ValueError(f"Selected game is at or after its cutoff: {game['game_id']}")
    weekly.mkdir(exist_ok=True)
    destination = weekly / revision_name
    with destination.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        completed_at = _checked_now()
        if completed_at < durable_check:
            raise ValueError("Registration clock moved backwards during write")
        for game in selected:
            if completed_at >= _utc(game["lock_at"]):
                raise ValueError(f"Durable write completed at or after cutoff: {game['game_id']}")
    except Exception:
        if (
            destination.parent != weekly
            or destination.name != revision_name
            or destination.is_symlink()
            or destination.read_bytes() != raw
        ):
            raise RuntimeError("Refusing to remove an unverified revision path")
        destination.unlink()
        raise
    return revision


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_WEEKLY_ROOT)
    parser.add_argument("--week", type=int)
    parser.add_argument("--game-id", action="append", dest="game_ids")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        series = load_weekly(args.output)
        print(f"Verified {len(series['revisions'])} weekly revisions; {series['count']} games")
        return 0
    if args.week is None:
        parser.error("recording requires --week")
    revision = record_week(args.snapshot, args.output, args.week, args.game_ids)
    print(f"Recorded {len(revision['games'])} games in {revision['revision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
