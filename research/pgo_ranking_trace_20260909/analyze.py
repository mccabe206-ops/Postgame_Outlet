"""Explain saved ratings without refitting or rebuilding features; print JSON."""
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / 'research/pgo_corrected_roster_candidate'
ISSUED = ROOT / 'docs/evidence/forecast-lab-2026/september-08-corrected'
PINS = {
    CANDIDATE / 'run-20260908/manifest.json': '6bbd0b987d7a619a7b6ffae10c2dde43268b44a3ccb81c7ccd22afd6f51da759',
    CANDIDATE / 'current-preflight-20260908/manifest.json': '0e35d51dc0bcdeb739a17b10e693d47d55e0f8b4810d59da4271dc85b6cf2200',
    CANDIDATE / 'preflight-20260908-revised/manifest.json': 'de0dcf0a80eb7daec12bd7c606a4d0f714496b782dd09d321296c9494d425a69',
    CANDIDATE / 'current-ratings-diagnostic-20260909.json': '0a155880cf135721c33a1797b7e54b6fbc80ce7dbdd480abf749f06b6343b290',
    ISSUED / 'manifest.json': '85fe35069145505410567709261663be0939b3ae2fbe05ad147da1d17fc54d83',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def contributions(features, fit):
    pp = fit['preprocessor']
    names = pp['feature_names']
    assert len(names) == len(pp['medians']) == len(pp['scales'])
    assert len(fit['coefficients']) == 1 + len(names) + len(pp['missing_features'])
    assert all(v is not None and math.isfinite(v) for f in features.values() for v in f.values())
    assert all(s > 0 and math.isfinite(s) for s in pp['scales'])
    raw = {}
    for team, f in features.items():
        raw[team] = {
            k: ((0.0 if k in ('home_field', 'rest_difference') else f[k]) - m) / s * b
            for k, m, s, b in zip(names, pp['medians'], pp['scales'], fit['coefficients'][1:])
        }
        raw[team].update({k + '_missing': 0.0 for k in pp['missing_features']})
    means = {k: statistics.fmean(row[k] for row in raw.values()) for k in next(iter(raw.values()))}
    return {t: {k: v - means[k] for k, v in row.items()} for t, row in raw.items()}


def analyze():
    pins = dict(PINS)
    for path, expected in PINS.items():
        assert digest(path) == expected, str(path)
        if path.name == 'manifest.json':
            for name, record in read(path)['files'].items():
                member = path.parent / name
                assert member.resolve().is_relative_to(path.parent.resolve())
                assert member.stat().st_size == record['bytes']
                assert digest(member) == record['sha256'], str(member)
                pins[member] = record['sha256']
    current = read(CANDIDATE / 'current-preflight-20260908/current-features.json')
    fit = read(CANDIDATE / 'run-20260908/final-fit.json')
    old_fit = read(ISSUED / 'final-fit.json')
    old = {r['team']: r for r in read(ISSUED / 'snapshot.json')['teams']}
    diagnostic = read(CANDIDATE / 'current-ratings-diagnostic-20260909.json')
    assert set(current) == set(old) == {r['team'] for r in diagnostic['ratings']}
    assert len(current) == 32
    for team in current:
        for key, value in old[team]['features'].items():
            assert current[team][key] == value, (team, key)
    base = set(old_fit['preprocessor']['feature_names'])
    added = set(fit['preprocessor']['feature_names']) - base
    assert len(added) == 10
    new_terms = contributions(current, fit)
    old_terms = contributions({t: row['features'] for t, row in old.items()}, old_fit)
    max_error = 0.0
    rows = []
    for rating in diagnostic['ratings']:
        team = rating['team']
        before, after = old_terms[team], new_terms[team]
        for k, v in before.items():
            max_error = max(max_error, abs(v - old[team]['contributions'][k]))
        delta = {k: after.get(k, 0.0) - before.get(k, 0.0) for k in sorted(set(before) | set(after))}
        total = rating['rating'] - rating['corrected_rating']
        errors = (sum(after.values()) - rating['rating'], sum(before.values()) - rating['corrected_rating'], sum(delta.values()) - total)
        max_error = max(max_error, *(abs(e) for e in errors))
        groups = {
            'added_qb_age': sum(after[k] for k in added if k.startswith('qb_')),
            'added_offense_descriptors': sum(after[k] for k in added if k.startswith('offense_')),
            'added_defense_descriptors': sum(after[k] for k in added if k.startswith('defense_')),
            'existing_feature_reweighting': sum(v for k, v in delta.items() if k not in added),
        }
        assert abs(sum(groups.values()) - total) < 1e-10
        rows.append({**rating, 'rating_change': total, 'groups': groups,
                     'feature_changes': delta, 'candidate_contributions': after,
                     'corrected_contributions': before, 'features': current[team]})
    assert max_error < 1e-10, max_error
    assert [r['team'] for r in rows] == sorted(current, key=lambda t: (-sum(new_terms[t].values()), t))
    folds = []
    for fold in read(CANDIDATE / 'run-20260908/fold-fits.json'):
        pp = fold['preprocessor']
        raw = {k: b / s for k, b, s in zip(pp['feature_names'], fold['coefficients'][1:], pp['scales'])}
        folds.append({'fit': fold['fit'], 'evaluation_season': fold['evaluation_season'],
                      'raw_unit_coefficients': {k: raw[k] for k in sorted(added | {'qb_experience_prior'})}})
    history = read(CANDIDATE / 'preflight-20260908-revised/historical-features.json')
    correlations = []
    for a, b in [('qb_age_centered', 'qb_age_squared'), ('qb_age_centered', 'qb_experience_prior'),
                 ('defense_role_weighted_age', 'defense_young_role_share')]:
        pairs = [(r['features'][a], r['features'][b]) for r in history
                 if r['features'][a] is not None and r['features'][b] is not None]
        doubled = pairs + [(-a, -b) for a, b in pairs]
        correlations.append({'features': [a, b], 'original_games': len(pairs),
                             'mirrored_training_correlation': statistics.correlation(*zip(*doubled))})
    with (CANDIDATE / 'run-20260908/matched-predictions.csv').open(newline='') as handle:
        predictions = list(csv.DictReader(handle))
    misses = []
    for row in predictions:
        actual, candidate, corrected = (float(row[k]) for k in ('actual_margin', 'candidate', 'corrected'))
        misses.append({k: row[k] for k in ('game_id', 'kickoff', 'season', 'week', 'home_team', 'away_team')} |
                      {'actual_margin': actual, 'candidate': candidate, 'corrected': corrected,
                       'candidate_absolute_error': abs(candidate - actual),
                       'corrected_absolute_error': abs(corrected - actual)})
    largest = sorted(misses, key=lambda r: -r['candidate_absolute_error'])[:10]
    added_error = sorted(misses, key=lambda r: -(r['candidate_absolute_error'] - r['corrected_absolute_error']))[:10]
    assert all(digest(path) == expected for path, expected in pins.items())
    return {
        'status': 'DESCRIPTIVE INPUT TRACE; EXPERIMENTAL / HOLD; NO ADOPTION',
        'inputs_as_of': diagnostic['inputs_as_of'],
        'method': 'Each feature contribution is centered across the same 32 teams. Changes separate added terms from reweighted existing terms. No coefficients fitted, features rebuilt, or sources captured.',
        'leakage_status': 'REVIEW REQUIRED: historical source publication vintage and recorded starters at decision time unresolved; no validated or causal player-value claims.',
        'checks': {'teams': 32, 'added_features': len(added), 'maximum_reconciliation_error': max_error,
                   'original_base_cells_identical': True, 'manifest_and_member_files_unchanged': len(pins)},
        'input_sha256': {str(p.relative_to(ROOT)): sha for p, sha in sorted(pins.items())},
        'ratings': rows, 'fold_coefficients': folds, 'collinearity_checks': correlations,
        'largest_historical_margin_misses': largest, 'largest_added_historical_errors': added_error,
        'historical_metrics': read(CANDIDATE / 'run-20260908/metrics.json'),
    }


if __name__ == '__main__':
    print(json.dumps(analyze(), indent=2, allow_nan=False))
