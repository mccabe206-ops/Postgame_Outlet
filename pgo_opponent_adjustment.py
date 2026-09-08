"""Research-only, prior-week opponent EPA ablation. Never publishes or fits.

Uses the incumbent walker and raw QB selector. Call sequentially in a dedicated
research process: its temporary helper hooks must not overlap other challenger
work in the same process. Public inference modules and files are untouched.
"""
from collections import defaultdict
from threading import Lock

import pgo_challenger as ch

MODES = ('raw', 'team_epa', 'team_qb_epa')
EPA_PAIRS = {
    'passing_epa_per_play_for': 'passing_epa_per_play_against',
    'passing_epa_per_play_against': 'passing_epa_per_play_for',
    'rushing_epa_per_play_for': 'rushing_epa_per_play_against',
    'rushing_epa_per_play_against': 'rushing_epa_per_play_for',
}
QB_EPA = ('qb_epa_per_dropback', 'qb_rushing_epa_per_carry')
_WALK_LOCK = Lock()


def _state(context):
    if 'opponent_epa' not in context:
        context['opponent_epa'] = {
            'ratios': defaultdict(dict),
            'qb_history': defaultdict(lambda: defaultdict(float)),
            'qb_population': defaultdict(float),
            'period': None, 'corrections': {}, 'weeks': [],
        }
    return context['opponent_epa']


def _freeze_week(context, season, week):
    """Freeze RAW opponent strengths before any result from this NFL week."""
    state = _state(context)
    period = (season, week)
    if state['period'] == period:
        return state['corrections']
    if state['period'] is not None and period < state['period']:
        raise ValueError('Opponent corrections require increasing NFL weeks')
    ratios = context['ratios']
    means = {}
    for name in EPA_PAIRS:
        values = [team[name] for team in ratios.values() if name in team]
        denominator = sum(value.denominator for value in values)
        means[name] = (sum(value.numerator for value in values) / denominator
                       if denominator > 0 else None)
    corrections, fallbacks = {}, 0
    for team in ch.pgo_model.CURRENT_TEAMS:
        corrections[team] = {}
        for name in EPA_PAIRS:
            value = ratios.get(team, {}).get(name, ch._RatioState()).value
            unavailable = value is None or means[name] is None
            corrections[team][name] = 0.0 if unavailable else value - means[name]
            fallbacks += int(unavailable)
    state['period'] = period
    state['corrections'] = corrections
    state['weeks'].append({'season': season, 'week': week,
                           'league_means': means, 'fallback_team_features': fallbacks})
    return corrections


def _update_adjusted(game, home, away, context, inputs, decay):
    state = _state(context)
    corrections = _freeze_week(context, game['season'], game['week'])
    for team, opponent, metadata in (
            (game['home'], game['away'], home),
            (game['away'], game['home'], away)):
        own = inputs['team_rows'].get((game['season'], game['week'], team))
        other = inputs['team_rows'].get((game['season'], game['week'], opponent))
        observations = ch._observations(own, other)
        for name, counterpart in EPA_PAIRS.items():
            numerator, denominator = observations[name]
            if numerator is not None and denominator is not None and denominator > 0:
                numerator += denominator * corrections[opponent][counterpart]
            previous = state['ratios'][team].get(name, ch._RatioState())
            state['ratios'][team][name] = previous.update(numerator, denominator, decay)
        for row in inputs['players'].get((game['season'], game['week'], team), ()):
            if row.get('position', '').strip().upper() != 'QB':
                continue
            player_id = row.get('player_id', '').strip()
            player_id = metadata['gsis_ids'].get(player_id, player_id)
            adjusted = dict(row)
            for column, denominator, defense in (
                ('passing_epa', ch._sum(row, 'attempts', 'sacks_suffered'),
                 'passing_epa_per_play_against'),
                ('rushing_epa', ch._number(row, 'carries'),
                 'rushing_epa_per_play_against'),
            ):
                numerator = ch._number(row, column)
                if numerator is not None and denominator is not None and denominator > 0:
                    adjusted[column] = numerator + denominator * corrections[opponent][defense]
            ch._accumulate_qb(adjusted, state['qb_history'][player_id])
            ch._accumulate_qb(adjusted, state['qb_population'])


def _adjusted_views(raw_views, team, context, mode):
    full, current, metadata = raw_views
    state = _state(context)
    base = dict(full)
    for name in EPA_PAIRS:
        base[name] = state['ratios'].get(team, {}).get(name, ch._RatioState()).value
    if mode == 'team_epa':
        return ({**full, **{k: base[k] for k in EPA_PAIRS}},
                {**current, **{k: base[k] for k in EPA_PAIRS}}, metadata)
    players = {key: dict(value) for key, value in metadata['roster'].items()}
    for player_id, player in players.items():
        if player['position'] == 'QB':
            adjusted = ch._qb_features(player_id, 0, None, state)
            # Retain RAW qb_value: the same players and probabilities must win
            # selection in both arms, even if adjusted EPA reverses their order.
            player.update({name: adjusted[name] for name in QB_EPA})
    full, current = ch.lineup_views(team, {team: players}, base)
    return full, current, metadata


def build_rows(paths, mode):
    """Return uncached (rows, raw context + side EPA state, inputs), half-life 4."""
    if mode not in MODES:
        raise ValueError(f'Unknown opponent experiment mode: {mode}')
    if not _WALK_LOCK.acquire(blocking=False):
        raise RuntimeError('Opponent experiment walks cannot nest or run concurrently')
    original_views, original_update = ch._team_views, ch._update_after_game

    def views(*args, **kwargs):
        return _adjusted_views(original_views(*args, **kwargs), args[0], args[5], mode)

    def update(game, home, away, context, inputs, decay):
        _update_adjusted(game, home, away, context, inputs, decay)
        original_update(game, home, away, context, inputs, decay)

    try:
        # ponytail: scoped hooks reuse the tested walker; a permanent extension
        # point is only warranted if a candidate earns further development.
        if mode != 'raw':
            ch._team_views, ch._update_after_game = views, update
        rows, context, inputs = ch._walk(paths, 4)
        context['colliding_gsis'] = inputs.get('colliding_gsis', ())
        return rows, context, inputs
    finally:
        ch._team_views, ch._update_after_game = original_views, original_update
        _WALK_LOCK.release()


def snapshot_features(snapshot, context, mode, apply_offseason=False):
    """Copy September features; fixed expected QB1 and optional one-time v0 decay.

    Always starts from the original snapshot, so repeated calls cannot compound
    the offseason correction or overwrite the original forecast edition.
    """
    if mode not in MODES:
        raise ValueError(f'Unknown opponent experiment mode: {mode}')
    if context['season'] != 2025 or snapshot['edition'] != 'pgo-active-roster-2026-09-07':
        raise ValueError('This sensitivity requires 2025 history and the September 2026 snapshot')
    output = {}
    for row in snapshot['teams']:
        team = row['team']
        features = dict(row['features'])
        if mode != 'raw':
            state = context['opponent_epa']
            for name in EPA_PAIRS:
                features[name] = state['ratios'][team][name].value
            if mode == 'team_qb_epa':
                player_id = row['qb_gsis_id']
                if player_id in context.get('colliding_gsis', ()):
                    raise ValueError('Ambiguous snapshot QB identity')
                adjusted = ch._qb_features(player_id, 0, None, state)
                features.update({name: adjusted[name] for name in QB_EPA})
                features['qb_current_minus_full'] = 0.0
        if apply_offseason:
            features['pgo_v0'] *= ch.V0_PARAMETERS.offseason_retention ** (2026 - context['season'])
        output[team] = features
    return output
