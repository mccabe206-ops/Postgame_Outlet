"""Present the verified registered corrected edition above the preserved July board."""
from datetime import datetime
import html
import math
import re
from zoneinfo import ZoneInfo

START = '<!-- PGO CURRENT BOARD START -->'
END = '<!-- PGO CURRENT BOARD END -->'
ARCHIVE_OPEN = ('<!-- PGO JULY ARCHIVE OPEN --><details class="pgo-july-archive">'
                '<summary>July 21, 2026 comparison archive</summary>')
ARCHIVE_CLOSE = '</details><!-- PGO JULY ARCHIVE CLOSE -->'


def strip_current_board(page):
    """Recover the exact legacy markup before its existing strict validators run."""
    counts = [page.count(marker) for marker in (START, END, ARCHIVE_OPEN, ARCHIVE_CLOSE)]
    if counts == [0, 0, 0, 0]:
        return page
    if counts != [1, 1, 1, 1] or not (
            page.index(START) < page.index(END) < page.index(ARCHIVE_OPEN) < page.index(ARCHIVE_CLOSE)):
        raise ValueError('Invalid current-board/archive presentation markers')
    page = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', page, count=1, flags=re.S)
    return page.replace(ARCHIVE_OPEN, '', 1).replace(ARCHIVE_CLOSE, '', 1)


def _time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Current board source timestamps require a timezone')
    return (f'<time datetime="{html.escape(value, quote=True)}">'
            f'{parsed.astimezone(ZoneInfo("America/New_York")):%B %d, %Y at %I:%M %p %Z}</time>')


def add_current_board(page, snapshot=None, mccabe_rows=None):
    # Lab imports comparison; defer these imports until rendering is requested.
    import pgo_comparison as comparison
    import pgo_forecast_corrected as corrected
    page = strip_current_board(page)
    if snapshot is None:
        import pgo_forecast_lab as lab
        weekly = lab.pgo_forecast_weekly.load_weekly(lab.WEEKLY_DIR)
        snapshot, _directory = lab._load_corrected(None, weekly, lab.WEEKLY_DIR)
    if snapshot['edition'] != corrected.EDITION:
        raise ValueError('Current board requires the corrected September 8 edition')
    if mccabe_rows is None:
        mccabe_rows = comparison.load_mccabe_rows(comparison.MCCABE_PATH)
    human = {row['abbr']: row for row in mccabe_rows}
    teams = sorted(snapshot['teams'], key=lambda row: row['rank'])
    if (len(teams) != 32 or len(human) != 32 or {row['team'] for row in teams} != set(human)
            or [row['rank'] for row in teams] != list(range(1, 33))
            or any(not math.isfinite(row['rating']) for row in teams)
            or teams != sorted(teams, key=lambda row: (-row['rating'], row['team']))):
        raise ValueError('Current board requires 32 verified ranked team identities')
    rows = []
    ne_rank = next(team['rank'] for team in teams if team['team'] == 'NE')
    for team in teams:
        code, rank = team['team'], team['rank']
        name = human[code]['team']
        mccabe_rank = human[code]['rank']
        rows.append(
            f'<tr data-current-pgo-team="{html.escape(code, quote=True)}">'
            f'<th scope="row"><a href="https://walshja9.github.io/Postgame_Outlet/forecast-lab.html#corrected-rating-{code}" '
            f'target="_blank" rel="noopener noreferrer">{html.escape(name)}</a></th>'
            f'<td>{rank}</td><td data-value="{team["rating"]}">{team["rating"]:+.3f}</td>'
            f'<td>{html.escape(team["qb_name"])}</td><td>{mccabe_rank}</td><td>{rank - mccabe_rank:+d}</td></tr>')
    current = (
        f'{START}<style>'
        '#panel-comparison .current-pgo-table th:first-child {text-align:left;position:sticky;left:0;z-index:1;}'
        '#panel-comparison .current-pgo-table tbody th {background:var(--panel);color:var(--ink);'
        'font-size:inherit;letter-spacing:normal;text-transform:none;user-select:text;border-bottom:1px solid var(--border);}'
        '#panel-comparison .current-pgo-table a {color:var(--accent);text-decoration:underline;text-underline-offset:3px;}'
        '#panel-comparison .current-pgo-table a:hover {color:var(--accent);text-decoration:underline;}'
        '@media(max-width:680px){#panel-comparison .current-pgo-table {font-size:12px;}'
        '#panel-comparison .current-pgo-table th,#panel-comparison .current-pgo-table td {padding:8px 7px;}}'
        f'</style><div class="pgo-current-board" data-edition="{corrected.EDITION}">'
        '<div class="model-status" data-model-status="HOLD">Experimental — still being tested</div>'
        '<h2>PGO Corrected — September 8, 2026</h2>'
        '<p>Higher ratings mean the model expects a stronger team. These numbers are not betting lines. '
        '“Corrected” means we repaired the calculation; greater accuracy has not been proved.</p>'
        '<p><strong>Injuries beyond the quarterback are not included.</strong> '
        'These ratings assume the listed quarterback plays.</p>'
        f'<p>Roster information saved through {_time(snapshot["inputs_as_of"])}. '
        'Game and player performance comes from the 2025 regular season and earlier. '
        'Select a team to see why it ranks here. Team explanations open in a new tab.</p>'
        f'<p><strong>New England is #{ne_rank} in this snapshot.</strong> '
        'The ranking is an estimate, not proof of where the team belongs. '
        '<a href="https://walshja9.github.io/Postgame_Outlet/forecast-lab.html#corrected-rating-NE" '
        'target="_blank" rel="noopener noreferrer">Read New England’s explanation</a>.</p>'
        '<details><summary>How to read this board — dates and technical details</summary>'
        '<p>Research status: EXPERIMENTAL / HOLD. Zero is the average of these 32 teams. '
        'A +5 rating does not mean a team should be favored by five points.</p>'
        f'<p>Snapshot generated {_time(snapshot["generated_at"])}. '
        f'McCabe source: {_time(comparison.mccabe_source_timestamp(comparison.MCCABE_PATH))}. '
        'Performance history ends with the 2025 regular season.</p>'
        '<p>“vs McCabe” compares rank positions: +3 means PGO ranks the team three spots lower. '
        'It is PGO rank minus McCabe rank, not a difference in points. '
        '<a href="https://walshja9.github.io/Postgame_Outlet/forecast-lab.html#corrected-ratings" '
        'target="_blank" rel="noopener noreferrer">Forecast Lab: explanations, source coverage, and weekly drafts</a>. '
        '</p></details>'
        '<div class="table-shell"><table class="current-pgo-table">'
        '<caption class="visually-hidden">All 32 teams: corrected PGO model output and current McCabe rank</caption>'
        '<thead><tr><th scope="col">Team</th><th scope="col">PGO #</th>'
        '<th scope="col">PGO rating</th><th scope="col">Expected QB</th>'
        '<th scope="col">McCabe #</th><th scope="col">vs McCabe</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div></div>{END}')
    panel = comparison.extract_comparison_panel(page)
    opening = panel.index('>') + 1
    closing = panel.rindex('</section>')
    updated = panel[:opening] + current + ARCHIVE_OPEN + panel[opening:closing] + ARCHIVE_CLOSE + panel[closing:]
    return page.replace(panel, updated, 1)
