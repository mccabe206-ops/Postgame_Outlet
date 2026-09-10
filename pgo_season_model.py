"""Replay completed 2026 weeks into the frozen postseason model; never fit."""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path

import pgo_current_strength as current
import pgo_forecast_corrected as scoring
import pgo_sources
from research.pgo_input_audit.audit_model import exposure_qb_features
from research.pgo_postseason_candidate import pinned_challenger as ch

ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / 'docs/evidence/forecast-lab-2026/september-09-postseason'
SEED_PATH = ROOT / 'docs/evidence/season-2026/model-seed.json'
SEED_SHA256 = 'afbad183b902547ec9c51889b89b6d345358e787288be493122be15a8d3ea3ff'
CONTEXT_SHA256 = '7986f97e97a85ef9f4bfa3cb59bbefcb3fb5d3068af8f7251e6593785e6aae1e'
FIT_SHA256 = '65b7eee1bd3c343f46f54bac61538d3060f86f2b464b3df153f5cbdf43fcb1d5'
CORE_SHA256 = 'f71712d88be59c1bc5f05f319277d1e9c9a76a719882455459317ecea2f28735'
SCORING_SHA256 = '24ca1d9a41a6e4f0c37b1e1b6328726220806108c8d6d41900cb9cace1fe7d00'
CORRECTED_FIT_SHA256 = 'f6e6deda6665ded3ea0764a486fc68bc4667abd4a49f17afe5e3c39284a8806f'
STATUS = 'EXPERIMENTAL / HOLD'
DECAY = .5 ** (1. / 4.)
GAME_IDENTITY = ('game_id', 'season', 'week', 'kickoff', 'game_type', 'location',
                 'home', 'away', 'home_rest', 'away_rest')
TEAM_COUNTS = ('attempts', 'sacks_suffered', 'carries', 'passing_interceptions',
               'fumbles_lost_total', 'passing_20', 'rushing_20')
QB_COUNTS = ('attempts', 'sacks_suffered', 'carries', 'passing_interceptions', 'sack_fumbles_lost')


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _utc(value):
    return current._utc(value)


def _number(value, *, nullable=False):
    if value is None or str(value).strip() == '':
        _require(nullable, 'Required numerical production is unavailable')
        return None
    _require(not isinstance(value, bool), 'Boolean is not numerical production')
    result = float(value)
    _require(math.isfinite(result), 'Production must be finite')
    return result


def _integer(value):
    result = _number(value)
    _require(result.is_integer(), 'Expected an integer')
    return int(result)


def _read_pinned(path, pin):
    path = Path(path)
    _require(not path.is_symlink() and path.is_file(), 'Pinned source must be a real file')
    raw = path.read_bytes()
    _require(_sha(raw) == pin, 'Pinned model source hash differs: ' + path.name)
    return json.loads(raw)


def _context():
    _require(_sha(Path(ch.__file__).read_bytes()) == CORE_SHA256, 'Trained historical helper code differs')
    return _read_pinned(SOURCE_DIR / 'historical-context.json', CONTEXT_SHA256)


def _ratio_values(states):
    return {team: {name: (pair[0] / pair[1] if pair[1] > 0 else None)
                   for name, pair in values.items()} for team, values in states.items()}


def _validate_seed(seed, context):
    _require(seed['schema_version'] == 1 and seed['kind'] == 'pgo-2026-model-seed'
             and seed['source_context_sha256'] == CONTEXT_SHA256 and seed['season'] == 2025,
             'Invalid season-model seed')
    _require(set(seed['ratio_states']) == set(context['ratios']), 'Seed team inventory differs')
    for team, values in seed['ratio_states'].items():
        _require(set(values) == set(ch.PERFORMANCE_FEATURES), 'Seed feature inventory differs')
        for pair in values.values():
            _require(isinstance(pair, list) and len(pair) == 2
                     and all(type(v) in (float, int) and math.isfinite(v) for v in pair)
                     and pair[1] >= 0, 'Invalid seed accumulator')
    scoring._same(_ratio_values(seed['ratio_states']), context['ratios'], 'Seed ratios versus issued context')


