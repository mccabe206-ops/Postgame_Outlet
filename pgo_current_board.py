"""Present the verified registered corrected edition above the preserved July board."""
from datetime import datetime, timezone
import html
import math
import re

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
            f'{parsed.astimezone(timezone.utc):%B %d, %Y at %H:%M UTC}</time>')


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
        'font-size:inherit;letter-spacing:normal;text-transform:none;border-bottom:1px solid var(--border);}'
        '#panel-comparison .current-pgo-table a {color:var(--ink);text-decoration:none;}'
        '#panel-comparison .current-pgo-table a:hover {color:var(--accent);text-decoration:underline;}'
        '@media(max-width:680px){#panel-comparison .current-pgo-table {font-size:12px;}'
        '#panel-comparison .current-pgo-table th,#panel-comparison .current-pgo-table td {padding:8px 7px;}}'
        f'</style><div class="pgo-current-board" data-edition="{corrected.EDITION}">'
        '<div class="model-status">EXPERIMENTAL / HOLD</div>'
        '<h2>PGO Corrected — September 8, 2026</h2>'
        '<p>Independent team-strength estimates, conditional on the listed QB. '
        'Non-QB injuries are unpriced. These model outputs are not calibrated point prices.</p>'
        f'<p>Inputs captured through {_time(snapshot["inputs_as_of"])}; '
        f'snapshot generated {_time(snapshot["generated_at"])}. '
        f'McCabe source: {_time(comparison.mccabe_source_timestamp(comparison.MCCABE_PATH))}. '
        'Performance history ends with the 2025 regular season.</p>'
        '<p>Rank gap = PGO rank minus McCabe rank; positive means PGO ranks the team lower. '
        '<a href="https://walshja9.github.io/Postgame_Outlet/forecast-lab.html#corrected-ratings" '
        'target="_blank" rel="noopener noreferrer">Forecast Lab: explanations, source coverage, and weekly drafts</a>. '
        'Select a team for its corrected explanation.</p>'
        '<div class="table-shell"><table class="current-pgo-table">'
        '<caption class="visually-hidden">All 32 teams: corrected PGO model output and current McCabe rank</caption>'
        '<thead><tr><th scope="col">Team</th><th scope="col">PGO #</th>'
        '<th scope="col">Model output</th><th scope="col">Expected QB</th>'
        '<th scope="col">McCabe #</th><th scope="col">Rank gap</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div></div>{END}')
    panel = comparison.extract_comparison_panel(page)
    opening = panel.index('>') + 1
    closing = panel.rindex('</section>')
    updated = panel[:opening] + current + ARCHIVE_OPEN + panel[opening:closing] + ARCHIVE_CLOSE + panel[closing:]
    return page.replace(panel, updated, 1)
