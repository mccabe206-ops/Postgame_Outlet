"""Pure presentation of verified season state; never fetches, fits, issues or grades."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
import html
import math
from urllib.parse import unquote, urlsplit

import pgo_current_board as board

GRADES = {'W': 'W', 'L': 'L', 'T': 'T', 'PENDING': 'Pending', 'NO_PICK': 'No pick'}
FORECAST_STATES = {'DRAFT', 'LOCKED', 'BLOCKED', 'FINAL'}
WEEK_STATES = {'UPCOMING', 'IN_PROGRESS', 'COMPLETE', 'BLOCKED'}


def _text(value):
    return html.escape(str(value), quote=True)


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Season display requires finite numeric values')
    return value


def _integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('Season display requires nonnegative integer counts')
    return value


def _time(value):
    return board._time(value) if value else 'Unavailable'


def _sources(sources):
    rows = []
    for source in sources:
        href = source['href']
        decoded = unquote(href)
        parsed = urlsplit(decoded)
        if (not href or any(ord(c) < 32 for c in decoded) or '\\' in decoded
                or decoded.startswith('//') or '..' in parsed.path.split('/')
                or (parsed.scheme and (parsed.scheme != 'https' or not parsed.netloc))
                or (not parsed.scheme and parsed.netloc)):
            raise ValueError('Season sources require safe relative or HTTPS links')
        rows.append(f'<li><a href="{_text(href)}">{_text(source.get("label", href))}</a></li>')
    return '<ul>' + ''.join(rows) + '</ul>' if rows else ''


def _rankings(snapshot):
    if snapshot is None:
        return '<p>Rankings unavailable.</p>'
    from pgo_forecast_lab import _rating_labels
    teams = sorted(snapshot['teams'], key=lambda row: row['rank'])
    codes = {row[0] for row in board.generate_site.TEAM.values()}
    if (len(teams) != 32 or {row['team'] for row in teams} != codes
            or [row['rank'] for row in teams] != list(range(1, 33))):
        raise ValueError('Season rankings require all 32 ranked team identities')
    labels = _rating_labels()
    plain = dict(pgo_v0='recent game results', passing_epa_per_play_for='passing performance',
                 passing_epa_per_play_against='pass defense', rushing_epa_per_play_for='rushing performance',
                 rushing_epa_per_play_against='run defense', sack_creation_rate='sacks made by the defense',
                 sack_avoidance_rate='avoiding sacks', takeaway_rate='winning turnovers',
                 giveaway_avoidance_rate='protecting the ball', qb_epa_per_dropback='quarterback passing history',
                 qb_cpoe='quarterback completion history', qb_log_dropbacks='amount of quarterback history',
                 qb_experience_prior='quarterback experience', qb_draft_prior='quarterback draft history')
    rows, explanations = [], []
    for team in teams:
        rating = _number(team['rating'])
        prior = team.get('prior_rank')
        if prior is not None and not 1 <= _integer(prior) <= 32:
            raise ValueError('Invalid previous rank')
        movement = 'First edition' if prior is None else ('Unchanged' if prior == team['rank'] else f'Up {prior-team["rank"]}' if prior > team['rank'] else f'Down {team["rank"]-prior}')
        code = _text(team['team'])
        rows.append(f'<tr data-season-team="{code}"><td class="pgo-rank">{team["rank"]}</td>'
            f'<th scope="row" class="pgo-team"><a href="#season-rating-{code}" data-view-key="rating-link-{code}">{board.team_identity(team["team"])}</a></th>'
            f'<td class="pgo-rating-value" data-value="{rating}">{rating:+.3f}</td><td>{movement}</td>'
            f'<td class="model-update-extra pgo-rating-scale">{board.rating_bar(rating)}</td>'
            f'<td class="model-update-extra">{_text(team["qb_name"])}</td></tr>')
        terms = team.get('contributions', {})
        for value in terms.values(): _number(value)
        if terms and not math.isclose(math.fsum(terms.values()), rating, rel_tol=0, abs_tol=1e-8):
            raise ValueError('Season rating contributions do not reconcile')
        def drivers(positive):
            chosen = sorted(((name, value) for name, value in terms.items()
                             if (value > 0 if positive else value < 0)), key=lambda pair: -abs(pair[1]))[:3]
            return ', '.join(_text(plain.get(name, 'adjustments for missing information' if name.endswith('_missing')
                                else labels.get(name, name.replace('_', ' ')))) for name, _ in chosen) or 'None recorded'
        calculations = []
        for name, value in sorted(terms.items(), key=lambda pair:-abs(pair[1])):
            raw = team.get('features', {}).get(name.removesuffix('_missing'))
            shown = str(int(raw is None)) if name.endswith('_missing') else ('Unavailable' if raw is None else f'{_number(raw):.4g}')
            calculations.append(f'<tr><th scope="row">{_text(labels.get(name, name.replace("_", " ")))}</th>'
                                f'<td>{shown}</td><td>{value:+.3f}</td></tr>')
        calculations = ''.join(calculations)
        explanations.append(f'<details class="model-update-evidence rating-explanation" id="season-rating-{code}" data-view-key="rating-{code}">'
            f'<summary>#{team["rank"]} {code}: why this rating</summary>'
            f'<p>Expected quarterback: {_text(team["qb_name"])}.</p>'
            f'<p><strong>What lifts this rating:</strong> {drivers(True)}.</p>'
            f'<p><strong>What holds this rating back:</strong> {drivers(False)}.</p>'
            '<p>These are overlapping influences in the formula, not separate player-quality grades. '
            'Current non-QB injuries and backup quality are not numerical adjustments here.</p>'
            f'<details data-view-key="rating-calculation-{code}"><summary>Saved calculation</summary><div class="table-shell" data-view-key="rating-table-{code}"><table><thead><tr>'
            '<th>Input</th><th>Saved input value</th><th>Contribution to rating</th></tr></thead>'
            f'<tbody>{calculations}</tbody></table></div>'
            '<p>Input values use different scales and cannot be added together. The formula converts each into a contribution; '
            'those contributions sum to the displayed rating. EPA measures how a play changes expected scoring; '
            'completion percentage above expectation compares completions with the expected rate for those throws.</p>'
            f'<p>Edition: {_text(snapshot["edition"])}. Generated {_time(snapshot["generated_at"])}.</p></details></details>')
    if teams != sorted(teams, key=lambda row: (-row['rating'], row['team'])):
        raise ValueError('Season team ranks differ from saved rating order')
    return (f'<h3 id="season-rankings">Current power rankings</h3><p>Inputs saved through {_time(snapshot["inputs_as_of"])}. '
            f'Performance history through {_time(snapshot["history_through"])}. '
            'Rank change compares this edition with the previous saved board.</p>'
            '<label class="model-update-columns"><input type="checkbox" data-view-key="rating-columns"> Show rating scale and expected QB</label>'
            '<div class="table-shell" data-view-key="rankings-table"><table class="postseason-team-table"><thead><tr>'
            '<th>Rank</th><th>Team</th><th>PGO strength</th><th>Rank change</th>'
            '<th class="model-update-extra">Rating scale</th><th class="model-update-extra">Expected QB</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            '<details class="model-update-evidence" data-view-key="rating-reasons"><summary>Why teams rank here</summary>'
            + ''.join(explanations) + '</details>')


def _game(game, week):
    from pgo_forecast_lab import _spread, _projected_score
    if game['grade'] not in GRADES or game['forecast_status'] not in FORECAST_STATES:
        raise ValueError('Unknown season forecast or grade status')
    codes = {row[0] for row in board.generate_site.TEAM.values()}
    if game['home'] not in codes or game['away'] not in codes or game['home'] == game['away']:
        raise ValueError('Invalid season game teams')
    if game.get('pick') not in (None, game['home'], game['away']):
        raise ValueError('Pick must identify one of the game teams')
    home, away = _text(game['home']), _text(game['away'])
    game_id = _text(game['game_id'])
    scores = 'Forecast unavailable'
    calculation = 'No saved numerical forecast is available for this matchup.'
    favorite = 'No pick' if game.get('pick') is None else _text(game['pick'])
    if game.get('margin') is not None:
        margin, total, hp, ap = (_number(game[name]) for name in ('margin','total','home_points','away_points'))
        if not (math.isclose(hp,(total+margin)/2,abs_tol=1e-8) and math.isclose(ap,(total-margin)/2,abs_tol=1e-8)):
            raise ValueError('Season saved scores do not reconcile')
        whole = [Decimal(str(value)).quantize(Decimal('1'),rounding=ROUND_HALF_UP) for value in (ap,hp)]
        summary = f'About {whole[0]} points each' if whole[0] == whole[1] else f'{away} {whole[0]}, {home} {whole[1]}'
        scores = f'{summary}<details data-view-key="score-{game_id}"><summary>Model averages</summary><p>{away} {_projected_score(ap)}, {home} {_projected_score(hp)}</p></details>'
        favorite += f'<br><small>{_spread(game)}</small>'
        explanation = game.get('explanation')
        components = ''
        if explanation is not None:
            neutral, venue, rest = (_number(explanation[name]) for name in ('neutral_margin','home_adjustment','rest_adjustment'))
            if not math.isclose(math.fsum((neutral,venue,rest)),margin,rel_tol=0,abs_tol=1e-8):
                raise ValueError('Saved matchup explanation does not reconcile to its margin')
            components = (f'Neutral matchup: {neutral:+.2f} points; Home/venue adjustment: {venue:+.2f} points; '
                          f'rest adjustment: {rest:+.2f} points. Positive values favor {home}. ')
            if 'home_rating' in explanation or 'away_rating' in explanation:
                home_rating, away_rating = (_number(explanation[name]) for name in ('home_rating','away_rating'))
                if not math.isclose(home_rating-away_rating,neutral,rel_tol=0,abs_tol=1e-8):
                    raise ValueError('Saved rating inputs do not reconcile to neutral matchup')
                components = (f'Ratings saved for this forecast: {home} {home_rating:+.3f}; {away} {away_rating:+.3f}. '
                              f'Rating inputs through {_time(explanation.get("rating_inputs_as_of"))}. ' + components)
        calculation = (components + f'The saved model favors {_spread(game)}. Its combined-points estimate is {total:.1f}. '
                       f'Home average = (combined points + home lead) / 2 = {hp:.2f}; away average = '
                       f'(combined points - home lead) / 2 = {ap:.2f}. Rounded scores are not literal final-score predictions.')
        if game['forecast_status'] == 'BLOCKED' or game.get('blocked_reason'):
            scores = '<strong>Saved conditional estimate</strong><br>' + scores
            calculation = 'This estimate is withheld as a pick until the blocking issue is resolved. ' + calculation
    result = game.get('result')
    actual = 'Pending' if result is None else f'{away} {_integer(result["away_score"])}, {home} {_integer(result["home_score"])}'
    confidence = game.get('confidence')
    pool = 'Confidence unavailable'
    if confidence is not None:
        points = _integer(confidence['points'])
        probability, expected = confidence.get('win_probability'), confidence.get('expected_points')
        if points < 1 or (probability is not None and not 0 <= _number(probability) <= 1):
            raise ValueError('Invalid season confidence allocation')
        shown = 'Unavailable' if probability is None else f'{probability:.1%}'
        expected_text = 'Unavailable' if expected is None else f'{_number(expected):.2f}'
        earned = confidence.get('earned_points')
        earned_text = 'Pending' if earned is None else str(_integer(earned))
        if ((expected is not None and (probability is None or not math.isclose(expected,points*probability,rel_tol=0,abs_tol=1e-8)))
                or (earned is not None and earned > points)):
            raise ValueError('Season confidence points do not reconcile')
        pool = f'{points} points; win chance {shown}<br>Expected: {expected_text}<br>Earned: {earned_text}'
        if confidence.get('added_after_lock'):
            pool += '<br><strong>Added after lock</strong>'
    availability = game.get('availability') or {}
    note = _text(availability.get('summary') or 'Availability not verified')
    reason = game.get('blocked_reason') or availability.get('blocked_reason')
    if reason: note += f'<br><strong>{_text(reason)}</strong>'
    note += '<br>Checked ' + _time(availability.get('checked_at'))
    provenance = ''
    if game.get('issued_at'):
        provenance += f'<p>Issued {_time(game["issued_at"])}; inputs through {_time(game.get("inputs_as_of"))}.</p>'
    if game.get('expected_qbs'):
        quarterbacks = '; '.join(f'{_text(team)}: {_text(game["expected_qbs"].get(team) or "Unavailable")}'
                                 for team in (game['away'],game['home']))
        provenance += f'<p>Expected quarterbacks saved with this forecast: {quarterbacks}.</p>'
    status = game['forecast_status']
    if status in ('DRAFT','LOCKED'):
        status = f'<span class="weekly-status" data-weekly-cutoff="{_text(game["lock_at"])}">{status.title()}</span>'
    return (f'<tr id="season-game-{game_id}" data-season-game-id="{game_id}"><th scope="row">{away} @ {home}</th>'
            f'<td>{favorite}</td><td>{scores}</td><td data-grade="{game["grade"]}">{GRADES[game["grade"]]}</td>'
            f'<td>{actual}</td><td>{pool}</td><td>{status}<br>Deadline {_time(game.get("lock_at"))}'
            f'<br>Kickoff {_time(game["kickoff"])}</td></tr>'
            f'<tr class="forecast-reason-row"><td colspan="7"><details class="forecast-reason" data-view-key="reason-{game_id}">'
            '<summary>Forecast explanation and availability</summary><div class="forecast-reason-body">'
            f'<div class="forecast-reason-block"><h3>Saved calculation</h3><p>{calculation}</p>'
            f'<p>Edition: {_text(game.get("source_edition",week["source_edition"]))}.</p>{provenance}</div>'
            f'<div class="forecast-reason-block"><h3>Availability context</h3><p>{note}</p>'
            '<p>Non-QB injury news is context, not a fitted injury adjustment.</p></div></div></details></td></tr>')


def _week(week, current):
    if week['status'] not in WEEK_STATES: raise ValueError('Unknown week status')
    games = week['games']
    _integer(week['week'])
    if any(game.get('week') != week['week'] for game in games):
        raise ValueError('Season game belongs to another week')
    ids = [game['game_id'] for game in games]
    points = [g['confidence']['points'] for g in games if g.get('confidence') is not None]
    if len(ids) != len(set(ids)) or len(points) != len(set(points)):
        raise ValueError('Duplicate game or confidence allocation in week')
    counts = Counter(game['grade'] for game in games)
    rows = ''.join(_game(game,week) for game in games)
    allocations = [game['confidence'] for game in games if game.get('confidence') is not None]
    pool_summary = ''
    if allocations:
        earned = sum(c.get('earned_points') or 0 for c in allocations)
        expected = ('Unavailable' if any(c.get('expected_points') is None for c in allocations)
                    else f"{math.fsum(c['expected_points'] for c in allocations):.2f}")
        pool_summary = (f'<p>Confidence pool: {earned} earned so far; {sum(c["points"] for c in allocations)} allocated points. '
                        f'Expected pool points from the saved chances: {expected}. Late entries remain marked below.</p>')
    return (f'<details class="forecast-week" id="season-week-{week["week"]}" data-view-key="week-{week["week"]}"{" open" if current else ""}>'
            f'<summary>Week {week["week"]}: {_text(week["status"].replace("_"," "))}</summary>'
            f'<p>{counts["W"]} W / {counts["L"]} L / {counts["T"]} T; {counts["NO_PICK"]} no pick; {counts["PENDING"]} pending.</p>'
            f'<p>Saved {_time(week["generated_at"])}; inputs through {_time(week["inputs_as_of"])}.</p>{pool_summary}'
            f'<div class="table-shell" data-view-key="week-table-{week["week"]}"><table><thead><tr><th>Matchup</th><th>PGO pick</th><th>Estimated score</th>'
            '<th>Grade</th><th>Final score</th><th>Confidence allocation</th><th>Forecast status and times</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div></details>')


def _penalty_shadow(shadow):
    if not shadow:
        return ''
    historical = shadow.get('historical') or {}
    history = ''
    if historical:
        baseline, candidate = (_number(historical[k]) for k in ('baseline_mae','candidate_mae'))
        result = 'met' if historical['status'] == 'PASS' else 'did not meet'
        interval = historical['interval']
        history = (f'<h4>Past-game test: {_integer(historical["games"]):,} games</h4>'
                   '<p>Average error in the predicted lead: '
                   f'existing model <strong>{baseline:.4f}</strong> points; '
                   f'penalty candidate <strong>{candidate:.4f}</strong> points. Lower error is better. '
                   f'The candidate {result} the predeclared improvement screen. '
                   f'It improved {_integer(historical["season_wins"])} of 8 seasons.</p>'
                   f'<p>Estimated improvement range: {_number(interval["lower"]):+.3f} to '
                   f'{_number(interval["upper"]):+.3f} points (95% interval). Positive means less error; '
                   'a range spanning zero does not show a clear gain. These historical seasons have already '
                   'been studied, so future saved predictions are the next test.</p>')
    metrics = shadow.get('metrics') or {}
    paired = _integer(metrics.get('paired_games',0))
    rows = []
    for key, label in (('control','Existing model on the same saved inputs'),('candidate','Penalty candidate')):
        metric = metrics.get(key) or {}
        error = 'Awaiting finals' if metric.get('mae') is None else f'{_number(metric["mae"]):.3f}'
        record = ' / '.join(str(_integer(metric.get(k,0))) for k in ('wins','losses','ties'))
        rows.append(f'<tr><th scope="row">{label}</th><td>{record}</td><td>{error}</td></tr>')
    games = []
    def lead(game, key):
        value = _number(game[key])
        return 'No edge' if value == 0 else f'{_text(game["home"] if value > 0 else game["away"])} by {abs(value):.3g}'
    for game in shadow.get('games',[]):
        grade = game.get('grade') or {}
        labels = [GRADES[grade.get(key,'PENDING')] for key in ('control','candidate')]
        games.append(f'<tr data-penalty-game-id="{_text(game["game_id"])}"><th scope="row">'
                     f'Week {_integer(game["week"])}: {_text(game["away"])} @ {_text(game["home"])}</th>'
                     f'<td>{lead(game,"control_margin")}</td><td>{lead(game,"candidate_margin")}</td>'
                     f'<td>{labels[0]} / {labels[1]}</td><td>{_time(game["issued_at"])}</td></tr>')
    reason = (f'<p><strong>Penalty test update blocked:</strong> {_text(shadow["blocked_reason"])}</p>'
              if shadow.get('blocked_reason') else '')
    excluded = shadow.get('excluded') or []
    exclusions = ('<details data-view-key="penalty-exclusions"><summary>Games excluded from this test</summary><ul>' + ''.join(
        f'<li>{_text(item["game_id"])}: {_text(item["reason"])}</li>' for item in excluded) + '</ul></details>' if excluded else '')
    return ('<details class="model-update-evidence" id="pgo-penalty-test" data-view-key="penalty-test"><summary>Penalty experiment and ongoing results</summary>'
            '<p><strong>Experimental comparison, separate from the main picks.</strong> '
            'This tests whether a team\'s prior penalty yards help predict its next game. Recent games receive more weight; '
            'four games later, an observation has half its original weight. Penalty counts are audited but are not another fitted input.</p>'
            '<p>Weights stay fixed. The scheduled updater checks new finals and prepares future test picks after the weekly '
            'rankings update. Each candidate and comparison pick is saved before the prediction deadline. '
            'Games already locked when the test began, including the NE–SEA opener, do not count toward its future record.</p>'
            + history + reason + f'<h4>Future test: {paired} completed paired games</h4>'
            '<p>The two methods are scored on exactly the same saved games and inputs. A later revision of a main pick '
            'does not replace this saved comparison. Small samples are only progress updates; no automatic model promotion occurs.</p>'
            '<div class="table-shell" data-view-key="penalty-records"><table><thead><tr><th>Test model</th><th>W / L / T</th>'
            '<th>Average lead error (points)</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
            '<details data-view-key="penalty-picks"><summary>Saved prospective test picks</summary><div class="table-shell" data-view-key="penalty-picks-table"><table><thead>'
            '<tr><th>Matchup</th><th>Existing model lead</th><th>Penalty candidate lead</th>'
            '<th>Grades: existing / candidate</th><th>Saved (Eastern)</th></tr></thead><tbody>'
            + ''.join(games) + '</tbody></table></div></details>' + exclusions +
            '<p>The penalty candidate refits the existing coefficients alongside one new input. Its full prediction change '
            'is not just the new coefficient. This tests scoring margins; it does not supply new score totals, probabilities '
            'or injury adjustments.</p>' + _sources([{'href':shadow.get('source_href','evidence/penalty-model-2026/manifest.json'),
            'label':'Verified weights and historical results'},
            {'href':'https://github.com/walshja9/Postgame_Outlet/blob/main/research/pgo_penalty_candidate/model-card.md',
             'label':'Penalty test methods, findings and review rules'}]) + '</details>')


def render_season(state):
    """Render validated saved state using the existing shared PGO styles once per page."""
    if state['schema_version'] != 1 or state['status'] not in ('READY','BLOCKED'):
        raise ValueError('Unknown season view state')
    season, current = _integer(state['season']), _integer(state['current_week'])
    weeks = state['weeks']
    if len({w['week'] for w in weeks}) != len(weeks): raise ValueError('Duplicate season week')
    games = [game for week in weeks for game in week['games']]
    if len({game['game_id'] for game in games}) != len(games) or any(game.get('season') != season for game in games):
        raise ValueError('Season game identity is duplicated or belongs to another season')
    records = []
    for row in state.get('model_records', []):
        counts = ''.join(f'<td>{_integer(row[key])}</td>' for key in ('wins','losses','ties','no_pick','pending'))
        records.append(f'<tr><th scope="row">{_text(row["name"])}<br><small>{_text(row["edition"])}</small></th>{counts}</tr>')
    block = f'<p><strong>Update blocked:</strong> {_text(state["blocked_reason"])}</p>' if state.get('blocked_reason') else ''
    current_weeks = ''.join(_week(w,True) for w in weeks if w['week'] == current)
    archives = ''.join(_week(w,False) for w in sorted(weeks,key=lambda w:w['week'],reverse=True) if w['week'] != current)
    links = [(f'season-week-{current}',f'Week {current} picks')] if current_weeks else []
    links.append(('season-records','Model records'))
    if state.get('rankings'): links.append(('season-rankings','Rankings'))
    if state.get('penalty_shadow'): links.append(('pgo-penalty-test','Penalty test'))
    navigation = '<nav class="season-nav" aria-label="PGO sections">' + ''.join(
        f'<a href="#{target}" data-view-key="nav-{target}">{label}</a>' for target,label in links) + '</nav>'
    return (f'<div class="pgo-model-updates" id="pgo-season" data-season-checked-at="{_text(state["checked_at"])}"><h2>PGO Power Rankings &mdash; Experimental</h2>'
            f'<p><strong>{season} &middot; Week {current} &middot; EXPERIMENTAL / HOLD.</strong> '
            'Accuracy is still being tested. The record below tracks saved forecasts.</p>'
            + navigation + '<details class="model-update-evidence" data-view-key="numbers-guide"><summary>How the numbers connect</summary>'
            '<p>Team ratings measure model strength from recent results and team/quarterback history. '
            'The home rating minus the away rating is the projected home-team point advantage at a neutral site with equal rest. '
            'The saved venue and rest adjustments then give the game lead. Each individual rating is centered model strength, '
            'not a standalone score prediction. '
            'A separate scoring estimate sets combined points; the lead splits those points into two score averages. '
            'That scoring estimate uses the saved 2025 regular-season and playoff scoring and points-allowed averages; '
            'it does not yet update with 2026 results.</p>'
            '<p>Win probability is a percentage from the saved model probability method, not a rating or a confidence-point percentage. '
            'Fixed confidence points weight the picks within one weekly pool. Points times win probability gives expected '
            'pool points, not NFL scoreboard points. None of these numbers guarantees a result.</p>'
            '<p>Rounded score estimates can look equal even when one team has a small edge. '
            'About 25 points each is not a prediction of a tied game. Open Model averages for decimal estimates.</p></details>'
            f'<p>Automation status: {state["status"]}. Last automation check: {_time(state["checked_at"])}. {_text(state.get("freshness", ""))}</p>{block}'
            '<p>W/L/T grades use each saved model pick and verified final scores. Missing results remain pending. '
            'Injury news is shown as context; current non-QB injuries and backup quality are not separately rated.</p>'
            + _rankings(state.get('rankings')) +
            '<h3 id="season-records">Model records</h3><div class="table-shell" data-view-key="model-records-table"><table><thead><tr><th>Saved model series</th>'
            '<th>W</th><th>L</th><th>T</th><th>No pick</th><th>Pending</th></tr></thead>'
            f'<tbody>{"".join(records)}</tbody></table></div>'
            '<p>Each record covers its own saved schedule. Weekly editions cover published weeks; '
            'the preseason baselines cover all 272 regular-season games, so their pending counts can be larger.</p>'
            f'<h3>Week {current} picks and grades</h3>'
            '<p><strong>Fixed confidence points:</strong> the weekly allocation is saved once. '
            'Before a game locks, an expected-QB update may change its win chance without reallocating its confidence points. '
            'Expected pool points = fixed points times win chance; these are not NFL scoreboard points. '
            'After-lock confidence entries are marked separately and are not pregame probability evidence; '
            'the original score forecast keeps its own saved timing.</p>'
            + (current_weeks or '<p>No saved slate is available for this week.</p>') +
            ('<details class="model-update-evidence" data-view-key="week-archives"><summary>Previous weekly grades and forecasts</summary>' + archives + '</details>' if archives else '') +
            _penalty_shadow(state.get('penalty_shadow')) +
            '<details class="model-update-evidence" data-view-key="season-sources"><summary>Sources and limitations</summary>'
            + _sources(state.get('sources', [])) + '<ul>' + ''.join(f'<li>{_text(item)}</li>' for item in state.get('limitations', [])) + '</ul></details></div>')
