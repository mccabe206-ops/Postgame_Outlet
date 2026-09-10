"""Separate full-slate tracking allocation, explicitly including an after-lock game."""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path

import pgo_confidence_picks as base

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / 'docs/evidence/confidence-pool-2026/week1-full'
ORIGINAL_DIR = ROOT / 'docs/evidence/confidence-pool-2026/week1-remaining'
ORIGINAL_PIN = '4fc0b0972bfc29b72d783fe2d3b12fd0f4b290ae4b400d8e18f7b2e24cc55437'
BASE_CODE_SHA = 'ee06b31a7c2135e1fd5287f83392da291fb2299af360fb7d166fcd88790abb9f'
KIND = 'full-slate-after-lock'
OPENER = '2026_01_NE_SEA'


def _same_replay(left, right):
    """Exact structure and values, allowing at most four finite-float ULPs."""
    if type(left) is not type(right):
        return False
    if isinstance(left, float):
        return (math.isfinite(left) and math.isfinite(right)
                and abs(left-right) <= 4*max(math.ulp(left), math.ulp(right)))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_replay(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_replay(a, b) for a, b in zip(left, right))
    return left == right


def load_remaining_verified(directory, expected_manifest_sha256, snapshot):
    """Preserve the frozen reader's gates while permitting platform exp rounding."""
    base._require(base._sha(Path(base.__file__).read_bytes()) == BASE_CODE_SHA, 'Original confidence code hash drift')
    try:
        return base.load_verified(directory, expected_manifest_sha256, snapshot)
    except ValueError as error:
        if str(error) != 'Confidence data does not reconcile with saved source':
            raise
    # The frozen reader passed every gate preceding its exact numerical replay.
    # Re-pin bytes on reread, reconcile strictly except float ULPs, then finish
    # the original reader's remaining durable-before-cutoff requirement.
    directory = Path(directory)
    raw = (directory/'manifest.json').read_bytes()
    base._require(base._sha(raw) == expected_manifest_sha256, 'Confidence manifest changed during replay')
    manifest = json.loads(raw)
    payload = (directory/'picks.json').read_bytes()
    base._require(base._sha(payload) == manifest['files']['picks.json']['sha256'] and len(payload) == manifest['files']['picks.json']['bytes'], 'Confidence member changed during replay')
    pool = json.loads(payload)
    expected = base._derive(snapshot, pool['generated_at'], pool['calibration'])
    base._require(_same_replay(expected, pool), 'Confidence data does not reconcile with saved source')
    durable = base._utc(manifest['durable_at'])
    base._require(all(durable < base._utc(g['lock_at']) for g in pool['games']), 'Package was not durable before each cutoff')
    return pool


def _original(snapshot):
    return load_remaining_verified(ORIGINAL_DIR, ORIGINAL_PIN, snapshot)


def _derive(snapshot, original, generated_at):
    generated = base._utc(generated_at)
    base._require(generated >= base._utc(original['generated_at']) and generated >= base._utc(snapshot['generated_at']), 'Generation precedes source capture')
    base._require(snapshot['edition'] == base.EDITION and base._snapshot_hash(snapshot) == original['source_snapshot_sha256'], 'Source snapshot differs')
    prior = {g['game_id']: g for g in original['games']}
    source = {g['game_id']: g for g in snapshot['games']}
    base._require(len(source) == len(snapshot['games']) == 16 and len(prior) == len(original['games']) == 15, 'Full/original game inventories differ')
    base._require(set(source)-set(prior) == {OPENER} and set(prior) < set(source), 'Exactly the opener must be added')
    calibration = copy.deepcopy(original['calibration'])
    games = []
    for key, g in source.items():
        base._require(g['season'] == 2026 and g['week'] == 1 and g['game_type'] == 'REG', 'Invalid full-slate game')
        margin, corrected = base._number(g['margin']), base._number(g['corrected_margin'])
        lock = base._utc(g['kickoff'])-timedelta(minutes=60)
        if key in prior:
            row = copy.deepcopy(prior[key])
            for field in ('game_id', 'season', 'week', 'home', 'away', 'kickoff', 'margin', 'corrected_margin'):
                base._require(row[field] == g[field], 'Original game field differs')
            base._require(base._utc(row['lock_at']) == lock, 'Original cutoff differs')
        else:
            identity = {name: g[name] for name in ('game_id', 'season', 'week', 'home', 'away', 'kickoff')}
            probabilities = base._probabilities(margin, calibration['slopes']['postseason'], calibration['tie_probability'])
            corrected_probabilities = base._probabilities(corrected, calibration['slopes']['corrected'], calibration['tie_probability'])
            row = dict(**identity, lock_at=lock.isoformat(), margin=margin, corrected_margin=corrected,
                       **base._pick(g, probabilities), baselines={
                           'corrected': base._pick(g, corrected_probabilities),
                           'constant': base._pick(g, copy.deepcopy(calibration['constant_probabilities']))})
        row['added_after_lock'] = lock <= generated
        games.append(row)
    games.sort(key=lambda g: (g['win_probability'], g['game_id']))
    for points, game in enumerate(games, 1):
        game['confidence_points'] = points
        game['expected_points'] = points*game['win_probability']
    late = sorted(g['game_id'] for g in games if g['added_after_lock'])
    base._require(late == [OPENER], 'This edition permits only the opener after lock')
    result = dict(schema_version=1, kind=KIND, status=base.STATUS,
                  generated_at=generated.isoformat(), source_edition=base.EDITION,
                  source_snapshot_generated_at=snapshot['generated_at'], source_snapshot_sha256=base._snapshot_hash(snapshot),
                  source_confidence_manifest_sha256=ORIGINAL_PIN, source_confidence_code_sha256=BASE_CODE_SHA,
                  source_confidence_generated_at=original['generated_at'], calibration=calibration,
                  games=games, excluded=[], after_lock_game_ids=late,
                  expected_points_total=math.fsum(g['expected_points'] for g in games), max_points=136,
                  slate_description='All 16 Week 1 games for tracking; NE-SEA added after lock; this allocation is not a prospective full-week entry')
    for game in games:
        if game['game_id'] in prior:
            restored = {k: v for k, v in game.items() if k != 'added_after_lock'}
            for field in ('confidence_points', 'expected_points'): restored[field] = prior[game['game_id']][field]
            base._require(restored == prior[game['game_id']], 'Original probabilities or game fields changed')
    return result


