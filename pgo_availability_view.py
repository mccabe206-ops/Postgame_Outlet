"""Display a verified non-QB scenario beside the unchanged PGO base."""
import html
import math
from urllib.parse import urlsplit


def _text(value):
    return html.escape(str(value), quote=True)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Availability display requires finite numbers')
    return f'{value:+.3f}'


def _cell(value):
    if value is None:
        return '<td>Unknown</td>'
    return f'<td data-value="{value}">{_number(value)}</td>'


def _source(row):
    from pgo_current_board import _time
    url = row.get('source_url')
    if not url:
        return 'Source unavailable'
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Availability sources require HTTPS URLs without credentials')
    captured = _time(row['captured_at'])
    return (f'<a href="{_text(url)}" target="_blank" rel="noopener noreferrer">Source report</a>'
            f' dated {_text(row.get("report_date") or "unknown")}; captured {captured}')


def _player(row):
    role = row.get('role')
    if role is None or role.get('snap_share') is None:
        usage = 'Past playing-time data unavailable'
    else:
        share = role['snap_share']
        _number(share)
        if not 0 <= share <= 1:
            raise ValueError('Availability role share is outside [0, 1]')
        usage = (f'Past share of offensive or defensive plays: {share:.1%}; {_text(role["sample_count"])} observations; '
                 f'last observed {_text(role.get("last_observed") or "unknown")}. '
                 f'Previous team: {_text(role.get("previous_team") or "not reported")}.')
    usage += ' ' + _text((role or {}).get('source_note') or '')
    delta = 'Cannot estimate' if row.get('delta') is None else _number(row['delta']) + ' points'
    return (f'<li><strong>{_text(row["name"])}</strong> ({_text(row["position"])}; '
            f'{_text(row["status"])}; {_text(row["unit"])}). '
            f'Player ID: {_text(row["gsis_id"])}. Estimated change: {delta}. '
            f'{_text(row.get("reason") or "")}<br>{usage}<br>{_source(row)}</li>')


