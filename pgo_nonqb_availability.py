"""Separate, before-cutoff non-QB sensitivity using the preserved corrected fit."""
import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import gzip
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import statistics
from urllib.parse import urlsplit

import pgo_challenger as ch
import pgo_forecast_corrected as corrected
from pgo_model import CURRENT_TEAMS


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / 'docs/evidence/nonqb-availability-2026/september-09'
IDENTITY = 'pgo-nonqb-availability-20260909'
BASE_SHA256 = '0873068f08d37d8e22d67395af3a95cdcb425f32448cd3620a67d1e8e8a85117'
FIT_SHA256 = '5300bb8f7039da0aac0976fce8a5d1f29163e47ac4726bee19c59891bead6da8'
KNOWN = {'OUT', 'IR', 'PUP'}
UNCERTAIN = {'QUESTIONABLE', 'DOUBTFUL'}
INPUT_FILES = ('base.json', 'fit.json', 'evidence.json', 'roles.json', 'scenario.json')
HISTORY_HASHES = {
    'snap_counts': '80b02a6e511aa20283551cae622b29ba4d0a6f006c489a2d91591fcad33792e7',
    'weekly_rosters': 'c3376e135a7e62bb8b31631d7fe7501e8dd931929eaf1245a7dc6787486b0b24',
}


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _semantic_digest(value):
    return _digest(_json(value).rstrip(b'\n'))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _utc(value):
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace('Z', '+00:00'))
        _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'Timestamp requires a timezone')
        return parsed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f'Invalid aware timestamp: {value}') from error


def _now():
    return datetime.now(timezone.utc)


def _finite(value, label):
    _require(type(value) in (int, float) and math.isfinite(value), f'{label} must be finite numeric')
    return float(value)


def _safe_file(value):
    _require(isinstance(value, str) and value and '\\' not in value, 'Source filename must be relative')
    path = PurePosixPath(value)
    _require(not path.is_absolute() and ':' not in value and all(p not in ('..', '.') for p in path.parts)
             and str(path) == value, 'Source filename must be a safe relative path')
    return value


def _url(value):
    _require(isinstance(value, str), 'Source URL is required')
    parsed = urlsplit(value)
    _require(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password,
             'Source URL must be HTTPS without credentials')


def _source_clock(row, as_of, *, report=True):
    _url(row['source_url'])
    captured = _utc(row['captured_at'])
    _require(captured <= as_of, 'Source capture is after evidence as_of')
    if report and row.get('report_date') is not None:
        try:
            published = date.fromisoformat(row['report_date'])
        except (TypeError, ValueError) as error:
            raise ValueError('Report date must be an ISO date') from error
        _require(published <= captured.date(), 'Report date is after source capture')


def _unit(position):
    _require(isinstance(position, str) and position == position.strip().upper() and position,
             'Position must be a nonempty uppercase label')
    if '/' in position:
        units = {_unit(part) for part in position.split('/')}
        return next(iter(units)) if len(units) == 1 else 'unknown'
    group = ch.ROLE_POSITION_GROUPS.get(position)
    return ('offense' if group in ('skill', 'line') else 'defense' if group == 'defense'
            else 'qb' if position == 'QB' else 'special' if position in ('K', 'P', 'LS') else 'unknown')


def _key(row):
    _require(row['team'] in CURRENT_TEAMS and isinstance(row['gsis_id'], str)
             and re.fullmatch(r'\d{2}-\d{7}', row['gsis_id']), 'Player team or GSIS identity is invalid')
    return row['team'], row['gsis_id']


def _source_entries(evidence):
    entries = {}
    for row in evidence.get('sources', []):
        name = _safe_file(row['source_file'])
        _require(name not in entries and row['status'] == 200 and type(row['bytes']) is int and row['bytes'] > 0
                 and isinstance(row['sha256'], str) and re.fullmatch('[0-9a-f]{64}', row['sha256']),
                 'Duplicate or invalid raw source metadata')
        _source_clock({'source_url': row['url'], 'captured_at': row['captured_at']}, _utc(evidence['as_of']), report=False)
        entries[name] = row
    return entries


