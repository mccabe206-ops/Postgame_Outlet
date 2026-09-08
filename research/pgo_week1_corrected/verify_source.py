"""Independent arithmetic for the first corrected source package; no model runs."""
import csv
from collections import Counter
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

import pgo_sources  # Team aliases only; no model or forecast-loader imports.
from research.pgo_input_audit import verify_run as independent


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'docs/evidence/forecast-lab-2026/september-08-corrected'
RUN = Path(__file__).with_name('run-20260908')
OUTPUT = Path(__file__).with_name('source-verification.json')
RUN_SHA = '7530b3199f8a17ffec34f9e5351919ea67cb45df66e16befd655ab4e746f7a4c'
FIT_SHA = 'f6e6deda6665ded3ea0764a486fc68bc4667abd4a49f17afe5e3c39284a8806f'
CONTEXT_SHA = 'c1ef8a85e091ed616db18a90d5594aea92fb55c5859108712a62a0a40737dfdc'
CAPTURE_SHA = '122ef5740e94ba2e8b4464d7ea9e6e8fe953d0e0ac49527fee5a6050039672f2'
QUALIFICATION_SHA = '4c7f700531dc43b38181f9c205564057615ff54613832a2c2970d1963d60d76b'


def compressed_rows(name):
    with gzip.open(PACKAGE / name, 'rt', newline='') as stream:
        return list(csv.DictReader(stream))