def load_seed(path=SEED_PATH, expected_sha256=None):
    """Load an externally pinned compact seed, checking its issued-context parity."""
    seed = _read_pinned(path, expected_sha256 or SEED_SHA256)
    _validate_seed(seed, _context())
    return seed


def prepare_seed(context, historical_games, historical_team_rows, *, sources=()):
    """Reconstruct exact trained ratio accumulators from pinned historical rows."""
    _require(context == _context(), 'Historical context is not the issued model context')
    games = []
    for raw in historical_games:
        if (raw.get('game_type') not in ('REG', 'WC', 'DIV', 'CON', 'SB')
                or not 2013 <= _integer(raw['season']) <= 2025
                or raw.get('home_score') in ('', None) or raw.get('away_score') in ('', None)):
            continue
        games.append(dict(game_id=raw['game_id'], season=_integer(raw['season']), week=_integer(raw['week']),
                          home=pgo_sources.normalize_team(raw['home_team']), away=pgo_sources.normalize_team(raw['away_team']),
                          kickoff=ch._kickoff(raw['gameday'], raw.get('gametime', '')).isoformat()))
    games.sort(key=lambda g: (_utc(g['kickoff']), g['game_id']))
    _require(len(games) == 3562 and len({g['game_id'] for g in games}) == len(games), 'Pinned history game inventory differs')
    _require(set(g['season'] for g in games) == set(range(2013, 2026)), 'Historical season coverage differs')
    by_period = {}
    for row in historical_team_rows:
        key = (_integer(row['season']), _integer(row['week']), pgo_sources.normalize_team(row['team']))
        _require(key not in by_period, 'Duplicate historical team period')
        by_period[key] = row
    ratios = defaultdict(dict)
    for game in games:
        for team, opponent in ((game['home'], game['away']), (game['away'], game['home'])):
            own = by_period.get((game['season'], game['week'], team))
            other = by_period.get((game['season'], game['week'], opponent))
            ch._validate_team_row(own, game, opponent)
            for name, pair in ch._observations(own, other).items():
                ratios[team][name] = ratios[team].get(name, ch._RatioState()).update(*pair, DECAY)
    seed = dict(schema_version=1, kind='pgo-2026-model-seed', season=2025,
                source_context_sha256=CONTEXT_SHA256, historical_helper_sha256=CORE_SHA256,
                history_games=len(games), history_last_kickoff=games[-1]['kickoff'], sources=list(sources),
                ratio_states={team: {name: [value.numerator, value.denominator]
                                     for name, value in values.items()} for team, values in ratios.items()})
    _validate_seed(seed, context)
    return seed


def _period(row):
    return (_integer(row['season']), _integer(row['week']), pgo_sources.normalize_team(row['team']))


def _game_identity(game, season):
    _require(all(k in game for k in GAME_IDENTITY), 'Game identity is incomplete')
    _require(_integer(game['season']) == season and game['game_type'] == 'REG', 'Wrong season or game type')
    _require(type(game['week']) is int and 1 <= game['week'] <= 18, 'Invalid week')
    _require(isinstance(game['game_id'], str) and game['game_id'], 'Missing game ID')
    teams = set(pgo_sources.CURRENT_TEAMS)
    _require(game['home'] in teams and game['away'] in teams and game['home'] != game['away'], 'Invalid game teams')
    _require(game['location'] in ('Home', 'Neutral'), 'Unknown venue status')
    _utc(game['kickoff'])
    for key in ('home_rest', 'away_rest'):
        value = _number(game[key], nullable=True)
        _require(value is None or value >= 0, 'Invalid rest interval')


