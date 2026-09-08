"""Research-only recorded-starter reconstruction and calendar-weighted QB history.

Recorded historical starters are not verified pregame/T-60 expectations. Run in
a dedicated sequential research process: temporary challenger hooks must not
overlap other challenger work. This module does not fit or publish anything.
"""
from collections import defaultdict
from copy import deepcopy
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import math
from pathlib import Path
from threading import Lock

import pgo_challenger as ch


MODES = ('raw', 'starter', 'starter_recency')
QB_HALF_LIFE_DAYS = 365.25
RECENT_QB_FEATURES = tuple(name for name in ch.QB_FEATURES
                           if name not in ('qb_experience_prior', 'qb_draft_prior'))
SNAPSHOT_DIR = Path(__file__).resolve().parent / 'docs/evidence/forecast-lab-2026/september-07'
_WALK_LOCK = Lock()


def _state(context):
    if 'current_strength' not in context:
        context['current_strength'] = {
            'qb_history': defaultdict(lambda: defaultdict(float)),
            'qb_population': defaultdict(float),
            'last_kickoff': None,
            'coverage': {'team_games': 0, 'matched': 0, 'missing_id': 0,
                         'missing_roster': 0, 'ambiguous_roster': 0,
                         'by_season': {}, 'unavailable': []},
            'roster_coverage': [],
        }
    return context['current_strength']


def _utc(value):
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('QB history timestamps must include a timezone')
    return parsed.astimezone(timezone.utc)


def _advance_qb_clock(context, kickoff):
    """Decay all player/population totals equally, once at each new instant."""
    state = _state(context)
    now = _utc(kickoff)
    previous = state['last_kickoff']
    if previous is not None:
        elapsed = (now - _utc(previous)).total_seconds() / 86400
        if elapsed < 0:
            raise ValueError('QB history clock moved backwards')
        if elapsed:
            factor = 2 ** (-elapsed / QB_HALF_LIFE_DAYS)
            for totals in (*state['qb_history'].values(), state['qb_population']):
                for key in totals:
                    totals[key] *= factor
    state['last_kickoff'] = now.isoformat()
    return state


def _recorded_starters(paths):
    """Identity-only final schedule reconstruction; no outcome-based fallback."""
    selected = {}
    for row in ch.open_csv(paths['schedule_results', None]):
        season = int(row['season'])
        if (row.get('game_type') != 'REG' or not ch.FIRST_SEASON <= season <= ch.LAST_SEASON
                or not row.get('home_score', '').strip() or not row.get('away_score', '').strip()):
            continue
        for side in ('home', 'away'):
            key = (season, int(float(row['week'])), ch.normalize_team(row[side + '_team']))
            if key in selected:
                raise ValueError(f'Duplicate recorded starter team-game: {key}')
            selected[key] = {
                'gsis_id': row.get(side + '_qb_id', '').strip(),
                'game_id': row['game_id'],
                'kickoff': ch._kickoff(row['gameday'], row.get('gametime', '')),
            }
    return selected


def _resolve_starter(metadata, gsis_id):
    if not gsis_id:
        return None, 'missing_id'
    matches = [key for key, player in metadata['roster'].items()
               if player.get('position') == 'QB' and player.get('gsis_id') == gsis_id]
    if len(matches) != 1:
        return None, 'ambiguous_roster' if matches else 'missing_roster'
    return matches[0], 'matched'


def _selected_views(raw_views, gsis_id, context, mode, *, team):
    full, current, raw_metadata = raw_views
    full, current, metadata = dict(full), dict(current), dict(raw_metadata)
    starter, status = _resolve_starter(metadata, gsis_id)
    metadata['starter'] = starter
    metadata['current_strength_starter_status'] = status
    if starter is None:
        for view in (full, current):
            view.update({name: None for name in (*ch.QB_FEATURES, 'qb_current_minus_full')})
        return full, current, metadata
    players = {key: dict(player) for key, player in metadata['roster'].items()}
    if mode == 'starter_recency':
        state = _state(context)
        for player_id, player in players.items():
            if player['position'] == 'QB':
                recent = ch._qb_features(player_id, 0, None, state)
                player.update({name: recent[name] for name in RECENT_QB_FEATURES})
    # The recorded ID comes first; all backups retain their RAW ordering and
    # original availability probabilities. Selector priority is not a feature.
    priorities = [ch._qb_sort_value(p) for p in players.values() if p['position'] == 'QB']
    players[starter]['qb_value'] = max([0.0] + [v for v in priorities if math.isfinite(v)]) + 1
    full, current = ch.lineup_views(team, {team: players}, full)
    return full, current, metadata


