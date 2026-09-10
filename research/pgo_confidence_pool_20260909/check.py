"""Fixed chronological probability diagnostic; never issues current probabilities."""
import csv
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'research/pgo_postseason_candidate/run-20260909-attempt01/matched-predictions.csv'
SOURCE_SHA = '3df4dbf26743a3686b6253bb4eb578457d0e2629dde1f0218f215c462feea0cf'
MODELS = {'corrected': 'corrected', 'postseason': 'candidate', 'constant': None}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


def sigmoid(x):
    return 1 / (1 + math.exp(-x)) if x >= 0 else math.exp(x) / (1 + math.exp(x))


def slope(rows, column):
    # Summed conditional non-tie NLL plus 0.5*a*a; derivative is strictly increasing.
    pairs = [(r[column], int(r['actual_margin'] > 0)) for r in rows if r['actual_margin'] != 0]
    def derivative(a):
        return a + math.fsum(x * (sigmoid(a*x) - y) for x, y in pairs)
    if derivative(0) >= 0:
        return 0.0
    low, high = 0.0, 1.0
    while derivative(high) < 0:
        high *= 2
    for _ in range(100):
        mid = (low + high) / 2
        if derivative(mid) < 0:
            low = mid
        else:
            high = mid
    result = (low + high) / 2
    assert abs(derivative(result)) < 1e-8
    return result


def probabilities(margin, a, tie):
    return ((1-tie)*sigmoid(a*margin), (1-tie)*sigmoid(-a*margin), tie)


def outcome(margin):
    return 0 if margin > 0 else 1 if margin < 0 else 2


def metrics(rows, model):
    loss, brier = [], []
    bins = [[] for _ in range(10)]
    for r in rows:
        p = [r[f'{model}_p_{x}'] for x in ('home', 'away', 'tie')]
        target = outcome(r['actual_margin'])
        loss.append(-math.log(max(1e-15, p[target])))
        brier.append(sum((v-int(i == target))**2 for i, v in enumerate(p)))
        selected = r[f'{model}_selected_probability']
        bins[min(9, int(selected*10))].append((selected, r[f'{model}_correct']))
    reliability = []
    for i, values in enumerate(bins):
        reliability.append({'lower': i/10, 'upper': (i+1)/10, 'count': len(values),
            'mean_probability': sum(p for p, _ in values)/len(values) if values else None,
            'observed_win_rate': sum(y for _, y in values)/len(values) if values else None})
    return {'games': len(rows), 'log_loss': math.fsum(loss)/len(rows),
            'brier_sum_three_classes': math.fsum(brier)/len(rows),
            'selected_team_reliability_ten_fixed_bins': reliability,
            'pool_realized_points': sum(r[f'{model}_realized_points'] for r in rows),
            'pool_expected_points': math.fsum(r[f'{model}_expected_points'] for r in rows)}


def self_check():
    p = probabilities(8, .2, .02)
    q = probabilities(-8, .2, .02)
    assert abs(sum(p)-1) < 1e-15 and p[0] == q[1] and p[1] == q[0]
    assert probabilities(0, .2, .02) == (.49, .49, .02)
    assert outcome(0) == 2 and outcome(-1) == 1 and outcome(1) == 0
    assert slope([{'m': 1., 'actual_margin': -1.}], 'm') == 0
    # Rearrangement: the higher probability receives the larger confidence value.
    assert 1*.55 + 2*.8 > 2*.55 + 1*.8
    assert int(outcome(0) == 0) == 0 and int(outcome(0) == 1) == 0


