"""Strict parser for the canonical NFL full-slate inactive article."""

from datetime import timedelta
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit

import generate_site
from pgo_inactive_club import _row, is_player_row
from pgo_season_availability import _Page, _utc


TEAM_NAMES = {value[0]: name for name, value in generate_site.TEAM.items()}


def nfl_game_url(game):
    nick = lambda team: TEAM_NAMES[team].split()[-1].lower()
    return f'https://www.nfl.com/games/{nick(game["away"])}-at-{nick(game["home"])}-{game["season"]}-reg-{game["week"]}'


def is_nfl_full_slate_url(url, game):
    parsed = urlsplit(url)
    expected = f'/news/inactive-reports-sunday-week-{game["week"]}-{game["season"]}-nfl-season'
    return (parsed.scheme == 'https' and parsed.netloc in ('nfl.com','www.nfl.com')
            and parsed.path.rstrip('/') == expected and not parsed.query and not parsed.fragment)


class _Cards(HTMLParser):
    def __init__(self, text, game, target):
        super().__init__(convert_charrefs=True)
        self.expected_url = nfl_game_url(game)
        self.expected_tiles = tuple(
            (team, '/teams/' + TEAM_NAMES[team].casefold().replace(' ', '-'))
            for team in (game['away'], game['home']))
        self.target = target
        self.story_depth = 0
        self.div_depth = 0
        self.card = self.heading = self.item = None
        self.sections = []
        self.errors = []
        self.teams = {TEAM_NAMES[t].casefold():t for t in (game['home'],game['away'])}
        self.teams.update({TEAM_NAMES[t].split()[-1].casefold():t for t in (game['home'],game['away'])})
        self.all_teams = {TEAM_NAMES[t].casefold():t for t in TEAM_NAMES}
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'section':
            if self.story_depth:
                self.story_depth += 1
            elif attrs.get('id') == 'Story-1' and attrs.get('data-testid') == 'Story-1':
                self.story_depth = 1
        if not self.story_depth:
            return
        if self.card is not None and self.card['pending']:
            if tag == 'ul':
                self.card['pending'], self.card['active'], self.card['rows'] = False, True, []
            else:
                self.card['pending'] = False
                self.card['error'] = 'NFL full-slate target heading is not followed immediately by its list'
        if tag == 'div':
            self.div_depth += 1
            if self.card is None and set(attrs.get('class','').split()) == {'flex','flex-col','gap-6'}:
                self.card = dict(depth=self.div_depth,tiles=[],links=[],pending=False,active=False,
                                 rows=[],lists=[],error=None)
            return
        if self.card is None:
            return
        href = attrs.get('href','')
        label = attrs.get('aria-label','')
        if tag == 'a' and label.startswith('View details for '):
            name = label.removeprefix('View details for ').strip().casefold()
            self.card['tiles'].append((self.all_teams.get(name),href.rstrip('/')))
        if tag == 'a' and re.search(r'(?:https://www\.nfl\.com)?/games/[^/?#]+-reg-\d+/?$',href):
            self.card['links'].append(href.rstrip('/'))
        if tag == 'h3':
            self.heading = []
        elif tag == 'li' and self.card['active']:
            self.item = []

    def handle_data(self, data):
        if not self.story_depth:
            return
        if self.card is not None and self.card['pending'] and data.strip():
            self.card['pending'] = False
            self.card['error'] = 'NFL full-slate target heading is not followed immediately by its list'
        if self.heading is not None:
            self.heading.append(data)
        if self.item is not None:
            self.item.append(data)

    def handle_endtag(self, tag):
        if not self.story_depth:
            return
        if tag == 'h3' and self.heading is not None:
            label = ' '.join(''.join(self.heading).split()).casefold()
            candidate = self.teams.get(label)
            if candidate == self.target:
                if self.card['lists'] or self.card['pending'] or self.card['active']:
                    self.card['error'] = 'NFL full-slate team section is duplicate'
                self.card['pending'] = True
            self.heading = None
        elif tag == 'li' and self.item is not None:
            text = ' '.join(''.join(self.item).split())
            if not is_player_row(text):
                self.card['error'] = 'NFL full-slate list contains a non-player row'
            else:
                self.card['rows'].append(_row(text))
            self.item = None
        elif tag == 'ul' and self.card is not None and self.card['active']:
            rows = self.card['rows']
            if not rows or len(rows) > 32:
                self.card['error'] = 'NFL full-slate team section is empty or oversized'
            elif len({row['name'].casefold() for row in rows}) != len(rows):
                self.card['error'] = 'NFL full-slate team section has duplicate players'
            self.card['lists'].append(rows)
            self.card['active'], self.card['rows'] = False, []
        if tag == 'div':
            if self.card is not None and self.card['depth'] == self.div_depth:
                self._finish_card()
            self.div_depth -= 1
        if tag == 'section':
            self.story_depth -= 1

    def _finish_card(self):
        card, self.card = self.card, None
        exact_tiles = tuple(card['tiles']) == self.expected_tiles
        exact_link = card['links'] == [self.expected_url]
        if not (exact_tiles and exact_link):
            return
        if card['pending'] or card['active']:
            card['error'] = card['error'] or 'NFL full-slate target list is incomplete'
        if card['error']:
            self.errors.append(card['error'])
        elif len(card['lists']) == 1:
            self.sections.append(card['lists'][0])
        elif len(card['lists']) > 1:
            self.errors.append('NFL full-slate team section is duplicate')