def _validate_production(game, teams, players):
    for team, opponent in ((game['home'], game['away']), (game['away'], game['home'])):
        key = (game['season'], game['week'], team)
        _require(key in teams and key in players, 'Completed game is missing team or player production')
        row = teams[key]
        ch._validate_team_row(row, game, opponent)
        for name in TEAM_COUNTS:
            _require(_integer(row.get(name)) >= 0, 'Negative team exposure')
        for name, exposure in (('passing_epa', row['attempts'] + row['sacks_suffered']), ('rushing_epa', row['carries'])):
            _number(row.get(name), nullable=exposure == 0)
        qbs = [r for r in players[key] if r['position'].strip().upper() == 'QB']
        _require(qbs, 'No quarterback production for completed team game')
        for name in ('attempts', 'sacks_suffered'):
            counts = [_integer(r.get(name)) for r in players[key]]
            _require(all(v >= 0 for v in counts) and sum(counts) == row[name], 'Player/team passing exposure differs')
        for r in qbs:
            for name in QB_COUNTS:
                _require(_integer(r.get(name)) >= 0, 'Negative quarterback exposure')
            for name, exposure in (('passing_epa', _number(r['attempts']) + _number(r['sacks_suffered'])),
                                   ('passing_cpoe', _number(r['attempts'])), ('rushing_epa', _number(r['carries']))):
                _number(r.get(name), nullable=exposure == 0)