def render_scenario(scenario):
    """Render already verified package data without recomputing or mutating it."""
    from pgo_current_board import _time, team_identity
    if scenario['status'] != 'EXPERIMENTAL / HOLD':
        raise ValueError('Availability scenarios must retain EXPERIMENTAL / HOLD')
    rows, unknown_rows, details = [], [], []
    labels = {'COMPLETE': 'All listed players accounted for',
              'PARTIAL': 'Incomplete — known players only', 'UNKNOWN': 'No verified report'}
    for team in scenario['teams']:
        status = team['status']
        if status not in labels:
            raise ValueError('Invalid availability team status')
        complete = status == 'COMPLETE'
        values = [team['base_rating'], team['known_out_delta'], team['all_uncertain_out_delta']]
        if complete:
            values += [team['known_out_rating'], team['all_uncertain_out_rating']]
            for value in values:
                _number(value)
        else:
            _number(team['base_rating'])
        adjusted = ''.join(_cell(value) for value in values)
        if not complete:
            adjusted += '<td>Unavailable</td><td>Unavailable</td>'
        target = unknown_rows if status == 'UNKNOWN' else rows
        target.append(f'<tr><th scope="row">{team_identity(team["team"])}</th>{adjusted}'
                      f'<td>{labels[status]}</td></tr>')
        coverage = team.get('coverage') or {}
        players = ''.join(_player(player) for player in team['players'])
        excluded = ''.join(
            f'<li>{_text(player["name"])} ({_text(player["status"])}): '
            f'{_text(player["reason"])}. Saved source: {_text(player["source_file"])}.</li>'
            for player in team.get('excluded', []))
        details.append(
            f'<details><summary>{_text(team["team"])} — {labels[status]}: '
            'players and injury reports</summary>'
            f'<p>{_text(team.get("reason") or "")} '
            f'Players we cannot fully account for: {_text(team["unknown_count"])}. '
            f'Report type: {_text({"formal_game_status": "official game-status report", "practice_only": "practice report only", "unknown": "no verified report"}.get(coverage.get("source_kind"), "no verified report"))}. '
            f'{_source(coverage)}</p>'
            + (f'<ul>{players}</ul>' if players else '<p>No individual player estimates are available. That does not mean the team is healthy.</p>')
            + (f'<p>Excluded observations</p><ul>{excluded}</ul>' if excluded else '')
            + '</details>')
    table_open = (
        '<div class="table-shell" role="region" aria-label="Team availability scenarios" tabindex="0">'
        '<table><thead><tr><th scope="col">Team</th>'
        '<th scope="col">Original PGO rating</th><th scope="col">Estimated change: ruled out</th>'
        '<th scope="col">Estimated change: uncertain players out too</th>'
        '<th scope="col">Rating with ruled-out players absent</th><th scope="col">Rating if uncertain players miss too</th>'
        '<th scope="col">What we know</th></tr></thead><tbody>')
    table_close = '</tbody></table></div>'
    team_tables = table_open + ''.join(rows) + table_close if rows else '<p>We do not have enough verified injury information for any team.</p>'
    if unknown_rows:
        count = len(unknown_rows)
        team_tables += (f'<details><summary>{count} team{"s" if count != 1 else ""} without a verified report</summary>'
                        '<p>We do not know enough to estimate their injury impact. Missing reports do not mean healthy teams.</p>'
                        + table_open + ''.join(unknown_rows) + table_close + '</details>')
    games, unknown_games = [], []
    for game in scenario['games']:
        status = game['status']
        if status not in {*labels, 'CUTOFF_PASSED'}:
            raise ValueError('Invalid availability game status')
        if status == 'COMPLETE':
            adjusted = _cell(game['known_out_margin'])
            if game['known_out_margin'] is None:
                raise ValueError('Complete availability game requires its margin')
            low, high = game['margin_low'], game['margin_high']
            span = f'{_number(low)} to {_number(high)}'
            if low > high:
                raise ValueError('Availability scenario range is reversed')
        else:
            adjusted, span = '<td>Unavailable</td>', 'Unavailable'
        label = 'Cutoff passed — no new estimate' if status == 'CUTOFF_PASSED' else labels[status]
        if status == 'UNKNOWN':
            label = 'Not enough verified injury information'
        target = unknown_games if status == 'UNKNOWN' else games
        target.append(f'<tr><th scope="row">{_text(game["away"])} at {_text(game["home"])}</th>'
                     f'{_cell(game["base_margin"])}{adjusted}<td>{span}</td><td>{label}</td>'
                     f'<td>{_time(game["kickoff"])}</td><td>{_time(game["cutoff"])}</td></tr>')
    game_table = ''
    if games or unknown_games:
        game_open = (
            '<div class="table-shell" role="region" aria-label="Matchup availability scenarios" tabindex="0">'
            '<table><thead><tr><th scope="col">Matchup</th>'
            '<th scope="col">Original home-team lead</th><th scope="col">Home-team lead with ruled-out players absent</th>'
            '<th scope="col">Possible leads if uncertain players miss</th><th scope="col">What we know</th>'
            '<th scope="col">Kickoff</th><th scope="col">Prediction deadline</th></tr></thead><tbody>')
        game_table = (
            '<h3>What this could mean for each game</h3><p>A positive lead favors the home team; a negative lead favors the away team. '
            'The range covers different combinations of players missing the game; it is not a confidence interval. '
            'We only show an injury-adjusted lead when both teams have enough verified information before the prediction deadline.</p>')
        if games:
            game_table += game_open + ''.join(games) + table_close
        if unknown_games:
            count = len(unknown_games)
            game_table += (f'<details><summary>{count} matchup{"s" if count != 1 else ""} without enough injury information</summary>'
                           + game_open + ''.join(unknown_games) + table_close + '</details>')
    return (
        '<div id="nonqb-availability" class="pgo-availability" role="region" aria-label="Injury estimates excluding quarterbacks">'
        '<div class="model-status" data-model-status="HOLD">Experimental — injury estimates are still being tested</div>'
        '<h2>How injuries could change the ratings</h2>'
        '<p>These estimates cover players other than quarterbacks. The original ratings and game predictions stay unchanged.</p>'
        '<p>A negative change means a lower team rating. “Incomplete” means we lack a full injury report or cannot estimate every listed player. '
        'We show the change for players we can estimate, but no full adjusted rating. “Unknown” never means zero impact.</p>'
        f'<p>Reports checked through {_time(scenario["as_of"])}. '
        f'Estimate saved {_time(scenario["generated_at"])}. This page does not refresh automatically.</p>'
        '<p>The first estimate counts players ruled out or on the listed injury reserve lists. The second also assumes '
        'questionable and doubtful players miss the game. Missing practice alone does not count as missing the game.</p>'
        f'{team_tables}{game_table}<details><summary>How we estimate injury effects — players, sources and limits</summary>'
        f'<p>Research status: EXPERIMENTAL / HOLD. Base edition: {_text(scenario["base_edition"])}. '
        'Known-out status includes OUT, IR and PUP. Information must be saved before each game’s deadline, '
        '60 minutes before kickoff. Complete covers the listed reports, not a guarantee that every absence is known.</p>'
        '<p>Role is the median of the last four positive regular-season unit snap shares through 2025. '
        'A transferred or returning player’s historical usage is a proxy, not a current depth-chart claim. '
        'The fitted unit-role effect is an aggregate conditional association, not an individual star '
        'valuation or a measurement of replacement quality. QB and special teams are excluded. '
        'Past team performance may already reflect absences, so residual overlap remains possible. '
        'This role/status policy is unvalidated; scenario endpoints and their midpoint are not forecasts '
        'or calibrated probabilities.</p>'
        f'{"".join(details)}</details></div>')


def render_current_scenario():
    """Missing optional package is quiet; malformed or unverified packages fail."""
    from pgo_nonqb_availability import load_package
    scenario = load_package()
    return '' if scenario is None else render_scenario(scenario)
