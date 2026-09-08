"""Fixed v2 descriptor formulas on corrected ACT identities; no model fitting.

Formula provenance and deliberate missingness/availability differences are in
charter.md. No imports or state changes in the older v2 worktree are needed.
"""
from collections import Counter
from datetime import date
import json
import math
import statistics

from research.pgo_week1_corrected import train as corrected

audit = corrected.audit
ch = audit.ch
IDENTITY = 'pgo-corrected-roster-candidate-2026-09-08'
UNIT_TERMS = ('role_weighted_age', 'young_role_share', 'role_weighted_draft_prior',
              'rookie_draft_capital')
FEATURES = ('qb_age_centered', 'qb_age_squared') + tuple(
    f'{unit}_{term}' for unit in ('offense', 'defense') for term in UNIT_TERMS)
ALIASES = dict(HB='RB', OT='T', OG='G', MLB='LB', FS='S', SS='S', SAF='S')
OFFENSE = frozenset('RB FB WR TE C G T OL'.split())
DEFENSE = frozenset('DE DT DL NT LB ILB OLB EDGE CB S DB'.split())


def age_years(value, clock):
    now = audit.current._utc(clock).date()
    if value is None or not str(value).strip():
        return None
    try:
        age = (now - date.fromisoformat(str(value).strip())).days / 365.2425
    except ValueError as error:
        raise ValueError(f'Invalid birth date: {value}') from error
    if not 18 <= age <= 50:
        raise ValueError(f'Invalid birth date age: {value}')
    return age


def integer(value, label):
    if value is None or not str(value).strip():
        return None
    try:
        result = float(value)
    except (ValueError, TypeError) as error:
        raise ValueError(f'Invalid {label}') from error
    if not math.isfinite(result) or result < 0 or not result.is_integer():
        raise ValueError(f'Invalid {label}: {value}')
    return int(result)


def position_unit(position):
    position = str(position or '').strip().upper().split('/', 1)[0]
    position = ALIASES.get(position, position)
    return ('offense' if position in OFFENSE else 'defense' if position in DEFENSE
            else 'qb' if position == 'QB' else 'special' if position in {'K', 'P', 'LS'}
            else 'unmapped')


def team_features(rows, starter, snap_history, clock, colliding_gsis):
    players = {}
    for row in rows:
        if (row.get('status') or '').strip() != 'ACT':
            raise ValueError('Non-ACT row reached roster adapter')
        pid = ch._roster_player_id(row, colliding_gsis)
        if not pid or pid in players:
            raise ValueError('Missing or duplicate roster identity')
        draft = integer(row.get('draft_number'), 'draft_number')
        player = dict(unit=position_unit(row.get('position')),
                      age=age_years(row.get('birth_date'), clock),
                      experience=integer(row.get('years_exp'), 'years_exp'),
                      draft=0.0 if not draft else 1 / math.sqrt(draft),
                      missing_draft=draft is None)
        for unit in ('offense', 'defense'):
            history = snap_history.get(pid, {}).get(unit, ())
            if len(history) > 4 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in history):
                raise ValueError('Invalid prior snap history')
            player[unit] = statistics.median(history) if history else None
        players[pid] = player
    if starter is not None and (starter not in players or players[starter]['unit'] != 'qb'):
        raise ValueError('Selected QB is not uniquely resolved on ACT roster')
    age = players[starter]['age'] if starter is not None else None
    values = dict(qb_age_centered=None if age is None else age-27,
                  qb_age_squared=None if age is None else (age-27)**2)
    coverage = {'resolved_ACT_rows': len(rows), 'resolved_players': len(players),
                'unmatched_identities': 0, 'unmapped_positions': sum(
                    p['unit'] == 'unmapped' for p in players.values()),
                'missing_selected_qb_age': int(age is None)}
    for unit in ('offense', 'defense'):
        selected = [p for p in players.values() if p['unit'] == unit]
        known = [p for p in selected if p[unit] is not None]
        ages = [p for p in known if p['age'] is not None]
        role = sum(p[unit] for p in known)
        age_role = sum(p[unit] for p in ages)
        missing_exp = sum(p['experience'] is None for p in selected)
        values.update({
            f'{unit}_role_weighted_age': sum(p[unit]*p['age'] for p in ages)/age_role if age_role else None,
            f'{unit}_young_role_share': sum(p[unit]*(p['age'] < 26) for p in ages)/age_role if age_role else None,
            f'{unit}_role_weighted_draft_prior': sum(p[unit]*p['draft'] for p in known)/role if role else None,
            f'{unit}_rookie_draft_capital': sum(p['draft'] for p in selected if p['experience'] == 0)/len(selected)
            if selected and not missing_exp else None,
        })
        coverage[unit] = dict(players=len(selected), known_role_players=len(known),
                              known_role_mass=role, known_age_role_mass=age_role,
                              missing_age=sum(p['age'] is None for p in selected),
                              missing_experience=missing_exp,
                              missing_draft=sum(p['missing_draft'] for p in selected))
    return values, coverage