def build(snapshot, generated_at):
    """Reuse the verified frozen calibration; never fit or read current results."""
    return _derive(snapshot, _original(snapshot), generated_at)


def load_verified(directory, expected_manifest_sha256, snapshot):
    directory = Path(directory)
    base._require(not directory.is_symlink() and {p.name for p in directory.iterdir()} == {'picks.json', 'manifest.json'}, 'Invalid full-slate package inventory')
    base._require(all(not (directory/name).is_symlink() for name in ('picks.json', 'manifest.json')), 'Symlink member rejected')
    raw = (directory/'manifest.json').read_bytes()
    base._require(isinstance(expected_manifest_sha256, str) and len(expected_manifest_sha256) == 64 and base._sha(raw) == expected_manifest_sha256, 'Unapproved full-slate manifest')
    m = json.loads(raw)
    base._require(m['schema_version'] == 1 and m['kind'] == KIND and m['code_sha256'] == base._sha(Path(__file__).read_bytes()), 'Full-slate code/schema/kind differs')
    base._require(m['source_confidence_manifest_sha256'] == ORIGINAL_PIN and m['source_snapshot_manifest_sha256'] == base.SOURCE_MANIFEST_SHA, 'Full-slate source pins differ')
    base._require(set(m['files']) == {'picks.json'}, 'Unexpected full-slate members')
    payload = (directory/'picks.json').read_bytes(); member = m['files']['picks.json']
    base._require(member['sha256'] == base._sha(payload) and member['bytes'] == len(payload), 'Full-slate member hash mismatch')
    pool = json.loads(payload)
    base._require(m['generated_at'] == pool['generated_at'], 'Full-slate timestamps differ')
    durable = base._utc(m['durable_at'])
    base._require(durable >= base._utc(pool['generated_at']), 'Full-slate clock moved backwards')
    original = _original(snapshot)
    base._require(_same_replay(pool, _derive(snapshot, original, pool['generated_at'])), 'Full-slate allocation does not reconcile')
    base._require(all(g['added_after_lock'] or durable < base._utc(g['lock_at']) for g in pool['games']), 'Another game locked before durable completion')
    return pool


def capture(output=DEFAULT_OUTPUT):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Full-slate output already exists: {output}')
    import pgo_forecast_postseason as source
    base._require(base._sha((base.SOURCE_DIR/'manifest.json').read_bytes()) == base.SOURCE_MANIFEST_SHA, 'Source snapshot manifest drift')
    snapshot = source.load_snapshot(base.SOURCE_DIR)
    original = _original(snapshot)
    generated = datetime.now(timezone.utc).isoformat()
    pool = _derive(snapshot, original, generated)
    output.mkdir(parents=True, exist_ok=False)
    payload = base._bytes(pool)
    with (output/'picks.json').open('xb') as handle:
        handle.write(payload); handle.flush(); os.fsync(handle.fileno())
    durable = datetime.now(timezone.utc)
    base._require(durable >= base._utc(generated) and all(g['added_after_lock'] or durable < base._utc(g['lock_at']) for g in pool['games']), 'Clock/cutoff changed during full-slate capture')
    m = dict(schema_version=1, kind=KIND, generated_at=generated, durable_at=durable.isoformat(),
             code_sha256=base._sha(Path(__file__).read_bytes()), source_confidence_manifest_sha256=ORIGINAL_PIN,
             source_snapshot_manifest_sha256=base.SOURCE_MANIFEST_SHA,
             files={'picks.json': {'sha256': base._sha(payload), 'bytes': len(payload)}})
    with (output/'manifest.json').open('xb') as handle:
        handle.write(base._bytes(m)); handle.flush(); os.fsync(handle.fileno())
    final = datetime.now(timezone.utc)
    base._require(final >= durable and all(g['added_after_lock'] or final < base._utc(g['lock_at']) for g in pool['games']), 'Cutoff changed during manifest completion')
    pin = base._sha((output/'manifest.json').read_bytes())
    load_verified(output, pin, snapshot)
    return pool, pin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.capture: parser.error('Explicit --capture is required')
    pool, pin = capture(args.output)
    print(json.dumps(dict(games=len(pool['games']), added_after_lock=pool['after_lock_game_ids'], generated_at=pool['generated_at'],
                          expected_points_total=pool['expected_points_total'], manifest_sha256=pin), indent=2))


if __name__ == '__main__':
    main()
