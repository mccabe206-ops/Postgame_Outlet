"""Read frozen evidence and reconstruct features for diagnostics; never fit."""
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pgo_challenger as ch
import pgo_current_strength as adapter
import pgo_roster_strength as roster
import pgo_opponent_evaluation as base
import pgo_sources

OUT = Path(__file__).resolve().parent
RUN = ROOT / 'research/pgo_current_strength/run-20260908'
read = lambda path: json.loads(path.read_bytes())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = read(RUN / 'manifest.json')
for name, item in manifest['files'].items():
    path = RUN / name
    assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
fits = read(RUN / 'fold-fits.json')
details = read(RUN / 'rating-details.json')
with (RUN / 'matched-predictions.csv').open(newline='', encoding='utf-8') as stream:
    predictions = list(csv.DictReader(stream))
ARMS = ('pgo_v0', 'raw', 'starter', 'starter_recency', 'starter_recency_roster',
        'without_roster_continuity', 'without_coaching', 'without_qb', 'without_team_passing')
for row in predictions:
    row['season'], row['week'] = int(row['season']), int(row['week'])
    row['away'], row['home'] = map(pgo_sources.normalize_team, row['game_id'].split('_')[2:])
    for key in (*ARMS, 'actual_margin'):
        row[key] = float(row[key])


def metrics(rows, arm, team=None):
    errors = [(r[arm] - r['actual_margin']) * (1 if team is None or r['home'] == team else -1)
              for r in rows]
    return {'n': len(errors), 'mae': float(np.mean(np.abs(errors))),
            'bias_predicted_minus_actual': float(np.mean(errors)),
            'rmse': float(np.sqrt(np.mean(np.square(errors))))}


ne = [r for r in predictions if 'NE' in (r['home'], r['away'])]
error_slices = {}
for arm in ARMS:
    error_slices[arm] = {
        'league': metrics(predictions, arm), 'NE': metrics(ne, arm, 'NE'),
        'NE_early': metrics([r for r in ne if r['week'] <= 4], arm, 'NE'),
        'NE_later': metrics([r for r in ne if r['week'] > 4], arm, 'NE'),
        'NE_home': metrics([r for r in ne if r['home'] == 'NE'], arm, 'NE'),
        'NE_away': metrics([r for r in ne if r['away'] == 'NE'], arm, 'NE'),
        'NE_seasons': {str(s): metrics([r for r in ne if r['season'] == s], arm, 'NE')
                       for s in range(2018, 2026)},
        'NE_early_seasons': {str(s): metrics([r for r in ne if r['season'] == s and r['week'] <= 4], arm, 'NE')
                             for s in range(2018, 2026)},
    }
largest = []
for row in sorted(ne, key=lambda r: -abs(r['starter_recency_roster'] - r['actual_margin']))[:12]:
    direction = 1 if row['home'] == 'NE' else -1
    largest.append({'game_id': row['game_id'], 'week': row['week'],
                    'actual_NE_margin': direction * row['actual_margin'],
                    'predicted_NE_margin': direction * row['starter_recency_roster'],
                    'NE_error': direction * (row['starter_recency_roster'] - row['actual_margin'])})

coefficients = {}
for arm in ('raw', 'starter', 'starter_recency', 'starter_recency_roster'):
    coefficients[arm] = {}
    for name in fits[arm][-1]['preprocessor']['feature_names']:
        values = []
        for fold in fits[arm]:
            p = fold['preprocessor']; i = p['feature_names'].index(name)
            values.append({'training_through': fold['training']['season_max'],
                           'validation_n': fold['validation']['count'],
                           'coefficient': fold['coefficients'][i + 1], 'scale': p['scales'][i],
                           'raw_slope': fold['coefficients'][i + 1] / p['scales'][i]})
        coefficients[arm][name] = values

print('saved diagnostics read; reconstructing one full feature walk', flush=True)
paths = pgo_sources.load_locked_sources(base.SOURCE_LOCK_PATH, base.CACHE_DIR)
quality_hook = roster.build_roster_hook(paths)
states = []


def capture(full, current, metadata, **kwargs):
    quality_hook(full, current, metadata, **kwargs)
    states.append({'season': kwargs['season'], 'week': kwargs['week'], 'team': kwargs['team'],
                   'full': dict(full), 'current': dict(current)})


