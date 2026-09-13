"""Bounded structured club-list extraction; source and clock admission is external."""

import html
import re

import generate_site


TEAM_NAMES = {value[0]: name for name, value in generate_site.TEAM.items()}
POSITIONS = 'QB RB FB WR TE OL C G T OG OT DL DT DE NT LB ILB OLB EDGE DB CB S FS SS K P LS'.split()
_POSITION = '(?:' + '|'.join(sorted(POSITIONS,key=len,reverse=True)) + ')'
_NAME = r"[A-Z][A-Za-z.'\u2019-]*(?:\s+(?:[A-Z][A-Za-z.'\u2019-]*|de|van|von)){1,5}"
_COUNTS = dict(zip('one two three four five six seven eight nine ten'.split(),range(1,11)))
_NUMBER = r'(?:\d{1,2}|' + '|'.join(_COUNTS) + ')'
_ENGLISH_POSITIONS = {'tight end':'TE','quarterback':'QB','running back':'RB','tackle':'T',
                     'defensive lineman':'DL','cornerback':'CB','safety':'S','linebacker':'LB',
                     'defensive tackle':'DT','offensive lineman':'OL','defensive end':'DE'}


def _row(line):
    source_text = line
    line = re.sub(r'^(?:No\.\s*)?\d{1,3}\s+','',line,flags=re.I)
    for label,code in _ENGLISH_POSITIONS.items():
        line = re.sub('^' + label + r'\s+',code+' ',line,flags=re.I)
    match = re.fullmatch(r'(' + _POSITION + r')\s+(' + _NAME + r')(?:\s*\(([^()]*)\))?',line,re.I)
    if match:
        position,name,note = match.groups()
    else:
        match = re.fullmatch(r'(' + _NAME + r')\s*\((' + _POSITION + r')\s+No\.\s*\d{1,3}\)',line,re.I)
        if not match:
            return None
        name,position = match.groups(); note = ''
    # Case-insensitive position matching must not turn narrative into a name.
    if not re.fullmatch(_NAME,name):
        return None
    position = position.upper(); note = note or ''
    return dict(name=name,position=position,designation_note=note,source_text=source_text,
                status='EMERGENCY_QB' if position == 'QB' and ('emergency' in note.casefold() or re.search(r'3\s*QB|3rd QB|third QB',note,re.I)) else 'INACTIVE')


def is_player_row(text):
    """Whether a complete DOM list item is an observed structured player row."""
    return isinstance(text,str) and _row(text) is not None


def parse_club_body(body, headline, source_team, team, game):
    """Return one complete explicit club list, or reject unsupported/ambiguous text.

    This supplies rows only. The caller must bind the official club source,
    matchup, and actual publication/modification/capture clocks separately.
    """
    if team not in TEAM_NAMES or team not in (game['home'],game['away']) or source_team not in (game['home'],game['away']):
        raise ValueError('Inactive club is outside the matchup')
    if not isinstance(body,str) or not isinstance(headline,str):
        raise ValueError('Inactive body and headline must be text')
    body = html.unescape(body).replace('\\n','\n').replace('\xa0',' ')
    own = '(?:' + '|'.join(re.escape(s) for s in (TEAM_NAMES[team],TEAM_NAMES[team].split()[-1])) + ')'
    other = game['away'] if team == game['home'] else game['home']
    opponent = '(?:' + '|'.join(re.escape(s) for s in (TEAM_NAMES[other],TEAM_NAMES[other].split()[-1])) + ')'
    # Some club CMS text glues a full team heading directly to the previous row.
    heading = re.compile(own + r"(?:['\u2019]s?)?(?:\s+inactive(?:s| players)(?:[^:\n]*:)?\s*)?[ \t]*(?=\n|$)",re.I)
    starts = {m.end() for m in heading.finditer(body)}
    generic = re.compile(r'(?<!\w)INACTIVES[ \t]*(?=\n)|listing the following players as INACTIVE[^:\n]*:|placed\s+' + _NUMBER + r'\s+players[^:\n]*inactive list:|ruled out\s+' + _NUMBER + r'\s+players[^:\n]*:',re.I)
    for match in generic.finditer(body) if source_team == team else ():
        line = body[body.rfind('\n',0,match.start())+1:match.start()]
        if not re.fullmatch(r'\s*' + opponent + r'\s*',line,re.I):
            starts.add(match.end())
    candidates = []
    for start in sorted(starts):
        section = body[start:]
        # A named next-club heading or link closes the current list, even glued.
        boundary = re.search(r'(?:The\s+)?' + opponent + r'(?:\s+inactives(?:\s+here\.)?\s*:?)?[ \t]*(?=\n|$)',section,re.I)
        if boundary:
            section = section[:boundary.start()]
        section = section.split('Bringing you the action:',1)[0]
        lines = [re.sub(r'\s+',' ',s.strip().lstrip('-*\u2022 ').strip()) for s in section.splitlines() if s.strip()]
        if not lines or not _row(lines[0]):
            continue
        rows = []
        for line in lines:
            row = _row(line)
            if row:
                rows.append(row); continue
            if (re.search(r'\b(?:elevated|practice squad|download)\b',line,re.I)
                    or re.match(r"\\?Editor's Note:",line,re.I)
                    or re.search(r'\b(?:was ruled out|are out due to injury)\b',line,re.I)
                    or (line.endswith(('.', '!', '?')) and ',' in line
                        and re.search(r'\b(?:who|was|is|are|will|has|have)\b',line))):
                break
            raise ValueError('Unrecognized line inside an inactive list')
        if not rows or len(rows)>32 or len({r['name'].casefold() for r in rows}) != len(rows):
            raise ValueError('Missing, oversized or duplicate inactive list')
        prefix = body[:start].rstrip().split('\n\n')[-1]
        counts = [match[1] for match in re.finditer(r'(' + _NUMBER + r')\s+(?:' + own + r'\s+)?inactives?\b',headline,re.I)
                  if not re.search(r'\bweek\s*$',headline[:match.start()],re.I)] if source_team == team else []
        counts += re.findall(r'(?:placed|ruled out)\s+(' + _NUMBER + r')\s+players',prefix,re.I) if source_team == team else []
        counts += re.findall(r'among\s+(' + _NUMBER + r')\s+players deactivated',prefix,re.I) if source_team == team else []
        declared = {_COUNTS.get(n.casefold(),int(n) if n.isdigit() else None) for n in counts}
        if declared and declared != {len(rows)}:
            raise ValueError('Declared inactive count does not match the complete list')
        candidates.append(rows)
    # Different headings can end at the same place; identical row lists are one.
    unique = {tuple((r['name'],r['position'],r['status']) for r in rows):rows for rows in candidates}
    if len(unique) != 1:
        raise ValueError('No unique complete structured inactive club list')
    return dict(observations=next(iter(unique.values())),unparsed_lines=[])
