"""Two observed prose layouts, corroborated by their article paragraph bounds.

The caller retains official-source, matchup, period and clock admission. This
module adds no identity aliases and is never called while replaying v1-v7.
"""
from html.parser import HTMLParser
import re

from pgo_inactive_club import TEAM_NAMES, _COUNTS, _NUMBER, _row


GENERIC_HEADING = "Before kickoff, here are the inactive players for today's game:"
_CHARGERS_FORM = {
    'id': '/sofi_interest_chargers_com?referrer=stories',
    'class': 'optanon-category-C0003',
    'data-src': 'https://chargers.formstack.com/forms//sofi_interest_chargers_com?referrer=stories',
    'frameborder': '0', 'webkitallowfullscreen': None, 'mozallowfullscreen': None,
    'allowfullscreen': None, 'style': 'width:100%;height:600px', 'title': 'Formstack content',
}
_FORM_BLOCK = 'chargers-sofi-interest-form'


class _Paragraphs(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.articles = self.depth = 0
        self.hidden = 0
        self.current = None
        self.current_unsupported = False
        self.iframe = False
        self.blocks = []
        self.feed(text)
        if self.articles != 1 or self.depth or self.current is not None or self.iframe:
            raise ValueError('Prose inactives require one complete article DOM')

    def handle_starttag(self, tag, attrs):
        if tag == 'article':
            self.articles += 1
            self.depth += 1
        if not self.depth:
            return
        if self.iframe:
            raise ValueError('Unexpected content inside inactive article iframe')
        if tag in ('script', 'style', 'template'):
            self.hidden += 1
        if self.hidden:
            return
        if tag == 'p':
            if self.current is not None:
                raise ValueError('Nested inactive paragraphs are ambiguous')
            self.current = []
            self.current_unsupported = False
        elif tag == 'br' and self.current is not None:
            self.current.append('\n')
        elif tag in ('ul', 'ol', 'table', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            # Such a block after the heading cannot silently disappear while
            # treating the following paragraphs as the whole inactive list.
            self.blocks.append(None)
        elif tag in ('img', 'svg', 'iframe', 'object', 'canvas', 'picture',
                     'video', 'audio', 'embed', 'input', 'select', 'textarea',
                     'button', 'meter', 'progress', 'math'):
            # A text-only inventory cannot establish whether visible media or
            # controls contain more list entries. Do not silently omit them.
            if self.current is None:
                known_form = (tag == 'iframe' and len(attrs) == len(_CHARGERS_FORM)
                              and dict(attrs) == _CHARGERS_FORM)
                self.blocks.append(_FORM_BLOCK if known_form else None)
            else:
                self.current_unsupported = True
            if tag == 'iframe':
                self.iframe = True

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if self.iframe:
            if tag != 'iframe':
                raise ValueError('Incomplete inactive article iframe')
            self.iframe = False
            return
        if tag in ('script', 'style', 'template') and self.hidden:
            self.hidden -= 1
            return
        if self.hidden:
            return
        if tag == 'p' and self.current is not None:
            self.blocks.append(None if self.current_unsupported else _lines(''.join(self.current)))
            self.current = None
        elif tag == 'article':
            if self.current is not None:
                raise ValueError('Incomplete inactive paragraph')
            self.depth -= 1

    def handle_data(self, text):
        if self.iframe:
            if text.strip():
                self.blocks.append(None)
            return
        if self.depth and not self.hidden:
            if self.current is not None:
                self.current.append(text)
            elif text.strip():
                self.blocks.append(None)

    def handle_comment(self, text):
        if self.iframe and text.strip():
            self.blocks.append(None)


def _lines(text):
    return [' '.join(line.split()) for line in text.splitlines() if line.strip()]


def _prose_row(line):
    # G/C is an explicit combined source position, not a name or an alias.
    if line.startswith('G/C '):
        row = _row('G ' + line[4:], version=7)
        if row is not None:
            row.update(position='G/C', source_text=line)
        return row
    return _row(line, version=7)


def _check_count(body, headline, heading_start, team, count):
    own = '(?:' + '|'.join(re.escape(name) for name in
           (TEAM_NAMES[team], TEAM_NAMES[team].split()[-1])) + ')'
    counts = [match[1] for match in re.finditer(
        r'(' + _NUMBER + r')\s+(?:' + own + r'\s+)?inactives?\b', headline, re.I)
        if not re.search(r'\bweek\s*$', headline[:match.start()], re.I)]
    prefix = body[:heading_start].rstrip().split('\n\n')[-1]
    counts += re.findall(r'(?:placed|ruled out)\s+(' + _NUMBER + r')\s+players', prefix, re.I)
    counts += re.findall(r'among\s+(' + _NUMBER + r')\s+players deactivated', prefix, re.I)
    declared = {_COUNTS.get(value.casefold(), int(value) if value.isdigit() else None)
                for value in counts}
    if declared and declared != {count}:
        raise ValueError('Declared inactive count does not match the complete list')


def prose_heading(body, team):
    if GENERIC_HEADING in body:
        return GENERIC_HEADING
    heading = 'Here are the ' + TEAM_NAMES[team].split()[-1] + ' inactives:'
    return heading if heading in body and 'This will be updated with ' in body else None


def parse_prose(raw, body, headline, source_team, team, game):
    """Return a complete new-format list, or None for a frozen v7 format."""
    heading = prose_heading(body, team)
    if heading is None:
        return None
    generic = heading == GENERIC_HEADING
    if source_team != team:
        raise ValueError('Prose inactive list belongs only to its source club')
    if body.count(heading) != 1:
        raise ValueError('Duplicate prose inactive heading')
    headings = list(re.finditer(r'(?m)^' + re.escape(heading) + r'[ \t]*$', body))
    if len(headings) != 1:
        raise ValueError('Prose inactive heading is not a standalone paragraph')
    following = body[headings[0].end():].strip()
    footer = None
    if not generic:
        opponent = game['away'] if team == game['home'] else game['home']
        city = TEAM_NAMES[opponent].rsplit(' ', 1)[0]
        footer = "This will be updated with " + city + "'s inactives."
        if following.count(footer) != 1 or not following.endswith(footer):
            raise ValueError('Inactive footer is not the exact terminal opponent notice')
        following = following[:-len(footer)].rstrip()
    lines = _lines(following)
    rows = [_prose_row(line) for line in lines]
    if (not rows or len(rows) > 32 or any(row is None for row in rows)
            or len({row['name'].casefold() for row in rows}) != len(rows)):
        raise ValueError('Incomplete, duplicate or unrecognized prose inactive rows')
    paragraphs = _Paragraphs(raw.decode('utf-8')).blocks
    starts = [index for index, block in enumerate(paragraphs) if block == [heading]]
    if len(starts) != 1:
        raise ValueError('No unique prose inactive heading in article DOM')
    tail = paragraphs[starts[0] + 1:]
    expected = [[line] for line in lines] if generic else [lines, [footer]]
    # This exact saved marketing widget follows the Chargers' terminal notice.
    # Keep it in the inventory; it is never an excuse to omit arbitrary media,
    # text beside the widget, or a form embedded in a player paragraph.
    if (team == 'LAC' and not generic and tail == expected + [_FORM_BLOCK]):
        tail = tail[:-1]
    if tail != expected:
        raise ValueError('Prose inactive rows differ from complete article DOM paragraphs')
    _check_count(body, headline, headings[0].start(), team, len(rows))
    return dict(observations=rows, unparsed_lines=[])
