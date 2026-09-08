"""Verify the frozen preseason diagnostic without importing its generator or fitting.

Run from any directory. Writes only preseason-independent-verification.json.
Saved recency states are inputs, not independently reconstructed player histories.
"""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ART = HERE / 'preseason-20260908-corrected'
RUN = ROOT / 'research/pgo_current_strength/run-20260908'
PIN = 'b972ba9f8ecc05b6ab023046c8b3afad5f91d44df38c741a1190c9bf7c5f9c0f'
RUN_PIN = '6682197b16fcc0974fef19e6c704ef238d4d2a30ba0db066e3e86a6bad35ee4a'
ALIASES = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LAR', 'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS'}
ARMS = ('rolling_recency', 'frozen_recency', 'rolling_v0', 'frozen_v0')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def rows(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def near(a, b, tolerance=1e-10):
    assert math.isfinite(a) and math.isfinite(b)
    assert abs(a - b) <= tolerance, (a, b)


def verify_manifest(directory, pin):
    assert sha(directory / 'manifest.json') == pin
    for name, item in read(directory / 'manifest.json')['files'].items():
        path = directory / name
        assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], name


def kickoff(row):
    return datetime.fromisoformat(row['gameday'] + 'T' + row['gametime']).replace(
        tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)


def score(fit, features):
    pp = fit['preprocessor']
    vector = [0.0 if features[k] is None else (features[k] - median) / scale
              for k, median, scale in zip(pp['feature_names'], pp['medians'], pp['scales'])]
    vector += [float(features[k] is None) for k in pp['missing_features']]
    assert len(vector) + 1 == len(fit['coefficients'])
    return fit['coefficients'][0] + math.fsum(v * b for v, b in zip(vector, fit['coefficients'][1:]))


