"""Check the frozen neutral-margin inconsistency without fitting or writing data."""

import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pgo_forecast_snapshot

SNAPSHOT = ROOT / 'docs/evidence/forecast-lab-2026/september-07'
MANIFEST_SHA256 = '43bdeee73a2d3301eedbcecc7d291dc9ebe68cf196860e7217326570e4fe2f42'


def independent_score(features, fit):
    """Scalar implementation of the saved affine transform, including missing flags."""
    pp = fit['preprocessor']
    raw = [features.get(name) for name in pp['feature_names']]
    transformed = [0.0 if value is None else (value - median) / scale
                   for value, median, scale in zip(raw, pp['medians'], pp['scales'])]
    transformed += [float(features.get(name) is None) for name in pp['missing_features']]
    assert len(transformed) + 1 == len(fit['coefficients'])
    return fit['coefficients'][0] + math.fsum(
        coefficient * value for coefficient, value in zip(fit['coefficients'][1:], transformed))


def main():
    raw_manifest = (SNAPSHOT / 'manifest.json').read_bytes()
    assert hashlib.sha256(raw_manifest).hexdigest() == MANIFEST_SHA256
    manifest = json.loads(raw_manifest)
    for name in ('snapshot.json', 'fit.json'):
        raw = (SNAPSHOT / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest['files'][name]['sha256']
        assert len(raw) == manifest['files'][name]['bytes']
    snapshot = json.loads((SNAPSHOT / 'snapshot.json').read_bytes())
    fit = json.loads((SNAPSHOT / 'fit.json').read_bytes())
    assert snapshot['fit'] == fit
    teams = {row['team']: row for row in snapshot['teams']}
    pp, beta = fit['preprocessor'], fit['coefficients']
    neutral_constant = beta[0] - math.fsum(
        b * median / scale for b, median, scale in zip(beta[1:], pp['medians'], pp['scales']))
    game = {'location': 'Neutral', 'home_rest': 7.0, 'away_rest': 7.0}
    observations = {}
    for home, away in (('NE', 'LAR'), ('LAR', 'NE'), ('NE', 'NE')):
        h, a = teams[home]['features'], teams[away]['features']
        assert all(value is not None for value in (*h.values(), *a.values()))
        difference = {name: h[name] - a[name] for name in h}
        difference.update(home_field=0.0, rest_difference=0.0)
        independent = independent_score(difference, fit)
        production = pgo_forecast_snapshot._margin(h, a, game, fit)
        assert math.isclose(independent, production, rel_tol=0, abs_tol=1e-10)
        rating_gap = teams[home]['rating'] - teams[away]['rating']
        assert math.isclose(independent, rating_gap + neutral_constant, rel_tol=0, abs_tol=1e-10)
        observations[f'{home}-{away}'] = {'margin': independent, 'rating_difference': rating_gap}
    forward, reverse = (observations[key]['margin'] for key in ('NE-LAR', 'LAR-NE'))
    identity = observations['NE-NE']['margin']
    assert abs(identity) > 1e-8, 'Expected frozen identity violation was not detected'
    assert abs(forward + reverse) > 1e-8, 'Expected frozen reversal violation was not detected'
    assert math.isclose(identity, -0.8011250871186806, rel_tol=0, abs_tol=1e-10)
    print(json.dumps({'status': 'FROZEN_INCONSISTENCY_REPRODUCED',
        'snapshot_manifest_sha256': MANIFEST_SHA256, 'raw_intercept': beta[0],
        'effective_neutral_constant': neutral_constant, 'observations': observations,
        'identity_violation_detected': True, 'reversal_violation_detected': True,
        'illustrative_neutral_odd_projection': (forward - reverse) / 2,
        'fits_run': 0, 'artifacts_modified': 0}, indent=2))


if __name__ == '__main__':
    main()
