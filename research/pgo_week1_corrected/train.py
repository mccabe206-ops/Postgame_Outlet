"""One fixed corrected construction; retrospective diagnostics remain HOLD.

Run once in a dedicated process: python -B -m research.pgo_week1_corrected.train
Fresh operational features and issuance are deliberately outside this trainer.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import json
import math
from pathlib import Path
import platform

import numpy as np

from research.pgo_input_audit import audit_model as audit


ROOT = Path(__file__).resolve().parents[2]
CHARTER = Path(__file__).with_name('charter.md')
CHARTER_SHA256 = '643cdc172fc3ad15393989d8e9b021b3975833d6ae51f7ee162a837c39a25c12'
DEFAULT_OUTPUT = Path(__file__).with_name('run-20260908')
AUDIT_RUN = ROOT / 'research/pgo_input_audit/run-20260908-eligibility-attempt02'
AUDIT_MANIFEST_SHA256 = '440734823c333f3f47229ba3edc2e43d50d84be62aa318c4c59395744d15899c'
IDENTITY = 'pgo-week1-corrected-2026-09-08'
COMPARATORS = ('reference4', 'active4_exposure', 'active4_symmetric', 'pgo_v0', 'constant')
NEW_CODE = ('research/pgo_week1_corrected/train.py', 'tests/test_pgo_week1_corrected.py')


def portable_context(context, inputs):
    """Export only immutable accumulators needed by a fresh ACT/QB constructor."""
    if context['season'] != 2025:
        raise ValueError('Historical context must end in the 2025 season')
    state = context['current_strength']
    result = {
        'schema_version': 1, 'identity': IDENTITY, 'season': 2025,
        'ratings': dict(context['ratings']),
        'ratios': {team: {name: ratio.value for name, ratio in values.items()}
                   for team, values in context['ratios'].items()},
        'current_strength': {name: state[name] for name in
                             ('last_kickoff', 'qb_history', 'qb_population')},
        'inputs': {'colliding_gsis': sorted(inputs.get('colliding_gsis', ()))},
    }
    # JSON both rejects nonfinite values and detaches the exported accumulators.
    return json.loads(audit.base._json_bytes(result))


def validate_rows(rows, saved, expected_ids, expected_features):
    ids = [row.game_id for row in rows]
    if len(ids) != len(set(ids)) or ids != expected_ids:
        raise ValueError('Training cohort or original ordering differs')
    seen = set()
    for row in rows:
        if set(row.features) != expected_features or set(row.features) & audit.ROSTER_COACH:
            raise ValueError('Corrected feature inventory differs')
        if not math.isfinite(row.actual_margin) or any(
                value is not None and not math.isfinite(value) for value in row.features.values()):
            raise ValueError('Nonfinite historical value')
        if row.season in audit.base.EVALUATION_SEASONS:
            old = saved.get(row.game_id)
            if old is None or (row.season, row.week, row.kickoff, row.actual_margin) != (
                    int(old['season']), int(old['week']), old['kickoff'], float(old['actual_margin'])):
                raise ValueError('Matched game identity or target differs')
            seen.add(row.game_id)
    if seen != set(saved):
        raise ValueError('Evaluation cohort differs')


def start_run(output, receipt):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    audit.base._write_exclusive(output / 'run-start.json', audit.base._json_bytes(receipt))


def fit_combined(rows):
    return audit._fit_arm('active4_symmetric', rows)


def replay(rows, fit):
    """Reconstruct predictions using JSON fields, independently of live objects."""
    p = fit['preprocessor']
    values = []
    for row in rows:
        x = [(0.0 if row.features.get(name) is None else
              (row.features[name] - median) / scale)
             for name, median, scale in zip(p['feature_names'], p['medians'], p['scales'])]
        x += [float(row.features.get(name) is None) for name in p['missing_features']]
        values.append(fit['coefficients'][0] + float(np.dot(x, fit['coefficients'][1:])))
    return values


def run(output=DEFAULT_OUTPUT):
    output = Path(output).resolve()
    if output.parent != CHARTER.parent.resolve() or output.exists():
        raise ValueError('Use a new run directory inside the corrected research directory')
    if audit.sha256(CHARTER.read_bytes()) != CHARTER_SHA256:
        raise ValueError('Corrected charter differs')
    audit._verified_manifest(AUDIT_RUN, AUDIT_MANIFEST_SHA256)
    audit._verified_manifest(audit.PRIOR_RUN, audit.PRIOR_RUN_MANIFEST_SHA256)
    audit._verified_manifest(audit.SNAPSHOT_DIR, audit.SNAPSHOT_MANIFEST_SHA256)
    previous = json.loads((AUDIT_RUN / 'run-receipt.json').read_bytes())
    prior = json.loads((audit.PRIOR_RUN / 'run-receipt.json').read_bytes())
    protected = dict(previous['code_sha256'])
    protected.update({name: audit.sha256((ROOT / name).read_bytes()) for name in NEW_CODE})
    protected[str(CHARTER)] = CHARTER_SHA256
    audit.base.verify_protected(protected)
    all_paths = audit._paths_from_prior(prior)
    paths = {key: path for key, path in all_paths.items() if key != ('current_roster', 2026)}
    if len(all_paths) != 67 or len(paths) != 66:
        raise ValueError('Historical source inventory differs')
    source_inventory = {name: {k: entry[k] for k in ('bytes', 'sha256')}
                        for name, entry in prior['source_inventory_before_after'].items()}
    if source_inventory != previous['source_inventory_before_after']:
        raise ValueError('Source inventory differs from the reviewed audit')
    start = {'schema_version': 1, 'identity': IDENTITY,
             'status': 'STARTED_INCOMPLETE_UNTIL_MANIFEST_EXISTS',
             'started_at': datetime.now(timezone.utc).isoformat(),
             'charter_sha256': CHARTER_SHA256, 'audit_manifest_sha256': AUDIT_MANIFEST_SHA256,
             'code_sha256': protected, 'source_inventory': source_inventory,
             'environment': {'python': platform.python_version(), 'numpy': np.__version__}}
    start_run(output, start)
    print('Building the one fixed ACT/exposure historical dataset', flush=True)
    old_snapshot = audit.pgo_forecast_snapshot.load_snapshot(audit.SNAPSHOT_DIR)
    rows, context, inputs, unused_old_features, coverage = audit.build_arm(
        paths, old_snapshot, audit.SNAPSHOT_DIR, 'active4_exposure')
    historical_context = portable_context(context, inputs)
    del context, inputs, unused_old_features
    gc.collect()
    saved = {r['game_id']: r for r in audit.pgo_sources.open_csv(AUDIT_RUN / 'matched-predictions.csv')}
    prior_fits = json.loads((AUDIT_RUN / 'fold-fits.json').read_bytes())['active4_exposure']
    validate_rows(rows, saved, prior_fits[-1]['training']['game_ids'],
                  set(prior_fits[-1]['preprocessor']['feature_names']))
    if len(rows) != 3407 or len(saved) != 2127:
        raise ValueError('Historical or evaluation game count differs')
    matched = {key: {**{k: r[k] for k in ('game_id', 'kickoff', 'home_team', 'away_team')},
                     'season': int(r['season']), 'week': int(r['week']),
                     'neutral_site': r['neutral_site'] == 'True',
                     'actual_margin': float(r['actual_margin']),
                     **{name: float(r[name]) for name in COMPARATORS}}
               for key, r in saved.items()}
    fits, maximum_replay_error = [], 0.0
    folds = [(f'fold_{season}', season, training, validation)
             for season, training, validation in audit.base.expanding_folds(rows)]
    folds.append(('final_2013_2025', None, rows, ()))
    for label, season, training, validation in folds:
        print(f'Fitting corrected {label}', flush=True)
        pp, coefficients, mirrored = fit_combined(training)
        fit = audit._fit_receipt(pp, coefficients, training, validation, 4,
                                 name='active4_symmetric', fit_training=mirrored)
        fit.update({'evaluation_season': season} if season is not None else {'fit': label})
        # This invokes symmetry checks before accepting any fold prediction.
        probe_rows = validation if season is not None else training
        predictions = audit.base._predict_rows(probe_rows, pp, coefficients)
        restored = replay(probe_rows, json.loads(audit.base._json_bytes(fit)))
        error = max(abs(a - b) for a, b in zip(predictions, restored))
        if not all(math.isfinite(v) for v in predictions + restored) or error > 1e-10:
            raise ValueError('Serialized fit replay differs or is nonfinite')
        maximum_replay_error = max(maximum_replay_error, error)
        if season is not None:
            for row, prediction in zip(validation, predictions):
                matched[row.game_id]['corrected'] = prediction
        fits.append(fit)
        del pp, coefficients, mirrored
    matched_rows = sorted(matched.values(), key=lambda r: (r['season'], r['week'], r['kickoff'], r['game_id']))
    metrics = {name: audit.metric_views(matched_rows, name) for name in (*COMPARATORS, 'corrected')}
    intervals = {f'vs_{name}': audit.base.season_block_bootstrap(
        matched_rows, 'corrected', name, seed=20260908) for name in COMPARATORS}
    historical_rows = [{'game_id': r.game_id, 'season': r.season, 'week': r.week,
                        'kickoff': r.kickoff, 'actual_margin': r.actual_margin, 'features': r.features}
                       for r in rows]
    artifacts = {'historical-context.json': audit.base._json_bytes(historical_context),
                 'historical-features.json': audit.base._json_bytes(historical_rows),
                 'matched-predictions.csv': audit.base._csv_bytes(matched_rows),
                 'fold-fits.json': audit.base._json_bytes(fits),
                 'metrics.json': audit.base._json_bytes({'metrics': metrics, 'paired_bootstrap': intervals})}
    final_fit = {'schema_version': 1, 'identity': IDENTITY, 'status': 'EXPERIMENTAL / HOLD',
                 'charter_sha256': CHARTER_SHA256,
                 'source_inventory_sha256': audit.sha256(audit.base._json_bytes(source_inventory)),
                 'historical_context_sha256': audit.sha256(artifacts['historical-context.json']),
                 'historical_features_sha256': audit.sha256(artifacts['historical-features.json']),
                 **fits[-1]}
    artifacts['final-fit.json'] = audit.base._json_bytes(final_fit)
    # Recheck every old member, actual configured source, and helper after fitting.
    audit._paths_from_prior(prior)
    audit._verified_manifest(AUDIT_RUN, AUDIT_MANIFEST_SHA256)
    audit._verified_manifest(audit.PRIOR_RUN, audit.PRIOR_RUN_MANIFEST_SHA256)
    audit._verified_manifest(audit.SNAPSHOT_DIR, audit.SNAPSHOT_MANIFEST_SHA256)
    audit.base.verify_protected(protected)
    receipt = {**start, 'status': 'EXPERIMENTAL / HOLD',
               'completed_at': datetime.now(timezone.utc).isoformat(),
               'historical_source_vintage': 'REVIEW REQUIRED',
               'validation_scope': 'Reused historical seasons; diagnostic only, no promotion',
               'construction': coverage, 'training_games': len(rows), 'evaluation_games': len(matched_rows),
               'maximum_serialized_replay_error': maximum_replay_error,
               'fresh_current_features_generated': False,
               'protected_sources_and_members_before_after': 'PASS'}
    artifacts['run-receipt.json'] = audit.base._json_bytes(receipt)
    for name, raw in artifacts.items():
        audit.base._write_exclusive(output / name, raw)
    artifacts['run-start.json'] = (output / 'run-start.json').read_bytes()
    audit.base._write_exclusive(output / 'manifest.json', audit.base._json_bytes({
        'schema_version': 1, 'identity': IDENTITY,
        'files': {name: {'sha256': audit.sha256(raw), 'bytes': len(raw)} for name, raw in artifacts.items()}}))
    print(json.dumps({'status': receipt['status'], 'output': str(output),
                      'mae': metrics['corrected']['overall']['mae']}), flush=True)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    run(parser.parse_args().output)
