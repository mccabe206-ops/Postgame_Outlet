"""One separately verified opening-week edition; no fitting or weekly registration."""
import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

import pgo_challenger as ch
import pgo_current_strength as current
import pgo_forecast_snapshot as incumbent
import pgo_model
import pgo_prospective as prospective
import pgo_sources
from research.pgo_input_audit.audit_model import exposure_qb_features

ROOT = Path(__file__).resolve().parent
EDITION = 'pgo-corrected-week1-2026-09-08'
CHARTER_SHA256 = '643cdc172fc3ad15393989d8e9b021b3975833d6ae51f7ee162a837c39a25c12'
REFRESH_SHA256 = 'c9749324b8bf39f088811717f121255f11b2dd6bb107372d6d0a7ea638c2f05b'
RUN_MANIFEST_SHA256 = '7530b3199f8a17ffec34f9e5351919ea67cb45df66e16befd655ab4e746f7a4c'
# Append reviewed capture/qualification pairs; never replace earlier pairs.
# Existing weekly revisions must remain verifiable after a source refresh.
APPROVED_SOURCE_PAIRS = frozenset({(
    '122ef5740e94ba2e8b4464d7ea9e6e8fe953d0e0ac49527fee5a6050039672f2',
    '4c7f700531dc43b38181f9c205564057615ff54613832a2c2970d1963d60d76b',
)})
INCUMBENT_DIR = ROOT / 'docs/evidence/forecast-lab-2026/september-07'
INCUMBENT_MANIFEST_SHA256 = '43bdeee73a2d3301eedbcecc7d291dc9ebe68cf196860e7217326570e4fe2f42'
DEFAULT_OUTPUT = INCUMBENT_DIR.parent / 'september-08-corrected'
IDENTITY = ('game_id', 'season', 'week', 'kickoff', 'game_type', 'location',
            'home', 'away', 'home_rest', 'away_rest')
GAME_COLUMNS = (*IDENTITY, 'margin', 'total', 'home_points', 'away_points',
                'pgo_v0_margin', 'legacy_margin', 'incumbent_margin', 'incumbent_total',
                'incumbent_home_points', 'incumbent_away_points', 'league_mean_total')
TEAM_COLUMNS = ('rank', 'team', 'rating', 'qb_name', 'qb_gsis_id')
METHOD = {'name': 'Corrected opening-week conditional draft', 'status': 'EXPERIMENTAL / HOLD',
          'roster_policy': 'ACT roster and sourced expected QB; ACT exclusion does not price lost injured-reserve talent.',
          'injury_coverage': 'Non-QB availability is explicitly unadjusted. Dated observations do not imply calibrated probabilities; missing reports mean unknown.',
          'history': 'ACT-derived history through 2025; clean four-game inputs, metric-specific QB exposure, symmetric fit; results retention 0.5 once. QB decay uses the fresh input capture clock.',
          'totals': 'Prior-season PF/PA heuristic; exact scores remain experimental.',
          'evaluation': 'Previously inspected historical seasons remain diagnostic; no scientific promotion. Grade every issued game against v0 and the September 7 incumbent.'}


def _json(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path):
    return json.loads(Path(path).read_bytes())


def _issued_incumbent():
    if _hash((INCUMBENT_DIR / 'manifest.json').read_bytes()) != INCUMBENT_MANIFEST_SHA256:
        raise ValueError('Issued September incumbent manifest differs')
    return incumbent.load_snapshot(INCUMBENT_DIR)


def _csv(rows, columns):
    text = io.StringIO(newline='')
    writer = csv.DictWriter(text, fieldnames=columns, extrasaction='ignore', lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    return text.getvalue().encode()


def _same(actual, expected, label):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise ValueError(f'{label} keys differ')
        for key in expected:
            _same(actual[key], expected[key], f'{label}.{key}')
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f'{label} rows differ')
        for a, b in zip(actual, expected):
            _same(a, b, label)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if (not isinstance(actual, (int, float)) or isinstance(actual, bool)
                or not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9)):
            raise ValueError(f'{label} does not reproduce')
    elif actual != expected:
        raise ValueError(f'{label} differs')


def _verified_files(directory, manifest):
    result = {}
    for name, item in manifest['files'].items():
        if Path(name).name != name or (directory / name).is_symlink():
            raise ValueError('Manifest member path is invalid')
        raw = (directory / name).read_bytes()
        if len(raw) != item['bytes'] or _hash(raw) != item['sha256']:
            raise ValueError(f'Manifest member differs: {name}')
        result[name] = raw
    return result