class RosterHook:
    def __init__(self):
        self.coverage = []

    def __call__(self, full, current, metadata, *, team, season, week, kickoff, context, inputs):
        rows = inputs['rosters'].get((season, week, team), ())
        ids = [ch._roster_player_id(row, inputs.get('colliding_gsis', ())) for row in rows]
        if set(ids) != set(metadata['roster']):
            raise ValueError('Raw roster and corrected player identities differ')
        values, coverage = team_features(rows, metadata['starter'], context['snap_history'],
                                         kickoff, inputs.get('colliding_gsis', ()))
        full.update(values)
        current.update(values)
        # Postgame coverage only: these data never enter values or prior history.
        # Mirror the inherited resolver to disclose its default-zero updates.
        snapped, unmatched, name_fallback = set(), 0, 0
        for row in inputs.get('snaps', {}).get((season, week, team), ()):
            pid = metadata.get('pfr_ids', {}).get(row.get('pfr_player_id', '').strip())
            if not pid:
                pid = metadata.get('name_ids', {}).get(ch._normalize_player_name(row.get('player', '')))
                name_fallback += int(pid is not None)
            if pid is None:
                unmatched += 1
            else:
                snapped.add(pid)
        coverage['postgame_role_update_audit_only'] = dict(
            ACT_without_resolved_snap_row=len(set(ids) - snapped),
            unmatched_snap_rows=unmatched, matched_snap_rows_by_name_fallback=name_fallback,
            by_unit={unit: sum(ch._roster_player_id(row, inputs.get('colliding_gsis', ())) not in snapped
                              and position_unit(row.get('position')) == unit for row in rows)
                     for unit in ('offense', 'defense', 'qb', 'special', 'unmapped')})
        self.coverage.append(dict(team=team, season=season, week=week, kickoff=str(kickoff),
                                  **coverage, missing_features=[k for k, v in values.items() if v is None]))


def validate_base(rows, saved):
    if len(rows) != len(saved) or len({r.game_id for r in rows}) != len(rows):
        raise ValueError('Corrected base cohort differs')
    for row, old in zip(rows, saved):
        if any(getattr(row, key) != old[key] for key in ('game_id', 'season', 'week', 'kickoff', 'actual_margin')):
            raise ValueError('Corrected base identity or target differs')
        if set(row.features) != set(old['features']) | set(FEATURES):
            raise ValueError('Candidate feature inventory differs')
        for name, value in old['features'].items():
            actual = row.features[name]
            if (value is None) != (actual is None) or (value is not None and (
                    not math.isfinite(actual) or abs(actual-value) > 1e-12)):
                raise ValueError(f'Corrected base cell differs: {row.game_id}/{name}')


def validate_variation(rows):
    for season, training, _ in audit.base.expanding_folds(rows):
        for name in FEATURES:
            values = [r.features[name] for r in training if r.features[name] is not None]
            if not values or not all(math.isfinite(v) for v in values) or max(values) == min(values):
                raise ValueError(f'No finite training variation: {season}/{name}')


def build_rows(paths):
    hook = RosterHook()
    with audit.construction_scope(paths, active_only=True, half_life_games=4, exposure_fix=True):
        rows, context, inputs = audit.current.build_rows(paths, 'starter_recency', roster_hook=hook)
    rows = audit.drop_features(rows, audit.ROSTER_COACH)
    return rows, context, inputs, hook.coverage


def portable_context(context, inputs):
    result = corrected.portable_context(context, inputs)
    result['identity'] = IDENTITY
    result['snap_history'] = {pid: {unit: list(history[unit]) for unit in ('offense', 'defense')}
                              for pid, history in context['snap_history'].items()}
    return json.loads(audit.base._json_bytes(result))


def current_features(context, snapshot, roster_rows):
    """Research diagnostic at the issued source clock; no new source or fit."""
    import pgo_forecast_corrected as issued
    by_team, gsis_teams, gsis_smart = {}, {}, {}
    for row in roster_rows:
        if (row.get('status') or '').strip() == 'ACT':
            if row.get('season') != '2026' or row.get('week') != '1':
                raise ValueError('Current ACT roster period differs')
            team = audit.pgo_sources.normalize_team(row['team'])
            gsis = (row.get('gsis_id') or '').strip()
            if not gsis and not (row.get('pfr_id') or '').strip():
                raise ValueError('Current ACT roster has an ID-less row')
            if gsis:
                gsis_teams.setdefault(gsis, set()).add(team)
                gsis_smart.setdefault(gsis, set()).add((row.get('smart_id') or '').strip())
            by_team.setdefault(team, []).append(row)
    if any(len(teams) > 1 for teams in gsis_teams.values()) or any(
            len({sid for sid in smart if sid}) > 1 for smart in gsis_smart.values()):
        raise ValueError('Current ACT GSIS collision requires review')
    selected = {}
    for old in snapshot['teams']:
        matches = [r for r in by_team.get(old['team'], ())
                   if r.get('gsis_id') == old['qb_gsis_id'] and r.get('position') == 'QB']
        if len(matches) != 1:
            raise ValueError('Current expected QB is not uniquely ACT')
        selected[old['team']] = matches[0]
    if len(selected) != 32 or set(by_team) != set(selected):
        raise ValueError('Current team coverage differs')
    base = issued.current_features(context, selected, snapshot['inputs_as_of'])
    result, coverage = {}, {}
    collisions = context['inputs']['colliding_gsis']
    for old in snapshot['teams']:
        team = old['team']
        issued._same(old['features'], base[team], f'{team} corrected base parity')
        starter = ch._roster_player_id(selected[team], collisions)
        block, coverage[team] = team_features(by_team[team], starter, context['snap_history'],
                                              snapshot['inputs_as_of'], collisions)
        result[team] = {**base[team], **block}
    return result, coverage


