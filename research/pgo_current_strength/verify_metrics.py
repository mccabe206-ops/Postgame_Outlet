"""Independent saved-prediction arithmetic check; no fitting or evaluator imports."""
from pathlib import Path
import csv, hashlib, json, math
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'research/pgo_current_strength/run-20260908'
EXPECTED = '6682197b16fcc0974fef19e6c704ef238d4d2a30ba0db066e3e86a6bad35ee4a'
manifest_raw = (RUN / 'manifest.json').read_bytes()
assert hashlib.sha256(manifest_raw).hexdigest() == EXPECTED
manifest = json.loads(manifest_raw)
for name, record in manifest['files'].items():
    raw = (RUN / name).read_bytes()
    assert len(raw) == record['bytes']
    assert hashlib.sha256(raw).hexdigest() == record['sha256']
with (RUN / 'matched-predictions.csv').open(newline='') as handle:
    rows = list(csv.DictReader(handle))
assert len(rows) == 2127 and len({r['game_id'] for r in rows}) == 2127
assert {int(r['season']) for r in rows} == set(range(2018, 2026))
saved = json.loads((RUN / 'metrics.json').read_bytes())
checks = 0

def compare(actual, expected):
    global checks
    if isinstance(expected, dict):
        assert set(actual) == set(expected)
        for key in expected:
            compare(actual[key], expected[key])
    elif expected is None:
        assert actual is None
        checks += 1
    elif isinstance(expected, (float, int)):
        assert math.isclose(actual, expected, rel_tol=0, abs_tol=1e-10), (actual, expected)
        checks += 1
    else:
        assert actual == expected
        checks += 1

def summarize(group, arm):
    errors = [float(r['actual_margin']) - float(r[arm]) for r in group]
    decisions = [(float(r['actual_margin']), float(r[arm])) for r in group
                 if float(r['actual_margin']) != 0 and float(r[arm]) != 0]
    correct = sum((a > 0) == (p > 0) for a, p in decisions)
    return dict(count=len(group), mae=math.fsum(map(abs, errors))/len(group),
        rmse=math.sqrt(math.fsum(e*e for e in errors)/len(group)),
        winner=dict(correct=correct, denominator=len(decisions),
            accuracy=correct/len(decisions) if decisions else None,
            actual_ties=sum(float(r['actual_margin']) == 0 for r in group),
            predicted_ties=sum(float(r[arm]) == 0 for r in group)))

for arm, views in saved['metrics'].items():
    compare(summarize(rows, arm), views['overall'])
    for annual in views['seasons']:
        compare(summarize([r for r in rows if int(r['season']) == annual['season']], arm),
                {k:v for k,v in annual.items() if k != 'season'})
    for key, low, high in [('weeks_1_4', 1, 4), ('weeks_5_18', 5, 18)]:
        compare(summarize([r for r in rows if low <= int(r['week']) <= high], arm), views[key])

bootstrap_count = 0
for arm, comparisons in saved['paired_bootstrap'].items():
    for label, record in comparisons.items():
        baseline = label.removeprefix('vs_')
        years = sorted({int(r['season']) for r in rows})
        totals, counts = [], []
        for year in years:
            group = [r for r in rows if int(r['season']) == year]
            gains = [abs(float(r['actual_margin'])-float(r[baseline]))
                     -abs(float(r['actual_margin'])-float(r[arm])) for r in group]
            totals.append(math.fsum(gains)); counts.append(len(group))
        assert record['seed'] == 20260908 and record['samples'] == 10000
        chosen = np.random.default_rng(20260908).integers(0, 8, (10000, 8))
        weights = np.array([np.bincount(draw, minlength=8) for draw in chosen])
        distribution = (weights @ np.array(totals))/(weights @ np.array(counts))
        compare(dict(mean=math.fsum(totals)/sum(counts),
            lower=float(np.quantile(distribution, .025)), upper=float(np.quantile(distribution, .975)),
            blocks=8, samples=10000, seed=20260908), record)
        bootstrap_count += 1
for arm, record in saved['screening'].items():
    raw = saved['metrics']['raw']; candidate = saved['metrics'][arm]
    wins = sum(c['mae'] < r['mae'] for c,r in zip(candidate['seasons'], raw['seasons']))
    expected = dict(pooled_mae_improves=candidate['overall']['mae'] < raw['overall']['mae'],
        season_block_interval_above_zero=saved['paired_bootstrap'][arm]['vs_raw']['lower'] > 0,
        at_least_five_seasons_improve=wins >= 5,
        weeks_1_4_not_worse=candidate['weeks_1_4']['mae'] <= raw['weeks_1_4']['mae'])
    assert record['checks'] == expected and record['season_mae_wins'] == wins
    assert record['merits_further_prospective_study'] == all(expected.values())
    assert record['promotion_status'] == 'HOLD'
result = dict(status='PASS', manifest_sha256=EXPECTED, game_count=len(rows),
    arms_with_all_metric_views=len(saved['metrics']), bootstrap_comparisons=bootstrap_count,
    numeric_checks=checks, tolerance=1e-10, fit_or_evaluator_functions_called=False)
print(json.dumps(result, indent=2))