def score(features, fit):
    pp = fit['preprocessor']
    if (len(pp['feature_names']) != len(pp['medians']) or len(pp['medians']) != len(pp['scales'])
            or len(set(pp['feature_names'])) != len(pp['feature_names'])
            or not set(pp['missing_features']) <= set(pp['feature_names'])):
        raise ValueError('Fitted feature schema differs')
    vector = []
    for key, median, scale in zip(pp['feature_names'], pp['medians'], pp['scales']):
        if not math.isfinite(median) or not math.isfinite(scale) or scale <= 0:
            raise ValueError('Fitted preprocessing must be finite and positive')
        value = features[key]
        vector.append(0. if value is None else (value - median) / scale)
    vector += [float(features[key] is None) for key in pp['missing_features']]
    coefficients = fit['coefficients']
    if len(coefficients) != len(vector) + 1 or not all(math.isfinite(v) for v in [*vector, *coefficients]):
        raise ValueError('Fitted values must be finite and aligned')
    return coefficients[0] + math.fsum(v * b for v, b in zip(vector, coefficients[1:]))


def current_features(context, selected_roster, inputs_as_of):
    if context['season'] != 2025:
        raise ValueError('Corrected construction requires final 2025 historical state')
    local = deepcopy(context)
    state = current._advance_qb_clock(local, inputs_as_of)
    features = {}
    for team, row in selected_roster.items():
        player_id = ch._roster_player_id(row, context['inputs']['colliding_gsis'])
        try:
            years_value = float(row['years_exp'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('Fresh QB years_exp must be present and numeric') from error
        if not math.isfinite(years_value) or years_value < 0 or not years_value.is_integer():
            raise ValueError('Fresh QB years_exp must be a finite nonnegative integer')
        years = int(years_value)
        draft = float(row['draft_number']) if row.get('draft_number') else None
        if draft is not None and (not math.isfinite(draft) or draft <= 0):
            raise ValueError('Fresh QB metadata is invalid')
        qb = exposure_qb_features(player_id, years, draft, state)
        features[team] = {name: context['ratios'][team].get(name) for name in ch.PERFORMANCE_FEATURES}
        features[team].update({name: qb[name] for name in ch.QB_FEATURES})
        features[team].update(pgo_v0=context['ratings'].get(team, 0.) * .5,
                              offense_availability=0., defense_availability=0., qb_current_minus_full=0.)
    return features


def team_coverage(source, qb_id):
    kind = source['source_kind']
    if kind not in {'no_formal_report', 'formal_injury_report'}:
        raise ValueError('Unsupported corrected coverage source')
    unavailable = source.get('known_unavailable', [])
    blocked = any(row.get('gsis_id') == qb_id for row in unavailable)
    status = 'BLOCKED_EXPECTED_QB_UNAVAILABLE' if blocked else ('UNKNOWN' if kind == 'no_formal_report' else 'DATED_REPORT_UNADJUSTED')
    return {'source_kind': kind, 'status': status,
            'report_date': source.get('report_date'), 'notes': source.get('notes', []),
            'known_unavailable': unavailable, 'observations': source.get('observations', []),
            'source_url': source.get('source_url'), 'captured_at': source.get('captured_at')}


def _inputs(directory, capture, qualification):
    sources = capture['sources']
    if len({s['file'] for s in sources}) != len(sources):
        raise ValueError('Duplicate captured source')
    for item in sources:
        name = item['file']
        if Path(name).name != name:
            raise ValueError('Captured source path is invalid')
        raw = (directory / name).read_bytes()
        if len(raw) != item['bytes'] or _hash(raw) != item['sha256']:
            raise ValueError('Captured source hash/size differs')
        url = urlsplit(item['url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password or item['status'] != 200:
            raise ValueError('Source must have a successful HTTPS capture')
        current._utc(item['captured_at'])
        if item.get('started_at') and current._utc(item['started_at']) > current._utc(item['captured_at']):
            raise ValueError('Source retrieval completion precedes start')
    if (qualification['status'] != 'PASS' or qualification.get('failed_checks')
            or qualification['charter_sha256'] != CHARTER_SHA256
            or qualification['capture_manifest_sha256'] != _hash((directory / 'capture.json').read_bytes())):
        raise ValueError('Source qualification is not bound to the capture')
    captured = {s['file']: s for s in sources}
    injury_sources = {s['file']: s for s in qualification['raw_injury_sources']}
    if len(injury_sources) != len(qualification['raw_injury_sources']) or not injury_sources:
        raise ValueError('Official injury provenance is missing or duplicate')
    for name, item in injury_sources.items():
        if name not in captured or any(item[k] != captured[name][k] for k in
                                      ('url', 'bytes', 'sha256', 'captured_at', 'status')):
            raise ValueError('Official injury source differs from captured bytes')
    for entry in qualification['coverage'].values():
        source = injury_sources.get(entry['source_file'])
        if (source is None or entry['source_url'] != source['url']
                or entry['captured_at'] != source['captured_at']):
            raise ValueError('Team coverage is not bound to official source capture')
        if entry['source_kind'] == 'formal_injury_report':
            report = datetime.fromisoformat(entry['report_date']).date()
            if report > current._utc(source['captured_at']).date():
                raise ValueError('Formal report date is after retrieval')
        for observation in [*entry.get('observations', []), *entry.get('known_unavailable', [])]:
            if observation.get('source_url') != source['url']:
                raise ValueError('Player observation has a different official source')
    all_roster = list(pgo_sources.open_csv(directory / 'roster.csv.gz'))
    active = {}
    for row in all_roster:
        if row['status'].strip() != 'ACT':
            continue
        if row['season'] != '2026' or row['week'] != '1':
            raise ValueError('ACT roster period differs')
        key = (pgo_sources.normalize_team(row['team']), row['gsis_id'])
        if key in active:
            raise ValueError('Duplicate ACT roster identity')
        active[key] = row
    depth = list(pgo_sources.open_csv(directory / 'depth.csv.gz'))
    depth_capture = next(s['captured_at'] for s in sources if s['file'] == 'depth.csv.gz')
    eligible = [r for r in depth if current._utc(r['dt']) <= current._utc(depth_capture)]
    latest = max(current._utc(r['dt']) for r in eligible)
    chosen = [r for r in eligible if current._utc(r['dt']) == latest and r['pos_abb'] == 'QB' and r['pos_rank'] == '1']
    selected = {}
    for row in chosen:
        team = pgo_sources.normalize_team(row['team'])
        if team in selected or (team, row['gsis_id']) not in active:
            raise ValueError('Expected QB is duplicate or not ACT')
        roster = active[team, row['gsis_id']]
        if roster['position'] != 'QB' or not roster['full_name']:
            raise ValueError('Expected QB roster position/name differs')
        selected[team] = roster
    if set(selected) != set(pgo_model.CURRENT_TEAMS) or len({r['gsis_id'] for r in selected.values()}) != 32:
        raise ValueError('Expected QBs must uniquely cover 32 teams')
    qualified = {(r['team'], r['gsis_id']) for r in qualification['chosen_qbs']}
    if len(qualification['chosen_qbs']) != 32 or qualified != {(t, r['gsis_id']) for t, r in selected.items()}:
        raise ValueError('Qualified QB selection differs from raw sources')
    schedule = []
    for row in pgo_sources.open_csv(directory / 'schedule.csv.gz'):
        if row['season'] != '2026' or row['game_type'] != 'REG' or int(row['week']) != 1:
            continue
        value = prospective._normalize_row(row)
        game = {k: value[k] for k in IDENTITY if k not in ('home', 'away')}
        game.update(home=value['home_team'], away=value['away_team'])
        game['_has_result'] = bool(value['home_score'] or value['away_score'])
        schedule.append(game)
    counts = Counter(t for g in schedule for t in (g['home'], g['away']))
    if (len(schedule) != 16 or len({g['game_id'] for g in schedule}) != 16
            or set(counts) != set(pgo_model.CURRENT_TEAMS) or set(counts.values()) != {1}):
        raise ValueError('Exactly 16 unique opening-week games are required')
    return selected, sorted(schedule, key=lambda g: (g['kickoff'], g['game_id'])), latest.isoformat()


def _derive(directory, capture, qualification, context, fit, inputs_as_of, prior, generated_at):
    selected, schedule, depth_as_of = _inputs(directory, capture, qualification)
    features = current_features(context, selected, inputs_as_of)
    pp = fit['preprocessor']
    expected_names = set(next(iter(features.values()))) | {'home_field', 'rest_difference'}
    if set(pp['feature_names']) != expected_names:
        raise ValueError('Fit is not the declared clean exposure construction')
    neutral = {t: {**f, 'home_field': 0., 'rest_difference': 0.} for t, f in features.items()}
    scores = {t: score(f, fit) for t, f in neutral.items()}
    center = math.fsum(scores.values()) / 32
    names = [*pp['feature_names'], *(k + '_missing' for k in pp['missing_features'])]
    terms = {}
    for team, f in neutral.items():
        vector = [0. if f[k] is None else (f[k] - m) / s for k, m, s in zip(pp['feature_names'], pp['medians'], pp['scales'])]
        vector += [float(f[k] is None) for k in pp['missing_features']]
        terms[team] = dict(zip(names, (v * b for v, b in zip(vector, fit['coefficients'][1:]))))
    means = {k: math.fsum(v[k] for v in terms.values()) / 32 for k in names}
    teams = []
    coverage = qualification['coverage']
    if set(coverage) != set(selected):
        raise ValueError('Coverage must explicitly include all 32 teams')
    for rank, team in enumerate(sorted(scores, key=lambda t: (-(scores[t] - center), t)), 1):
        row = selected[team]
        teams.append({'rank': rank, 'team': team, 'rating': scores[team] - center,
                      'qb_name': row['full_name'], 'qb_gsis_id': row['gsis_id'], 'features': features[team],
                      'contributions': {k: terms[team][k] - means[k] for k in names},
                      'coverage': team_coverage(coverage[team], row['gsis_id'])})
    # Structural checks include individual missing inputs and both signed venues.
    for f in neutral.values():
        zero = {k: 0. if value is not None else None for k, value in f.items()}
        if abs(score(zero, fit)) > 1e-8:
            raise ValueError('Identical neutral teams violate symmetry')
        for missing in [None, *pp['feature_names']]:
            forward = {**f, 'home_field': 1., 'rest_difference': 1.}
            if missing is not None:
                forward[missing] = None
            reverse = {k: -v if v is not None else None for k, v in forward.items()}
            if abs(score(forward, fit) + score(reverse, fit)) > 1e-8:
                raise ValueError('Fitted reversal violates symmetry')
    prior_games = {g['game_id']: g for g in prior['games']}
    rates, league = incumbent._scoring_rates({('schedule_results', None): directory / 'scoring-history-2025.csv'})
    games, omitted = [], []
    team_status = {row['team']: row['coverage']['status'] for row in teams}
    for game in schedule:
        old = prior_games[game['game_id']]
        if any(game[k] != old[k] for k in IDENTITY):
            raise ValueError('Fresh game identity/rest differs from incumbent; review required')
        lock_at = current._utc(game['kickoff']) - timedelta(minutes=60)
        if current._utc(generated_at) >= lock_at:
            omitted.append({'game_id': game['game_id'], 'reason': 'EXISTING_CUTOFF_ELAPSED', 'lock_at': lock_at.isoformat()})
            continue
        if game['_has_result']:
            raise ValueError('Eligible opening-week game already has results')
        if any(team_status[t] == 'BLOCKED_EXPECTED_QB_UNAVAILABLE' for t in (game['home'], game['away'])):
            omitted.append({'game_id': game['game_id'], 'reason': 'EXPECTED_QB_UNAVAILABLE', 'lock_at': lock_at.isoformat()})
            continue
        game = {k: game[k] for k in IDENTITY}
        matchup = {**game, 'neutral': game['location'] == 'Neutral'}
        margin = score(ch._matchup_features(features[game['home']], features[game['away']], matchup), fit)
        total = math.fsum(rates[t][k] for t in (game['home'], game['away']) for k in ('pf', 'pa')) / 2
        hp, ap = incumbent.expected_scores(total, margin)
        games.append({**game, 'margin': margin, 'total': total, 'home_points': hp, 'away_points': ap,
                      'pgo_v0_margin': old['pgo_v0_margin'], 'legacy_margin': old['legacy_margin'],
                      'incumbent_margin': old['margin'], 'incumbent_total': old['total'],
                      'incumbent_home_points': old['home_points'], 'incumbent_away_points': old['away_points'],
                      'league_mean_total': league})
    if not games:
        raise ValueError('No eligible opening-week matchup remains')
    return teams, games, rates, league, depth_as_of, omitted


def load_snapshot(directory):
    try:
        return _load_snapshot(directory)
    except (KeyError, TypeError, IndexError, StopIteration) as error:
        raise ValueError(f'Incomplete corrected snapshot schema: {error}') from error


def _load_snapshot(directory):
    directory = Path(directory)
    manifest = _read(directory / 'manifest.json')
    if manifest['schema_version'] != 1 or manifest['edition'] != EDITION:
        raise ValueError('Unknown corrected forecast edition')
    raw = _verified_files(directory, manifest)
    return _validate(directory, manifest, raw)


def _validate(directory, manifest, raw):
    data = json.loads(raw['snapshot.json'])
    if data['edition'] != EDITION or data['schema_version'] != 1:
        raise ValueError('Unknown corrected snapshot schema')
    if RUN_MANIFEST_SHA256 is None or _hash(raw['research-manifest.json']) != RUN_MANIFEST_SHA256:
        raise ValueError('Corrected research run is not the verified pinned run')
    if _hash(raw['charter.md']) != CHARTER_SHA256:
        raise ValueError('Corrected charter differs')
    if _hash(raw['source-refresh-clarification.md']) != REFRESH_SHA256:
        raise ValueError('Corrected source-refresh contract differs')
    if (_hash(raw['capture.json']), _hash(raw['source-qualification.json'])) not in APPROVED_SOURCE_PAIRS:
        raise ValueError('Corrected capture/qualification differ from verified sources')
    run_files = json.loads(raw['research-manifest.json'])['files']
    for name in ('final-fit.json', 'historical-context.json', 'run-receipt.json'):
        if _hash(raw[name]) != run_files[name]['sha256'] or len(raw[name]) != run_files[name]['bytes']:
            raise ValueError('Fit/context differ from research run')
    fit, context = json.loads(raw['final-fit.json']), json.loads(raw['historical-context.json'])
    if (fit['charter_sha256'] != CHARTER_SHA256
            or fit['historical_context_sha256'] != _hash(raw['historical-context.json'])):
        raise ValueError('Final fit is not bound to the declared context/charter')
    capture, qualification = json.loads(raw['capture.json']), json.loads(raw['source-qualification.json'])
    inputs_as_of = max(current._utc(s['captured_at']) for s in capture['sources']).isoformat()
    generated = current._utc(data['generated_at'])
    if (current._utc(inputs_as_of) > generated or data['inputs_as_of'] != inputs_as_of
            or manifest['generated_at'] != data['generated_at']
            or current._utc(json.loads(raw['run-receipt.json'])['completed_at']) > generated):
        raise ValueError('Source/issuance timestamps differ')
    prior = _issued_incumbent()
    if raw['scoring-history-2025.csv'] != (INCUMBENT_DIR / 'scoring-history-2025.csv').read_bytes():
        raise ValueError('Historical scoring baseline differs')
    teams, games, rates, league, depth, omitted = _derive(directory, capture, qualification, context, fit, inputs_as_of, prior, generated)
    for key, value in {'fit': fit, 'teams': teams, 'games': games, 'scoring_rates': rates,
                       'league_mean_total': league, 'depth_as_of': depth,
                       'coverage': qualification['coverage'], 'research_run_manifest_sha256': RUN_MANIFEST_SHA256,
                       'method': METHOD, 'skipped_games': omitted}.items():
        _same(data[key], value, key)
    for game in games:
        if generated >= current._utc(game['kickoff']) - timedelta(minutes=60):
            raise ValueError('Corrected issuance is at or after a game cutoff')
    sources = [dict(name=s['file'], url=s['url'], sha256=s['sha256'], bytes=s['bytes'], captured_at=s['captured_at']) for s in capture['sources']]
    _same(data['sources'], sources, 'sources')
    # Numerical replay was checked above; CSV must exactly match the saved JSON.
    if (raw['ratings.csv'] != _csv(data['teams'], TEAM_COLUMNS)
            or raw['forecasts.csv'] != _csv(data['games'], GAME_COLUMNS)):
        raise ValueError('Corrected CSV differs from verified values')
    return data


def build_snapshot(run, capture_dir, qualification_path, output=DEFAULT_OUTPUT):
    run, capture_dir, output = Path(run), Path(capture_dir), Path(output)
    if output.exists():
        raise ValueError('Corrected output must be a new directory')
    run_raw = (run / 'manifest.json').read_bytes()
    if RUN_MANIFEST_SHA256 is None or _hash(run_raw) != RUN_MANIFEST_SHA256:
        raise ValueError('Corrected run must pass independent verification before source build')
    _verified_files(run, json.loads(run_raw))
    charter = ROOT / 'research/pgo_week1_corrected/charter.md'
    refresh = charter.with_name('source-refresh-clarification.md')
    if _hash(charter.read_bytes()) != CHARTER_SHA256:
        raise ValueError('Corrected charter differs')
    if _hash(refresh.read_bytes()) != REFRESH_SHA256:
        raise ValueError('Corrected source-refresh contract differs')
    capture = _read(capture_dir / 'capture.json')
    qualification = _read(qualification_path)
    if (_hash((capture_dir / 'capture.json').read_bytes()), _hash(Path(qualification_path).read_bytes())) not in APPROVED_SOURCE_PAIRS:
        raise ValueError('Fresh capture/qualification must pass independent verification before source build')
    payloads = {'research-manifest.json': run_raw, 'charter.md': charter.read_bytes(),
                'source-refresh-clarification.md': refresh.read_bytes(),
                'final-fit.json': (run / 'final-fit.json').read_bytes(),
                'historical-context.json': (run / 'historical-context.json').read_bytes(),
                'run-receipt.json': (run / 'run-receipt.json').read_bytes(),
                'capture.json': (capture_dir / 'capture.json').read_bytes(),
                'source-qualification.json': Path(qualification_path).read_bytes(),
                'scoring-history-2025.csv': (INCUMBENT_DIR / 'scoring-history-2025.csv').read_bytes()}
    if any(Path(s['file']).name != s['file'] or s['file'] in payloads for s in capture['sources']):
        raise ValueError('Captured filename is invalid or reserved')
    _inputs(capture_dir, capture, qualification)
    payloads.update({s['file']: (capture_dir / s['file']).read_bytes() for s in capture['sources']})
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        with (output / name).open('xb') as stream:
            stream.write(raw)
    inputs_as_of = max(current._utc(s['captured_at']) for s in capture['sources']).isoformat()
    prior = _issued_incumbent()
    fit, context = json.loads(payloads['final-fit.json']), json.loads(payloads['historical-context.json'])
    generated = datetime.now(timezone.utc).isoformat()
    teams, games, rates, league, depth, omitted = _derive(output, capture, qualification, context, fit, inputs_as_of, prior, generated)
    data = {'schema_version': 1, 'edition': EDITION, 'generated_at': generated, 'inputs_as_of': inputs_as_of,
            'depth_as_of': depth, 'fit': fit, 'teams': teams, 'games': games,
            'scoring_rates': rates, 'league_mean_total': league, 'coverage': qualification['coverage'],
            'sources': [dict(name=s['file'], url=s['url'], sha256=s['sha256'], bytes=s['bytes'], captured_at=s['captured_at']) for s in capture['sources']],
            'research_run_manifest_sha256': RUN_MANIFEST_SHA256,
            'method': dict(METHOD), 'skipped_games': omitted,
            'builder_code_sha256': _hash(Path(__file__).read_bytes().replace(b'\r\n', b'\n')),
            'builder_code_hash_format': 'UTF-8 source with LF line endings; informational generation binding'}
    payloads.update({'snapshot.json': _json(data), 'ratings.csv': _csv(teams, TEAM_COLUMNS), 'forecasts.csv': _csv(games, GAME_COLUMNS)})
    for name in ('snapshot.json', 'ratings.csv', 'forecasts.csv'):
        with (output / name).open('xb') as stream:
            stream.write(payloads[name])
    manifest = {'schema_version': 1, 'edition': EDITION, 'generated_at': generated,
                'files': {name: {'bytes': len(raw), 'sha256': _hash(raw)} for name, raw in payloads.items()}}
    _validate(output, manifest, payloads)
    with (output / 'manifest.json').open('xb') as stream:
        stream.write(_json(manifest))
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            result = load_snapshot(args.verify)
        else:
            if not all((args.run, args.capture, args.qualification)):
                parser.error('--run, --capture and --qualification are required to build')
            result = build_snapshot(args.run, args.capture, args.qualification, args.output)
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
        parser.exit(1, f'Corrected forecast failed: {error}\n')
    print(f"Verified {result['edition']}: {len(result['teams'])} teams, {len(result['games'])} games; HOLD")
