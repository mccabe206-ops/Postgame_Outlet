"""Research-only QB/roster comparison and refitted component ablations."""

import argparse
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np

import pgo_challenger as ch
import pgo_opponent_evaluation as base
import pgo_forecast_snapshot
import pgo_sources

ROOT = Path(__file__).resolve().parent
CHARTER = ROOT / 'research/pgo_current_strength/charter.md'
CHARTER_SHA256 = 'edf1328d2dc1a7d047f75d40cffa6ba3eb1d4e0a2b5858e8de5ef0b74aafa157'
DEFAULT_OUTPUT = ROOT / 'research/pgo_current_strength/run-20260908'
ARMS = ('raw', 'starter', 'starter_recency', 'starter_recency_roster')
QUALITY = ('quality_wr_receiving', 'quality_te_receiving', 'quality_rb_receiving', 'quality_rb_rushing')
GROUPS = {
    'results_history': ('pgo_v0',),
    'team_passing': ('passing_epa_per_play_for',),
    'other_team_performance': ch.PERFORMANCE_FEATURES[1:],
    'qb': (*ch.QB_FEATURES, 'qb_current_minus_full'),
    'roster_continuity': ('returning_offense_snap_share', 'returning_defense_snap_share',
                          'incoming_prior_snap_share', 'rookie_draft_capital'),
    'coaching': ('head_coach_continuity', 'head_coach_tenure'),
    'skill_quality': QUALITY,
    'availability': ('offense_availability', 'defense_availability'),
}
CODE = ('pgo_strength_evaluation.py', 'pgo_current_strength.py', 'pgo_roster_strength.py',
        'pgo_opponent_evaluation.py', 'pgo_challenger.py', 'pgo_model.py',
        'pgo_prospective.py', 'pgo_sources.py', 'pgo_forecast_snapshot.py')


def ablate(rows, group):
    removed = set(GROUPS[group])
    if any(not removed <= row.features.keys() for row in rows):
        raise ValueError(f'Missing ablation feature group: {group}')
    return [replace(row, features={key: value for key, value in row.features.items()
                                  if key not in removed}) for row in rows]


def validate_matching_arms(arms):
    reference = [base._row_identity(row) for row in arms['raw']]
    if len({row[0] for row in reference}) != len(reference):
        raise ValueError('Duplicate reference game identity')
    for name, rows in arms.items():
        if [base._row_identity(row) for row in rows] != reference:
            raise ValueError(f'Game identity or target differs: {name}')


def screen(candidate, raw, interval):
    prior = {row['season']: row['mae'] for row in raw['seasons']}
    wins = sum(row['mae'] < prior[row['season']] for row in candidate['seasons'])
    checks = {
        'pooled_mae_improves': candidate['overall']['mae'] < raw['overall']['mae'],
        'season_block_interval_above_zero': interval['lower'] > 0,
        'at_least_five_seasons_improve': wins >= 5,
        'weeks_1_4_not_worse': candidate['weeks_1_4']['mae'] <= raw['weeks_1_4']['mae'],
    }
    return {'season_mae_wins': wins, 'checks': checks,
            'merits_further_prospective_study': all(checks.values()),
            'promotion_status': 'HOLD'}


def coverage_receipt(state):
    annual = defaultdict(lambda: {'team_games': 0, 'missing_role_team_games': 0,
                                  'total_role_weight': 0.0, 'observed_history_role_weight': 0.0})
    for row in state.get('roster_coverage', ()):
        for feature, values in row['features'].items():
            summary = annual[row['season'], feature]
            summary['team_games'] += 1
            summary['missing_role_team_games'] += values['total_role_weight'] == 0
            for key in ('total_role_weight', 'observed_history_role_weight'):
                summary[key] += values[key]
    return {'starter': state.get('coverage', {}), 'last_kickoff': state.get('last_kickoff'),
            'historical_roster_by_season': [dict(season=season, feature=feature, **values)
                for (season, feature), values in sorted(annual.items())],
            'snapshot_roster_coverage': state.get('snapshot_roster_coverage', [])}