def run():
    self_check()
    assert digest(SOURCE) == SOURCE_SHA
    with SOURCE.open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2127 and len({r['game_id'] for r in rows}) == 2127
    for r in rows:
        r['season'], r['week'] = int(r['season']), int(r['week'])
        for field in ('actual_margin', 'corrected', 'candidate'):
            r[field] = float(r[field]); assert math.isfinite(r[field])
    assert set(r['season'] for r in rows) == set(range(2018, 2026))
    output = HERE / 'attempt01'
    output.mkdir(exist_ok=False)
    pins = {'source': {'path': str(SOURCE.relative_to(ROOT)), 'sha256': SOURCE_SHA},
            'code_sha256': digest(Path(__file__)), 'charter_sha256': digest(HERE/'CHARTER.md')}
    save(output/'run-start.json', {**pins, 'started_at': datetime.now(timezone.utc).isoformat(),
                                  'status': 'STARTED_EXCLUSIVE_ATTEMPT'})
    predictions, fits = [], []
    for season in range(2020, 2026):
        train = [r for r in rows if r['season'] < season]
        test = [r for r in rows if r['season'] == season]
        train_end = max(datetime.fromisoformat(r['kickoff']) for r in train)
        test_start = min(datetime.fromisoformat(r['kickoff']) for r in test)
        assert max(r['season'] for r in train) < season and train_end < test_start
        counts = [sum(outcome(r['actual_margin']) == k for r in train) for k in range(3)]
        tie = (counts[2]+1)/(len(train)+2)
        fitted = {name: slope(train, col) for name, col in MODELS.items() if col}
        constant = [(n+1)/(len(train)+3) for n in counts]
        fits.append({'test_season': season, 'training_seasons': sorted({r['season'] for r in train}),
                     'training_games': len(train), 'training_ties': counts[2],
                     'training_latest_kickoff': train_end.isoformat(), 'test_first_kickoff': test_start.isoformat(),
                     'non_tie_logistic_slopes': fitted, 'tie_probability': tie,
                     'constant_probabilities_home_away_tie': constant})
        for row in test:
            r = {k: row[k] for k in ('game_id', 'kickoff', 'season', 'week', 'home_team', 'away_team', 'actual_margin')}
            for name, column in MODELS.items():
                p = probabilities(row[column], fitted[name], tie) if column else constant
                assert all(math.isfinite(v) and 0 <= v <= 1 for v in p) and abs(sum(p)-1) < 1e-12
                for label, value in zip(('home', 'away', 'tie'), p): r[f'{name}_p_{label}'] = value
                side = 0 if p[0] >= p[1] else 1
                r[f'{name}_selected_team'] = row['home_team' if side == 0 else 'away_team']
                r[f'{name}_selected_probability'] = p[side]
                r[f'{name}_correct'] = int(outcome(row['actual_margin']) == side)
                if column: r[f'{name}_raw_margin'] = row[column]
            predictions.append(r)
    assert len(predictions) == 1615
    weeks = defaultdict(list)
    for r in predictions: weeks[r['season'], r['week']].append(r)
    ordering, weekly = [], []
    for key, games in sorted(weeks.items()):
        record = {'season': key[0], 'week': key[1], 'games': len(games)}
        for name, column in MODELS.items():
            ordered = sorted(games, key=lambda r: (r[f'{name}_selected_probability'], r['game_id']))
            for points, r in enumerate(ordered, 1):
                r[f'{name}_confidence_points'] = points
                r[f'{name}_realized_points'] = points*r[f'{name}_correct']
                r[f'{name}_expected_points'] = points*r[f'{name}_selected_probability']
            assert sorted(r[f'{name}_confidence_points'] for r in games) == list(range(1, len(games)+1))
            record[name] = {'realized': sum(r[f'{name}_realized_points'] for r in games),
                            'expected': math.fsum(r[f'{name}_expected_points'] for r in games)}
            if column:
                raw_order = sorted(games, key=lambda r: (abs(r[f'{name}_raw_margin']), r['game_id']))
                same = [r['game_id'] for r in ordered] == [r['game_id'] for r in raw_order]
                same_picks = all(r[f'{name}_selected_team'] == r['home_team' if r[f'{name}_raw_margin'] >= 0 else 'away_team'] for r in games)
                ordering.append({'season': key[0], 'week': key[1], 'model': name, 'same_order': same, 'same_picks': same_picks})
        weekly.append(record)
    result = {name: {'overall': metrics(predictions, name),
                    'seasons': {str(s): metrics([r for r in predictions if r['season'] == s], name) for s in range(2020, 2026)},
                    'week1': metrics([r for r in predictions if r['week'] == 1], name),
                    'weeks1_4': metrics([r for r in predictions if r['week'] <= 4], name)} for name in MODELS}
    wins = sum(result['postseason']['seasons'][str(s)]['log_loss'] < result['corrected']['seasons'][str(s)]['log_loss'] for s in range(2020, 2026))
    checks = {'beats_corrected_logloss': result['postseason']['overall']['log_loss'] < result['corrected']['overall']['log_loss'],
              'beats_constant_logloss': result['postseason']['overall']['log_loss'] < result['constant']['overall']['log_loss'],
              'at_least_four_season_wins': wins >= 4}
    summary = {'status': 'EXPERIMENTAL / HOLD', 'metrics': result,
               'screen': {'result': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'season_wins': wins},
               'ordering_unchanged_all_slates': all(r['same_order'] and r['same_picks'] for r in ordering),
               'slates': len(weeks), 'evaluation_games': len(predictions),
               'brier_definition': 'Sum of three squared class errors; range 0 to 2', 'log_loss_probability_floor': 1e-15}
    for name, value in [('fits.json', fits), ('metrics.json', summary), ('weekly-points.json', weekly), ('ordering-check.json', ordering)]: save(output/name, value)
    with (output/'predictions.csv').open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0])); writer.writeheader(); writer.writerows(predictions)
    assert digest(SOURCE) == SOURCE_SHA and digest(Path(__file__)) == pins['code_sha256'] and digest(HERE/'CHARTER.md') == pins['charter_sha256']
    save(output/'manifest.json', {**pins, 'finished_at': datetime.now(timezone.utc).isoformat(),
        'status': 'COMPLETE / EXPERIMENTAL / HOLD', 'fold_calibrators': 12, 'self_checks': 'PASS',
        'files': {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size} for p in output.iterdir() if p.is_file()}})
    report = ['# Confidence-pool probability study', '', 'September 9, 2026. **EXPERIMENTAL / HOLD. No current probabilities were issued and no saved forecasts were changed.**', '',
              'The fixed chronological diagnostic evaluated 1,615 games from 2020-2025 after 2018-2019 warmup. Each calibration used only earlier out-of-fold seasons.', '',
              '| Construction | Three-outcome log loss | Three-outcome Brier | Realized pool points | Expected pool points |', '|---|---:|---:|---:|---:|']
    for name in MODELS:
        m = result[name]['overall']; report.append(f"| {name.title()} | {m['log_loss']:.6f} | {m['brier_sum_three_classes']:.6f} | {m['pool_realized_points']} | {m['pool_expected_points']:.2f} |")
    report += ['', f"The predefined diagnostic screen **{summary['screen']['result']}ED**: postseason log loss improved over corrected in {wins} of six seasons. This does not lift HOLD or establish future probability reliability.", '',
               f"Across {len(weeks)} available-game weekly slates, favorite choices and confidence ordering were unchanged from each margin model's absolute-margin ordering: **{summary['ordering_unchanged_all_slates']}**. A positive monotonic scalar calibration cannot improve that ordering; differences between corrected and postseason pool points come from their original margin forecasts.", '',
               'Confidence values are the unique integers 1 through the available slate size, assigned in ascending selected-team unconditional win probability. Wrong picks and ties earn zero. This maximizes expected total points under the supplied probabilities, not the chance of winning a pool.', '',
               'The scalar logistic fit minimizes summed non-tie negative log likelihood plus 0.5 times slope squared, with nonnegative slope and no intercept. The training-only tie estimate is (ties+1)/(games+2); remaining mass is split between home and away. The constant comparator adds one pseudocount to each of the three outcome counts. Brier is the sum over all three classes; log loss uses a 1e-15 floor.', '',
               'Limits: these historical seasons were already inspected; underlying forecast source timing and recorded-starter limitations remain. Training predictions came from changing past-season models, so calibration transfer is not guaranteed. A constant tie rate does not capture margin-specific tie risk; the small number of ties makes this uncertain. Fixed ten-bin selected-team reliability, season, Week 1 and Weeks 1-4 results are saved with bin counts. Sparse and empty bins cannot demonstrate reliability. No probability percentages from this study are attached to current locked forecasts.', '',
               'Weekly results are retrospective slates of matched available games, not actual entries or proof of any particular pool rules. Missing or canceled games, including the unplayed 2022 Buffalo-Cincinnati game, are absent rather than adjudicated under a real contest policy. Predictions must also share a valid contest lock time before prospective weekly-pool use. Game dependence does not alter the expectation of a sum but does affect pool-winning chances.', '',
               '[Charter](../research/pgo_confidence_pool_20260909/CHARTER.md), [metrics and reliability bins](../research/pgo_confidence_pool_20260909/attempt01/metrics.json), [row predictions](../research/pgo_confidence_pool_20260909/attempt01/predictions.csv), [weekly points](../research/pgo_confidence_pool_20260909/attempt01/weekly-points.json), [source and code hashes](../research/pgo_confidence_pool_20260909/attempt01/manifest.json).', '']
    (ROOT/'docs/confidence-pool-study.md').write_text('\n'.join(report), encoding='utf-8', newline='\n')
    print(json.dumps({'screen': summary['screen'], 'overall': {k: {x: v['overall'][x] for x in ('log_loss', 'brier_sum_three_classes', 'pool_realized_points', 'pool_expected_points')} for k, v in result.items()}, 'ordering_unchanged': summary['ordering_unchanged_all_slates'], 'output': str(output)}, indent=2))


if __name__ == '__main__':
    run()
