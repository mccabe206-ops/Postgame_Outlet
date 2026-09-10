"""Frozen experimental confidence picks; readers never refit or reallocate."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / 'docs/evidence/confidence-pool-2026/week1-remaining'
SOURCE_DIR = ROOT / 'docs/evidence/forecast-lab-2026/september-09-postseason'
SOURCE_MANIFEST_SHA = '20397b88cb8703f3a003bd2b1393e018f21f22153b2f32489104c3b0959ce83b'
METHOD_PATH = ROOT / 'research/pgo_confidence_pool_20260909/check.py'
METHOD_SHA = '35bdbab63f77b76b9e555dfdd64d8f1b66e05de827e48fda5ca50fb157843f68'
HISTORY = ROOT / 'research/pgo_postseason_candidate/run-20260909-attempt01/matched-predictions.csv'
HISTORY_SHA = '3df4dbf26743a3686b6253bb4eb578457d0e2629dde1f0218f215c462feea0cf'
EDITION = 'pgo-postseason-week1-2026-09-09'
STATUS = 'EXPERIMENTAL / HOLD'


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _utc(value):
    _require(isinstance(value, str), 'Timestamp must be text')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid timestamp') from exc
    _require(result.tzinfo is not None and result.utcoffset() is not None, 'Timestamp needs timezone')
    return result.astimezone(timezone.utc)


def _number(value):
    _require(type(value) in (int, float) and math.isfinite(value), 'Expected finite number')
    return float(value)


def _snapshot_hash(snapshot):
    return _sha(_bytes({k: v for k, v in snapshot.items() if k != '_manifest_sha256'}))


def _method_history():
    _require(_sha(METHOD_PATH.read_bytes()) == METHOD_SHA, 'Calibration method hash drift')
    _require(_sha(HISTORY.read_bytes()) == HISTORY_SHA, 'Calibration history hash drift')
    from research.pgo_confidence_pool_20260909 import check
    with HISTORY.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    _require(len(rows) == 2127 and len({r['game_id'] for r in rows}) == 2127, 'Calibration game inventory differs')
    for r in rows:
        r['season'] = int(r['season'])
        for name in ('actual_margin', 'corrected', 'candidate'):
            r[name] = float(r[name]); _number(r[name])
    _require(set(r['season'] for r in rows) == set(range(2018, 2026)), 'Calibration seasons differ')
    return check, rows


def _calibration():
    method, rows = _method_history()
    counts = [sum(method.outcome(r['actual_margin']) == k for r in rows) for k in range(3)]
    return dict(training_games=len(rows), training_seasons=list(range(2018, 2026)),
                training_latest_kickoff=max(_utc(r['kickoff']) for r in rows).isoformat(),
                tie_probability=(counts[2]+1)/(len(rows)+2),
                slopes={'postseason': method.slope(rows, 'candidate'), 'corrected': method.slope(rows, 'corrected')},
                constant_probabilities=dict(zip(('home', 'away', 'tie'), ((n+1)/(len(rows)+3) for n in counts))),
                history_sha256=HISTORY_SHA, method_code_sha256=METHOD_SHA,
                objective='Summed non-tie negative log likelihood plus 0.5*slope^2; nonnegative scalar; no intercept')


def _validate_calibration(c):
    method, rows = _method_history()  # Verify optimality without fitting during reads.
    counts = [sum(method.outcome(r['actual_margin']) == k for r in rows) for k in range(3)]
    _require(c['history_sha256'] == HISTORY_SHA and c['method_code_sha256'] == METHOD_SHA, 'Calibration pins differ')
    _require(c['training_games'] == len(rows) and c['training_seasons'] == list(range(2018, 2026)), 'Calibration inventory differs')
    _require(c['training_latest_kickoff'] == max(_utc(r['kickoff']) for r in rows).isoformat(), 'Calibration dates differ')
    _require(c['tie_probability'] == (counts[2]+1)/(len(rows)+2), 'Tie probability differs')
    _require(c['constant_probabilities'] == dict(zip(('home', 'away', 'tie'), ((n+1)/(len(rows)+3) for n in counts))), 'Constant baseline differs')
    for name, column in (('postseason', 'candidate'), ('corrected', 'corrected')):
        a = _number(c['slopes'][name]); _require(a >= 0, 'Negative calibration slope')
        derivative = a + math.fsum(r[column]*(method.sigmoid(a*r[column])-int(r['actual_margin'] > 0)) for r in rows if r['actual_margin'] != 0)
        _require(abs(derivative) < 1e-8 if a > 0 else derivative >= -1e-8, 'Saved calibration is not the fixed optimum')


def _probabilities(margin, a, tie):
    z = a*margin
    sigmoid = lambda v: 1/(1+math.exp(-v)) if v >= 0 else math.exp(v)/(1+math.exp(v))
    p = {'home': (1-tie)*sigmoid(z), 'away': (1-tie)*sigmoid(-z), 'tie': tie}
    _require(all(0 <= _number(v) <= 1 for v in p.values()) and abs(math.fsum(p.values())-1) < 1e-12, 'Invalid probabilities')
    return p


def _pick(game, probabilities):
    side = 'home' if probabilities['home'] >= probabilities['away'] else 'away'
    return dict(probabilities=probabilities, selected_team=game[side], win_probability=probabilities[side])


def _derive(snapshot, generated_at, calibration):
    generated = _utc(generated_at)
    _require(snapshot['edition'] == EDITION, 'Unexpected source edition')
    _require(_utc(snapshot['generated_at']) <= generated, 'Source snapshot is from the future')
    _require(_utc(calibration['training_latest_kickoff']) < generated, 'Future calibration history')
    source_games = snapshot['games']; ids = [g['game_id'] for g in source_games]
    _require(source_games and len(set(ids)) == len(ids), 'Missing or duplicate source games')
    games, excluded = [], []
    for g in source_games:
        _require(g['season'] == 2026 and g['week'] == 1 and g['game_type'] == 'REG', 'Only Week 1 2026 regular-season games are admitted')
        _require(isinstance(g['game_id'], str) and g['game_id'] and g['home'] != g['away'], 'Invalid game identity')
        margin, corrected = _number(g['margin']), _number(g['corrected_margin'])
        lock = _utc(g['kickoff'])-timedelta(minutes=60)
        identity = {k: g[k] for k in ('game_id', 'season', 'week', 'home', 'away', 'kickoff')}
        identity['lock_at'] = lock.isoformat()
        if generated >= lock:
            excluded.append({**identity, 'reason': 'EXISTING_CUTOFF_ELAPSED'})
            continue
        p = _probabilities(margin, calibration['slopes']['postseason'], calibration['tie_probability'])
        cp = _probabilities(corrected, calibration['slopes']['corrected'], calibration['tie_probability'])
        games.append({**identity, 'margin': margin, 'corrected_margin': corrected, **_pick(g, p),
                      'baselines': {'corrected': _pick(g, cp), 'constant': _pick(g, dict(calibration['constant_probabilities']))}})
    _require(games, 'No game remains before its cutoff')
    games.sort(key=lambda r: (r['win_probability'], r['game_id']))
    for points, game in enumerate(games, 1):
        game.update(confidence_points=points, expected_points=points*game['win_probability'])
    return dict(schema_version=1, status=STATUS, generated_at=generated.isoformat(), source_edition=EDITION,
                source_snapshot_generated_at=snapshot['generated_at'], source_snapshot_sha256=_snapshot_hash(snapshot),
                calibration=calibration, games=games, excluded=sorted(excluded, key=lambda g: g['game_id']),
                expected_points_total=math.fsum(g['expected_points'] for g in games), max_points=len(games)*(len(games)+1)//2,
                slate_description='Remaining Week 1 games only; frozen confidence values, not a full-week pool entry')


def build(snapshot, generated_at):
    """Fit the previously fixed mapping to historical OOF records; no current outcomes."""
    return _derive(snapshot, generated_at, _calibration())


def load_verified(directory, expected_manifest_sha256, snapshot):
    directory = Path(directory)
    _require(not directory.is_symlink(), 'Symlink package is not accepted')
    _require(not (directory/'manifest.json').is_symlink(), 'Symlink manifest is not accepted')
    _require({p.name for p in directory.iterdir()} == {'manifest.json', 'picks.json'}, 'Unexpected package files')
    raw = (directory/'manifest.json').read_bytes()
    _require(isinstance(expected_manifest_sha256, str) and len(expected_manifest_sha256) == 64 and _sha(raw) == expected_manifest_sha256, 'Unapproved confidence manifest')
    manifest = json.loads(raw)
    _require(manifest['schema_version'] == 1 and manifest['source_manifest_sha256'] == SOURCE_MANIFEST_SHA, 'Manifest schema/source pin differs')
    _require(set(manifest['files']) == {'picks.json'}, 'Unexpected package inventory')
    _require(manifest['code_sha256'] == _sha(Path(__file__).read_bytes()), 'Confidence code hash drift')
    _require(not (directory/'picks.json').is_symlink(), 'Symlink member is not accepted')
    data = (directory/'picks.json').read_bytes(); info = manifest['files']['picks.json']
    _require(info['bytes'] == len(data) and info['sha256'] == _sha(data), 'Confidence member hash mismatch')
    pool = json.loads(data)
    _require(pool['status'] == STATUS and pool['schema_version'] == 1, 'Confidence status/schema differs')
    _require(manifest['generated_at'] == pool['generated_at'], 'Capture timestamps differ')
    durable = _utc(manifest['durable_at'])
    _require(_utc(pool['generated_at']) <= durable, 'Capture clock moved backwards')
    _validate_calibration(pool['calibration'])
    _require(_bytes(_derive(snapshot, pool['generated_at'], pool['calibration'])) == _bytes(pool), 'Confidence data does not reconcile with saved source')
    _require(all(durable < _utc(g['lock_at']) for g in pool['games']), 'Package was not durable before each cutoff')
    return pool


def capture(output=DEFAULT_OUTPUT):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Confidence output already exists: {output}')
    import pgo_forecast_postseason as source
    _require(_sha((SOURCE_DIR/'manifest.json').read_bytes()) == SOURCE_MANIFEST_SHA, 'Source manifest drift')
    snapshot = source.load_snapshot(SOURCE_DIR)
    generated = datetime.now(timezone.utc).isoformat()
    pool = build(snapshot, generated)
    _require(len(pool['games']) == 15 and [g['game_id'] for g in pool['excluded']] == ['2026_01_NE_SEA'],
             'This publication requires exactly 15 remaining games and the excluded opener')
    output.mkdir(parents=True, exist_ok=False)
    payload = _bytes(pool)
    with (output/'picks.json').open('xb') as handle:
        handle.write(payload); handle.flush()
        import os
        os.fsync(handle.fileno())
    durable = datetime.now(timezone.utc)
    _require(durable >= _utc(generated) and all(durable < _utc(g['lock_at']) for g in pool['games']), 'Clock/cutoff changed during capture')
    manifest = dict(schema_version=1, generated_at=pool['generated_at'], durable_at=durable.isoformat(),
                    code_sha256=_sha(Path(__file__).read_bytes()), source_manifest_sha256=SOURCE_MANIFEST_SHA,
                    files={'picks.json': {'sha256': _sha(payload), 'bytes': len(payload)}})
    with (output/'manifest.json').open('xb') as handle:
        handle.write(_bytes(manifest)); handle.flush(); os.fsync(handle.fileno())
    final = datetime.now(timezone.utc)
    _require(final >= durable and all(final < _utc(g['lock_at']) for g in pool['games']), 'Cutoff passed while committing manifest')
    pin = _sha((output/'manifest.json').read_bytes())
    load_verified(output, pin, snapshot)
    return pool, pin


def grade(pool, results):
    """Grade only supplied, already verified final results; never fetch or reallocate."""
    games = {g['game_id']: g for g in pool['games']}
    _require(len(games) == len(pool['games']), 'Duplicate confidence game')
    earned, available, finished, seen = 0, 0, {}, set()
    scores = {name: [] for name in ('postseason', 'corrected', 'constant')}
    for r in results:
        key = r['game_id']; _require(key not in seen, 'Duplicate result'); seen.add(key)
        if key not in games:
            continue
        g = games[key]
        _require(r['home_team'] == g['home'] and r['away_team'] == g['away'] and _utc(r['kickoff']) == _utc(g['kickoff']), 'Result game identity differs')
        _require(all(r.get(k, g[k]) == g[k] for k in ('season', 'week')) and r.get('game_type', 'REG') == 'REG', 'Result season/week/type differs')
        _require(all(type(r[k]) is int and r[k] >= 0 for k in ('home_score', 'away_score')), 'Final scores must be nonnegative integers')
        _require(_utc(r['finalized_at']) > _utc(g['kickoff']), 'Result is not final after kickoff')
        actual = r['home_score']-r['away_score']
        if 'actual_margin' in r: _require(r['actual_margin'] == actual, 'Result margin differs from scores')
        side = 'home' if actual > 0 else 'away' if actual < 0 else 'tie'
        correct = side != 'tie' and g['selected_team'] == g[side]
        points = g['confidence_points'] if correct else 0
        earned += points; available += g['confidence_points']
        finished[key] = dict(earned_points=points, correct=correct, actual_margin=actual,
                             home_score=r['home_score'], away_score=r['away_score'])
        for model in scores:
            p = g['probabilities'] if model == 'postseason' else g['baselines'][model]['probabilities']
            scores[model].append((-math.log(max(1e-15, p[side])), math.fsum((p[k]-int(k == side))**2 for k in ('home', 'away', 'tie'))))
    metrics = {model: {'log_loss': math.fsum(v[0] for v in values)/len(values) if values else None,
                       'brier': math.fsum(v[1] for v in values)/len(values) if values else None} for model, values in scores.items()}
    return dict(finalized_games=len(finished), earned_points=earned, available_points=available, metrics=metrics, games=finished)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.capture: parser.error('Explicit --capture is required')
    pool, pin = capture(args.output)
    print(json.dumps(dict(games=len(pool['games']), excluded=pool['excluded'], generated_at=pool['generated_at'],
                          expected_points_total=pool['expected_points_total'], manifest_sha256=pin, output=str(args.output)), indent=2))


if __name__ == '__main__':
    main()
