"""Verified, separately dated postseason-history forecasts. No training at render time."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

import pgo_forecast_corrected as base
from research.pgo_postseason_candidate import sources

ROOT = Path(__file__).resolve().parent
EDITION = 'pgo-postseason-week1-2026-09-09'
DEFAULT_DIR = ROOT / 'docs/evidence/forecast-lab-2026/september-09-postseason'
DEFAULT_OUTPUT = DEFAULT_DIR
CHARTER_SHA256 = '7d3e2a926de0f84537b765e8e13b6fedc3fa41f90161036cd1c2448a2e695b0e'
# Filled only after the independent run and source reviews complete.
RUN_MANIFEST_SHA256 = 'a58aeff835471182a555e4b926beafd0db01c7c5e3fe19827ddf56bd03f2514a'
APPROVED_SOURCE_PAIRS = frozenset({(
    '4d25beb5d1c5afa6fde1d05d2a8ab1f23e7fe23a7a1ff338272dbbad23606a98',
    'cc527ba4b18d24499f9a05ce27cc86cb61ff00d56bd2c18c0e66f7ab6a83bcc9',
)})
RUN_MEMBERS = ('final-fit.json', 'historical-context.json', 'run-receipt.json',
               'metrics.json', 'coverage.json', 'scoring-history-2025.csv', 'scoring-rates.json')
METHOD = dict(name='Postseason history experiment', status='EXPERIMENTAL / HOLD',
              history='All completed regular-season and postseason team, results and quarterback history; regular-season training targets.',
              injury_coverage='Non-QB injuries and replacement quality remain unadjusted; see separate availability and defensive-depth evidence.',
              totals='Prior-season regular-season plus postseason PF/PA heuristic, using each team\'s game count; exact scores are experimental.',
              evaluation='Reused historical seasons are diagnostic. Grade this separately dated edition prospectively.')


def derive(qualification, context, fit, rates, league, prior, generated_at):
    features = base.current_features(context, qualification['selected_roster'], qualification['inputs_as_of'])
    pp = fit['preprocessor']
    if set(pp['feature_names']) != set(next(iter(features.values()))) | {'home_field', 'rest_difference'}:
        raise ValueError('Postseason fit feature inventory differs')
    neutral = {t: {**f, 'home_field': 0., 'rest_difference': 0.} for t, f in features.items()}
    scores = {t: base.score(f, fit) for t, f in neutral.items()}
    if len(scores) != 32:
        raise ValueError('Postseason ratings require all 32 teams')
    center = math.fsum(scores.values()) / 32
    names = [*pp['feature_names'], *(k + '_missing' for k in pp['missing_features'])]
    terms = {}
    for team, f in neutral.items():
        vector = [0. if f[k] is None else (f[k]-m)/s for k, m, s in zip(pp['feature_names'], pp['medians'], pp['scales'])]
        vector += [float(f[k] is None) for k in pp['missing_features']]
        terms[team] = dict(zip(names, (v*b for v, b in zip(vector, fit['coefficients'][1:]))))
        zero = {k: None if v is None else 0. for k, v in f.items()}
        reverse = {k: None if v is None else -v for k, v in f.items()}
        if abs(base.score(zero, fit)) > 1e-8 or abs(base.score(f, fit)+base.score(reverse, fit)) > 1e-8:
            raise ValueError('Postseason fit fails neutral/reversal symmetry')
    means = {k: math.fsum(v[k] for v in terms.values())/32 for k in names}
    old_teams = {r['team']: r for r in prior['teams']}
    teams = []
    for rank, team in enumerate(sorted(scores, key=lambda t: (-scores[t], t)), 1):
        qb = qualification['selected_roster'][team]
        contributions = {k: terms[team][k]-means[k] for k in names}
        if abs(math.fsum(contributions.values())-(scores[team]-center)) > 1e-8:
            raise ValueError('Postseason contributions do not reconcile')
        teams.append(dict(rank=rank, team=team, rating=scores[team]-center,
                          qb_name=qb['full_name'], qb_gsis_id=qb['gsis_id'], features=features[team],
                          contributions=contributions, coverage=qualification['coverage'][team],
                          baseline_rank=old_teams[team]['rank'], baseline_rating=old_teams[team]['rating']))
    old_games = {g['game_id']: g for g in prior['games']}
    games, skipped = [], []
    for game in qualification['games']:
        old = old_games[game['game_id']]
        if any(game[k] != old[k] for k in base.IDENTITY):
            raise ValueError('Postseason game identity differs from issued game')
        cutoff = base.current._utc(game['kickoff'])-timedelta(minutes=60)
        reason = ('EXISTING_CUTOFF_ELAPSED' if base.current._utc(generated_at) >= cutoff else
                  'EXPECTED_QB_UNAVAILABLE' if any(qualification['coverage'][t]['status'] == 'BLOCKED_EXPECTED_QB_UNAVAILABLE'
                                                 for t in (game['home'], game['away'])) else None)
        if reason:
            skipped.append(dict(game_id=game['game_id'], reason=reason, lock_at=cutoff.isoformat()))
            continue
        matchup = {**game, 'neutral': game['location'] == 'Neutral'}
        margin = base.score(base.ch._matchup_features(features[game['home']], features[game['away']], matchup), fit)
        total = math.fsum(rates[t][k] for t in (game['home'], game['away']) for k in ('pf', 'pa'))/2
        hp, ap = base.incumbent.expected_scores(total, margin)
        games.append(dict(**game, margin=margin, total=total, home_points=hp, away_points=ap,
                          corrected_margin=old['margin'], corrected_total=old['total'],
                          incumbent_margin=old['margin'], incumbent_total=old['total'],
                          pgo_v0_margin=old['pgo_v0_margin'], legacy_margin=old['legacy_margin'],
                          league_mean_total=league))
    if not games:
        raise ValueError('No eligible postseason-edition game remains')
    return teams, games, skipped


def validation(metrics):
    m = metrics['metrics']
    candidate, control = m['candidate'], m['corrected']
    interval = metrics['paired_bootstrap']['vs_corrected']
    wins = sum(c['mae'] < b['mae'] for c, b in zip(candidate['seasons'], control['seasons']))
    passed = candidate['overall']['mae'] < control['overall']['mae'] and wins >= 5 and interval['lower'] > 0
    return dict(status='PASS' if passed else 'FAIL', candidate_mae=candidate['overall']['mae'],
                baseline_mae=control['overall']['mae'], games=2127, season_wins=wins,
                interval={k: interval[k] for k in ('lower', 'upper')},
                limitations=['Previously inspected seasons; diagnostic comparison, not fresh validation.',
                             'Historical source vintage and recorded-starter timing remain under review.',
                             'A passing comparison does not remove EXPERIMENTAL / HOLD.'])


def _derive_payload(directory, raw, generated):
    qualification = json.loads(raw['postseason-qualification.json'])
    rebuilt = sources.qualify(directory)
    # Review time is metadata, not an input; every other field must reconstruct.
    base._same({k: v for k, v in qualification.items() if k != 'qualification_time'},
               {k: v for k, v in rebuilt.items() if k != 'qualification_time'}, 'fresh source qualification')
    fit, context = json.loads(raw['final-fit.json']), json.loads(raw['historical-context.json'])
    scoring = json.loads(raw['scoring-rates.json'])
    from research.pgo_postseason_candidate.adapter import scoring_rates
    rates, league = scoring_rates({('schedule_results', None): directory / 'scoring-history-2025.csv'})
    base._same(scoring['rates'], rates, 'postseason scoring rates')
    base._same(scoring['league_mean_total'], league, 'postseason scoring baseline')
    prior = base.load_snapshot(base.DEFAULT_OUTPUT)
    teams, games, skipped = derive(qualification, context, fit, rates, league, prior, generated)
    coverage = json.loads(raw['coverage.json'])
    return dict(schema_version=1, edition=EDITION, label='Postseason update - September 9',
                status='EXPERIMENTAL / HOLD', generated_at=generated,
                inputs_as_of=qualification['inputs_as_of'], depth_as_of=qualification['depth_as_of'],
                fit=fit, teams=teams, games=games, skipped_games=skipped,
                scoring_rates=rates, league_mean_total=league, coverage=qualification['coverage'],
                baseline_edition=base.EDITION,
                baseline_manifest_sha256=base._hash((base.DEFAULT_OUTPUT / 'manifest.json').read_bytes()),
                fit_sha256=base._hash(raw['final-fit.json']), research_run_manifest_sha256=RUN_MANIFEST_SHA256,
                history=dict(game_types=['REG', 'WC', 'DIV', 'CON', 'SB'],
                             through=context['current_strength']['last_kickoff'],
                             regular_games=coverage['regular_targets'], postseason_games=coverage['postseason_games'],
                             scoring_season=2025),
                validation=validation(json.loads(raw['metrics.json'])), method=METHOD,
                sources=[{k: s[k] for k in ('file', 'url', 'sha256', 'bytes', 'captured_at')}
                         for s in json.loads(raw['capture.json'])['sources']])


def _validate(directory, manifest, raw):
    if manifest['edition'] != EDITION or manifest['schema_version'] != 1:
        raise ValueError('Unknown postseason edition')
    if RUN_MANIFEST_SHA256 is None or base._hash(raw['research-manifest.json']) != RUN_MANIFEST_SHA256:
        raise ValueError('Postseason research run is not independently verified')
    if base._hash(raw['charter.md']) != CHARTER_SHA256:
        raise ValueError('Postseason charter differs')
    pair = (base._hash(raw['capture.json']), base._hash(raw['postseason-qualification.json']))
    if pair not in APPROVED_SOURCE_PAIRS:
        raise ValueError('Postseason source capture/qualification is not reviewed')
    members = json.loads(raw['research-manifest.json'])['files']
    for name in RUN_MEMBERS:
        if len(raw[name]) != members[name]['bytes'] or base._hash(raw[name]) != members[name]['sha256']:
            raise ValueError('Postseason research member differs: ' + name)
    data = json.loads(raw['snapshot.json'])
    generated = data['generated_at']
    if manifest['generated_at'] != generated:
        raise ValueError('Postseason issuance timestamps differ')
    q = json.loads(raw['postseason-qualification.json'])
    completed = json.loads(raw['run-receipt.json'])['completed_at']
    if any(base.current._utc(t) > base.current._utc(generated) for t in (q['inputs_as_of'], q['qualification_time'], completed)):
        raise ValueError('Postseason issue precedes its inputs, qualification or fit')
    base._same(data, _derive_payload(directory, raw, generated), 'postseason snapshot')
    if raw['ratings.csv'] != base._csv(data['teams'], base.TEAM_COLUMNS):
        raise ValueError('Postseason ratings CSV differs')
    if raw['forecasts.csv'] != base._csv(data['games'], (*base.IDENTITY, 'margin', 'total', 'home_points', 'away_points')):
        raise ValueError('Postseason forecasts CSV differs')
    return data


def load_snapshot(directory=DEFAULT_DIR):
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError('Postseason source must be a real directory')
    try:
        manifest = base._read(directory / 'manifest.json')
        raw = base._verified_files(directory, manifest)
        return _validate(directory, manifest, raw)
    except (KeyError, TypeError, IndexError, StopIteration) as error:
        raise ValueError('Incomplete postseason source: ' + str(error)) from error


def build_snapshot(run, capture, output=DEFAULT_DIR):
    run, capture, output = Path(run), Path(capture), Path(output)
    if output.exists():
        raise ValueError('Postseason output must be a new directory')
    run_raw = (run / 'manifest.json').read_bytes()
    if RUN_MANIFEST_SHA256 is None or base._hash(run_raw) != RUN_MANIFEST_SHA256:
        raise ValueError('Postseason run requires independent verification')
    base._verified_files(run, json.loads(run_raw))
    payloads = {name: (run / name).read_bytes() for name in RUN_MEMBERS}
    payloads.update({'research-manifest.json': run_raw, 'charter.md': sources.CHARTER.read_bytes(),
                     'capture.json': (capture / 'capture.json').read_bytes(),
                     'postseason-qualification.json': (capture / 'postseason-qualification.json').read_bytes()})
    for s in json.loads(payloads['capture.json'])['sources']:
        if Path(s['file']).name != s['file'] or s['file'] in payloads:
            raise ValueError('Invalid or reserved capture member')
        payloads[s['file']] = (capture / s['file']).read_bytes()
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        with (output / name).open('xb') as f:
            f.write(raw)
    generated = datetime.now(timezone.utc).isoformat()
    data = _derive_payload(output, payloads, generated)
    payloads.update({'snapshot.json': base._json(data), 'ratings.csv': base._csv(data['teams'], base.TEAM_COLUMNS),
                     'forecasts.csv': base._csv(data['games'], (*base.IDENTITY, 'margin', 'total', 'home_points', 'away_points'))})
    manifest = dict(schema_version=1, edition=EDITION, generated_at=generated,
                    files={name: dict(bytes=len(raw), sha256=base._hash(raw)) for name, raw in payloads.items()})
    _validate(output, manifest, payloads)
    for name in ('snapshot.json', 'ratings.csv', 'forecasts.csv'):
        with (output / name).open('xb') as f:
            f.write(payloads[name])
    with (output / 'manifest.json').open('xb') as f:
        f.write(base._json(manifest))
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--output', type=Path, default=DEFAULT_DIR)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    data = load_snapshot(args.verify) if args.verify else build_snapshot(args.run, args.capture, args.output)
    print(json.dumps(dict(edition=data['edition'], teams=len(data['teams']), games=len(data['games']), validation=data['validation'])))