def _record_coverage(state, metadata, *, team, season, week, game_id, gsis_id):
    coverage = state['coverage']
    status = metadata['current_strength_starter_status']
    coverage['team_games'] += 1
    coverage[status] += 1
    annual = coverage['by_season'].setdefault(str(season), dict.fromkeys(
        ('team_games', 'matched', 'missing_id', 'missing_roster', 'ambiguous_roster'), 0))
    annual['team_games'] += 1
    annual[status] += 1
    if status != 'matched':
        coverage['unavailable'].append(dict(team=team, season=season, week=week,
                                             game_id=game_id, gsis_id=gsis_id, reason=status))


def build_rows(paths, mode, roster_hook=None):
    """Return uncached historical rows/context/inputs; no model fitting."""
    if mode not in MODES:
        raise ValueError(f'Unknown current-strength mode: {mode}')
    if not _WALK_LOCK.acquire(blocking=False):
        raise RuntimeError('Current-strength walks cannot nest or run concurrently')
    original_views, original_update = ch._team_views, ch._update_after_game
    # Current roster identity cannot enter historical feature construction.
    historical = {key: value for key, value in paths.items() if key != ('current_roster', 2026)}

    def views(team, season, week, coach, kickoff, context, inputs, *args, **kwargs):
        if mode == 'starter_recency':
            _advance_qb_clock(context, kickoff)
        full, current, metadata = original_views(team, season, week, coach, kickoff,
                                                  context, inputs, *args, **kwargs)
        state = _state(context)
        if mode != 'raw':
            chosen = selected[season, week, team]
            if _utc(kickoff) != _utc(chosen['kickoff']):
                raise ValueError('Recorded starter kickoff differs from historical game')
            full, current, metadata = _selected_views((full, current, metadata),
                                                       chosen['gsis_id'], context, mode, team=team)
            _record_coverage(state, metadata, team=team, season=season, week=week,
                             game_id=chosen['game_id'], gsis_id=chosen['gsis_id'])
        if roster_hook is not None:
            roster_hook(full, current, metadata, team=team, season=season, week=week,
                        kickoff=kickoff, context=context, inputs=inputs)
            state['roster_coverage'].append({
                'team': team, 'season': season, 'week': week,
                'features': deepcopy(metadata.get('roster_strength', {})),
                'window': deepcopy(metadata.get('roster_strength_window')),
                'unavailable_player_quality': deepcopy(metadata.get('unavailable_player_quality')),
            })
        return full, current, metadata

    def update(game, home, away, context, inputs, decay):
        if mode == 'starter_recency':
            state = _advance_qb_clock(context, game['kickoff_dt'])
            for team, metadata in ((game['home'], home), (game['away'], away)):
                for row in inputs['players'].get((game['season'], game['week'], team), ()):
                    if row.get('position', '').strip().upper() != 'QB':
                        continue
                    player_id = row.get('player_id', '').strip()
                    player_id = metadata['gsis_ids'].get(player_id, player_id)
                    ch._accumulate_qb(row, state['qb_history'][player_id])
                    ch._accumulate_qb(row, state['qb_population'])
        original_update(game, home, away, context, inputs, decay)

    try:
        selected = _recorded_starters(historical) if mode != 'raw' else {}
        # ponytail: scoped hooks avoid duplicating the pinned historical walker.
        ch._team_views, ch._update_after_game = views, update
        rows, context, inputs = ch._walk(historical, 4)
        _state(context)['inputs'] = inputs  # Internal only; export coverage, not this state.
        return rows, context, inputs
    finally:
        ch._team_views, ch._update_after_game = original_views, original_update
        _WALK_LOCK.release()