def parse_nfl_full_slate(raw, url, game, team, captured_at):
    """Return an existing-shape parsed list from one exact NFL matchup card."""
    if team not in (game['home'],game['away']):
        raise ValueError('Target team is outside the matchup')
    if not is_nfl_full_slate_url(url,game):
        raise ValueError('NFL full-slate URL does not bind the season and week')
    text = raw.decode('utf-8')
    articles = []
    for script in _Page(text.split('<article',1)[0]).scripts:
        value = json.loads(script)
        for item in value if isinstance(value,list) else [value]:
            if isinstance(item,dict) and item.get('@type') in ('NewsArticle','Article') and item.get('articleBody'):
                articles.append(item)
    if len(articles) != 1:
        raise ValueError('No unique NFL full-slate article metadata')
    article = articles[0]
    headline = article.get('headline','')
    weeks = {int(n) for n in re.findall(r'\bweek\s+(\d{1,2})\b',headline,re.I)}
    seasons = {int(n) for n in re.findall(r'(?<!\d)(20\d{2})(?!\d)',headline)}
    if (not re.search(r'\binactive(?:s)?\b',headline,re.I) or weeks != {game['week']}
            or (seasons and seasons != {game['season']})):
        raise ValueError('NFL full-slate headline conflicts with the season or week')
    intro = article['articleBody']
    intro_weeks = {int(n) for n in re.findall(r'\bweek\s+(\d{1,2})\b',intro,re.I)}
    intro_seasons = {int(n) for n in re.findall(r'(?<!\d)(20\d{2})(?!\d)',intro)}
    if intro_weeks != {game['week']} or intro_seasons != {game['season']}:
        raise ValueError('NFL full-slate introduction conflicts with the season or week')
    published = _utc(article['datePublished'])
    modified = _utc(article.get('dateModified',article['datePublished']))
    kickoff, captured = _utc(game['kickoff']), _utc(captured_at)
    lower = kickoff-timedelta(hours=24)
    if not (lower <= published < kickoff and published <= captured
            and lower <= modified < kickoff and modified <= captured):
        raise ValueError('NFL full-slate clocks are outside the capture window')
    cards = _Cards(text,game,team)
    if cards.errors:
        raise ValueError(cards.errors[0])
    if len(cards.sections) != 1:
        raise ValueError('No unique complete target list in the NFL matchup card')
    return dict(observations=cards.sections[0],unparsed_lines=[],headline=headline,
                published_at=published.isoformat(),modified_at=modified.isoformat())
