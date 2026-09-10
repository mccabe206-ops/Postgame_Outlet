"""Independently replay saved candidate arithmetic; no trainer imports or fits.

The reviewed preparation is fixed. A receipt verifies saved arithmetic and
preservation, not fit authorization, source vintage, or prospective validity.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np

from research.pgo_input_audit import verify_run as independent


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).resolve().parent
IDENTITY = 'pgo-corrected-roster-candidate-2026-09-08'
CHARTER_SHA = 'a33f4d400dcbfe4a466ac332400067bae4c136592113b8368d4603800edf2b6b'
HELPER_SHA = '366514b4259eb13355cb1fe04e257a2bd1be7a50f8b087a1399abe06fe6bf3fc'
PREPARED = DIRECTORY / 'preflight-20260908-revised'
PREPARED_SHA = 'de0dcf0a80eb7daec12bd7c606a4d0f714496b782dd09d321296c9494d425a69'
CURRENT = DIRECTORY / 'current-preflight-20260908'
CURRENT_SHA = '0e35d51dc0bcdeb739a17b10e693d47d55e0f8b4810d59da4271dc85b6cf2200'
CORRECTED = ROOT / 'research/pgo_week1_corrected/run-20260908'
CORRECTED_SHA = '7530b3199f8a17ffec34f9e5351919ea67cb45df66e16befd655ab4e746f7a4c'
SOURCE = ROOT / 'docs/evidence/forecast-lab-2026/september-08-corrected'
SOURCE_SHA = '85fe35069145505410567709261663be0939b3ae2fbe05ad147da1d17fc54d83'
COMPARATORS = ('reference4', 'active4_exposure', 'active4_symmetric', 'pgo_v0', 'constant', 'corrected')
FEATURES = {'qb_age_centered', 'qb_age_squared'} | {
    f'{unit}_{term}' for unit in ('offense', 'defense')
    for term in ('role_weighted_age', 'young_role_share', 'role_weighted_draft_prior', 'rookie_draft_capital')}


def compare(actual, expected):
    """Require exact structure and finite numeric agreement; return count/error."""
    count, maximum = 0, 0.0
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and set(actual) == set(expected)
        pairs = [(actual[k], expected[k]) for k in expected]
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected)
        pairs = zip(actual, expected)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert isinstance(actual, (int, float)) and not isinstance(actual, bool)
        assert math.isfinite(actual) and math.isfinite(expected)
        error = abs(actual - expected)
        assert error <= 1e-10, (actual, expected)
        return 1, error
    else:
        assert type(actual) is type(expected) and actual == expected, (actual, expected)
        return 0, 0.0
    for a, b in pairs:
        checked, error = compare(a, b)
        count += checked
        maximum = max(maximum, error)
    return count, maximum


def screen(metrics, interval):
    candidate, control = metrics['candidate'], metrics['corrected']
    expected_seasons = list(range(2018, 2026))
    assert [r['season'] for r in candidate['seasons']] == expected_seasons
    assert [r['season'] for r in control['seasons']] == expected_seasons
    wins = sum(a['mae'] < b['mae'] for a, b in zip(candidate['seasons'], control['seasons']))
    checks = dict(lower_pooled_mae=candidate['overall']['mae'] < control['overall']['mae'],
                  at_least_five_of_eight_seasons=wins >= 5, positive_interval_lower=interval['lower'] > 0)
    return dict(status='PASS' if all(checks.values()) else 'FAIL', checks=checks, season_wins=wins,
                scientific_status='EXPERIMENTAL / HOLD', early_weeks='DESCRIPTIVE_ONLY')


def symmetry(fit, features):
    names = fit['preprocessor']['feature_names']
    coefficients = fit['coefficients']
    assert np.isfinite(coefficients).all()
    assert abs(coefficients[0]) <= 1e-8
    assert all(abs(c) <= 1e-8 for c in coefficients[1 + len(names):])
    patterns = [set(), *({name} for name in names), set(names)]
    maximum = 0.0
    for pattern in patterns:
        # Exercise stored patterns with venue/rest signed, and then neutralized.
        for neutral in (False, True):
            forward = [{k: None if k in pattern else 0.0 if neutral and k in
                        ('home_field', 'rest_difference') else v for k, v in row.items()}
                       for row in features]
            reverse = [{k: None if v is None else -v for k, v in row.items()} for row in forward]
            identical = [{name: None if name in pattern else 0.0 for name in names}]
            first = independent.predict(forward, fit)
            second = independent.predict(reverse, fit)
            zero = independent.predict(identical, fit)
            assert np.isfinite(first).all() and np.isfinite(second).all() and np.isfinite(zero).all()
            maximum = max(maximum, float(np.max(np.abs(first + second))), abs(float(zero[0])))
    assert maximum <= 1e-8, maximum
    return dict(rows=len(features), missing_patterns=len(patterns), signed_and_neutral=True,
                maximum_error=maximum, tolerance=1e-8)


def verify(run, output):
    if not __debug__:
        raise RuntimeError('Run without -O; assertions are verification guards')
    run, output = Path(run).resolve(), Path(output).resolve()
    if (output.exists() or output.parent != DIRECTORY or output.suffix != '.json'
            or run == output or run in output.parents):
        raise ValueError('Verification must be a new JSON file directly in candidate research, outside the run')
    if run.parent != DIRECTORY:
        raise ValueError('Candidate run must be directly in candidate research')
    started = datetime.now(timezone.utc).isoformat()
    verifier_sha = independent.sha(Path(__file__))
    assert independent.sha(Path(independent.__file__)) == HELPER_SHA
    manifests = {PREPARED: PREPARED_SHA, CURRENT: CURRENT_SHA, CORRECTED: CORRECTED_SHA,
                 SOURCE: SOURCE_SHA, independent.PRIOR: independent.PRIOR_SHA,
                 independent.SNAPSHOT: independent.SNAPSHOT_SHA,
                 run: independent.sha(run / 'manifest.json')}
    before = {str(path): independent.manifest(path, digest) for path, digest in manifests.items()}
    assert before[str(run)]['identity'] == IDENTITY
    assert set(before[str(run)]['files']) == {'run-start.json', 'run-receipt.json', 'fold-fits.json',
                                           'final-fit.json', 'matched-predictions.csv', 'metrics.json'}
    preparation = independent.read(PREPARED / 'run-receipt.json')
    current = independent.read(CURRENT / 'run-receipt.json')
    receipt = independent.read(run / 'run-receipt.json')
    run_start = independent.read(run / 'run-start.json')
    assert preparation['kind'] == 'FEATURE_PREPARATION_NO_FIT' and preparation['model_fits'] == 0
    assert current['kind'] == 'CURRENT_FEATURE_DIAGNOSTIC_NO_FIT' and current['model_fits'] == 0
    assert receipt['kind'] == 'ONE_FIXED_CANDIDATE_FIT' and receipt['model_fits'] == 9
    assert receipt['training_games'] == 3407 and receipt['evaluation_games'] == 2127
    for recorded in (preparation, current, receipt, run_start):
        assert recorded['identity'] == IDENTITY and recorded['charter_sha256'] == CHARTER_SHA
        assert recorded['code_sha256'] == preparation['code_sha256']
        assert recorded['sources'] == preparation['sources']
        assert recorded['corrected_manifest_sha256'] == CORRECTED_SHA
        assert recorded['current_source_manifest_sha256'] == SOURCE_SHA
    for recorded in (current, receipt, run_start):
        assert recorded['prepared_manifest_sha256'] == PREPARED_SHA
    for recorded in (preparation, current, receipt):
        assert recorded['status'] == 'EXPERIMENTAL / HOLD'
        assert datetime.fromisoformat(recorded['completed_at']) >= datetime.fromisoformat(recorded['started_at'])
    assert run_start['status'] == 'STARTED_INCOMPLETE'
    assert all(receipt[key] == value for key, value in run_start.items() if key != 'status')
    original = independent.read(independent.PRIOR / 'run-receipt.json')['source_inventory_before_after']
    original = {key if ':' in key else key + ':None': entry for key, entry in original.items()}
    sources = preparation['sources']
    assert set(original) == set(sources) and len(sources) == 67
    for key, entry in sources.items():
        assert entry == {k: original[key][k] for k in ('path', 'bytes', 'sha256')}, key
    code = preparation['code_sha256']
    assert len(code) == 23

    def preserved():
        assert independent.sha(Path(__file__)) == verifier_sha
        assert independent.sha(Path(independent.__file__)) == HELPER_SHA
        for path, digest in manifests.items():
            assert independent.manifest(path, digest) == before[str(path)]
        for path, digest in code.items():
            assert independent.sha(ROOT / path) == digest, path
        for entry in sources.values():
            assert Path(entry['path']).stat().st_size == entry['bytes']
            assert independent.sha(entry['path']) == entry['sha256'], entry['path']

    preserved()
    historical = independent.read(PREPARED / 'historical-features.json')
    old_history = independent.read(CORRECTED / 'historical-features.json')
    rowmap = {r['game_id']: r for r in historical}
    assert len(historical) == len(old_history) == len(rowmap) == 3407
    assert set(r['season'] for r in historical) == set(range(2013, 2026))
    for row, old in zip(historical, old_history):
        assert all(row[k] == old[k] for k in ('game_id', 'season', 'week', 'kickoff', 'actual_margin'))
        assert set(row['features']) == set(old['features']) | FEATURES
        assert all(value is None or math.isfinite(value) for value in row['features'].values())
        for name, value in old['features'].items():
            actual = row['features'][name]
            assert (value is None) == (actual is None)
            assert value is None or abs(actual - value) <= 1e-12, (row['game_id'], name)
    saved = independent.csv_rows(run / 'matched-predictions.csv')
    previous = independent.csv_rows(CORRECTED / 'matched-predictions.csv')
    savedmap = {r['game_id']: r for r in saved}
    assert len(saved) == len(savedmap) == len(previous) == 2127
    assert [r['game_id'] for r in saved] == [r['game_id'] for r in previous]
    assert set(savedmap) == {r['game_id'] for r in historical if r['season'] >= 2018}
    for row, old in zip(saved, previous):
        assert set(row) == set(old) | {'candidate'}
        for key, value in old.items():
            if key in ('actual_margin', *COMPARATORS):
                assert math.isfinite(float(row[key])) and float(row[key]) == float(value)
            else:
                assert row[key] == value, (row['game_id'], key)
        assert math.isfinite(float(row['candidate']))

    fits = independent.read(run / 'fold-fits.json')
    oldfits = independent.read(CORRECTED / 'fold-fits.json')
    final = independent.read(run / 'final-fit.json')
    assert len(fits) == len(oldfits) == 9
    assert final == dict(identity=IDENTITY, status='EXPERIMENTAL / HOLD', charter_sha256=CHARTER_SHA,
                         prepared_manifest_sha256=PREPARED_SHA, **fits[-1])
    maximum_prediction_error, verified_ids, symmetry_checks = 0.0, [], []
    for index, (fit, oldfit) in enumerate(zip(fits, oldfits)):
        season = 2018 + index if index < 8 else None
        training = [r for r in historical if season is None or r['season'] < season]
        validation = [r for r in historical if r['season'] == season]
        assert fit['fit'] == (f'fold_{season}' if season else 'final_2013_2025')
        assert fit['evaluation_season'] == season
        assert fit['parameters'] == {'half_life_games': 4, 'alpha': 200.0, 'delta': 1.0}
        assert fit['training'] == oldfit['training']
        assert fit['validation'] == oldfit['validation'] == {
            'count': len(validation), 'game_ids': [r['game_id'] for r in validation]}
        assert fit['training'] == dict(count=len(training), unique_game_count=len(training),
            augmented_row_count=2 * len(training), season_min=2013,
            season_max=season - 1 if season else 2025, game_ids=[r['game_id'] for r in training])
        if validation:
            assert max(datetime.fromisoformat(r['kickoff']) for r in training) < min(
                datetime.fromisoformat(r['kickoff']) for r in validation)
        pp = fit['preprocessor']
        names = sorted(historical[0]['features'])
        assert pp['feature_names'] == names
        assert len(fit['coefficients']) == 1 + len(names) + len(pp['missing_features'])
        raw = np.asarray([[r['features'][name] for name in names] for r in training], dtype=float)
        assert pp['missing_features'] == [name for i, name in enumerate(names) if np.isnan(raw[:, i]).any()]
        for name in FEATURES:
            observed = raw[:, names.index(name)]
            observed = observed[~np.isnan(observed)]
            assert len(observed) and np.isfinite(observed).all() and np.ptp(observed) > 0
        # Recompute only training preprocessing arithmetic, never coefficients.
        doubled = np.concatenate((raw, -raw))
        medians = np.nanmedian(doubled, axis=0)
        scales = np.where(np.isnan(doubled), medians, doubled).std(axis=0)
        scales[scales == 0] = 1.0
        compare(pp['medians'], medians.tolist())
        compare(pp['scales'], scales.tolist())
        assert np.max(np.abs(medians)) <= 1e-12
        selected = validation if season else historical
        features = [r['features'] for r in selected]
        predictions = independent.predict(features, fit)
        assert np.isfinite(predictions).all()
        if season:
            for row, prediction in zip(selected, predictions):
                savedrow = savedmap[row['game_id']]
                assert all(str(row[k]) == savedrow[k] for k in ('season', 'week', 'kickoff'))
                assert row['actual_margin'] == float(savedrow['actual_margin'])
                error = abs(float(prediction) - float(savedrow['candidate']))
                maximum_prediction_error = max(maximum_prediction_error, error)
                assert error <= 1e-10, row['game_id']
                verified_ids.append(row['game_id'])
        assert fit['symmetry_invariants']['passed'] is True
        assert fit['candidate_missing_pattern_symmetry']['maximum_error'] <= 1e-8
        symmetry_checks.append(dict(fit=fit['fit'], **symmetry(fit, features)))
    assert len(verified_ids) == len(set(verified_ids)) == 2127 and set(verified_ids) == set(savedmap)
    metrics = {key: independent.views(saved, key) for key in (*COMPARATORS, 'candidate')}
    intervals = {f'vs_{key}': independent.bootstrap(saved, 'candidate', key) for key in COMPARATORS}
    decision = screen(metrics, intervals['vs_corrected'])
    count, maximum_metric_error = compare(independent.read(run / 'metrics.json'),
        dict(metrics=metrics, paired_bootstrap=intervals, further_study_screen=decision))
    preserved()
    result = dict(status='PASS', started_at=started, completed_at=datetime.now(timezone.utc).isoformat(),
        identity=IDENTITY, run_manifest_sha256=manifests[run], final_fit_sha256=independent.sha(run / 'final-fit.json'),
        verifier_sha256=verifier_sha, independent_helper_sha256=HELPER_SHA,
        manifest_sha256={str(path): digest for path, digest in manifests.items()},
        manifest_member_counts={path: len(value['files']) for path, value in before.items()},
        code_sha256_before_after=code, sources_before_after=sources, preservation_status='PASS',
        training_games=3407, serialized_fits_verified=9, matched_predictions_verified=2127,
        maximum_prediction_error=maximum_prediction_error, metric_and_bootstrap_values_verified=count,
        maximum_metric_error=maximum_metric_error, symmetry=symmetry_checks,
        metrics=metrics, paired_bootstrap=intervals, further_study_screen=decision,
        no_fit_or_trainer_helpers=True, promotion_status='HOLD',
        limitations=['No independent second historical feature walk or Huber coefficient refit.',
                     'Saved current features are hash-verified; no candidate current ratings are generated or verified.',
                     'Historical source publication vintage remains REVIEW REQUIRED; recorded starters are not verified T-60 expectations.',
                     'Reused 2018-2025 outcomes are diagnostic, not fresh prospective confirmation.',
                     'Verification does not supply the external Fable verdict, fit authorization, issuance, or adoption.'])
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=DIRECTORY / 'run-20260908')
    parser.add_argument('--output', type=Path, default=DIRECTORY / 'saved-fit-verification.json')
    args = parser.parse_args()
    result = verify(args.run, args.output)
    print(json.dumps({k: result[k] for k in ('status', 'run_manifest_sha256', 'matched_predictions_verified',
                                          'maximum_prediction_error', 'further_study_screen', 'promotion_status')}, indent=2))