def _ratings(features, fit):
    preprocessor, coefficients = fit
    teams = sorted(features)
    if len(teams) != 32 or len(set(teams)) != 32:
        raise ValueError('Current ratings require all 32 teams')
    rows = [ch._neutral_feature_row(team, features[team], preprocessor) for team in teams]
    x = preprocessor.transform(rows)
    scores = ch.predict(x, coefficients)
    centered = scores - scores.mean()
    if not np.isfinite(centered).all():
        raise ValueError('Non-finite current rating')
    contributions = (x - x.mean(axis=0)) * coefficients[1:]
    labels = list(preprocessor.feature_names) + [f'{name}_missing' for name in preprocessor.missing_features]
    ranks = {teams[index]: rank for rank, index in enumerate(
        sorted(range(len(teams)), key=lambda i: (-centered[i], teams[i])), 1)}
    result = []
    for i, team in enumerate(teams):
        terms = {name: float(value) for name, value in zip(labels, contributions[i])}
        if not math.isclose(sum(terms.values()), centered[i], abs_tol=1e-9):
            raise ValueError(f'Contributions do not reconcile: {team}')
        result.append({'team': team, 'rank': ranks[team], 'rating': float(centered[i]),
                       'features': features[team], 'centered_contributions': terms})
    return result


def _report(metrics, screening, bootstrap):
    lines = ['# Current-strength research', '',
             'EXPERIMENTAL / HOLD. Historical source vintage: REVIEW REQUIRED.',
             'Recorded actual starters are reconstructed, not verified T-60 expectations.', '',
             '| Arm | Games | Margin MAE | RMSE | Winner accuracy |',
             '|---|---:|---:|---:|---:|']
    for name, views in metrics.items():
        row = views['overall']
        lines.append(f"| {name} | {row['count']} | {row['mae']:.4f} | {row['rmse']:.4f} | "
                     f"{row['winner']['accuracy']:.2%} |")
    lines.extend(['', '## Predeclared screens against matched raw', ''])
    for name, result in screening.items():
        ci = bootstrap[name]['vs_raw']
        passed = result['merits_further_prospective_study']
        lines.append(f"- {name}: {'merits further study' if passed else 'screen not met'}; "
                     f"{result['season_mae_wins']}/8 seasons improve; MAE gain {ci['mean']:+.4f}, "
                     f"95% season-block interval [{ci['lower']:+.4f}, {ci['upper']:+.4f}]. Promotion: HOLD.")
    lines.extend(['', 'All ablations refit preprocessing and coefficients on earlier seasons.',
                  'Positive MAE improvement means lower error. Ablation gains are exploratory.',
                  'Current ranks are model-scale sensitivities, not calibrated confidence intervals.',
                  'Skill-player features are efficiency proxies; OL and defensive player quality are unavailable.',
                  'Issued forecasts and promoted ratings remain unchanged.', ''])
    return '\n'.join(lines).encode('utf-8')


