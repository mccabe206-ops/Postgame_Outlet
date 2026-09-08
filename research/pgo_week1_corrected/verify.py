"""Independent saved-arithmetic verification; never imports the trainer or fits."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from research.pgo_input_audit import verify_run as independent


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).resolve().parent
AUDIT = ROOT / 'research/pgo_input_audit/run-20260908-eligibility-attempt02'
AUDIT_SHA = '440734823c333f3f47229ba3edc2e43d50d84be62aa318c4c59395744d15899c'
TRAINER_SHA = '4691328c63049031147419f0960f3a51ea48c4bd0f381ea27988f0092e511074'
CHARTER_SHA = '643cdc172fc3ad15393989d8e9b021b3975833d6ae51f7ee162a837c39a25c12'
HELPER_SHA = '366514b4259eb13355cb1fe04e257a2bd1be7a50f8b087a1399abe06fe6bf3fc'
COMPARATORS = ('reference4', 'active4_exposure', 'active4_symmetric', 'pgo_v0', 'constant')


def verify(run, output):
    run, output = Path(run), Path(output)
    if output.exists() or run.resolve() in output.resolve().parents:
        raise ValueError('Verification must be a new file outside the immutable run')
    assert independent.sha(DIRECTORY / 'charter.md') == CHARTER_SHA
    assert independent.sha(DIRECTORY / 'train.py') == TRAINER_SHA
    assert independent.sha(Path(independent.__file__)) == HELPER_SHA
    members = independent.manifest(run)
    independent.manifest(AUDIT, AUDIT_SHA)
    independent.manifest(independent.PRIOR, independent.PRIOR_SHA)
    independent.manifest(independent.SNAPSHOT, independent.SNAPSHOT_SHA)
    receipt = independent.read(run / 'run-receipt.json')
    assert receipt['charter_sha256'] == CHARTER_SHA
    assert receipt['status'] == 'EXPERIMENTAL / HOLD'
    assert receipt['fresh_current_features_generated'] is False
    for name, digest in receipt['code_sha256'].items():
        assert independent.sha(ROOT / name) == digest, name
    original_sources = independent.read(independent.PRIOR / 'run-receipt.json')['source_inventory_before_after']
    assert len(original_sources) == 67
    for name, entry in original_sources.items():
        assert receipt['source_inventory'][name] == {k: entry[k] for k in ('bytes', 'sha256')}
        assert Path(entry['path']).stat().st_size == entry['bytes']
        assert independent.sha(entry['path']) == entry['sha256'], name
    expected_coverage = independent.read(AUDIT / 'run-receipt.json')['arm_construction']['active4_exposure']
    assert receipt['construction'] == expected_coverage
    saved = independent.csv_rows(run / 'matched-predictions.csv')
    previous = {r['game_id']: r for r in independent.csv_rows(AUDIT / 'matched-predictions.csv')}
    assert len(saved) == len({r['game_id'] for r in saved}) == len(previous) == 2127
    assert {r['game_id'] for r in saved} == set(previous)
    for row in saved:
        old = previous[row['game_id']]
        for key in ('season', 'week', 'kickoff', 'home_team', 'away_team', 'neutral_site'):
            assert row[key] == old[key], (row['game_id'], key)
        for key in ('actual_margin', *COMPARATORS):
            assert float(row[key]) == float(old[key]), (row['game_id'], key)
    historical = independent.read(run / 'historical-features.json')
    rowmap = {r['game_id']: r for r in historical}
    assert len(historical) == len(rowmap) == 3407
    fits = independent.read(run / 'fold-fits.json')
    oldfits = independent.read(AUDIT / 'fold-fits.json')['active4_exposure']
    assert len(fits) == len(oldfits) == 9
    assert [r['game_id'] for r in historical] == oldfits[-1]['training']['game_ids']
    maximum_prediction_error = 0.0
    symmetry = []
    final = independent.read(run / 'final-fit.json')
    for i, (fit, oldfit) in enumerate(zip(fits, oldfits)):
        assert fit['parameters'] == {'half_life_games': 4, 'alpha': 200.0, 'delta': 1.0}
        assert fit['training']['game_ids'] == oldfit['training']['game_ids']
        assert fit['validation'] == oldfit['validation']
        assert fit['training']['augmented_row_count'] == 2 * fit['training']['count']
        assert fit['training']['unique_game_count'] == fit['training']['count']
        assert fit['symmetry_invariants']['passed']
        if i < 8:
            assert fit['evaluation_season'] == 2018 + i
            assert max(rowmap[g]['season'] for g in fit['training']['game_ids']) < 2018 + i
            assert all(rowmap[g]['season'] == 2018 + i for g in fit['validation']['game_ids'])
            selected = [rowmap[g] for g in fit['validation']['game_ids']]
        else:
            assert fit['fit'] == 'final_2013_2025'
            selected = historical
            for key, value in fit.items():
                assert final[key] == value
        features = [row['features'] for row in selected]
        for row in selected:
            assert set(row['features']) == set(fit['preprocessor']['feature_names'])
        predictions = independent.predict(features, fit)
        assert np.isfinite(predictions).all()
        if i < 8:
            savedmap = {r['game_id']: r for r in saved}
            for row, pred in zip(selected, predictions):
                assert row['actual_margin'] == float(savedmap[row['game_id']]['actual_margin'])
                error = abs(float(pred) - float(savedmap[row['game_id']]['corrected']))
                maximum_prediction_error = max(maximum_prediction_error, error)
                assert error <= 1e-10
        names = fit['preprocessor']['feature_names']
        # Full signed venue/rest, all stored feature patterns, each extra
        # single missing feature and the entirely missing pattern.
        probes = features + [{name: 0.0 for name in names}]
        maximum_symmetry_error = 0.0
        patterns = [set(), *({name} for name in names), set(names)]
        for pattern in patterns:
            forward = [{k: None if k in pattern else v for k, v in row.items()} for row in probes]
            reverse = [{k: None if v is None else -v for k, v in row.items()} for row in forward]
            error = float(np.max(np.abs(independent.predict(forward, fit) + independent.predict(reverse, fit))))
            maximum_symmetry_error = max(maximum_symmetry_error, error)
        assert maximum_symmetry_error <= 1e-8
        assert all(abs(c) <= 1e-8 for c in fit['coefficients'][1 + len(names):])
        symmetry.append({'fold': i, 'rows': len(probes), 'missing_patterns': len(patterns),
                         'maximum_signed_swap_sum': maximum_symmetry_error})
    calculated_metrics = {key: independent.views(saved, key) for key in (*COMPARATORS, 'corrected')}
    calculated_bootstrap = {f'vs_{key}': independent.bootstrap(saved, 'corrected', key) for key in COMPARATORS}
    metric_file = independent.read(run / 'metrics.json')
    count, maximum_metric_error = 0, 0.0

    def compare(actual, expected):
        nonlocal count, maximum_metric_error
        if isinstance(expected, dict):
            assert set(actual) == set(expected)
            for key in expected:
                compare(actual[key], expected[key])
        elif isinstance(expected, list):
            assert len(actual) == len(expected)
            for a, b in zip(actual, expected):
                compare(a, b)
        elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
            assert math.isfinite(actual)
            error = abs(actual - expected)
            assert error <= 1e-10
            count += 1
            maximum_metric_error = max(maximum_metric_error, error)
        else:
            assert actual == expected

    compare(metric_file, {'metrics': calculated_metrics, 'paired_bootstrap': calculated_bootstrap})
    assert final['historical_context_sha256'] == independent.sha(run / 'historical-context.json')
    assert final['historical_features_sha256'] == independent.sha(run / 'historical-features.json')
    source_bytes = (json.dumps(receipt['source_inventory'], indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    assert final['source_inventory_sha256'] == hashlib.sha256(source_bytes).hexdigest()
    context = independent.read(run / 'historical-context.json')
    assert context['season'] == 2025 and set(context['ratings']) == set(independent.TEAMS)
    assert set(context['ratios']) == set(independent.TEAMS)
    assert set(context['current_strength']) == {'last_kickoff', 'qb_history', 'qb_population'}
    assert 'inputs' not in context['current_strength'] and set(context['inputs']) == {'colliding_gsis'}
    clock = context['current_strength']['last_kickoff']
    assert datetime.fromisoformat(clock) == max(datetime.fromisoformat(r['kickoff']) for r in historical)
    for state in (*context['current_strength']['qb_history'].values(), context['current_strength']['qb_population']):
        assert all(math.isfinite(value) for value in state.values())
    # All critical byte guards repeated after arithmetic.
    independent.manifest(run)
    independent.manifest(AUDIT, AUDIT_SHA)
    independent.manifest(independent.PRIOR, independent.PRIOR_SHA)
    independent.manifest(independent.SNAPSHOT, independent.SNAPSHOT_SHA)
    for name, digest in receipt['code_sha256'].items():
        assert independent.sha(ROOT / name) == digest
    for entry in original_sources.values():
        assert independent.sha(entry['path']) == entry['sha256']
    result = {'status': 'PASS', 'run_manifest_sha256': independent.sha(run / 'manifest.json'),
              'final_fit_sha256': independent.sha(run / 'final-fit.json'),
              'historical_context_sha256': independent.sha(run / 'historical-context.json'),
              'verifier_sha256': independent.sha(Path(__file__)), 'independent_helper_sha256': HELPER_SHA,
              'members_verified': len(members['files']), 'sources_verified': len(original_sources),
              'training_games': 3407, 'matched_predictions_verified': 2127,
              'maximum_prediction_error': maximum_prediction_error,
              'metric_and_bootstrap_values_verified': count, 'maximum_metric_error': maximum_metric_error,
              'symmetry': symmetry, 'metrics': calculated_metrics['corrected'],
              'paired_bootstrap': calculated_bootstrap,
              'context_clock': clock, 'context_provenance': 'Pinned ACT/exposure construction; no independent second historical walk',
              'no_fit_or_trainer_metric_helpers': True, 'promotion_status': 'HOLD'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=DIRECTORY / 'run-20260908')
    parser.add_argument('--output', type=Path, default=DIRECTORY / 'verification.json')
    args = parser.parse_args()
    result = verify(args.run, args.output)
    print(json.dumps({key: value for key, value in result.items() if key not in ('metrics', 'paired_bootstrap', 'symmetry')}, indent=2))
