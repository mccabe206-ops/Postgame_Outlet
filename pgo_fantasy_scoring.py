"""Separate deterministic scoring adjustment; never fits or changes the challenger."""

import argparse
import ast
import csv
import hashlib
import itertools
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pgo_fantasy as fantasy


MODEL_VERSION = 'pgo_fantasy_scoring_adjustment_v1'
HALF_PPR = dict(passing_yards=.04, passing_tds=4., passing_interceptions=-2.,
                passing_2pt_conversions=2., rushing_yards=.1, rushing_tds=6.,
                rushing_2pt_conversions=2., receptions=.5, receiving_yards=.1,
                receiving_tds=6., receiving_2pt_conversions=2., special_teams_tds=6.,
                fumbles_lost_total=-2.)
PRESETS = {'standard': {**HALF_PPR, 'receptions': 0.}, 'half_ppr': HALF_PPR,
           'ppr': {**HALF_PPR, 'receptions': 1.},
           'six_point_pass_td': {**HALF_PPR, 'passing_tds': 6.},
           'te_premium': HALF_PPR}


def validate_components(value):
    if not isinstance(value, dict) or set(value) != set(HALF_PPR):
        raise ValueError('Scoring requires exactly the 13 canonical components')
    try:
        result = {name: float(number) for name, number in value.items()}
    except (ValueError, TypeError) as error:
        raise ValueError('Scoring components must be finite numbers') from error
    if any(isinstance(value[name], bool) or not math.isfinite(number) for name, number in result.items()):
        raise ValueError('Scoring components must be finite numbers')
    return result


def score(components, weights):
    return math.fsum(components[name] * weights[name] for name in HALF_PPR)


def adjusted_points(half_ppr_prediction, components, weights):
    return half_ppr_prediction + math.fsum((weights[name] - HALF_PPR[name]) * components[name] for name in HALF_PPR)


def attach_components(population, raw_stats):
    """Only the existing audited population builder may authorize missing-stat zeroes."""
    stats = {}
    for row in raw_stats:
        if row.get('season_type') != 'REG':
            continue
        key = int(row['season']), int(row['week']), row['player_id']
        if key in stats:
            raise ValueError(f'Duplicate raw stat identity: {key}')
        components = validate_components({name: row.get(name) for name in HALF_PPR})
        stats[key] = row, components
    rows = []
    for row in population:
        key = row['season'], row['week'], row['gsis_id']
        components = dict.fromkeys(HALF_PPR, 0.)
        if key in stats:
            stat, components = stats[key]
            if (stat['game_id'], fantasy.normalize_team(stat['team']), fantasy.normalize_team(stat['opponent_team'])) != (row['game_id'], row['team'], row['opponent']):
                raise ValueError(f'Raw component identity mismatch: {key}')
        if abs(score(components, HALF_PPR) - row['fantasy_points']) > 1e-9:
            raise ValueError(f'Reconstructed half-PPR target mismatch: {key}')
        rows.append({**row, 'components': components})
    return rows


def walk_components(rows):
    """Same eight-game baseline and live priors; state-only outcomes affect history."""
    ordered = sorted(rows, key=fantasy._row_key)
    identities, player_weeks = set(), set()
    for row in ordered:
        key, player_week = fantasy._natural_key(row), (row['season'], row['week'], row['gsis_id'])
        if key in identities or player_week in player_weeks:
            raise ValueError('Duplicate component population identity')
        identities.add(key)
        player_weeks.add(player_week)
        validate_components(row['components'])
        if row['position'] not in {'QB', 'RB', 'WR', 'TE'}:
            raise ValueError('Unknown component position')
    histories = defaultdict(list)
    sums = {p: dict.fromkeys(HALF_PPR, 0.) for p in ('QB', 'RB', 'WR', 'TE')}
    counts = dict.fromkeys(sums, 0)
    predictions = []
    season_means = {}
    for (season, week), grouped in itertools.groupby(ordered, key=lambda r: (r['season'], r['week'])):
        weekly = list(grouped)
        means = {p: {name: total / counts[p] if counts[p] else 0. for name, total in values.items()} for p, values in sums.items()}
        if season not in season_means:
            season_means[season] = means
        for row in weekly:
            history = histories[row['gsis_id']]
            components = {name: fantasy.strong_baseline([previous[name] for previous in history], means[row['position']][name]) for name in HALF_PPR}
            predictions.append({**row, 'projected_components': components,
                                'training_position_components': season_means[season][row['position']],
                                'history_count': len(history), 'cold_start': not history})
        for row in weekly:
            histories[row['gsis_id']].append(row['components'])
            histories[row['gsis_id']] = histories[row['gsis_id']][-8:]
            if fantasy._is_evaluation_row(row):
                counts[row['position']] += 1
                for name in HALF_PPR:
                    sums[row['position']][name] += row['components'][name]
    means = {p: {name: total / counts[p] if counts[p] else 0. for name, total in values.items()} for p, values in sums.items()}
    return predictions, dict(histories), means