rows, context, inputs = adapter.build_rows(paths, 'starter_recency', roster_hook=capture)
assert len(rows) == 3407 and len(states) == 6814
bygame = {r.game_id: r for r in rows}
assert set(r['game_id'] for r in predictions) <= bygame.keys()
current = {r['team']: r for r in details if r['variant'] == 'starter_recency_roster'}
final = fits['starter_recency_roster'][-1]
p = final['preprocessor']
FEATURES = ('pgo_v0', 'passing_epa_per_play_for', 'qb_epa_per_dropback', 'qb_cpoe',
            'qb_log_dropbacks', 'returning_offense_snap_share', 'returning_defense_snap_share',
            'incoming_prior_snap_share', 'head_coach_continuity', 'head_coach_tenure')


def distribution(values):
    finite = [v for v in values if v is not None]
    return {'n': len(values), 'missing': len(values) - len(finite),
            'zero': sum(v == 0 for v in finite), 'one': sum(v == 1 for v in finite),
            'mean': float(np.mean(finite)), 'sd': float(np.std(finite)),
            'quantiles': dict(zip(('min', 'p01', 'p05', 'p25', 'p50', 'p75', 'p95', 'p99', 'max'),
                                  map(float, np.quantile(finite, (0, .01, .05, .25, .5, .75, .95, .99, 1)))))}


distributions = {}
domain = {}
for feature in FEATURES:
    slices = {'historical_2013_2025': states,
              'historical_2014_2025': [s for s in states if s['season'] >= 2014],
              'week1_2014_2025': [s for s in states if s['season'] >= 2014 and s['week'] == 1],
              'week2plus_2014_2025': [s for s in states if s['season'] >= 2014 and s['week'] >= 2]}
    distributions[feature] = {label: distribution([s['current'][feature] for s in selection])
                               for label, selection in slices.items()}
    distributions[feature]['september_32'] = distribution([s['features'][feature] for s in current.values()])
    empirical = distributions[feature]['historical_2014_2025']
    first = distributions[feature]['week1_2014_2025']
    i = p['feature_names'].index(feature)
    domain[feature] = []
    current_mean = np.mean([r['features'][feature] for r in current.values()])
    for team, saved in current.items():
        value = saved['features'][feature]
        domain[feature].append({'team': team, 'value': value,
                               'z_vs_historical_team_states': (value - empirical['mean']) / empirical['sd'],
                               'z_vs_historical_week1': (value - first['mean']) / first['sd'],
                               'centered_current_in_training_matchup_sd': (value-current_mean)/p['scales'][i],
                               'contribution': saved['centered_contributions'][feature]})

correlations = []
for a_index, a in enumerate(FEATURES):
    for b in FEATURES[a_index + 1:]:
        pairs = [(r.features[a], r.features[b]) for r in rows
                 if r.features[a] is not None and r.features[b] is not None]
        corr = float(np.corrcoef(np.array(pairs).T)[0, 1])
        correlations.append({'a': a, 'b': b, 'n': len(pairs), 'r': corr})

# Verify saved fold predictions with saved preprocessing/coefficients, no fitting.
reproduction = []
for fold in fits['starter_recency_roster'][:-1]:
    prep = fold['preprocessor']
    preprocessor = ch.Preprocessor(tuple(prep['feature_names']), np.array(prep['medians']),
                                  np.array(prep['scales']), tuple(prep['missing_features']))
    observed = [bygame[g] for g in fold['validation']['game_ids']]
    calculated = ch.predict(preprocessor.transform(observed), fold['coefficients'])
    saved = {r['game_id']: r['starter_recency_roster'] for r in predictions}
    error = max(abs(value-saved[row.game_id]) for row, value in zip(observed, calculated))
    assert error < 1e-10
    reproduction.append({'training_through': fold['training']['season_max'], 'n': len(observed),
                         'maximum_saved_prediction_error': error})

result = {'run_manifest_sha256': sha(RUN / 'manifest.json'),
          'read_only_diagnostic_no_fit': True, 'error_slices': error_slices,
          'largest_NE_errors_full_arm': largest, 'fold_coefficients': coefficients,
          'feature_distributions': distributions, 'current_domain': domain,
          'matchup_feature_correlations': correlations, 'saved_prediction_reproduction': reproduction}
with (OUT / 'diagnostics.json').open('x', encoding='utf-8') as stream:
    json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
print('diagnostics.json written; no fits performed', flush=True)