def _role_sources(evidence):
    entries = {}
    for row in evidence.get('role_sources', []):
        name = _safe_file(row['source_file'])
        _require(name not in entries and row['kind'] == 'qualified_local_source'
                 and row['qualification_manifest_sha256'] == '17f1dec348ad4992dbe32c6e5d54461ef8bd858e7e9d1775e37951385c492f2a'
                 and type(row['bytes']) is int and row['bytes'] > 0
                 and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'Invalid qualified historical source')
        _require(row['sha256'] in HISTORY_HASHES.values(), 'Historical role source differs from the qualified 2025 source')
        entries[name] = row
    return entries


def _role_observations(role, unit):
    observations = role.get('observations')
    if observations is None:
        return False
    _require(isinstance(observations, list) and len(observations) == role['sample_count'], 'Role witness count differs')
    seen, order = set(), []
    for row in observations:
        season, week = row['season'], row['week']
        _require(type(season) is int and 2013 <= season <= 2025 and type(week) is int and 1 <= week <= 18,
                 'Role witness season/week is invalid')
        _require(row['team'] in CURRENT_TEAMS and row['game_id'] not in seen, 'Duplicate or invalid role witness game')
        share, snaps, denominator = (_finite(row[k], k) for k in ('share', 'unit_snaps', 'team_unit_denominator'))
        _require(0 < share <= 1 and 0 < snaps <= denominator and abs(share - snaps / denominator) < 1e-12,
                 'Role witness snap ratio does not reproduce')
        roster, snap = row['roster_row'], row['snap_row']
        _require(roster['gsis_id'] == role['gsis_id'] and ch.normalize_team(roster['team']) == row['team']
                 and roster['status'] == 'ACT' and _unit(roster['position']) == unit,
                 'Role witness roster identity differs')
        _require(ch.normalize_team(snap['team']) == row['team'] and snap['game_id'] == row['game_id']
                 and snap['game_type'] == 'REG' and int(snap['season']) == season
                 and int(snap['week']) == week and int(roster['season']) == season
                 and int(roster['week']) == week and float(snap[unit + '_snaps']) == snaps,
                 'Role witness source row differs')
        resolved, method = ch._snap_identity(snap, ch._roster_identity_maps([roster], ()))
        _require(resolved == role['gsis_id'] and method == row['identity_method'], 'Role witness snap identity differs')
        seen.add(row['game_id'])
        order.append((season, week, row['game_id']))
    _require(order == sorted(order), 'Role witnesses are not chronological')
    if observations:
        _require(abs(statistics.median(r['share'] for r in observations) - role['snap_share']) < 1e-12,
                 'Role witness median differs')
        last = observations[-1]
        _require(role['last_observed'] == f"{last['season']} Week {last['week']}"
                 and role['previous_team'] == last['team'], 'Last role observation differs')
    return True


def _bound_source(row, sources):
    if not sources:
        return
    candidates = ([sources.get(row['source_file'])] if row.get('source_file') else list(sources.values()))
    _require(any(s and s['url'] == row['source_url'] and s['captured_at'] == row['captured_at'] for s in candidates),
             'Observation does not match a captured source URL and clock')


def build_scenario(base_snapshot, fit, evidence, roles, generated_at):
    """Calculate scoped scenarios without changing any input or issued forecast."""
    try:
        return _build_scenario(base_snapshot, fit, evidence, roles, generated_at)
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError(f'Invalid availability input schema: {error}') from error