def binding(path):
    data = Path(path).read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def metric(rows, name):
    errors = [r[name] - r['target'] for r in rows]
    return {'count': len(errors), 'mae': math.fsum(map(abs, errors)) / len(errors) if errors else None,
            'bias': math.fsum(errors) / len(errors) if errors else None}


def evaluate(predictions, heldout):
    expected = {fantasy._natural_key(r): r for r in predictions if r['season'] in fantasy.TEST_SEASONS and fantasy._is_evaluation_row(r)}
    if len(heldout) != len(expected) or {fantasy._natural_key(r) for r in heldout} != set(expected):
        raise ValueError('Held-out population mismatch or duplicate identities')
    joined, max_error = [], 0.
    for frozen in heldout:
        for name in ('fantasy_points', 'strong_prediction', 'candidate_prediction', 'history_count', 'cold_start'):
            if isinstance(frozen[name], bool) or not math.isfinite(float(frozen[name])):
                raise ValueError(f'Nonfinite or invalid held-out scalar: {name}')
        if float(frozen['cold_start']) not in (0., 1.):
            raise ValueError('Invalid held-out cold-start state')
        row = expected[fantasy._natural_key(frozen)]
        for name in ('season', 'week', 'game_id', 'gsis_id', 'team', 'opponent', 'position'):
            if str(row[name]) != str(frozen[name]):
                raise ValueError(f'Held-out identity mismatch: {name}')
        if abs(row['fantasy_points'] - float(frozen['fantasy_points'])) > 1e-9:
            raise ValueError('Held-out target mismatch')
        error = abs(score(row['projected_components'], HALF_PPR) - float(frozen['strong_prediction']))
        max_error = max(max_error, error)
        if error > 1e-9 or float(frozen['history_count']) != row['history_count'] or bool(float(frozen['cold_start'])) != row['cold_start']:
            raise ValueError('Component/scalar linearity or history mismatch')
        if frozen['primary_pool'] not in ('true', 'false'):
            raise ValueError('Invalid frozen primary membership')
        joined.append({**row, 'half_ppr_prediction': float(frozen['candidate_prediction']), 'primary_pool': frozen['primary_pool'] == 'true'})
    reports, output = {}, []
    for preset, weights in PRESETS.items():
        scored = []
        for row in joined:
            weights_used = {**weights, 'receptions': weights['receptions'] + .5} if preset == 'te_premium' and row['position'] == 'TE' else weights
            result = {key: row[key] for key in ('season', 'week', 'game_id', 'gsis_id', 'position', 'primary_pool', 'cold_start')}
            result.update(preset=preset, target=score(row['components'], weights_used),
                          anchored=adjusted_points(row['half_ppr_prediction'], row['projected_components'], weights_used),
                          component=score(row['projected_components'], weights_used),
                          position_mean=score(row['training_position_components'], weights_used))
            if not all(math.isfinite(result[key]) for key in ('target', 'anchored', 'component', 'position_mean')):
                raise ValueError('Nonfinite scoring prediction')
            if preset == 'half_ppr' and result['anchored'] != row['half_ppr_prediction']:
                raise ValueError('Canonical forecast changed')
            scored.append(result)
        output.extend(scored)
        primary = [r for r in scored if r['primary_pool']]
        groups = {'pooled_primary': primary, 'all_eligible': scored}
        for season in fantasy.TEST_SEASONS:
            groups[f'primary_season_{season}'] = [r for r in primary if r['season'] == season]
            for position in ('QB', 'RB', 'WR', 'TE'):
                groups[f'primary_{position}_{season}'] = [r for r in primary if r['season'] == season and r['position'] == position]
        for position in ('QB', 'RB', 'WR', 'TE'):
            groups[f'position_{position}'] = [r for r in scored if r['position'] == position]
        groups['cold_start'] = [r for r in scored if r['cold_start']]
        groups['with_history'] = [r for r in scored if not r['cold_start']]
        metrics = {key: {name: metric(values, name) for name in ('anchored', 'component', 'position_mean')} for key, values in groups.items()}
        no_worse = lambda key: metrics[key]['anchored']['mae'] <= metrics[key]['component']['mae']
        folds_passed = sum(no_worse(f'primary_season_{season}') for season in fantasy.TEST_SEASONS)
        slice_failures = [key for key in groups if key.startswith(tuple(f'primary_{p}_' for p in ('QB', 'RB', 'WR', 'TE'))) and len(groups[key]) >= 30 and metrics[key]['anchored']['mae'] > 1.25 * metrics[key]['component']['mae']]
        gates = {'pooled_primary_no_worse': no_worse('pooled_primary'), 'three_of_four_folds': folds_passed >= 3, 'position_season_guardrail': not slice_failures}
        reports[preset] = {'accepted': all(gates.values()), 'gates': gates, 'folds_passed': folds_passed, 'slice_failures': slice_failures, 'metrics': metrics}
    return {'accepted': all(r['accepted'] for r in reports.values()), 'presets': reports,
            'checks': {'population_identity': True, 'targets_reconstructed': True, 'canonical_preserved': True, 'component_linearity': True, 'history_state': True},
            'max_half_ppr_linearity_error': max_error, 'heldout_rows': len(joined), 'primary_rows': sum(r['primary_pool'] for r in joined)}, output