def run_experiment(output=DEFAULT_OUTPUT, *, cache_dir=base.CACHE_DIR, snapshot_dir=base.SNAPSHOT_DIR):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Research output directory must be new')
    if base.sha256(CHARTER.read_bytes()) != CHARTER_SHA256:
        raise ValueError('Pre-fit charter hash differs')
    pinned = {
        str(base.RECOVERED_FIT_PATH): base.EXPECTED_RECOVERED_FIT_SHA256,
        str(base.SOURCE_LOCK_PATH): base.EXPECTED_SOURCE_LOCK_SHA256,
        str(Path(snapshot_dir) / 'manifest.json'): base.EXPECTED_SNAPSHOT_MANIFEST_SHA256,
    }
    base.verify_protected(pinned)
    snapshot = pgo_forecast_snapshot.load_snapshot(snapshot_dir)
    recovered = json.loads(base.RECOVERED_FIT_PATH.read_bytes())
    protected = dict(recovered['original_artifacts_sha256'])
    protected.update(pinned)
    for directory in ('docs/evidence/forecast-lab-2026', 'research/pgo_opponent_adjustment'):
        protected.update({str(path): base.sha256(path.read_bytes())
                          for path in (ROOT / directory).rglob('*') if path.is_file()})
    protected[str(CHARTER)] = CHARTER_SHA256
    for name in CODE:
        protected[str(ROOT / name)] = base.sha256((ROOT / name).read_bytes())
    base.verify_protected(protected)
    original_sources = base._source_inventory(recovered)
    all_paths = pgo_sources.load_locked_sources(base.SOURCE_LOCK_PATH, cache_dir)
    source_inventory = base.loaded_source_inventory(all_paths)
    paths = {key: path for key, path in all_paths.items() if key != ('current_roster', 2026)}
    if len(paths) != 66 or len(all_paths) != 67:
        raise ValueError('Historical source selection differs')
    started = datetime.now(timezone.utc).isoformat()
    output.mkdir(parents=True, exist_ok=False)
    start = {'started_at': started, 'charter_sha256': CHARTER_SHA256,
             'status': 'STARTED_INCOMPLETE_UNTIL_MANIFEST_EXISTS',
             'code_sha256': {name: protected[str(ROOT / name)] for name in CODE}}
    base._write_exclusive(output / 'run-start.json', base._json_bytes(start))

    import pgo_current_strength as adapter
    import pgo_roster_strength as roster
    hook = roster.build_roster_hook(paths)
    arms, current_features, coverage = {}, {}, {}
    for name in ARMS:
        mode = 'starter_recency' if name.endswith('_roster') else name
        selected_hook = hook if name.endswith('_roster') else None
        print(f'building {name}', flush=True)
        rows, context, inputs = adapter.build_rows(paths, mode, roster_hook=selected_hook)
        arms[name] = rows
        current_features[name] = adapter.snapshot_features(
            snapshot, context, mode, apply_offseason=name != 'raw', roster_hook=selected_hook,
            snapshot_dir=snapshot_dir)
        state = context.get('current_strength', {})
        coverage[name] = coverage_receipt(state)
    full = arms['starter_recency_roster']
    expected = {name for names in GROUPS.values() for name in names} | {'home_field', 'rest_difference'}
    if set(full[0].features) != expected:
        raise ValueError(f'Ablation coverage differs: {set(full[0].features) ^ expected}')
    for group in GROUPS:
        arms[f'without_{group}'] = ablate(full, group)
    validate_matching_arms(arms)
    v0 = ch._unique_predictions(base._frozen_v0_predictions(paths), 'pgo_v0')
    matched = {row.game_id: {'game_id': row.game_id, 'season': row.season, 'week': row.week,
                            'kickoff': row.kickoff, 'actual_margin': row.actual_margin}
               for row in arms['raw'] if row.season in base.EVALUATION_SEASONS}
    if set(matched) != set(v0):
        raise ValueError('Baseline game identities differ')
    for game, prediction in v0.items():
        if prediction.actual != matched[game]['actual_margin'] or prediction.season != matched[game]['season']:
            raise ValueError('Baseline target differs')
        matched[game]['pgo_v0'] = prediction.predicted
    fits = {}
    for name, rows in arms.items():
        fits[name] = []
        for season, training, validation in base.expanding_folds(rows):
            preprocessor, coefficients = base._fit(training)
            predictions = base._predict_rows(validation, preprocessor, coefficients)
            constant = float(np.mean([row.actual_margin for row in training]))
            for row, prediction in zip(validation, predictions):
                matched[row.game_id][name] = prediction
                matched[row.game_id]['constant'] = constant
            fits[name].append({'evaluation_season': season,
                              **base._fit_receipt(preprocessor, coefficients, training, validation)})
        print(f'fitted {name}', flush=True)
    matched_rows = sorted(matched.values(), key=lambda row: (row['season'], row['week'], row['kickoff'], row['game_id']))
    metrics = {name: base.metric_views(matched_rows, name) for name in ('constant', 'pgo_v0', *arms)}
    bootstrap = {'raw': {'vs_pgo_v0': base.season_block_bootstrap(
        matched_rows, 'raw', 'pgo_v0', seed=20260908)}}
    for name in list(arms)[1:]:
        comparisons = {'raw', 'pgo_v0'}
        comparisons.add('starter_recency_roster' if name.startswith('without_') else ARMS[ARMS.index(name)-1])
        bootstrap[name] = {f'vs_{comparison}': base.season_block_bootstrap(
            matched_rows, name, comparison, seed=20260908) for comparison in sorted(comparisons)}
    screening = {name: screen(metrics[name], metrics['raw'], bootstrap[name]['vs_raw']) for name in ARMS[1:]}
    details, ratings = [], {team['team']: {'team': team['team'], 'qb_name': team['qb_name']} for team in snapshot['teams']}
    for name in ARMS:
        fit = base._fit(arms[name])
        fits[name].append({'fit': 'final_2013_2025', **base._fit_receipt(*fit, arms[name])})
        if name == 'raw':
            raw_check = base._exact_raw_fit(*fit, arms[name], snapshot)
        for row in _ratings(current_features[name], fit):
            details.append({'variant': name, **row})
            ratings[row['team']][f'{name}_rank'] = row['rank']
            ratings[row['team']][f'{name}_rating'] = row['rating']
            if name == 'raw':
                frozen = next(team for team in snapshot['teams'] if team['team'] == row['team'])
                if not math.isclose(row['rating'], frozen['rating'], abs_tol=1e-9):
                    raise ValueError('Raw current ratings do not reproduce frozen snapshot')
    base.verify_protected(protected)
    base.verify_loaded_sources(source_inventory, all_paths)
    if base._source_inventory(recovered) != original_sources:
        raise ValueError('Original sources changed')
    receipt = {**start, 'status': 'EXPLORATORY_RETROSPECTIVE_RESEARCH',
               'completed_at': datetime.now(timezone.utc).isoformat(),
               'arms': list(arms), 'raw_final_fit_reproduction': raw_check,
               'source_inventory_before_after': source_inventory,
               'protected_artifacts_before_after': protected, 'coverage': coverage,
               'roster_profile_receipt': hook.receipt,
               'snapshot_generated_at': snapshot['generated_at'],
               'leakage_verdict': 'REVIEW REQUIRED', 'promotion_status': 'HOLD'}
    artifacts = {'matched-predictions.csv': base._csv_bytes(matched_rows),
                 'fold-fits.json': base._json_bytes(fits),
                 'metrics.json': base._json_bytes({'metrics': metrics, 'paired_bootstrap': bootstrap, 'screening': screening}),
                 'ratings.csv': base._csv_bytes([ratings[team] for team in sorted(ratings)]),
                 'rating-details.json': base._json_bytes(details),
                 'run-receipt.json': base._json_bytes(receipt),
                 'report.md': _report(metrics, screening, bootstrap)}
    for name, raw in artifacts.items():
        base._write_exclusive(output / name, raw)
    artifacts['run-start.json'] = (output / 'run-start.json').read_bytes()
    base._write_exclusive(output / 'manifest.json', base._json_bytes({
        'schema_version': 1, 'identity': 'pgo-current-strength-research-20260908',
        'files': {name: {'sha256': base.sha256(raw), 'bytes': len(raw)} for name, raw in artifacts.items()}}))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run_experiment(args.output)
    print(json.dumps({'status': result['status'], 'output': str(args.output)}))