def raw_inventory(paths):
    """Source counters precede the loader, including otherwise skipped ID-less rows."""
    result = {}
    for (name, season), path in paths.items():
        if name != 'weekly_rosters':
            continue
        annual, teams = Counter(), {}
        for row in audit.pgo_sources.open_csv(path):
            annual['raw_rows'] += 1
            if (row.get('status') or '').strip() != 'ACT':
                annual['excluded_non_ACT_rows'] += 1
                continue
            annual['ACT_rows'] += 1
            if not (row.get('gsis_id') or '').strip() and not (row.get('pfr_id') or '').strip():
                annual['ID_less_ACT_rows'] += 1
            team = audit.pgo_sources.normalize_team(row['team'])
            entry = teams.setdefault(team, Counter())
            entry['ACT_rows'] += 1
            entry['blank_draft_rows'] += int(not (row.get('draft_number') or '').strip())
            entry['blank_experience_rows'] += int(not (row.get('years_exp') or '').strip())
            entry['blank_DOB_rows'] += int(not (row.get('birth_date') or '').strip())
        result[str(season)] = dict(counts=dict(annual), by_team=teams)
    return result


def coverage_report(coverage, paths, inputs, rows):
    """Raw pre-collapse accounting, and separate eligible-game denominators."""
    raw_by_key, raw_by_season = Counter(), {}
    for (name, season), path in paths.items():
        if name != 'weekly_rosters':
            continue
        annual, identities = Counter(), Counter()
        for row in audit.pgo_sources.open_csv(path):
            annual['raw_source_rows_all_weeks'] += 1
            if (row.get('status') or '').strip() != 'ACT':
                annual['non_ACT_rows_excluded'] += 1
                continue
            annual['raw_ACT_rows_all_weeks'] += 1
            key = (season, int(row['week']), audit.pgo_sources.normalize_team(row['team']))
            raw_by_key[key] += 1
            pid = ch._roster_player_id(row, inputs.get('colliding_gsis', ()))
            identities[key + (pid,)] += 1
            annual['collision_resolved_ACT_rows'] += int(row.get('gsis_id') in inputs.get('colliding_gsis', ()))
        annual['extra_ACT_rows_before_collapse'] = sum(n-1 for n in identities.values())
        raw_by_season[str(season)] = dict(annual)
    summaries = {}
    for entry in coverage:
        entry['raw_ACT_rows_before_collapse'] = raw_by_key[entry['season'], entry['week'], entry['team']]
        entry['collapsed_ACT_rows'] = entry['raw_ACT_rows_before_collapse'] - entry['resolved_ACT_rows']
        annual = summaries.setdefault(str(entry['season']), {
            'team_games': 0, 'offense': Counter(), 'defense': Counter(), 'missing_features': Counter(),
            'raw_ACT_rows_before_collapse': 0, 'resolved_ACT_rows': 0, 'collapsed_ACT_rows': 0,
            'unmapped_positions': 0, 'missing_selected_qb_age': 0,
            'ACT_without_resolved_snap_row_postgame': 0})
        annual['team_games'] += 1
        for key in ('raw_ACT_rows_before_collapse', 'resolved_ACT_rows', 'collapsed_ACT_rows',
                    'unmapped_positions', 'missing_selected_qb_age'):
            annual[key] += entry[key]
        annual['ACT_without_resolved_snap_row_postgame'] += entry['postgame_role_update_audit_only']['ACT_without_resolved_snap_row']
        for unit in ('offense', 'defense'):
            annual[unit].update(entry[unit])
        annual['missing_features'].update(entry['missing_features'])
    feature_missing = {str(season): {name: dict(missing=sum(r.features[name] is None for r in rows if r.season==season),
                          games=sum(r.season==season for r in rows)) for name in FEATURES}
                       for season in sorted({r.season for r in rows})}
    return dict(raw_sources=raw_by_season, identity_resolution=inputs['identity_resolution'],
                by_season=summaries, matchup_feature_missing=feature_missing, team_games=coverage)