def _snapshot_metadata(snapshot, context, snapshot_dir=SNAPSHOT_DIR):
    """Recreate real ACT-roster role weights from verified September bytes."""
    entries = [item for item in snapshot['sources'] if item['name'] == 'roster.csv.gz']
    if len(entries) != 1:
        raise ValueError('September roster source identity is missing or ambiguous')
    raw = (Path(snapshot_dir) / 'roster.csv.gz').read_bytes()
    if len(raw) != entries[0]['bytes'] or hashlib.sha256(raw).hexdigest() != entries[0]['sha256']:
        raise ValueError('September roster source hash/size differs')
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        rows = list(csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8', newline='')))
    active = defaultdict(list)
    for row in rows:
        if row['status'] == 'ACT':
            if int(row['season']) != 2026 or int(row['week']) != 1:
                raise ValueError('September ACT roster period differs')
            active[ch.normalize_team(row['team'])].append(row)
    inputs = context['current_strength']['inputs']
    output = {}
    for team_row in snapshot['teams']:
        team = team_row['team']
        if not active[team]:
            raise ValueError(f'September ACT roster unavailable: {team}')
        players, identity = ch._players_for_team(team, 2026, 1,
                                                _utc(snapshot['generated_at']), active[team], context, inputs)
        metadata = {**identity, 'roster': players}
        starter, status = _resolve_starter(metadata, team_row['qb_gsis_id'])
        if status != 'matched':
            raise ValueError(f'September QB1 roster identity is unavailable: {team}')
        metadata['starter'] = starter
        output[team] = metadata
    return output


def snapshot_features(snapshot, context, mode, apply_offseason=True, roster_hook=None,
                      *, snapshot_dir=SNAPSHOT_DIR):
    """Copy frozen September inputs, with fixed QB1 and optional one-time decay."""
    if mode not in MODES:
        raise ValueError(f'Unknown current-strength mode: {mode}')
    if context['season'] != 2025 or snapshot['edition'] != 'pgo-active-roster-2026-09-07':
        raise ValueError('This sensitivity requires 2025 history and the frozen September edition')
    if mode == 'raw' and roster_hook is None:
        output = {row['team']: dict(row['features']) for row in snapshot['teams']}
    else:
        # Copy only QB accumulators. Never mutate final historical state when
        # evaluating multiple candidate views of the same snapshot.
        state = _state(context)
        local = dict(context)
        local['current_strength'] = {**state, 'qb_history': deepcopy(state['qb_history']),
                                     'qb_population': deepcopy(state['qb_population'])}
        if mode == 'starter_recency':
            _advance_qb_clock(local, snapshot['generated_at'])
        metadata_by_team = _snapshot_metadata(snapshot, context, snapshot_dir)
        output = {}
        snapshot_coverage = []
        for row in snapshot['teams']:
            team = row['team']
            features = dict(row['features'])
            metadata = metadata_by_team[team]
            starter, status = _resolve_starter(metadata, row['qb_gsis_id'])
            if status != 'matched':
                raise ValueError(f'September QB1 is unavailable: {team}')
            if mode == 'starter_recency':
                recent = ch._qb_features(starter, 0, None, local['current_strength'])
                features.update({name: recent[name] for name in RECENT_QB_FEATURES})
            features['qb_current_minus_full'] = 0.0
            if roster_hook is not None:
                current = dict(features)
                roster_hook(features, current, metadata, team=team, season=2026, week=1,
                            kickoff=_utc(snapshot['generated_at']), context=local, inputs=state['inputs'])
                snapshot_coverage.append({'team': team,
                    'features': deepcopy(metadata.get('roster_strength', {})),
                    'window': deepcopy(metadata.get('roster_strength_window')),
                    'unavailable_player_quality': deepcopy(metadata.get('unavailable_player_quality'))})
            output[team] = features
        # Audit-only metadata, not any historical predictor accumulator.
        if roster_hook is not None:
            state['snapshot_roster_coverage'] = snapshot_coverage
    if apply_offseason:
        for features in output.values():
            features['pgo_v0'] *= ch.V0_PARAMETERS.offseason_retention ** (2026 - context['season'])
    return output