def run(frozen_root, output_dir):
    root, output_dir = Path(frozen_root).resolve(), Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    source_dir = root / 'output/pgo-fantasy-challenger-v2/source-20260905-125358'
    evaluation_dir = root / 'output/pgo-fantasy-challenger-v2/evaluation-20260905-125358'
    preview_dir = root / 'output/pgo-fantasy-challenger-v2/preview-20260905-125700'
    paths = {'source_lock': source_dir / 'sources.lock.json', 'source_qualification': source_dir / 'source-qualification.json',
             'heldout_predictions': evaluation_dir / 'fold-predictions.csv', 'candidate_model': evaluation_dir / 'candidate-model.json',
             'candidate_history': evaluation_dir / 'candidate-history-2025.json', 'development_receipt': evaluation_dir / 'development-receipt.json',
             'base_preview': preview_dir / 'candidate-preview.json', 'preview_receipt': preview_dir / 'preview-receipt.json',
             'scoring_code': Path(__file__), 'population_code': Path(fantasy.__file__), 'frozen_population_code': root / 'pgo_fantasy.py',
             'evaluation_charter': Path(__file__).parent / 'docs/superpowers/specs/2026-09-07-fantasy-league-profiles-design.md'}
    inputs = {name: binding(path) for name, path in paths.items()}
    # Verify imported read-only population construction is semantically identical.
    nodes = lambda path: {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n, ast.FunctionDef)}
    current, frozen = nodes(paths['population_code']), nodes(paths['frozen_population_code'])
    for name in ('_build_player_games_from_sources', '_reconcile_fantasy_population', '_load_schedule', 'half_ppr', 'strong_baseline'):
        if current[name] != frozen[name]:
            raise ValueError(f'Frozen population function differs: {name}')
    lock = json.loads(paths['source_lock'].read_bytes())
    qualified = json.loads(paths['source_qualification'].read_bytes())
    if qualified['qualification_status'] != 'PASS' or qualified['source_lock_sha256'] != inputs['source_lock']['sha256']:
        raise ValueError('Frozen source qualification binding mismatch')
    source_paths = {}
    for entry in lock['sources']:
        path = (root / entry['cache_path']).resolve()
        if not path.is_relative_to(root / '.cache/pgo_fantasy_challenger') or binding(path) != {key: entry[key] for key in ('bytes', 'sha256')}:
            raise ValueError('Frozen source cache binding mismatch')
        key = entry['name'], entry['season']
        if key in source_paths:
            raise ValueError('Duplicate locked source')
        source_paths[key] = path
        inputs[f'source:{entry["name"]}:{entry["season"]}'] = binding(path)
    source_rows, receipts = fantasy._load_source_rows(source_paths)
    population, audit = fantasy._build_player_games_from_sources(source_rows, receipts)
    if len(population) != qualified['population_rows'] or any(audit[key] != qualified[key] for key in ('sources', 'coverage', 'blocking_discrepancies', 'diagnostics')):
        raise ValueError('Frozen audited population did not reproduce')
    raw = itertools.chain.from_iterable(source_rows['player_weekly_stats', season] for season in fantasy.MODEL_SEASONS)
    rows = attach_components(population, raw)
    del source_rows
    predictions, histories, means = walk_components(rows)
    with paths['heldout_predictions'].open(encoding='utf-8', newline='') as stream:
        heldout = list(csv.DictReader(stream))
    qualification, scored = evaluate(predictions, heldout)
    preview = json.loads(paths['base_preview'].read_bytes())
    public_rows, seen = [], set()
    for row in preview['rows']:
        key = fantasy._natural_key(row)
        if key in seen or row['position'] not in means:
            raise ValueError('Duplicate or unknown preview identity')
        seen.add(key)
        components = {name: fantasy.strong_baseline([previous[name] for previous in histories.get(row['gsis_id'], [])], means[row['position']][name]) for name in HALF_PPR}
        validate_components(components)
        if not math.isfinite(row['strong_prediction']):
            raise ValueError('Nonfinite canonical preview')
        public_rows.append({key: row[key] for key in ('gsis_id', 'game_id', 'position', 'player_name', 'team')} | {'half_ppr_prediction': row['strong_prediction'], 'components': components})
    for name, path in paths.items():
        if binding(path) != inputs[name]:
            raise ValueError(f'Input changed during evaluation: {name}')
    for entry in lock['sources']:
        if binding(root / entry['cache_path']) != inputs[f'source:{entry["name"]}:{entry["season"]}']:
            raise ValueError('Source cache changed during evaluation')
    receipt = {'schema_version': 1, 'model_version': MODEL_VERSION, 'status': 'EXPERIMENTAL_HOLD',
               'created_at': datetime.now(timezone.utc).isoformat(), 'base_preview_sha256': inputs['base_preview']['sha256'],
               'input_bindings': inputs, 'qualification': qualification, 'population_rows': len(rows),
               'preview_population': 'all_frozen_preview_rows', 'preview_rows': len(public_rows),
               'limitations': ['Retrospective source publication vintage remains REVIEW_REQUIRED.',
                               'Separate deterministic scoring adjustment; challenger remains HOLD.',
                               'Custom weight scenarios are not separately validated models.'],
               'formula': 'C_half + sum((w - w_half) * projected_component)',
               'history_rule': '8-game strong_baseline; outcomes update only after the complete week; eligible outcomes update position priors'}
    bundle = {**receipt, 'rows': public_rows}
    for name, value in (('scoring-components.json', bundle), ('scoring-receipt.json', receipt)):
        (output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')
    with (output_dir / 'scoring-fold-predictions.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(scored[0]))
        writer.writeheader()
        writer.writerows(scored)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = run(args.frozen_root, args.output)
    print(json.dumps({'output': str(args.output), 'qualification': {key: value for key, value in result['qualification'].items() if key != 'presets'}, 'presets': {key: {'accepted': value['accepted'], 'gates': value['gates']} for key, value in result['qualification']['presets'].items()}}, indent=2))