def verify():
    if OUTPUT.exists():
        raise ValueError('Verification output already exists')
    manifest = independent.manifest(PACKAGE)
    independent.manifest(RUN, RUN_SHA)
    independent.manifest(independent.SNAPSHOT, independent.SNAPSHOT_SHA)
    independent.manifest(independent.PRIOR, independent.PRIOR_SHA)
    audit_run = ROOT / 'research/pgo_input_audit/run-20260908-eligibility-attempt02'
    audit_sha = '440734823c333f3f47229ba3edc2e43d50d84be62aa318c4c59395744d15899c'
    independent.manifest(audit_run, audit_sha)
    for name, digest in [('final-fit.json', FIT_SHA), ('historical-context.json', CONTEXT_SHA),
                         ('capture.json', CAPTURE_SHA), ('source-qualification.json', QUALIFICATION_SHA)]:
        assert independent.sha(PACKAGE / name) == digest
    data = independent.read(PACKAGE / 'snapshot.json')
    fit = independent.read(PACKAGE / 'final-fit.json')
    context = independent.read(PACKAGE / 'historical-context.json')
    capture = independent.read(PACKAGE / 'capture.json')
    qualification = independent.read(PACKAGE / 'source-qualification.json')
    for item in capture['sources']:
        assert independent.sha(PACKAGE / item['file']) == item['sha256']
        assert (PACKAGE / item['file']).stat().st_size == item['bytes']
    assert qualification['status'] == 'PASS' and not qualification['failed_checks']
    assert qualification['capture_manifest_sha256'] == CAPTURE_SHA
    asof = max(datetime.fromisoformat(s['captured_at']) for s in capture['sources'])
    generated = datetime.fromisoformat(data['generated_at'])
    assert asof <= datetime.fromisoformat(qualification['issued_at']) <= generated
    assert datetime.fromisoformat(data['inputs_as_of']) == asof
    active = {}
    for row in compressed_rows('roster.csv.gz'):
        if row['status'] != 'ACT':
            continue
        assert row['season'] == '2026' and row['week'] == '1'
        key = pgo_sources.normalize_team(row['team']), row['gsis_id']
        assert key not in active
        active[key] = row
    depth_asof = datetime.fromisoformat(next(s['captured_at'] for s in capture['sources'] if s['file'] == 'depth.csv.gz'))
    depth = [r for r in compressed_rows('depth.csv.gz') if datetime.fromisoformat(r['dt']) <= depth_asof]
    latest = max(datetime.fromisoformat(r['dt']) for r in depth)
    selected = {}
    for row in depth:
        if datetime.fromisoformat(row['dt']) != latest or row['pos_abb'] != 'QB' or row['pos_rank'] != '1':
            continue
        team = pgo_sources.normalize_team(row['team'])
        assert team not in selected
        selected[team] = active[team, row['gsis_id']]
        assert selected[team]['position'] == 'QB'
    assert set(selected) == set(independent.TEAMS)
    assert len({r['gsis_id'] for r in selected.values()}) == 32
    elapsed = (asof - datetime.fromisoformat(context['current_strength']['last_kickoff'])).total_seconds() / 86400
    assert elapsed >= 0 and context['season'] == 2025
    decay = 2 ** (-elapsed / 365.25)
    pop = context['current_strength']['qb_population']
    rate_terms = {'qb_epa_per_dropback': ('passing_epa', 'passing_epa_plays', 200),
                  'qb_cpoe': ('cpoe_sum', 'cpoe_plays', 200),
                  'qb_sack_avoidance': ('sack_free_dropbacks', 'sack_dropbacks', 200),
                  'qb_ball_security': ('secure_dropbacks', 'security_dropbacks', 200),
                  'qb_rushing_epa_per_carry': ('rushing_epa', 'carries', 50)}
    features = {}
    for team, row in selected.items():
        player = row['gsis_id']
        if player in context['inputs']['colliding_gsis']:
            assert row['smart_id']
            player += ':' + row['smart_id']
        history = context['current_strength']['qb_history'].get(player, {})
        f = dict(context['ratios'][team], pgo_v0=context['ratings'][team] * .5,
                 offense_availability=0., defense_availability=0., qb_current_minus_full=0.)
        for name, (num, den, prior) in rate_terms.items():
            denominator = history.get(den, 0.) * decay
            f[name] = None if pop.get(den, 0.) <= 0 else (
                history.get(num, 0.) * decay + prior * pop.get(num, 0.) / pop[den]) / (denominator + prior)
        f['qb_log_dropbacks'] = math.log1p(history.get('dropbacks', 0.) * decay)
        f['qb_experience_prior'] = math.log1p(max(0, int(float(row['years_exp'] or 0))))
        draft = float(row['draft_number']) if row['draft_number'] else 0
        f['qb_draft_prior'] = 1 / math.sqrt(draft) if draft > 0 else 0.
        features[team] = f
    errors, counts = {}, Counter()

    def close(actual, expected, category):
        counts[category] += 1
        if expected is None:
            assert actual is None
            return
        assert math.isfinite(actual) and math.isfinite(expected)
        error = abs(actual - expected)
        errors[category] = max(error, errors.get(category, 0.))
        assert error <= 1e-9, (category, actual, expected)

    teams = independent.TEAMS
    neutral = [{**features[t], 'home_field': 0., 'rest_difference': 0.} for t in teams]
    x = independent.transform(neutral, fit)
    raw_scores = independent.predict(neutral, fit)
    ratings = raw_scores - raw_scores.mean()
    contributions = (x - x.mean(axis=0)) * np.asarray(fit['coefficients'][1:])
    names = fit['preprocessor']['feature_names'] + [n + '_missing' for n in fit['preprocessor']['missing_features']]
    ranks = {teams[i]: rank for rank, i in enumerate(sorted(range(32), key=lambda i: (-ratings[i], teams[i])), 1)}
    saved_teams = {r['team']: r for r in data['teams']}
    assert len(saved_teams) == len(data['teams']) == 32
    for i, team in enumerate(teams):
        saved = saved_teams[team]
        assert saved['rank'] == ranks[team]
        assert saved['qb_gsis_id'] == selected[team]['gsis_id']
        assert saved['qb_name'] == selected[team]['full_name']
        assert set(saved['features']) == set(features[team])
        for name, value in features[team].items():
            close(saved['features'][name], value, 'features')
        close(saved['rating'], ratings[i], 'ratings')
        assert set(saved['contributions']) == set(names)
        for name, value in zip(names, contributions[i]):
            close(saved['contributions'][name], value, 'contributions')
        close(math.fsum(saved['contributions'].values()), saved['rating'], 'contribution_sums')
    history = independent.csv_rows(PACKAGE / 'scoring-history-2025.csv')
    assert independent.sha(PACKAGE / 'scoring-history-2025.csv') == independent.sha(independent.SNAPSHOT / 'scoring-history-2025.csv')
    pf, pa, played = Counter(), Counter(), Counter()
    total_points = 0.
    assert len(history) == len({r['game_id'] for r in history}) == 272
    for row in history:
        assert row['season'] == '2025' and row['game_type'] == 'REG'
        home, away = [pgo_sources.normalize_team(row[k]) for k in ('home_team', 'away_team')]
        hp, ap = float(row['home_score']), float(row['away_score'])
        pf[home] += hp; pf[away] += ap; pa[home] += ap; pa[away] += hp
        played.update((home, away)); total_points += hp + ap
    assert set(played) == set(teams) and set(played.values()) == {17}
    league = total_points / 272
    close(data['league_mean_total'], league, 'totals')
    old = {g['game_id']: g for g in independent.read(independent.SNAPSHOT / 'snapshot.json')['games']}
    schedule = {r['game_id']: r for r in compressed_rows('schedule.csv.gz') if r['season'] == '2026' and r['game_type'] == 'REG' and r['week'] == '1'}
    assert len(data['games']) == len(schedule) == 16 and data['skipped_games'] == []
    game_ids = set()
    for game in data['games']:
        key = game['game_id']; game_ids.add(key)
        source = schedule[key]
        assert not source['home_score'] and not source['away_score']
        kickoff = datetime.fromisoformat(source['gameday'] + 'T' + source['gametime']).replace(tzinfo=ZoneInfo('America/New_York'))
        assert kickoff == datetime.fromisoformat(game['kickoff'])
        assert generated < kickoff - timedelta(minutes=60)
        for name in ('game_id', 'season', 'week', 'kickoff', 'game_type', 'location', 'home', 'away', 'home_rest', 'away_rest'):
            assert game[name] == old[key][name]
        home, away = pgo_sources.normalize_team(source['home_team']), pgo_sources.normalize_team(source['away_team'])
        assert home == game['home'] and away == game['away']
        assert float(source['home_rest']) == game['home_rest'] and float(source['away_rest']) == game['away_rest']
        diff = independent.neutral_difference(features[home], features[away], fit['preprocessor']['feature_names'])
        diff['home_field'] = 0. if source['location'] == 'Neutral' else 1.
        diff['rest_difference'] = max(-7., min(7., game['home_rest'] - game['away_rest'])) / 7
        margin = float(independent.predict([diff], fit)[0])
        total = (pf[home] + pa[home] + pf[away] + pa[away]) / 34
        close(game['margin'], margin, 'margins')
        close(game['total'], total, 'totals')
        close(game['home_points'], (total + margin) / 2, 'scores')
        close(game['away_points'], (total - margin) / 2, 'scores')
        close(game['league_mean_total'], league, 'totals')
        for new, prior_key in [('pgo_v0_margin', 'pgo_v0_margin'), ('legacy_margin', 'legacy_margin'),
                               ('incumbent_margin', 'margin'), ('incumbent_total', 'total'),
                               ('incumbent_home_points', 'home_points'), ('incumbent_away_points', 'away_points')]:
            close(game[new], old[key][prior_key], 'baseline_joins')
    assert game_ids == set(schedule)
    pairs = [independent.neutral_difference(features[a], features[b], fit['preprocessor']['feature_names']) for a in teams for b in teams]
    maximum_symmetry = 0.
    patterns = [set(), *({n} for n in fit['preprocessor']['feature_names']), set(fit['preprocessor']['feature_names'])]
    for pattern in patterns:
        forward = [{k: None if k in pattern else v for k, v in row.items()} for row in pairs]
        reverse = [{k: None if v is None else -v for k, v in row.items()} for row in forward]
        maximum_symmetry = max(maximum_symmetry, float(np.max(np.abs(independent.predict(forward, fit) + independent.predict(reverse, fit)))))
    assert maximum_symmetry <= 1e-8
    # CSV values must also match the verified unrounded JSON, independent of formatting.
    for row in independent.csv_rows(PACKAGE / 'ratings.csv'):
        saved = saved_teams[row['team']]
        close(float(row['rating']), saved['rating'], 'csv_ratings')
        assert int(row['rank']) == saved['rank']
    saved_games = {g['game_id']: g for g in data['games']}
    for row in independent.csv_rows(PACKAGE / 'forecasts.csv'):
        for key, value in saved_games[row['game_id']].items():
            if isinstance(value, (int, float)):
                close(float(row[key]), value, 'csv_game_numbers')
            else:
                assert row[key] == value
    independent.manifest(PACKAGE)
    independent.manifest(RUN, RUN_SHA)
    independent.manifest(independent.SNAPSHOT, independent.SNAPSHOT_SHA)
    independent.manifest(independent.PRIOR, independent.PRIOR_SHA)
    independent.manifest(audit_run, audit_sha)
    train_receipt = independent.read(RUN / 'run-receipt.json')
    for name, digest in train_receipt['code_sha256'].items():
        assert independent.sha(ROOT / name) == digest
    original_sources = independent.read(independent.PRIOR / 'run-receipt.json')['source_inventory_before_after']
    for entry in original_sources.values():
        assert independent.sha(entry['path']) == entry['sha256']
    result = {'status': 'PASS', 'snapshot_manifest_sha256': independent.sha(PACKAGE / 'manifest.json'),
              'run_manifest_sha256': RUN_SHA, 'final_fit_sha256': FIT_SHA, 'historical_context_sha256': CONTEXT_SHA,
              'capture_sha256': CAPTURE_SHA, 'qualification_sha256': QUALIFICATION_SHA,
              'verifier_sha256': independent.sha(Path(__file__)),
              'independent_math_helper_sha256': independent.sha(Path(independent.__file__)),
              'package_members_verified': len(manifest['files']), 'raw_capture_files': len(capture['sources']),
              'protected_historical_sources_rehashed': len(original_sources), 'old_manifests_and_code_unchanged': True,
              'counts': dict(counts), 'maximum_errors': errors, 'neutral_team_pairs': len(pairs),
              'missing_patterns': len(patterns), 'maximum_symmetry_error': maximum_symmetry,
              'inputs_as_of': asof.isoformat(), 'depth_as_of': latest.isoformat(), 'generated_at': generated.isoformat(),
              'qb_decay_days': elapsed, 'qb_decay_factor': decay,
              'no_fitting_or_forecast_loader_calls': True, 'scientific_status': 'EXPERIMENTAL / HOLD',
              'limitations': 'Official report extraction relies on the separately reviewed byte-pinned qualification; this receipt verifies arithmetic and provenance, not clinical availability or predictive validity.'}
    with OUTPUT.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
    return result


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