def build_week(seed, fit, completed_games, team_rows, qb_rows, selected_roster, upcoming_games, *,
               season=2026, completed_week, generated_at, scoring_rates, league_mean_total,
               inputs_as_of=None, corrected_fit=None):
    """Replay from the original seed; caller verifies full completed-week inventory.

    qb_rows contains the full player feed for exposure reconciliation. Only QB
    rows update QB history. Later-week production is ignored, never zero-filled.
    """
    _require(_sha(_bytes(seed)) == SEED_SHA256, 'Unverified or already advanced model seed')
    context = _context(); _validate_seed(seed, context)
    _require(fit == _read_pinned(SOURCE_DIR / 'final-fit.json', FIT_SHA256), 'Frozen fit changed')
    fixed_scoring = _read_pinned(SOURCE_DIR / 'scoring-rates.json', SCORING_SHA256)
    _require(scoring_rates == fixed_scoring['rates'] and league_mean_total == fixed_scoring['league_mean_total'], 'Frozen total scoring rates changed')
    if corrected_fit is not None:
        _require(corrected_fit == _read_pinned(SOURCE_DIR.parent / 'september-08-corrected/final-fit.json', CORRECTED_FIT_SHA256), 'Frozen comparison fit changed')
    _require(season == 2026 and type(completed_week) is int and 0 <= completed_week <= 18, 'Unsupported season or completed week')
    generated = _utc(generated_at); captured = _utc(inputs_as_of or generated_at)
    _require(captured <= generated and captured >= _utc(context['current_strength']['last_kickoff']), 'Input clock is invalid')
    games = sorted(deepcopy(completed_games), key=lambda g: (_utc(g['kickoff']), g['game_id']))
    _require(len({g['game_id'] for g in games}) == len(games), 'Duplicate completed game')
    _require(set(g['week'] for g in games) == set(range(1, completed_week + 1)), 'Completed weeks are missing or include a future week')
    periods = set()
    for game in games:
        _game_identity(game, season)
        _require(_utc(game['kickoff']) < _utc(game['finalized_at']) <= captured, 'Game final is not known at capture')
        for side in ('home', 'away'):
            value = _number(game[side + '_score'])
            _require(value >= 0 and value.is_integer(), 'Invalid final score')
            game[side + '_score'] = int(value)
            key = (season, game['week'], game[side])
            _require(key not in periods, 'Duplicate completed team period'); periods.add(key)
    teams, players, seen_players = {}, defaultdict(list), set()
    for original in team_rows:
        key = _period(original)
        if key not in periods:
            continue
        _require(key not in teams, 'Duplicate team production')
        row = dict(original)
        for name in (*TEAM_COUNTS, 'passing_epa', 'rushing_epa'):
            row[name] = _number(row.get(name), nullable=name not in TEAM_COUNTS)
        teams[key] = row
    for original in qb_rows:
        key = _period(original)
        if key not in periods:
            continue
        row = dict(original); identity = (*key, row.get('player_id'))
        _require(isinstance(row.get('player_id'), str) and row['player_id'].strip()
                 and isinstance(row.get('position'), str) and row['position'].strip(), 'Player production identity missing')
        _require(identity not in seen_players, 'Duplicate player production'); seen_players.add(identity)
        _require(row['player_id'] not in context['inputs']['colliding_gsis'], 'Ambiguous historical player ID requires explicit identity review')
        players[key].append(row)
    for game in games:
        _validate_production(game, teams, players)
    # This state is always copied from final 2025. Apply offseason retention once.
    context['ratings'] = {t: v * ch.V0_PARAMETERS.offseason_retention for t, v in context['ratings'].items()}
    ratios = {t: {k: ch._RatioState(*v) for k, v in values.items()} for t, values in seed['ratio_states'].items()}
    for game in games:
        state = current._advance_qb_clock(context, game['kickoff'])
        for team, opponent in ((game['home'], game['away']), (game['away'], game['home'])):
            key = (season, game['week'], team)
            for name, values in ch._observations(teams[key], teams[season, game['week'], opponent]).items():
                ratios[team][name] = ratios[team][name].update(*values, DECAY)
            for row in players[key]:
                if row['position'].strip().upper() == 'QB':
                    totals = state['qb_history'].setdefault(row['player_id'], {})
                    totals = defaultdict(float, totals)
                    ch._accumulate_qb(row, totals); state['qb_history'][row['player_id']] = dict(totals)
                    population = defaultdict(float, state['qb_population'])
                    ch._accumulate_qb(row, population); state['qb_population'] = dict(population)
        # Exact results-history update from the pinned chronological constructor.
        predicted = context['ratings'][game['home']] - context['ratings'][game['away']] + (0. if game['location'] == 'Neutral' else ch.V0_PARAMETERS.home_field)
        residual = max(-ch.V0_PARAMETERS.margin_cap, min(ch.V0_PARAMETERS.margin_cap, game['home_score'] - game['away_score'] - predicted))
        change = ch.V0_PARAMETERS.learning_rate * residual / 2.
        context['ratings'][game['home']] += change; context['ratings'][game['away']] -= change
    state = current._advance_qb_clock(context, captured)
    _require(set(selected_roster) == set(context['ratings']), 'Current QB selection must cover all 32 teams')
    features, selected_ids = {}, set()
    for team, row in selected_roster.items():
        _require(row['position'] == 'QB' and row['status'] == 'ACT' and pgo_sources.normalize_team(row['team']) == team
                 and _integer(row['season']) == season and row.get('full_name'), 'QB selection must be a current active same-team identity')
        player_id = ch._roster_player_id(row, context['inputs']['colliding_gsis'])
        _require(row.get('gsis_id') and player_id not in selected_ids, 'Missing or duplicate selected QB identity'); selected_ids.add(player_id)
        years = _integer(row['years_exp']); draft = _number(row.get('draft_number'), nullable=True)
        _require(years >= 0 and (draft is None or draft > 0), 'Invalid QB metadata')
        qb = exposure_qb_features(player_id, years, draft, state)
        features[team] = {name: ratios[team][name].value for name in ch.PERFORMANCE_FEATURES}
        features[team].update({name: qb[name] for name in ch.QB_FEATURES})
        features[team].update(pgo_v0=context['ratings'][team], offense_availability=0., defense_availability=0., qb_current_minus_full=0.)
    scores = {t: scoring.score({**f, 'home_field': 0., 'rest_difference': 0.}, fit) for t, f in features.items()}
    center = math.fsum(scores.values()) / 32
    pp = fit['preprocessor']
    names = [*pp['feature_names'], *(name + '_missing' for name in pp['missing_features'])]
    terms = {}
    for team, values in features.items():
        values = {**values, 'home_field': 0., 'rest_difference': 0.}
        vector = [0. if values[name] is None else (values[name] - median) / scale
                  for name, median, scale in zip(pp['feature_names'], pp['medians'], pp['scales'])]
        vector += [float(values[name] is None) for name in pp['missing_features']]
        terms[team] = dict(zip(names, (value * coefficient for value, coefficient in zip(vector, fit['coefficients'][1:]))))
    means = {name: math.fsum(term[name] for term in terms.values()) / 32 for name in names}
    contributions = {team: {name: term[name] - means[name] for name in names} for team, term in terms.items()}
    _require(all(math.isclose(math.fsum(contributions[team].values()), scores[team] - center, abs_tol=1e-9, rel_tol=0.)
                 for team in scores), 'Centered feature contributions do not reconcile with ratings')
    ranked = [dict(rank=rank, team=team, rating=scores[team] - center, features=features[team],
                   contributions=contributions[team],
                   qb_name=selected_roster[team]['full_name'], qb_gsis_id=selected_roster[team]['gsis_id'],
                   qb_history_observed=state['qb_history'].get(ch._roster_player_id(selected_roster[team], context['inputs']['colliding_gsis']), {}).get('dropbacks', 0.) > 0)
              for rank, team in enumerate(sorted(scores, key=lambda t: (-scores[t], t)), 1)]
    upcoming = sorted(deepcopy(upcoming_games), key=lambda g: (_utc(g['kickoff']), g['game_id']))
    _require((completed_week < 18 or not upcoming)
             and len({g['game_id'] for g in upcoming}) == len(upcoming), 'Unexpected or duplicate upcoming games')
    _require(not {g['game_id'] for g in upcoming} & {g['game_id'] for g in games}, 'A completed game cannot be forecast')
    _require(len({t for g in upcoming for t in (g['home'], g['away'])}) == 2 * len(upcoming), 'Duplicate upcoming team period')
    output = []
    for game in upcoming:
        _game_identity(game, season)
        _require(game['week'] == completed_week + 1 and generated < _utc(game['kickoff']) - timedelta(minutes=60), 'Upcoming week or cutoff is invalid')
        _require(not any(game.get(k) is not None for k in ('home_score', 'away_score', 'actual_margin', 'finalized_at')), 'Upcoming game contains a result')
        matchup = {**game, 'neutral': game['location'] == 'Neutral'}
        vector = ch._matchup_features(features[game['home']], features[game['away']], matchup)
        margin = scoring.score(vector, fit)
        neutral = scoring.score({**vector, 'home_field': 0., 'rest_difference': 0.}, fit)
        venue = scoring.score({**vector, 'rest_difference': 0.}, fit) - neutral
        rest = margin - neutral - venue
        _require(math.isclose(neutral, scores[game['home']] - scores[game['away']], abs_tol=1e-9, rel_tol=0.), 'Rankings and neutral margin do not reconcile')
        total = math.fsum(_number(scoring_rates[t][k]) for t in (game['home'], game['away']) for k in ('pf', 'pa')) / 2
        home_points, away_points = scoring.incumbent.expected_scores(total, margin)
        _require(math.isclose(home_points - away_points, margin, abs_tol=1e-9, rel_tol=0.)
                 and math.isclose(home_points + away_points, total, abs_tol=1e-9, rel_tol=0.), 'Scores do not reconcile with margin and total')
        output.append(dict(**{k: game[k] for k in GAME_IDENTITY}, margin=margin, total=total,
                           home_points=home_points, away_points=away_points, league_mean_total=league_mean_total,
                           explanation=dict(home_rating=scores[game['home']] - center, away_rating=scores[game['away']] - center,
                                            rating_inputs_as_of=captured.isoformat(), neutral_margin=neutral, home_adjustment=venue, rest_adjustment=rest,
                                            total_method='Frozen 2025 regular-season plus playoff points scored/allowed rates'),
                           **({'corrected_fit_margin': scoring.score(vector, corrected_fit)} if corrected_fit is not None else {})))
    return dict(schema_version=1, status=STATUS, season=season, week=min(18, completed_week + 1),
                season_complete=completed_week == 18,
                generated_at=generated.isoformat(), inputs_as_of=captured.isoformat(), teams=ranked, games=output,
                coverage=dict(completed_games=len(games), completed_weeks=completed_week,
                              offseason_retention_applications=1, non_qb_adjustments=False),
                state=dict(season=season, ratings=context['ratings'], current_strength=state,
                           ratio_states={t: {k:[v.numerator,v.denominator] for k,v in values.items()} for t,values in ratios.items()},
                           processed_game_ids=[g['game_id'] for g in games]))
