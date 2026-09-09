"""One fixed postseason experiment; prepare separately, then fit reviewed bytes."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import json
import math
from pathlib import Path
import platform

from research.pgo_postseason_candidate import adapter as a

audit, corrected = a.audit, a.corrected
ROOT = corrected.ROOT
DIRECTORY = Path(__file__).resolve().parent
CHARTER_SHA256 = '7d3e2a926de0f84537b765e8e13b6fedc3fa41f90161036cd1c2448a2e695b0e'
CORRECTED_RUN = ROOT / 'research/pgo_week1_corrected/run-20260908'
CORRECTED_MANIFEST = '7530b3199f8a17ffec34f9e5351919ea67cb45df66e16befd655ab4e746f7a4c'
COMPARATORS = (*corrected.COMPARATORS, 'corrected')
PREPARED_FILES = ('historical-context.json', 'historical-features.json', 'coverage.json',
                  'scoring-history-2025.csv', 'scoring-rates.json', 'control-parity.json')


def pins():
    if audit.sha256((DIRECTORY / 'charter.md').read_bytes()) != CHARTER_SHA256:
        raise ValueError('Postseason charter differs')
    audit._verified_manifest(CORRECTED_RUN, CORRECTED_MANIFEST)
    audit._verified_manifest(audit.PRIOR_RUN, audit.PRIOR_RUN_MANIFEST_SHA256)
    previous = json.loads((CORRECTED_RUN / 'run-receipt.json').read_bytes())
    names = set(previous['code_sha256']) | {
        str(DIRECTORY / 'adapter.py'), str(DIRECTORY / 'train.py'), str(DIRECTORY / 'charter.md'),
        str(DIRECTORY / 'pinned_challenger.py'),
        'tests/test_pgo_postseason_candidate.py'}
    protected = {name: audit.sha256((ROOT / name).read_bytes()) for name in sorted(names)}
    # Every issued source member stays byte-pinned across this new experiment.
    protected.update({str(p): audit.sha256(p.read_bytes()) for p in (ROOT / 'docs/evidence').rglob('*') if p.is_file()})
    prior = json.loads((audit.PRIOR_RUN / 'run-receipt.json').read_bytes())
    all_paths = audit._paths_from_prior(prior)
    paths = {k: p for k, p in all_paths.items() if k != ('current_roster', 2026)}
    if len(paths) != 66:
        raise ValueError('Historical source inventory differs')
    return protected, paths


def start(output, kind, **bindings):
    output = Path(output).resolve()
    if output.parent != DIRECTORY or output.exists():
        raise ValueError('Use a new exclusive directory under postseason research')
    protected, paths = pins()
    receipt = dict(identity=a.IDENTITY, status='STARTED_INCOMPLETE', kind=kind,
                   started_at=datetime.now(timezone.utc).isoformat(), charter_sha256=CHARTER_SHA256,
                   code_and_issued_sha256=protected, corrected_manifest_sha256=CORRECTED_MANIFEST,
                   sources={f'{k[0]}:{k[1]}': dict(path=str(p), sha256=audit.sha256(p.read_bytes()),
                            bytes=p.stat().st_size) for k, p in paths.items()},
                   environment=dict(python=platform.python_version(), numpy=audit.np.__version__), **bindings)
    corrected.start_run(output, receipt)
    return output, receipt, paths


def finish(output, receipt, artifacts):
    protected, paths = pins()
    if protected != receipt['code_and_issued_sha256']:
        raise ValueError('Code or issued evidence changed during operation')
    for key, path in paths.items():
        old = receipt['sources'][f'{key[0]}:{key[1]}']
        if old['sha256'] != audit.sha256(path.read_bytes()) or old['bytes'] != path.stat().st_size:
            raise ValueError('Historical source changed during operation')
    receipt = {**receipt, 'status': 'EXPERIMENTAL / HOLD',
               'completed_at': datetime.now(timezone.utc).isoformat(),
               'historical_source_vintage': 'REVIEW REQUIRED',
               'validation_scope': 'Reused historical seasons; diagnostic only, no scientific promotion',
               'protected_sources_and_members_before_after': 'PASS'}
    artifacts['run-receipt.json'] = audit.base._json_bytes(receipt)
    for name, raw in artifacts.items():
        audit.base._write_exclusive(output / name, raw)
    if (output / 'control-parity.json').exists():
        artifacts['control-parity.json'] = (output / 'control-parity.json').read_bytes()
    artifacts['run-start.json'] = (output / 'run-start.json').read_bytes()
    audit.base._write_exclusive(output / 'manifest.json', audit.base._json_bytes({
        'identity': a.IDENTITY, 'files': {name: dict(sha256=audit.sha256(raw), bytes=len(raw))
                                       for name, raw in artifacts.items()}}))
    print(json.dumps({'output': str(output), 'kind': receipt['kind'], 'status': receipt['status']}), flush=True)
    return receipt


def prepare(output):
    output, receipt, paths = start(output, 'FEATURE_PREPARATION_NO_FIT')
    prior = json.loads((CORRECTED_RUN / 'historical-features.json').read_bytes())
    print('Verifying complete REG-only parity with frozen corrected features; no fitting', flush=True)
    control, control_context, control_inputs, _ = a.build_rows(paths, include_postseason=False)
    maximum_parity_error = 0.
    if [r.game_id for r in control] != [r['game_id'] for r in prior]:
        raise ValueError('REG-only control cohort differs')
    for actual, expected in zip(control, prior):
        if set(actual.features) != set(expected['features']):
            raise ValueError('REG-only control feature inventory differs')
        for name, old in expected['features'].items():
            new = actual.features[name]
            if (new is None) != (old is None):
                raise ValueError(f'REG-only control missingness differs: {actual.game_id} {name}')
            if old is not None:
                maximum_parity_error = max(maximum_parity_error, abs(new-old))
    if maximum_parity_error > 1e-12:
        raise ValueError('REG-only control differs from frozen corrected feature values')
    parity = dict(games=len(control), maximum_error=maximum_parity_error, missingness='EXACT', status='PASS',
                  pinned_core_sha256=a.PINNED_CORE_SHA256)
    audit.base._write_exclusive(output / 'control-parity.json', audit.base._json_bytes(parity))
    del control, control_context, control_inputs
    gc.collect()
    print('Building fixed REG+POST histories; REG targets only; no fitting', flush=True)
    rows, context, inputs, coverage = a.build_rows(paths)
    saved = {r['game_id']: r for r in audit.pgo_sources.open_csv(CORRECTED_RUN / 'matched-predictions.csv')}
    corrected.validate_rows(rows, saved, [r['game_id'] for r in prior], set(prior[0]['features']))
    if len(rows) != 3407 or len(saved) != 2127:
        raise ValueError('Historical or evaluation cohort count differs')
    schedule = [r for r in a.history_schedule(paths) if r['season'] == '2025']
    rates, league_total = a.scoring_rates(paths)
    receipt.update(training_games=len(rows), evaluation_games=len(saved), model_fits=0,
                   history_games=coverage['history_games'], postseason_games=coverage['postseason_games'],
                   control_parity=parity)
    return finish(output, receipt, {
        'historical-features.json': audit.base._json_bytes([asdict(r) for r in rows]),
        'historical-context.json': audit.base._json_bytes(a.portable_context(context, inputs)),
        'coverage.json': audit.base._json_bytes(coverage),
        'scoring-history-2025.csv': audit.base._csv_bytes(schedule),
        'scoring-rates.json': audit.base._json_bytes(dict(rates=rates, league_mean_total=league_total,
                              policy='2025 REG+POST PF/PA; equally weighted games per team; unfitted heuristic'))})


def screen(metrics, interval):
    candidate, control = metrics['candidate'], metrics['corrected']
    cseasons = {int(r['season']): r for r in candidate['seasons']}
    bseasons = {int(r['season']): r for r in control['seasons']}
    if set(cseasons) != set(range(2018, 2026)) or set(bseasons) != set(cseasons):
        raise ValueError('Screen requires the eight locked evaluation seasons')
    wins = sum(cseasons[s]['mae'] < bseasons[s]['mae'] for s in cseasons)
    checks = dict(lower_pooled_mae=candidate['overall']['mae'] < control['overall']['mae'],
                  at_least_five_of_eight_seasons=wins >= 5, positive_interval_lower=interval['lower'] > 0)
    return dict(status='PASS' if all(checks.values()) else 'FAIL', checks=checks, season_wins=wins,
                scientific_status='EXPERIMENTAL / HOLD')


def fit(output, prepared, digest):
    prepared = Path(prepared).resolve()
    if prepared.parent != DIRECTORY:
        raise ValueError('Preparation must be under postseason research')
    audit._verified_manifest(prepared, digest)
    prior = json.loads((prepared / 'run-receipt.json').read_bytes())
    protected, _ = pins()
    if (prior['kind'] != 'FEATURE_PREPARATION_NO_FIT' or prior['charter_sha256'] != CHARTER_SHA256
            or prior['code_and_issued_sha256'] != protected):
        raise ValueError('Prepared evidence differs from reviewed code/charter')
    output, receipt, _ = start(output, 'FIXED_DIAGNOSTIC_FIT', prepared_manifest_sha256=digest)
    rows = [a.ch.FeatureRow(**r) for r in json.loads((prepared / 'historical-features.json').read_bytes())]
    saved = {r['game_id']: r for r in audit.pgo_sources.open_csv(CORRECTED_RUN / 'matched-predictions.csv')}
    originals = json.loads((CORRECTED_RUN / 'historical-features.json').read_bytes())
    corrected.validate_rows(rows, saved, [r['game_id'] for r in originals], set(originals[0]['features']))
    matched = {key: {**{k: r[k] for k in ('game_id', 'kickoff', 'home_team', 'away_team')},
                    'season': int(r['season']), 'week': int(r['week']),
                    'neutral_site': r['neutral_site'] == 'True', 'actual_margin': float(r['actual_margin']),
                    **{name: float(r[name]) for name in COMPARATORS}} for key, r in saved.items()}
    fits, maximum_error = [], 0.
    folds = [(f'fold_{season}', season, training, validation)
             for season, training, validation in audit.base.expanding_folds(rows)]
    folds.append(('final_2013_2025', None, rows, ()))
    for label, season, training, validation in folds:
        print(f'Fitting fixed postseason {label}', flush=True)
        pp, coefficients, mirrored = corrected.fit_combined(training)
        fitted = audit._fit_receipt(pp, coefficients, training, validation, 4,
                                    name='active4_symmetric', fit_training=mirrored)
        fitted.update({'evaluation_season': season} if season is not None else {'fit': label})
        probes = validation if season is not None else training
        predictions = audit.base._predict_rows(probes, pp, coefficients)
        replayed = corrected.replay(probes, json.loads(audit.base._json_bytes(fitted)))
        error = max(abs(x-y) for x, y in zip(predictions, replayed))
        if not all(math.isfinite(v) for v in predictions + replayed) or error > 1e-10:
            raise ValueError('Serialized fit replay differs or is nonfinite')
        maximum_error = max(maximum_error, error)
        if season is not None:
            for row, prediction in zip(validation, predictions):
                matched[row.game_id]['candidate'] = prediction
        fits.append(fitted)
    values = sorted(matched.values(), key=lambda r: (r['season'], r['week'], r['kickoff'], r['game_id']))
    metrics = {name: audit.metric_views(values, name) for name in (*COMPARATORS, 'candidate')}
    intervals = {f'vs_{name}': audit.base.season_block_bootstrap(values, 'candidate', name, seed=20260909)
                 for name in COMPARATORS}
    audit._verified_manifest(prepared, digest)
    artifacts = {name: (prepared / name).read_bytes() for name in PREPARED_FILES}
    final_fit = dict(schema_version=1, identity=a.IDENTITY, status='EXPERIMENTAL / HOLD',
                     charter_sha256=CHARTER_SHA256,
                     historical_context_sha256=audit.sha256(artifacts['historical-context.json']),
                     historical_features_sha256=audit.sha256(artifacts['historical-features.json']), **fits[-1])
    artifacts.update({'final-fit.json': audit.base._json_bytes(final_fit),
                      'fold-fits.json': audit.base._json_bytes(fits),
                      'matched-predictions.csv': audit.base._csv_bytes(values),
                      'metrics.json': audit.base._json_bytes(dict(metrics=metrics, paired_bootstrap=intervals,
                                      further_study_screen=screen(metrics, intervals['vs_corrected'])))})
    receipt.update(training_games=len(rows), evaluation_games=len(values), model_fits=len(fits),
                   history_games=prior['history_games'], postseason_games=prior['postseason_games'],
                   maximum_serialized_replay_error=maximum_error,
                   further_study_screen=screen(metrics, intervals['vs_corrected']))
    return finish(output, receipt, artifacts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    pre = sub.add_parser('prepare')
    pre.add_argument('--output', type=Path, required=True)
    fitted = sub.add_parser('fit')
    fitted.add_argument('--output', type=Path, required=True)
    fitted.add_argument('--prepared', type=Path, required=True)
    fitted.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    if args.operation == 'prepare':
        prepare(args.output)
    else:
        fit(args.output, args.prepared, args.manifest_sha256)
