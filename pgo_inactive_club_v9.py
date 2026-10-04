"""Own-club prose followed by an explicitly named opponent paragraph list.

Only the source club becomes observations here. The opponent span corroborates
the boundary and complete DOM inventory; it does not resolve names or identities.
Frozen v7 opponent parsing and frozen v8 prose parsing remain separate paths.
"""
import re

from pgo_inactive_club import TEAM_NAMES, _NAME, _POSITION
from pgo_inactive_club_v8 import (
    GENERIC_HEADING, _FORM_BLOCK, _Paragraphs, _check_count, _lines, _prose_row,
)


def parse_two_team_prose(raw, body, headline, source_team, team, game):
    if team != source_team or team not in ('LV', 'LAC') or team not in (game['away'], game['home']):
        raise ValueError('Two-team prose observations require the supported source club')
    opponent = game['away'] if team == game['home'] else game['home']
    if team == 'LV':
        heading = GENERIC_HEADING
        boundary = TEAM_NAMES[opponent].split()[-1] + ' inactives:'
    else:
        heading = 'Here are the Chargers inactives:'
        boundary = "Here are " + TEAM_NAMES[opponent].rsplit(' ', 1)[0] + "'s inactives:"
    if body.count(heading) != 1 or body.count(boundary) != 1:
        raise ValueError('No unique own and opponent prose headings')
    starts = list(re.finditer(r'(?m)^' + re.escape(heading) + r'[ \t]*$', body))
    if len(starts) != 1:
        raise ValueError('Own prose heading is not a standalone paragraph')
    start = starts[0]
    split = body.index(boundary)
    if split <= start.end() or not re.match(r'[ \t]*\n', body[split + len(boundary):]):
        raise ValueError('Opponent prose heading is outside the observed list boundary')
    own_lines = _lines(body[start.end():split])
    other_lines = _lines(body[split + len(boundary):])
    rows = [_prose_row(line) for line in own_lines]
    if (not rows or len(rows) > 32 or any(row is None for row in rows)
            or len({row['name'].casefold() for row in rows}) != len(rows)):
        raise ValueError('Incomplete, duplicate or unrecognized own prose rows')
    # The observed opponent span includes a literal comma-before-Jr. row. Its
    # text may corroborate a boundary without becoming an observation or alias.
    def boundary_name(line):
        row = _prose_row(line)
        if row is not None:
            return row['name'].casefold()
        match = re.fullmatch(_POSITION + r'\s+(' + _NAME + r', Jr\.)', line)
        return match[1].casefold() if match else None
    other_names = [boundary_name(line) for line in other_lines]
    if (not other_lines or len(other_lines) > 32
            or len(set(other_names)) != len(other_names)
            or any(name is None for name in other_names)):
        raise ValueError('Incomplete, duplicate or unrecognized opponent boundary rows')
    blocks = _Paragraphs(raw.decode('utf-8')).blocks
    headings = [index for index, block in enumerate(blocks) if block == [heading]]
    if len(headings) != 1:
        raise ValueError('No unique own prose heading in article DOM')
    tail = blocks[headings[0] + 1:]
    expected = ([[line] for line in own_lines] if team == 'LV' else [own_lines])
    expected += [[boundary]] + [[line] for line in other_lines]
    # Retain the frozen exact-attribute marketing sentinel, now after the
    # complete explicit opponent section rather than the old pending notice.
    if team == 'LAC' and tail == expected + [_FORM_BLOCK]:
        tail = tail[:-1]
    if tail != expected:
        raise ValueError('Two-team prose differs from complete article DOM paragraphs')
    _check_count(body, headline, start.start(), team, len(rows))
    return dict(observations=rows, unparsed_lines=[])