def _build_scenario(base, fit, evidence, roles, generated_at):
    _require(_semantic_digest(base) == BASE_SHA256 and _semantic_digest(fit) == FIT_SHA256,
             'Only the exact preserved September 8 corrected base and fit are accepted')
    generated, as_of = _utc(generated_at), _utc(evidence['as_of'])
    _require(_utc(base['generated_at']) <= as_of <= generated, 'Base/evidence/generation clocks are out of order')
    _require(base['fit'] == fit, 'Base snapshot and fit differ')
    sources = _source_entries(evidence)
    _role_sources(evidence)
    coverage = {}
    for row in evidence['teams']:
        team = row['team']
        _require(team in CURRENT_TEAMS and team not in coverage, 'Duplicate or unknown team coverage')
        _require(row['source_kind'] in ('formal_game_status', 'practice_only', 'unknown'), 'Unknown coverage kind')
        _require(row['source_kind'] != 'formal_game_status' or row.get('report_date'), 'Formal game-status reports need a report date')
        _source_clock(row, as_of)
        _bound_source(row, sources)
        coverage[team] = dict(row)
    _require(set(coverage) == set(CURRENT_TEAMS), 'Coverage must explicitly include all 32 teams')
    players, ids = {}, set()
    for row in evidence['players']:
        key = _key(row)
        _require(key not in players and key[1] not in ids, 'Duplicate or conflicting current player identity')
        _require(row['status'] in KNOWN | UNCERTAIN, 'Unsupported availability status')
        _require(isinstance(row['name'], str) and row['name'].strip(), 'Player name is required')
        _source_clock(row, as_of)
        _safe_file(row['source_file'])
        _bound_source(row, sources)
        players[key] = {**row, 'unit': _unit(row['position'])}
        ids.add(key[1])
    role_map = {}
    for role in roles:
        key = _key(role)
        _require(key in players and key not in role_map, 'Role identity is duplicate or absent from current observations')
        _require(_unit(role['position']) == players[key]['unit'], 'Player and role units disagree')
        count, share = role['sample_count'], role['snap_share']
        _require(type(count) is int and 0 <= count <= 4, 'Role sample count must be an integer from zero to four')
        _require(isinstance(role['source_note'], str) and role['source_note'].strip(), 'Role source note is required')
        _require(role['previous_team'] is None or role['previous_team'] in CURRENT_TEAMS, 'Previous team is invalid')
        if share is not None:
            _require(0 < _finite(share, 'Snap share') <= 1 and count > 0, 'Known role requires positive share and observations')
            if not _role_observations(role, players[key]['unit']):
                stamp = role['last_observed']
                observed = date.fromisoformat(stamp) if isinstance(stamp, str) and len(stamp) == 10 else _utc(stamp).date()
                _require(observed.year <= 2025 and observed <= as_of.date(), 'Role history must end before 2026')
        else:
            _require(count == 0 and role['last_observed'] is None, 'Unknown role cannot claim supporting observations')
            _role_observations(role, players[key]['unit'])
        role_map[key] = dict(role)
    for row in evidence.get('excluded', []):
        _require(row['team'] in CURRENT_TEAMS, 'Excluded observation team is unknown')
        if sources:
            _require(row['source_file'] in sources, 'Excluded observation lacks its source')
    pp = fit['preprocessor']
    weights = {unit: fit['coefficients'][pp['feature_names'].index(unit + '_availability') + 1]
               / pp['scales'][pp['feature_names'].index(unit + '_availability')] for unit in ('offense', 'defense')}
    _require(all(v > 0 for v in weights.values()), 'Availability coefficients must preserve monotonic losses')
    neutral = {row['team']: {**row['features'], 'home_field': 0., 'rest_difference': 0.} for row in base['teams']}
    baseline_scores = {team: corrected.score(features, fit) for team, features in neutral.items()}
    center = math.fsum(baseline_scores.values()) / len(baseline_scores)
    teams = []
    for old in base['teams']:
        team = old['team']
        _require(abs(old['rating'] - (baseline_scores[team] - center)) < 1e-9, 'Base rating does not replay')
        _require(all(neutral[team][u + '_availability'] == 0 for u in weights), 'Base availability is not zero')
        excluded = [dict(row) for row in evidence.get('excluded', []) if row['team'] == team]
        for row in excluded:
            _require(isinstance(row.get('name'), str) and row['name'] and isinstance(row.get('reason'), str)
                     and row['reason'], 'Excluded observations need a name and reason')
            _safe_file(row['source_file'])
        rows, unknown = [], sum(row.get('position') not in ('K', 'P', 'LS') for row in excluded)
        for key, observation in players.items():
            if key[0] != team:
                continue
            unit, role = observation['unit'], role_map.get(key)
            reason = None
            if unit == 'qb':
                reason = 'QB availability requires the separate expected-QB policy'
            elif unit == 'special':
                reason = 'Special teams are outside this adjustment'
            elif unit == 'unknown':
                reason = 'Unsupported position has no qualified unit role'
            elif role is None or role['snap_share'] is None:
                reason = (role or {}).get('reason') or 'Expected playing role is unavailable'
            delta = None if reason else -weights[unit] * role['snap_share']
            unknown += int(reason is not None and unit != 'special')
            rows.append({**observation, 'role': role, 'delta': delta, 'reason': reason})
        reported = coverage[team]['source_kind'] == 'formal_game_status'
        complete = reported and not unknown
        status = 'COMPLETE' if complete else 'PARTIAL' if rows or excluded or coverage[team]['source_kind'] == 'practice_only' else 'UNKNOWN'
        known = math.fsum(r['delta'] for r in rows if r['delta'] is not None and r['status'] in KNOWN)
        low = math.fsum(r['delta'] for r in rows if r['delta'] is not None)
        has_priced_players = any(r['delta'] is not None for r in rows)
        # Verify the arithmetic through the existing scorer, not a separate model.
        for statuses, subtotal in ((KNOWN, known), (KNOWN | UNCERTAIN, low)):
            features = dict(neutral[team])
            for unit in weights:
                features[unit + '_availability'] = -math.fsum(r['role']['snap_share'] for r in rows
                    if r['unit'] == unit and r['delta'] is not None and r['status'] in statuses)
            _require(abs(corrected.score(features, fit) - baseline_scores[team] - subtotal) < 1e-9,
                     'Availability subtotal does not replay through the saved fit')
        teams.append(dict(team=team, base_rating=old['rating'],
            known_out_delta=known if has_priced_players or complete else None,
            all_uncertain_out_delta=low if has_priced_players or complete else None,
            known_out_rating=old['rating'] + known if complete else None,
            all_uncertain_out_rating=old['rating'] + low if complete else None,
            status=status, unknown_count=unknown, players=rows, excluded=excluded, coverage=coverage[team],
            reason=None if complete else 'Missing formal game-status coverage or an unpriced player; subtotals are partial'))
    by_team = {t['team']: t for t in teams}
    games = []
    for old in base['games']:
        home, away = (by_team[old[t]] for t in ('home', 'away'))
        cutoff = _utc(old['kickoff']) - timedelta(minutes=60)
        complete = home['status'] == away['status'] == 'COMPLETE' and generated < cutoff
        game = {k: old[k] for k in ('game_id', 'season', 'week', 'kickoff', 'game_type', 'location', 'home', 'away', 'home_rest', 'away_rest')}
        game.update(base_margin=old['margin'], cutoff=cutoff.isoformat(),
            status='CUTOFF_PASSED' if generated >= cutoff else 'COMPLETE' if complete else 'PARTIAL'
                   if 'PARTIAL' in (home['status'], away['status']) else 'UNKNOWN',
            known_out_margin=old['margin'] + home['known_out_delta'] - away['known_out_delta'] if complete else None,
            margin_low=old['margin'] + home['all_uncertain_out_delta'] - away['known_out_delta'] if complete else None,
            margin_high=old['margin'] + home['known_out_delta'] - away['all_uncertain_out_delta'] if complete else None)
        games.append(game)
    return dict(schema_version=1, identity=IDENTITY, status='EXPERIMENTAL / HOLD',
        generated_at=generated.isoformat(), as_of=as_of.isoformat(), base_edition=base['edition'],
        base_snapshot_sha256=BASE_SHA256, fit_sha256=FIT_SHA256, effective_unit_weights=weights,
        role_policy='Median of up to four positive prior regular-season unit snap shares through 2025; unvalidated playing-role proxy.',
        coverage_scope='Listed game-status observations and explicitly captured reserve supplements; missing reports are unknown.',
        interpretation='Conditional model-scale sensitivity; no player replacement valuation, probability, midpoint forecast, or promotion.',
        teams=teams, games=games)