def main():
    verify_manifest(ART, PIN)
    verify_manifest(RUN, RUN_PIN)
    receipt = read(ART / 'receipt.json')
    for path, digest in receipt['protected_sha256'].items():
        assert sha(path) == digest, path
    for name, digest in receipt['code_sha256'].items():
        assert sha(ROOT / name) == digest, name
    assert sha(HERE / 'charter.md') == receipt['charter_sha256']
    lock_path = ROOT / 'research/pgo_v1/sources.lock.json'
    assert sha(lock_path) == '3a7673ac4617d57954cb56954f2216226a358c7b187b1e3ce62994a6f2b3fd29'
    locked = {i['sha256'] for i in read(lock_path)['sources']}
    for name, item in receipt['source_inventory'].items():
        path = Path(item['path'])
        assert item['sha256'] in locked and path.stat().st_size == item['bytes'], name
        assert sha(path) == item['sha256'], name
    schedule = [g for g in rows(receipt['source_inventory']['schedule_results']['path'])
                if g['game_type'] == 'REG' and g['home_score'] and g['away_score']
                and 1999 <= int(g['season']) <= 2025]
    assert len({g['game_id'] for g in schedule}) == len(schedule)
    for g in schedule:
        for side in ('home', 'away'):
            g[side] = ALIASES.get(g[side + '_team'], g[side + '_team'])
        g['year'], g['w'] = int(g['season']), int(g['week'])
        g['margin'] = float(g['home_score']) - float(g['away_score'])
        g['hfa'] = 0.0 if g['location'].strip().lower() == 'neutral' else 2.5
    by_id = {g['game_id']: g for g in schedule}
    saved = rows(ART / 'predictions.csv')
    original = {r['game_id']: r for r in rows(RUN / 'matched-predictions.csv')}
    assert len(saved) == len(original) == len({r['game_id'] for r in saved}) == 2127
    assert {r['game_id'] for r in saved} == set(original) == {
        g['game_id'] for g in schedule if 2018 <= g['year'] <= 2025}
    states = read(ART / 'preseason-states.json')
    v0_states = read(ART / 'v0-preseason-states.json')
    folds = read(RUN / 'fold-fits.json')['starter_recency'][:-1]
    fits = {f['evaluation_season']: f for f in folds}
    assert len(fits) == 8
    # Independent original baseline replay, including its actual 1999 warm-up.
    ratings, rolling_v0, reconstructed_states, last = defaultdict(float), {}, {}, None
    for g in sorted(schedule, key=lambda x: (x['gameday'], x['game_id'])):
        if last is not None and g['year'] != last:
            ratings = defaultdict(float, {t: v * .5 ** (g['year'] - last) for t, v in ratings.items()})
        if g['year'] != last and g['year'] >= 2018:
            reconstructed_states[str(g['year'])] = dict(ratings)
        last = g['year']
        predicted = ratings[g['home']] - ratings[g['away']] + g['hfa']
        rolling_v0[g['game_id']] = predicted
        update = .15 * max(-20., min(20., g['margin'] - predicted)) / 2
        ratings[g['home']] += update
        ratings[g['away']] -= update
    boundaries, statuses = [], Counter()
    for year, state in states.items():
        games = sorted((g for g in schedule if g['year'] == int(year)), key=lambda g: (kickoff(g), g['game_id']))
        cutoff = min(map(kickoff, games))
        first = {}
        for g in games:
            for side in ('home', 'away'):
                first.setdefault(g[side], (g, side))
        assert len(first) == len(state['teams']) == len(state['identities']) == 32
        assert set(first) == set(state['teams']) == set(state['identities'])
        assert datetime.fromisoformat(state['exclusive_performance_cutoff']) == cutoff
        assert state['current_season_observed_games'] == 0
        prior = [g for g in schedule if 2013 <= g['year'] < int(year)]
        assert len(prior) == state['prior_observed_games']
        assert max(map(kickoff, prior)) == datetime.fromisoformat(state['latest_prior_kickoff']) < cutoff
        oracle_later, hours = 0, []
        for team, (g, side) in first.items():
            identity = state['identities'][team]
            assert g['w'] == 1 and identity['source_game_id'] == g['game_id']
            assert datetime.fromisoformat(identity['source_week1_kickoff']) == kickoff(g)
            assert identity['recorded_week1_qb_gsis'] == g[side + '_qb_id']
            statuses[identity['starter_match']] += 1
            hours.append((kickoff(g) - cutoff).total_seconds() / 3600)
            oracle_later += kickoff(g) > cutoff
            near(v0_states[year][team], reconstructed_states[year][team], 1e-12)
            for key in ('offense_availability', 'defense_availability', 'qb_current_minus_full'):
                assert state['teams'][team][key] in (0., None)
        fit = fits[int(year)]
        assert fit['training']['season_max'] < int(year)
        assert all(by_id[g]['year'] < int(year) for g in fit['training']['game_ids'])
        assert set(fit['validation']['game_ids']) == {g['game_id'] for g in games}
        boundaries.append({'season': int(year), 'cutoff': cutoff.isoformat(), 'teams': 32,
                           'later_week1_identity_teams': oracle_later, 'latest_identity_hours_after_freeze': max(hours)})
    maximum = defaultdict(float)
    for r in saved:
        g, old = by_id[r['game_id']], original[r['game_id']]
        assert int(r['season']) == g['year'] and int(r['week']) == g['w']
        assert datetime.fromisoformat(r['kickoff']) == kickoff(g)
        near(float(r['actual_margin']), g['margin'], 0)
        team = states[str(g['year'])]['teams']
        home, away = team[g['home']], team[g['away']]
        features = {k: None if home[k] is None or away[k] is None else home[k] - away[k] for k in home}
        features['home_field'] = g['hfa'] / 2.5
        features['rest_difference'] = (max(-7., min(7., float(g['home_rest']) - float(g['away_rest']))) / 7
                                       if g['home_rest'] and g['away_rest'] else None)
        reconstructed = {'frozen_recency': score(fits[g['year']], features),
                         'frozen_v0': v0_states[str(g['year'])][g['home']] - v0_states[str(g['year'])][g['away']] + g['hfa'],
                         'rolling_v0': rolling_v0[g['game_id']],
                         'rolling_recency': float(old['starter_recency'])}
        for arm, value in reconstructed.items():
            near(float(r[arm]), value)
            maximum[arm] = max(maximum[arm], abs(float(r[arm]) - value))
        near(float(old['pgo_v0']), reconstructed['rolling_v0'])
        if g['w'] == 1:
            near(float(r['frozen_v0']), float(r['rolling_v0']), 1e-12)
    metrics = read(ART / 'metrics.json')
    checked = 0
    for arm in ARMS:
        slices = {'overall': saved, 'week1': [r for r in saved if int(r['week']) == 1],
                  'weeks1_4': [r for r in saved if int(r['week']) <= 4],
                  'weeks5_18': [r for r in saved if int(r['week']) >= 5]}
        slices.update({str(y): [r for r in saved if int(r['season']) == y] for y in range(2018, 2026)})
        for name, subset in slices.items():
            expected = metrics[arm]['seasons'][name] if name.isdigit() else metrics[arm][name]
            errors = [float(r[arm]) - float(r['actual_margin']) for r in subset]
            actual = {'count': len(errors), 'mae': math.fsum(map(abs, errors)) / len(errors),
                      'rmse': math.sqrt(math.fsum(e * e for e in errors) / len(errors)),
                      'bias_home_minus_away': math.fsum(errors) / len(errors)}
            for key, value in actual.items():
                near(value, expected[key]); checked += 1
    report = {'status': 'PASS_WITH_DOCUMENTATION_FINDING_AND_RETROSPECTIVE_LIMITATIONS',
              'manifest_sha256': PIN, 'verifier_sha256': sha(__file__), 'no_fit_performed': True,
              'verified_source_files': len(receipt['source_inventory']), 'matched_games': len(saved),
              'verified_metric_values': checked, 'maximum_prediction_difference': dict(maximum),
              'v0_week1_matches': 128, 'v0_warmup_actual_first_season': min(g['year'] for g in schedule),
              'boundaries': boundaries, 'starter_identity_status_counts': dict(statuses),
              'overall_metrics': {arm: metrics[arm]['overall'] for arm in ARMS},
              'finding': 'Receipt/report/comments incorrectly call v0 history 2002-start. parse_games defaults to 1999; independent 1999 replay reproduces all 256 frozen team states and all 2127 rolling-v0 predictions. 2002 is TRAIN_START, not warm-up start. No numeric artifact repair needed.',
              'scope': 'Independently reconstructed every frozen-recency prediction from saved states and prior-fold fits; original rolling-recency values checked against immutable prior predictions, not rebuilt player histories. Freeze construction was source-reviewed and saved boundaries/identities independently checked.',
              'construction_review': 'Capture hook runs during first team view before evaluation_metadata/update; all32 views use common earliest kickoff; current/future season observations rejected before and after capture; saved dictionaries are copies. All later predictions reuse these fixed states.',
              'limitations': ['All256 team-season identities use retrospective actual Week1 QB, roster and coach information, not certified preseason or T-60 sources.',
                              '240/256 team-season first-game identities occur after the common freeze kickoff; individual delays are recorded above.',
                              'Full-strength Week1 roster/QB held fixed for every season game; later injuries, roster changes and QB substitutions are not simulated.',
                              'All2127 games retain eventual recorded venue; recency additionally retains recorded rest. Those schedule vintages are not verified preseason. v0 has no rest term.',
                              'Historical roster/source vintages and saved recency states were not independently reconstructed here. No clean-leakage, calibrated score, interval, playoff or promotion claim.'],
              'metric_interpretation': 'Frozen-recency MAE10.9191 exceeds frozen-v0 10.7404; rolling-recency10.1198 does not validate a fixed-season forecast.'}
    (HERE / 'preseason-independent-verification.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
