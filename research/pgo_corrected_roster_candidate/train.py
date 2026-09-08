"""Prepare the fixed candidate without fitting; --fit requires prior review.

Preparation and training are exclusive, separate receipts. Training reuses the
verified prepared feature bytes, avoiding a second historical walk.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform

from research.pgo_corrected_roster_candidate import adapter as a

audit, corrected = a.audit, a.corrected
ROOT = corrected.ROOT
DIRECTORY = Path(__file__).resolve().parent
CHARTER_SHA256 = 'a33f4d400dcbfe4a466ac332400067bae4c136592113b8368d4603800edf2b6b'
CORRECTED_RUN = ROOT / 'research/pgo_week1_corrected/run-20260908'
CORRECTED_MANIFEST = '7530b3199f8a17ffec34f9e5351919ea67cb45df66e16befd655ab4e746f7a4c'
SOURCE_DIR = ROOT / 'docs/evidence/forecast-lab-2026/september-08-corrected'
SOURCE_MANIFEST = '85fe35069145505410567709261663be0939b3ae2fbe05ad147da1d17fc54d83'
COMPARATORS = (*corrected.COMPARATORS, 'corrected')
V2_ROOT = Path('D:/CodexWorktrees/Postgame_Outlet-pgo-v2-roster')
V2_PINS = {'pgo_challenger.py': '70ab4a09f793bc61accae02490e9dba2bb308ebc95e58a324db0e69ddabfd3af',
           'pgo_roster_challenger.py': '2b37f2e2fb182d9e42692ab9c05ad731dd7b76271bccbe3c45294b64096fb3d1',
           'research/pgo_v2/backtest.json': 'cb199b67c582b09e8e67e05b8d6e9f236ef69107a3daa3251733b0fc4b5412c3'}


def pins():
    if audit.sha256((DIRECTORY / 'charter.md').read_bytes()) != CHARTER_SHA256:
        raise ValueError('Candidate charter differs')
    audit._verified_manifest(CORRECTED_RUN, CORRECTED_MANIFEST)
    audit._verified_manifest(SOURCE_DIR, SOURCE_MANIFEST)
    audit._verified_manifest(audit.PRIOR_RUN, audit.PRIOR_RUN_MANIFEST_SHA256)
    receipt = json.loads((CORRECTED_RUN / 'run-receipt.json').read_bytes())
    protected = dict(receipt['code_sha256'])
    protected['research/pgo_v1/sources.lock.json'] = '3a7673ac4617d57954cb56954f2216226a358c7b187b1e3ce62994a6f2b3fd29'
    for name, digest in V2_PINS.items():
        protected[str(V2_ROOT / name)] = digest
    protected['pgo_forecast_corrected.py'] = audit.sha256((ROOT / 'pgo_forecast_corrected.py').read_bytes())
    for name in ('adapter.py', 'train.py', 'test_candidate.py', 'test_temporal.py',
                 'charter.md', 'implementation-status.json'):
        path = DIRECTORY / name
        protected[str(path)] = audit.sha256(path.read_bytes())
    audit.base.verify_protected(protected)
    prior = json.loads((audit.PRIOR_RUN / 'run-receipt.json').read_bytes())
    paths = audit._paths_from_prior(prior)
    if len(paths) != 67:
        raise ValueError('Locked source count differs')
    return protected, paths


def start(output, kind, **bindings):
    output = Path(output).resolve()
    if output.parent != DIRECTORY or output.exists():
        raise ValueError('Use a new exclusive directory under candidate research')
    protected, paths = pins()
    receipt = dict(identity=a.IDENTITY, status='STARTED_INCOMPLETE', kind=kind,
                   started_at=datetime.now(timezone.utc).isoformat(),
                   charter_sha256=CHARTER_SHA256, code_sha256=protected,
                   corrected_manifest_sha256=CORRECTED_MANIFEST,
                   current_source_manifest_sha256=SOURCE_MANIFEST,
                   sources={f'{key[0]}:{key[1]}': dict(path=str(path),
                            sha256=audit.sha256(path.read_bytes()), bytes=path.stat().st_size)
                            for key, path in paths.items()},
                   environment=dict(python=platform.python_version(), numpy=audit.np.__version__), **bindings)
    corrected.start_run(output, receipt)
    return output, receipt, paths


def finish(output, receipt, artifacts):
    protected, _ = pins()
    if protected != receipt['code_sha256']:
        raise ValueError('Code changed during candidate operation')
    receipt = {**receipt, 'status': 'EXPERIMENTAL / HOLD',
               'completed_at': datetime.now(timezone.utc).isoformat()}
    artifacts['run-receipt.json'] = audit.base._json_bytes(receipt)
    for name, raw in artifacts.items():
        audit.base._write_exclusive(output / name, raw)
    if receipt.get('raw_roster_inventory_sha256'):
        raw = (output / 'raw-roster-inventory.json').read_bytes()
        if audit.sha256(raw) != receipt['raw_roster_inventory_sha256']:
            raise ValueError('Raw roster inventory changed during preparation')
        artifacts['raw-roster-inventory.json'] = raw
    artifacts['run-start.json'] = (output / 'run-start.json').read_bytes()
    audit.base._write_exclusive(output / 'manifest.json', audit.base._json_bytes({
        'identity': a.IDENTITY, 'files': {name: dict(sha256=audit.sha256(raw), bytes=len(raw))
                                         for name, raw in artifacts.items()}}))
    return receipt


def prepare(output):
    output, receipt, paths = start(output, 'FEATURE_PREPARATION_NO_FIT')
    raw_inventory = a.raw_inventory(paths)
    raw_bytes = audit.base._json_bytes(raw_inventory)
    audit.base._write_exclusive(output / 'raw-roster-inventory.json', raw_bytes)
    receipt['raw_roster_inventory_sha256'] = audit.sha256(raw_bytes)
    if any(entry['counts'].get('ID_less_ACT_rows', 0) for entry in raw_inventory.values()):
        raise ValueError('Raw historical ACT roster contains ID-less rows; inventory preserved')
    print('Constructing the fixed candidate; no fitting', flush=True)
    rows, context, inputs, coverage = a.build_rows(paths)
    saved = json.loads((CORRECTED_RUN / 'historical-features.json').read_bytes())
    a.validate_base(rows, saved)
    a.validate_variation(rows)
    if len(rows) != 3407 or len(coverage) != 6814:
        raise ValueError('Historical coverage count differs')
    portable = a.portable_context(context, inputs)
    report = a.coverage_report(coverage, paths, inputs, rows)
    report['raw_roster_inventory'] = raw_inventory
    receipt.update(training_games=len(rows), base_parity='PASS: all cells within 1e-12; exact missingness',
                   model_fits=0, current_diagnostic='Separate optional operation; not required for history')
    return finish(output, receipt, {
        'historical-features.json': audit.base._json_bytes([asdict(r) for r in rows]),
        'historical-context.json': audit.base._json_bytes(portable),
        'coverage.json': audit.base._json_bytes(report)})


def verified_preparation(prepared, digest):
    prepared = Path(prepared).resolve()
    if prepared.parent != DIRECTORY:
        raise ValueError('Prepared evidence must be in candidate directory')
    audit._verified_manifest(prepared, digest)
    pre = json.loads((prepared / 'run-receipt.json').read_bytes())
    protected, _ = pins()
    if (pre['kind'] != 'FEATURE_PREPARATION_NO_FIT' or pre['charter_sha256'] != CHARTER_SHA256
            or pre['code_sha256'] != protected):
        raise ValueError('Prepared evidence differs from reviewed code/charter')
    return prepared


def diagnose_current(output, prepared, digest):
    prepared = verified_preparation(prepared, digest)
    output, receipt, _ = start(output, 'CURRENT_FEATURE_DIAGNOSTIC_NO_FIT', prepared_manifest_sha256=digest)
    import pgo_forecast_corrected as issued
    snapshot = issued.load_snapshot(SOURCE_DIR)
    context = json.loads((prepared / 'historical-context.json').read_bytes())
    values, coverage = a.current_features(context, snapshot,
        list(audit.pgo_sources.open_csv(SOURCE_DIR / 'roster.csv.gz')))
    audit._verified_manifest(prepared, digest)
    receipt.update(model_fits=0, current_inputs_as_of=snapshot['inputs_as_of'], corrected_base_parity='PASS')
    return finish(output, receipt, {'current-features.json': audit.base._json_bytes(values),
                                    'coverage.json': audit.base._json_bytes(coverage)})


def screen(metrics, interval):
    candidate = metrics['candidate']
    control = metrics['corrected']
    wins = sum(c['mae'] < b['mae'] for c, b in zip(candidate['seasons'], control['seasons']))
    checks = dict(lower_pooled_mae=candidate['overall']['mae'] < control['overall']['mae'],
                  at_least_five_of_eight_seasons=wins >= 5, positive_interval_lower=interval['lower'] > 0)
    return dict(status='PASS' if all(checks.values()) else 'FAIL', checks=checks, season_wins=wins,
                scientific_status='EXPERIMENTAL / HOLD', early_weeks='DESCRIPTIVE_ONLY')


def symmetry_check(fit, row):
    names = fit['preprocessor']['feature_names']
    missing = fit['preprocessor']['missing_features']
    patterns = [(), *[(name,) for name in missing], tuple(missing)]
    maximum = 0.
    for pattern in patterns:
        values = {name: None if name in pattern else float(row.features.get(name) or 0.) for name in names}
        values['home_field'] = values['rest_difference'] = 0.
        reverse = {name: None if value is None else -value for name, value in values.items()}
        same = {name: None if value is None else 0. for name, value in values.items()}
        probes = [a.ch.FeatureRow('probe', 2026, 0, '', 0, f, {}) for f in (values, reverse, same)]
        first, second, zero = corrected.replay(probes, fit)
        if not all(math.isfinite(v) for v in (first, second, zero)):
            raise ValueError('Nonfinite symmetric prediction')
        maximum = max(maximum, abs(first+second), abs(zero))
    if maximum > 1e-8:
        raise ValueError('Candidate neutral symmetry or missing-pattern invariant fails')
    return dict(patterns=len(patterns), maximum_error=maximum, tolerance=1e-8)


def run(output, prepared, digest):
    # Never called by prepare or by feature tests. Root review gates execution.
    prepared = verified_preparation(prepared, digest)
    rows = [a.ch.FeatureRow(**row) for row in json.loads((prepared / 'historical-features.json').read_bytes())]
    a.validate_base(rows, json.loads((CORRECTED_RUN / 'historical-features.json').read_bytes()))
    a.validate_variation(rows)
    output, receipt, _ = start(output, 'ONE_FIXED_CANDIDATE_FIT', prepared_manifest_sha256=digest)
    saved = list(audit.pgo_sources.open_csv(CORRECTED_RUN / 'matched-predictions.csv'))
    matched = {r['game_id']: {**{k: r[k] for k in ('game_id', 'kickoff', 'home_team', 'away_team')},
                'season': int(r['season']), 'week': int(r['week']),
                'neutral_site': r['neutral_site'] == 'True', 'actual_margin': float(r['actual_margin']),
                **{name: float(r[name]) for name in COMPARATORS}} for r in saved}
    if len(matched) != 2127 or len(saved) != 2127:
        raise ValueError('Matched evaluation cohort differs')
    fits = []
    folds = [(f'fold_{season}', season, training, validation)
             for season, training, validation in audit.base.expanding_folds(rows)]
    folds.append(('final_2013_2025', None, rows, ()))
    for label, season, training, validation in folds:
        print(f'Fitting {label}', flush=True)
        pp, coefficients, mirrored = corrected.fit_combined(training)
        fit = audit._fit_receipt(pp, coefficients, training, validation, 4,
                                name='active4_symmetric', fit_training=mirrored)
        fit.update(evaluation_season=season, fit=label)
        probe = validation if season is not None else training
        fit['candidate_missing_pattern_symmetry'] = symmetry_check(fit, probe[0])
        predictions = audit.base._predict_rows(probe, pp, coefficients)
        replayed = corrected.replay(probe, json.loads(audit.base._json_bytes(fit)))
        if any(not math.isfinite(x) or abs(x-y) > 1e-10 for x, y in zip(predictions, replayed)):
            raise ValueError('Candidate serialized replay differs')
        if season is not None:
            for row, prediction in zip(validation, predictions):
                matched[row.game_id]['candidate'] = prediction
        fits.append(fit)
    values = sorted(matched.values(), key=lambda r: (r['season'], r['week'], r['kickoff'], r['game_id']))
    metrics = {name: audit.metric_views(values, name) for name in (*COMPARATORS, 'candidate')}
    intervals = {f'vs_{name}': audit.base.season_block_bootstrap(values, 'candidate', name, seed=20260908)
                 for name in COMPARATORS}
    receipt.update(training_games=len(rows), evaluation_games=len(values), model_fits=len(fits))
    audit._verified_manifest(prepared, digest)
    return finish(output, receipt, {
        'fold-fits.json': audit.base._json_bytes(fits),
        'final-fit.json': audit.base._json_bytes(dict(identity=a.IDENTITY, status='EXPERIMENTAL / HOLD',
                                  charter_sha256=CHARTER_SHA256, prepared_manifest_sha256=digest, **fits[-1])),
        'matched-predictions.csv': audit.base._csv_bytes(values),
        'metrics.json': audit.base._json_bytes(dict(metrics=metrics, paired_bootstrap=intervals,
                           further_study_screen=screen(metrics, intervals['vs_corrected'])))})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fit', action='store_true')
    parser.add_argument('--current-only', action='store_true')
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--prepared-manifest')
    args = parser.parse_args()
    if args.fit and args.current_only:
        parser.error('Choose either --fit or --current-only')
    if (args.fit or args.current_only) and (args.prepared is None or not args.prepared_manifest):
        parser.error('Fit/current diagnostic requires --prepared and reviewed --prepared-manifest')
    action = run if args.fit else diagnose_current if args.current_only else None
    print(json.dumps(action(args.output, args.prepared, args.prepared_manifest)
                     if action else prepare(args.output), indent=2))
