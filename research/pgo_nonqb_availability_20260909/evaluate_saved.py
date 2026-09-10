"""Replay the saved corrected folds; zero two observed terms without refitting."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.pgo_input_audit import verify_run as saved

DIRECTORY = Path(__file__).resolve().parent
RUN = ROOT / 'research/pgo_week1_corrected/run-20260908'
RUN_HASH = '7530b3199f8a17ffec34f9e5351919ea67cb45df66e16befd655ab4e746f7a4c'
HELPER_HASH = '366514b4259eb13355cb1fe04e257a2bd1be7a50f8b087a1399abe06fe6bf3fc'
CHARTER_HASH = '5832240b04d722eafeb92e74187ad63cd42966561626df1db57f0016c86573d8'
TERMS = ('offense_availability', 'defense_availability')
SEASONS = tuple(range(2018, 2026))
SEED, SAMPLES = 20260909, 10000
LIMITS = [
    'Post-hoc diagnostic on already inspected 2018-2025 history; not new validation.',
    'Historical availability includes QB lost snaps and heuristic status probabilities; this is not an isolated non-QB injury test.',
    'Only observed offense/defense availability values are zeroed; nulls and all missingness indicators are preserved.',
    'The same saved season-fold coefficients and preprocessing are used for both predictions; no refit, tuning, historical rebuild or promotion.',
    'Historical feature publication vintages and historical starter identities retain their previously documented limitations.',
    'This does not validate the new last-four-positive-snap role proxy or the new OUT/IR/PUP versus uncertain-out scenario policy.',
    'Eight season blocks give limited uncertainty information; intervals are diagnostic, not scenario confidence ranges.',
    'Issued forecasts and the active corrected fit remain unchanged. EXPERIMENTAL / HOLD.',
]


def inventory(path):
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def metrics(rows):
    result = {}
    for key in ('with_availability', 'zero_observed_availability'):
        summary = saved.summary(rows, key)
        result[key] = {name: summary[name] for name in ('count', 'mae', 'rmse')}
    result['gain_with_availability'] = {
        metric: result['zero_observed_availability'][metric] - result['with_availability'][metric]
        for metric in ('mae', 'rmse')}
    return result


def bootstrap(rows):
    # Each selected season contributes all its games; both arms use the same blocks.
    counts, absolute, squared = [], [[], []], [[], []]
    for season in SEASONS:
        selected = [row for row in rows if int(row['season']) == season]
        assert selected
        counts.append(len(selected))
        for index, key in enumerate(('with_availability', 'zero_observed_availability')):
            errors = [float(row[key]) - float(row['actual_margin']) for row in selected]
            absolute[index].append(math.fsum(abs(error) for error in errors))
            squared[index].append(math.fsum(error * error for error in errors))
    selections = np.random.default_rng(SEED).integers(0, len(SEASONS), size=(SAMPLES, len(SEASONS)))
    denominators = np.asarray(counts)[selections].sum(axis=1)
    maes = [np.asarray(values)[selections].sum(axis=1) / denominators for values in absolute]
    rmses = [np.sqrt(np.asarray(values)[selections].sum(axis=1) / denominators) for values in squared]
    result = {'blocks': len(SEASONS), 'samples': SAMPLES, 'seed': SEED,
              'method': 'paired game-weighted season-block resampling; percentile 95% interval',
              'positive_gain_means': 'lower error with the saved availability terms'}
    for metric, values in (('mae', maes), ('rmse', rmses)):
        low, high = np.quantile(values[1] - values[0], [.025, .975])
        result[metric] = {'estimate': metrics(rows)['gain_with_availability'][metric],
                          'lower': float(low), 'upper': float(high)}
    return result


def evaluate(output):
    output = Path(output).resolve()
    if output.parent != DIRECTORY or output.exists():
        raise ValueError('Diagnostic output must be a new direct child of this research directory')
    started = datetime.now(timezone.utc).isoformat()
    assert saved.sha(Path(saved.__file__)) == HELPER_HASH
    assert saved.sha(DIRECTORY / 'charter.md') == CHARTER_HASH
    saved.manifest(RUN, RUN_HASH)
    paths = [RUN / 'manifest.json', RUN / 'historical-features.json', RUN / 'fold-fits.json',
             RUN / 'matched-predictions.csv', Path(saved.__file__), Path(__file__), DIRECTORY / 'charter.md']
    inputs = {path.relative_to(ROOT).as_posix(): inventory(path) for path in paths}
    history = saved.read(RUN / 'historical-features.json')
    historical = {row['game_id']: row for row in history}
    assert len(history) == len(historical) == 3407
    reference = saved.csv_rows(RUN / 'matched-predictions.csv')
    reference_map = {row['game_id']: row for row in reference}
    assert len(reference) == len(reference_map) == 2127
    folds = [fit for fit in saved.read(RUN / 'fold-fits.json') if 'evaluation_season' in fit]
    assert tuple(fit['evaluation_season'] for fit in folds) == SEASONS
    rows, maximum_error, null_counts = [], 0.0, dict.fromkeys(TERMS, 0)
    for fit in folds:
        ids = fit['validation']['game_ids']
        assert len(ids) == len(set(ids)) == fit['validation']['count']
        selected = [historical[game] for game in ids]
        assert all(row['season'] == fit['evaluation_season'] for row in selected)
        assert max(historical[game]['season'] for game in fit['training']['game_ids']) < fit['evaluation_season']
        original = [row['features'] for row in selected]
        changed = [{key: (0.0 if key in TERMS and value is not None else value)
                    for key, value in features.items()} for features in original]
        for before, after in zip(original, changed):
            assert set(before) == set(fit['preprocessor']['feature_names'])
            assert {key for key, value in before.items() if value is None} == {key for key, value in after.items() if value is None}
            assert all(before[key] == after[key] for key in before if key not in TERMS)
            for key in TERMS:
                null_counts[key] += before[key] is None
        predictions, zeroed = saved.predict(original, fit), saved.predict(changed, fit)
        for row, predicted, without in zip(selected, predictions, zeroed):
            ref = reference_map[row['game_id']]
            assert all(str(row[key]) == ref[key] for key in ('season', 'week', 'kickoff'))
            assert row['actual_margin'] == float(ref['actual_margin'])
            error = abs(float(predicted) - float(ref['corrected']))
            maximum_error = max(maximum_error, error)
            assert error <= 1e-9
            values = {key: ref[key] for key in ('game_id', 'season', 'week', 'kickoff', 'home_team', 'away_team', 'actual_margin')}
            values.update(with_availability=float(predicted), zero_observed_availability=float(without),
                          saved_corrected=float(ref['corrected']), replay_error=error,
                          **{key: row['features'][key] for key in TERMS})
            rows.append(values)
    assert len(rows) == len({row['game_id'] for row in rows}) == 2127
    assert {row['game_id'] for row in rows} == set(reference_map)
    groups = {'overall': rows, 'weeks_1_4': [row for row in rows if int(row['week']) <= 4],
              'weeks_5_18': [row for row in rows if int(row['week']) >= 5]}
    slices = {name: {'metrics': metrics(selected), 'bootstrap': bootstrap(selected)} for name, selected in groups.items()}
    seasons = [{'season': season, **metrics([row for row in rows if int(row['season']) == season])} for season in SEASONS]
    assert all(inventory(ROOT / name) == value for name, value in inputs.items())
    result = {'status': 'EXPERIMENTAL / HOLD', 'started_at': started,
              'completed_at': datetime.now(timezone.utc).isoformat(), 'inputs': inputs,
              'python': sys.version, 'numpy': np.__version__, 'games': len(rows),
              'maximum_saved_prediction_error': maximum_error, 'preserved_null_counts': null_counts,
              'slices': slices, 'seasons': seasons,
              'seasons_with_positive_mae_gain': sum(row['gain_with_availability']['mae'] > 0 for row in seasons),
              'limits': LIMITS}
    output.mkdir(exist_ok=False)
    with (output / 'predictions.csv').open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    write_json(output / 'metrics-receipt.json', result)
    overall = slices['overall']; estimate = overall['metrics']['gain_with_availability']['mae']
    interval = overall['bootstrap']['mae']
    report = ('# Saved availability-term diagnostic\n\n**EXPERIMENTAL / HOLD.**\n\n'
              f'All {len(rows):,} saved games replay within {maximum_error:.3g} points. '
              f'With availability MAE is {overall["metrics"]["with_availability"]["mae"]:.9f}; '
              f'zeroing the two observed terms gives {overall["metrics"]["zero_observed_availability"]["mae"]:.9f}. '
              f'Availability MAE gain is {estimate:+.9f}, with paired season-block 95% interval '
              f'[{interval["lower"]:+.9f}, {interval["upper"]:+.9f}]; '
              f'{result["seasons_with_positive_mae_gain"]}/8 seasons improve.\n\n' +
              '\n'.join('- ' + line for line in LIMITS) + '\n')
    with (output / 'README.md').open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(report)
    write_json(output / 'manifest.json', {'identity': 'pgo-saved-availability-diagnostic-20260909',
        'files': {name: inventory(output / name) for name in ('predictions.csv', 'metrics-receipt.json', 'README.md')}})
    print(json.dumps({'output': str(output), 'games': len(rows), 'maximum_replay_error': maximum_error,
                      'overall': overall, 'seasons_with_positive_mae_gain': result['seasons_with_positive_mae_gain']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DIRECTORY / 'diagnostic-20260909')
    evaluate(parser.parse_args().output)