def _checked_file(root, name):
    name = _safe_file(name)
    path = Path(root) / name
    _require(not path.is_symlink() and path.resolve().is_relative_to(Path(root).resolve()), 'Package file escapes its directory')
    return path


def _all_sources(evidence):
    sources, historical = _source_entries(evidence), _role_sources(evidence)
    _require(not set(sources) & set(historical), 'Live and historical source filenames overlap')
    return {**sources, **historical}


def _verify_depth_rows(roles, evidence, payloads, sources):
    if not any('current_depth_rows' in role for role in roles) and 'qb_checks' not in evidence:
        return
    source = evidence['depth_source']
    entry = sources.get(source['source_file'])
    _require(entry is not None and all(entry[k] == source[k] for k in ('sha256', 'bytes', 'url', 'captured_at')),
             'Current depth metadata is not bound to its captured source')
    raw = payloads['raw/' + source['source_file']]
    _require(len(raw) == source['bytes'] and _digest(raw) == source['sha256'], 'Current depth source bytes differ')
    captured, selected_at = _utc(source['captured_at']), _utc(evidence['depth_as_of'])
    _require(selected_at <= captured, 'Selected depth clock is after capture')
    latest, selected = None, []
    # Stream this large feed; only the latest eligible depth snapshot is retained.
    binary = gzip.GzipFile(fileobj=io.BytesIO(raw)) if raw.startswith(b'\x1f\x8b') else io.BytesIO(raw)
    with io.TextIOWrapper(binary, encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            stamp = _utc(row['dt'])
            if stamp > captured or (latest is not None and stamp < latest):
                continue
            if latest is None or stamp > latest:
                latest, selected = stamp, []
            selected.append(row)
    _require(latest == selected_at, 'Current depth is not the latest eligible captured snapshot')
    for role in roles:
        if 'current_depth_rows' not in role:
            continue
        matches = [r for r in selected if ch.normalize_team(r['team']) == role['team'] and r['gsis_id'] == role['gsis_id']]
        _require(role['current_depth_rows'] == matches, 'Current depth annotation differs from its exact captured rows')
    if 'qb_checks' not in evidence:
        return
    roster_source = evidence['roster_source']
    roster_entry = sources.get(roster_source['source_file'])
    _require(roster_entry is not None and all(roster_entry[k] == roster_source[k]
             for k in ('sha256', 'bytes', 'url', 'captured_at')), 'QB roster source metadata differs')
    roster_raw = payloads['raw/' + roster_source['source_file']]
    _require(len(roster_raw) == roster_source['bytes'] and _digest(roster_raw) == roster_source['sha256'],
             'QB roster source bytes differ')
    if roster_raw.startswith(b'\x1f\x8b'):
        roster_raw = gzip.decompress(roster_raw)
    roster_members = {_json(row) for row in csv.DictReader(io.StringIO(roster_raw.decode('utf-8-sig')))}
    expected = {(row['team'], row['qb_gsis_id']) for row in json.loads(payloads['base.json'])['teams']}
    checks = evidence['qb_checks']
    actual = {_key(row) for row in checks}
    depth_qbs = [row for row in selected if row['pos_abb'] == 'QB' and row['pos_rank'] == '1']
    _require(len(checks) == len(actual) == 32 and actual == expected
             and len(depth_qbs) == 32 and {(ch.normalize_team(r['team']), r['gsis_id']) for r in depth_qbs} == expected,
             'Current expected-QB identities differ from the preserved base')
    for check in checks:
        team, gsis = _key(check)
        roster, depth = check['roster_row'], check['depth_row']
        _require(_json(roster) in roster_members and roster['status'] == 'ACT' and roster['position'] == 'QB'
                 and int(roster['season']) == 2026 and int(roster['week']) == 1
                 and (ch.normalize_team(roster['team']), roster['gsis_id']) == (team, gsis)
                 and depth in depth_qbs and (ch.normalize_team(depth['team']), depth['gsis_id']) == (team, gsis),
                 'Current QB depth or roster witness differs')


def _verify_role_witnesses(roles, evidence, payloads):
    """Bind embedded role rows and denominators to the copied, pinned source bytes."""
    sources = _all_sources(evidence)
    _verify_depth_rows(roles, evidence, payloads, sources)
    by_hash = {entry['sha256']: payloads['raw/' + name] for name, entry in sources.items()}
    tables, memberships, denominators = {}, {}, {}
    histories = None
    observations = {_key(row): row for row in evidence.get('players', [])}
    _require(set(observations) == {_key(role) for role in roles}, 'Each observation needs a current roster role witness')
    for role in roles:
        _require(role.get('source_hashes') == HISTORY_HASHES, 'Role history source hashes differ')
        required = [*HISTORY_HASHES.values(), role['current_roster_sha256']]
        for sha in required:
            _require(sha in by_hash, 'Role witness raw source is absent from the package')
            if sha not in tables:
                data = by_hash[sha]
                if data.startswith(b'\x1f\x8b'):
                    data = gzip.decompress(data)
                tables[sha] = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
                memberships[sha] = {_json(row) for row in tables[sha]}
        roster = role['current_roster_row']
        _require(_json(roster) in memberships[role['current_roster_sha256']]
                 and roster['gsis_id'] == role['gsis_id'] and ch.normalize_team(roster['team']) == role['team']
                 and int(roster['season']) == 2026 and int(roster['week']) == 1
                 and _unit(roster['position']) == _unit(role['position']), 'Current role roster witness differs')
        aliases = {ch._normalize_player_name(roster.get('full_name'))}
        aliases.update(ch._normalize_player_name(f"{roster.get(given, '')} {roster.get('last_name', '')}")
                       for given in ('first_name', 'football_name'))
        _require(ch._normalize_player_name(observations[_key(role)]['name']) in aliases - {''},
                 'Current observation name disagrees with the exact roster identity')
        snap_hash, roster_hash = (HISTORY_HASHES[n] for n in ('snap_counts', 'weekly_rosters'))
        unit = _unit(role['position'])
        if histories is None:
            from research.pgo_nonqb_availability_20260909.prepare_roles import role_observations
            # The pinned 2025 qualification has no colliding GSIS identities.
            histories = role_observations(tables[roster_hash], tables[snap_hash], [])
        expected = histories.get((role['gsis_id'], unit), [])[-4:]
        _require(role.get('observations') == expected, 'Role witnesses are not the last four positive observations')
        if unit not in denominators and unit in ('offense', 'defense'):
            values = {}
            for row in tables[snap_hash]:
                if row['game_type'] == 'REG':
                    key = int(row['season']), int(row['week']), ch.normalize_team(row['team'])
                    values[key] = max(values.get(key, 0.), float(row[unit + '_snaps']))
            denominators[unit] = values
        _require('observations' in role, 'Role source observations are required')
        for witness in role['observations']:
            _require(_json(witness['snap_row']) in memberships[snap_hash]
                     and _json(witness['roster_row']) in memberships[roster_hash], 'Role witness is absent from its raw source')
            key = witness['season'], witness['week'], witness['team']
            _require(witness['team_unit_denominator'] == denominators[unit][key], 'Role denominator differs from the whole team feed')


def _write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _check_cutoff(clock, earlier, scenario):
    _require(clock >= earlier, 'Issuance clock moved backwards')
    eligible = [g for g in scenario['games'] if g['status'] != 'CUTOFF_PASSED']
    _require(eligible, 'No before-cutoff games remain')
    _require(all(clock < _utc(g['cutoff']) for g in eligible), 'Scenario write reached a game cutoff')


def save_package(base_snapshot, fit, evidence, roles, output=DEFAULT_OUTPUT, *, source_root=None):
    """Write a new manifested package, refusing source drift and late issuance."""
    output = Path(output)
    if output.exists():
        raise FileExistsError(f'Availability output already exists: {output}')
    generated = _utc(_now())
    scenario = build_scenario(base_snapshot, fit, evidence, roles, generated)
    payloads = dict(zip(INPUT_FILES, map(_json, (base_snapshot, fit, evidence, roles, scenario))))
    sources = _all_sources(evidence)
    _require(sources and source_root is not None, 'A captured raw source bundle is required')
    for name, entry in sources.items():
        raw = _checked_file(source_root, name).read_bytes()
        _require(len(raw) == entry['bytes'] and _digest(raw) == entry['sha256'], 'Captured raw source bytes differ')
        payloads['raw/' + name] = raw
    _verify_role_witnesses(roles, evidence, payloads)
    before = _utc(_now())
    _check_cutoff(before, generated, scenario)
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in payloads.items():
        _write(_checked_file(output, name), raw)
    manifest = dict(schema_version=1, identity=IDENTITY, generated_at=scenario['generated_at'],
                    files={n: dict(bytes=len(raw), sha256=_digest(raw)) for n, raw in payloads.items()})
    manifest_path = output / 'manifest.json'
    manifest_raw = _json(manifest)
    _write(manifest_path, manifest_raw)
    try:
        _check_cutoff(_utc(_now()), before, scenario)
    except Exception:
        _require(not manifest_path.is_symlink() and manifest_path.read_bytes() == manifest_raw,
                 'Refusing to invalidate a changed manifest')
        manifest_path.rename(output / 'rejected-manifest.json')
        raise
    return load_package(output)


def load_package(directory=DEFAULT_OUTPUT):
    """Return None only when absent; otherwise verify all bytes and replay."""
    directory = Path(directory)
    if not directory.exists():
        return None
    try:
        _require(directory.is_dir() and not directory.is_symlink(), 'Availability package must be a real directory')
        manifest = json.loads(_checked_file(directory, 'manifest.json').read_bytes())
        _require(manifest['schema_version'] == 1 and manifest['identity'] == IDENTITY, 'Unknown availability package')
        raw = {}
        for name, entry in manifest['files'].items():
            data = _checked_file(directory, name).read_bytes()
            _require(type(entry['bytes']) is int and len(data) == entry['bytes'] and _digest(data) == entry['sha256'],
                     f'Availability package bytes differ: {name}')
            raw[name] = data
        base, fit, evidence, roles, saved = (json.loads(raw[n]) for n in INPUT_FILES)
        sources = _all_sources(evidence)
        _require(sources and set(raw) == set(INPUT_FILES) | {'raw/' + n for n in sources}, 'Package source inventory differs')
        for name, entry in sources.items():
            _require(len(raw['raw/' + name]) == entry['bytes'] and _digest(raw['raw/' + name]) == entry['sha256'],
                     'Raw evidence source differs from its metadata')
        _verify_role_witnesses(roles, evidence, raw)
        rebuilt = build_scenario(base, fit, evidence, roles, manifest['generated_at'])
        _require(_json(rebuilt) == _json(saved), 'Availability scenario does not replay')
        return saved
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f'Incomplete or invalid availability package: {error}') from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--fit', type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--roles', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.verify:
        result = load_package(args.verify)
        _require(result is not None, 'Requested package does not exist')
    else:
        _require(all((args.base, args.fit, args.evidence, args.roles, args.source_root)), 'All five source arguments are required')
        result = save_package(*(json.loads(p.read_bytes()) for p in (args.base, args.fit, args.evidence, args.roles)),
                              args.output, source_root=args.source_root)
    print(json.dumps(dict(status=result['status'], teams=len(result['teams']), games=len(result['games']))))


if __name__ == '__main__':
    main()
