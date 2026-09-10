"""Fit the single declared defense block on independently reviewed prepared rows."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from research.pgo_week1_corrected import train as corrected
from research.pgo_postseason_candidate.train import screen
from research.pgo_corrected_roster_candidate.train import symmetry_check
import pgo_forecast_corrected as issued

audit = corrected.audit
ROOT = corrected.ROOT
DIRECTORY = Path(__file__).resolve().parent
CHARTER_SHA256 = '775a215d48513a7883c112f6720fe0d70a3c6cf979701990cb4bcb2b11df00bd'
CORRECTED_RUN = ROOT / 'research/pgo_week1_corrected/run-20260908'
CORRECTED_MANIFEST = '7530b3199f8a17ffec34f9e5351919ea67cb45df66e16befd655ab4e746f7a4c'
FEATURES = frozenset(('defense_prior_qb_hits_per_100_snaps', 'defense_prior_pass_defended_per_100_snaps',
                      'defense_prior_effective_contributors', 'defense_prior_history_coverage'))
IDENTITY = 'pgo-defensive-production-candidate-2026-09-09'


def validate_rows(rows, originals):
    if len(rows) != len(originals) or len({r.game_id for r in rows}) != len(rows):
        raise ValueError('Defense candidate game cohort differs')
    for row, old in zip(rows, originals):
        if any(getattr(row, k) != old[k] for k in ('game_id', 'season', 'week', 'kickoff', 'actual_margin')):
            raise ValueError('Defense candidate identity, order or target differs')
        if set(row.features) != set(old['features']) | FEATURES:
            raise ValueError('Defense candidate feature inventory differs')
        if any(row.features[k] != v for k, v in old['features'].items()):
            raise ValueError('Defense candidate changed a corrected baseline feature')
        if any(v is not None and not math.isfinite(v) for v in row.features.values()):
            raise ValueError('Defense candidate has nonfinite features')


def current_ratings(features, fit, baseline):
    if set(features) != set(audit.pgo_model.CURRENT_TEAMS):
        raise ValueError('Current defense comparison requires all 32 teams')
    scores = {}
    controls = {}
    for team, f in features.items():
        scores[team] = issued.score({**f, 'home_field': 0., 'rest_difference': 0.}, fit)
        controls[team] = issued.score({k: 0. if k in ('home_field', 'rest_difference') else f[k]
                                      for k in baseline['preprocessor']['feature_names']}, baseline)
    center, control_center = math.fsum(scores.values())/32, math.fsum(controls.values())/32
    ranks = {t: n for n, t in enumerate(sorted(controls, key=lambda t: (-controls[t], t)), 1)}
    return [dict(team=t, rank=n, rating=scores[t]-center, baseline_rank=ranks[t],
                 baseline_rating=controls[t]-control_center,
                 added_features={k: features[t][k] for k in sorted(FEATURES)})
            for n, t in enumerate(sorted(scores, key=lambda t: (-scores[t], t)), 1)]


def run(prepared, digest, output):
    prepared, output = Path(prepared).resolve(), Path(output).resolve()
    if output.exists() or output.parent != DIRECTORY:
        raise ValueError('Use a new exclusive defense run directory')
    if audit.sha256((DIRECTORY / 'predictive-charter.md').read_bytes()) != CHARTER_SHA256:
        raise ValueError('Defense predictive charter differs')
    audit._verified_manifest(prepared, digest)
    audit._verified_manifest(CORRECTED_RUN, CORRECTED_MANIFEST)
    original = json.loads((CORRECTED_RUN / 'historical-features.json').read_bytes())
    rows = [audit.ch.FeatureRow(**{**r, 'subgroup_flags': r.get('subgroup_flags', {})})
            for r in json.loads((prepared / 'historical-features.json').read_bytes())]
    validate_rows(rows, original)
    if len(rows) != 3407:
        raise ValueError('Defense training must retain all 3407 regular-season rows')
    protected_paths = [p for p in DIRECTORY.glob('*.py')] + [DIRECTORY / 'predictive-charter.md']
    protected_paths += [ROOT / p for p in ('pgo_forecast_corrected.py', 'research/pgo_postseason_candidate/train.py',
                                          'research/pgo_corrected_roster_candidate/train.py', 'research/pgo_week1_corrected/train.py',
                                          'research/pgo_input_audit/audit_model.py')]
    protected = {str(p): audit.sha256(p.read_bytes()) for p in protected_paths}
    old_evidence = {str(p): audit.sha256(p.read_bytes()) for p in (ROOT / 'docs/evidence').rglob('*') if p.is_file()}
    receipt = dict(identity=IDENTITY, status='STARTED_INCOMPLETE', started_at=datetime.now(timezone.utc).isoformat(),
                   charter_sha256=CHARTER_SHA256, prepared_manifest_sha256=digest,
                   corrected_manifest_sha256=CORRECTED_MANIFEST, code_sha256=protected,
                   issued_before_sha256=old_evidence, policy='Four fixed prior-season defensive production/experience fields; corrected REG-only base')
    corrected.start_run(output, receipt)
    names = (*corrected.COMPARATORS, 'corrected')
    saved = list(audit.pgo_sources.open_csv(CORRECTED_RUN / 'matched-predictions.csv'))
    matched = {r['game_id']: {**{k: r[k] for k in ('game_id', 'kickoff', 'home_team', 'away_team')},
                            'season': int(r['season']), 'week': int(r['week']), 'neutral_site': r['neutral_site'] == 'True',
                            'actual_margin': float(r['actual_margin']), **{k: float(r[k]) for k in names}} for r in saved}
    if len(saved) != len(matched) or len(matched) != 2127:
        raise ValueError('Defense evaluation must retain the same 2127 games')
    fits, replay_error = [], 0.
    folds = [(str(s), s, train, test) for s, train, test in audit.base.expanding_folds(rows)]
    folds.append(('final_2013_2025', None, rows, ()))
    for label, season, training, testing in folds:
        for name in FEATURES:
            values = [r.features[name] for r in training if r.features[name] is not None]
            if not values or min(values) == max(values):
                raise ValueError('No defense feature training variation: ' + name)
        print('Fitting fixed defense ' + label, flush=True)
        pp, coefficients, mirrored = corrected.fit_combined(training)
        fit = audit._fit_receipt(pp, coefficients, training, testing, 4, name='active4_symmetric', fit_training=mirrored)
        fit.update(evaluation_season=season, fit=label)
        probes = testing if season is not None else training
        fit['missing_pattern_symmetry'] = symmetry_check(fit, probes[0])
        predictions = audit.base._predict_rows(probes, pp, coefficients)
        replayed = corrected.replay(probes, json.loads(audit.base._json_bytes(fit)))
        error = max(abs(x-y) for x, y in zip(predictions, replayed))
        if not all(math.isfinite(v) for v in predictions+replayed) or error > 1e-10:
            raise ValueError('Defense fit serialized replay differs')
        replay_error = max(replay_error, error)
        if season is not None:
            for row, value in zip(testing, predictions):
                matched[row.game_id]['candidate'] = value
        fits.append(fit)
    values = sorted(matched.values(), key=lambda r: (r['season'], r['week'], r['kickoff'], r['game_id']))
    metrics = {name: audit.metric_views(values, name) for name in (*names, 'candidate')}
    intervals = {f'vs_{name}': audit.base.season_block_bootstrap(values, 'candidate', name, seed=20260909) for name in names}
    final = dict(schema_version=1, identity=IDENTITY, status='EXPERIMENTAL / HOLD',
                 charter_sha256=CHARTER_SHA256, prepared_manifest_sha256=digest, **fits[-1])
    current = current_ratings(json.loads((prepared / 'current-features.json').read_bytes()), final,
                              json.loads((CORRECTED_RUN / 'final-fit.json').read_bytes()))
    audit._verified_manifest(prepared, digest)
    audit._verified_manifest(CORRECTED_RUN, CORRECTED_MANIFEST)
    if protected != {str(p): audit.sha256(p.read_bytes()) for p in protected_paths}:
        raise ValueError('Defense code changed during fit')
    if any(audit.sha256(Path(p).read_bytes()) != h for p, h in old_evidence.items()):
        raise ValueError('Issued evidence changed during defense fit')
    result = screen(metrics, intervals['vs_corrected'])
    receipt.update(status='EXPERIMENTAL / HOLD', completed_at=datetime.now(timezone.utc).isoformat(),
                   training_games=len(rows), evaluation_games=len(values), model_fits=len(fits),
                   maximum_serialized_replay_error=replay_error, further_study_screen=result,
                   historical_source_vintage='REVIEW REQUIRED', protected_sources_and_members_before_after='PASS')
    artifacts = {'final-fit.json': audit.base._json_bytes(final), 'fold-fits.json': audit.base._json_bytes(fits),
                 'matched-predictions.csv': audit.base._csv_bytes(values),
                 'metrics.json': audit.base._json_bytes(dict(metrics=metrics, paired_bootstrap=intervals, further_study_screen=result)),
                 'current-ratings.json': audit.base._json_bytes(current), 'run-receipt.json': audit.base._json_bytes(receipt)}
    for name, raw in artifacts.items():
        audit.base._write_exclusive(output / name, raw)
    artifacts['run-start.json'] = (output / 'run-start.json').read_bytes()
    audit.base._write_exclusive(output / 'manifest.json', audit.base._json_bytes(dict(identity=IDENTITY,
                 files={n: dict(bytes=len(raw), sha256=audit.sha256(raw)) for n, raw in artifacts.items()})))
    print(json.dumps(result), flush=True)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.prepared, args.manifest_sha256, args.output)
