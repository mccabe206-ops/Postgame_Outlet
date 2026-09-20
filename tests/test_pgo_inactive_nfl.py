import gzip
import json
from pathlib import Path
import re
import tempfile
import unittest

import pgo_inactive_nfl as nfl
import pgo_season_availability as availability


FIXTURE = Path(__file__).parent/'fixtures/pgo_availability_v4_nfl.html'
META = json.loads((FIXTURE.with_suffix('.json')).read_bytes())
RAW = FIXTURE.read_bytes()
URL = META['url']
CAPTURED = META['captured_at']


def game(away, home):
    return dict(game_id=f'2026_01_{away}_{home}',season=2026,week=1,game_type='REG',away=away,home=home,
                kickoff='2026-09-13T17:00:00Z',lock_at='2026-09-13T16:00:00Z')


def article_change(**changes):
    text=RAW.decode('utf-8')
    pattern=re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)',re.S)
    for match in pattern.finditer(text):
        value=json.loads(match[2]); rows=value if isinstance(value,list) else [value]
        target=next((row for row in rows if isinstance(row,dict) and row.get('@type') in ('NewsArticle','Article')
                     and row.get('articleBody')),None)
        if target:
            target.update(changes)
            replacement=match[1]+json.dumps(value,ensure_ascii=False,separators=(',',':'))+match[3]
            return (text[:match.start()]+replacement+text[match.end():]).encode('utf-8')
    raise AssertionError('article JSON-LD not found')


def article_shell(story):
    text=RAW.decode('utf-8')
    pattern=re.compile(r'<script type="application/ld\+json">.*?</script>',re.S)
    script=next(match[0] for match in pattern.finditer(text)
                if 'articleBody' in match[0] and 'NewsArticle' in match[0])
    return (script+'<section data-testid="Story-1" id="Story-1">'+story+'</section>').encode('utf-8')


def card(tiles, link, sections):
    tile_html=''.join(f'<a aria-label="View details for {name}" href="/teams/{name.casefold().replace(" ","-")}"></a>'
                      for name in tiles)
    link_html=f'<a href="{link}">game</a>' if link else ''
    section_html=''.join(f'<h3>{heading}</h3>{middle}<ul>{"".join(f"<li>{row}</li>" for row in rows)}</ul>'
                         for heading,middle,rows in sections)
    return f'<div class="flex flex-col gap-6">{tile_html}{link_html}{section_html}</div>'


class NflInactiveTests(unittest.TestCase):
    def test_retained_actual_story_yields_13_strict_team_lists(self):
        fixtures={
            'ATL':(game('ATL','PIT'),6),'PIT':(game('ATL','PIT'),6),
            'BAL':(game('BAL','IND'),7),'IND':(game('BAL','IND'),6),
            'HOU':(game('BUF','HOU'),6),'CHI':(game('CHI','CAR'),7),'CAR':(game('CHI','CAR'),7),
            'CLE':(game('CLE','JAX'),7),'JAX':(game('CLE','JAX'),6),
            'NO':(game('NO','DET'),7),'DET':(game('NO','DET'),5),
            'NYJ':(game('NYJ','TEN'),5),'TEN':(game('NYJ','TEN'),7),
        }
        for team,(candidate,count) in fixtures.items():
            with self.subTest(team=team):
                self.assertEqual(len(nfl.parse_nfl_full_slate(RAW,URL,candidate,team,CAPTURED)['observations']),count)
        self.assertEqual([r['name'] for r in nfl.parse_nfl_full_slate(
            RAW,URL,game('BAL','IND'),'BAL',CAPTURED)['observations']],
            ['Nnamdi Madubuike','Teddye Buchanan','Devontez Walker','Elijah Sarratt',
             'Chandler Rivers','Emery Jones','Joe Fagnano'])

    def test_malformed_target_and_missing_game_link_fail_without_poisoning_other_cards(self):
        with self.assertRaisesRegex(ValueError,'non-player'):
            nfl.parse_nfl_full_slate(RAW,URL,game('BUF','HOU'),'BUF',CAPTURED)
        self.assertEqual(len(nfl.parse_nfl_full_slate(RAW,URL,game('BUF','HOU'),'HOU',CAPTURED)['observations']),6)
        for team in ('TB','CIN'):
            with self.subTest(team=team), self.assertRaisesRegex(ValueError,'target list'):
                nfl.parse_nfl_full_slate(RAW,URL,game('TB','CIN'),team,CAPTURED)

    def test_exact_url_metadata_and_independent_clocks_fail_closed(self):
        candidate=game('BAL','IND')
        cases=(
            (RAW,URL.replace('week-1-2026','week-2-2026'),CAPTURED),
            (RAW,URL.replace('www.nfl.com','user@www.nfl.com'),CAPTURED),
            (RAW,URL.replace('www.nfl.com','www.nfl.com:443'),CAPTURED),
            (article_change(headline="NFL Week 2 inactives: Players ruled out for Sunday's games"),URL,CAPTURED),
            (article_change(articleBody='NFL inactive reports for every game in Week 1 of the 2025 NFL season.'),URL,CAPTURED),
            (article_change(datePublished=candidate['kickoff'],dateModified=candidate['kickoff']),URL,'2026-09-13T17:00:01Z'),
            (RAW,URL,'2026-09-13T15:46:51Z'),
        )
        for raw,url,captured in cases:
            with self.subTest(url=url,captured=captured), self.assertRaises(ValueError):
                nfl.parse_nfl_full_slate(raw,url,candidate,'BAL',captured)

    def test_card_scope_tiles_immediate_list_and_scripts_are_fail_closed(self):
        candidate=game('BAL','IND'); link=nfl.nfl_game_url(candidate)
        attacks=(
            card(('Baltimore Ravens','Indianapolis Colts'),link,(('COLTS','',('QB First Player',)),))+
            card(('Atlanta Falcons','Pittsburgh Steelers'),None,(('RAVENS','',('QB Leaked Player',)),)),
            card(('Baltimore Ravens','Pittsburgh Steelers'),link,(('RAVENS','',('QB Wrong Tile Player',)),)),
            card(('Baltimore Ravens','Indianapolis Colts'),link,(('RAVENS','<p>prose</p>',('QB Redirected Player',)),)),
            card(('Baltimore Ravens','Indianapolis Colts'),link,(('RAVENS','<div></div>',('QB Wrapped Player',)),)),
            '<script type="text/plain">'+card(('Baltimore Ravens','Indianapolis Colts'),link,
                (('RAVENS','',('QB Script Player',)),))+'</script>',
        )
        for story in attacks:
            with self.subTest(story=story[:80]), self.assertRaises(ValueError):
                nfl.parse_nfl_full_slate(article_shell(story),URL,candidate,'BAL',CAPTURED)

    def test_duplicate_or_nontarget_section_never_fills_target(self):
        candidate=game('BAL','IND'); link=nfl.nfl_game_url(candidate)
        duplicate=card(('Baltimore Ravens','Indianapolis Colts'),link,
                       (('RAVENS','',('QB One Player',)),('RAVENS','',('QB Two Player',))))
        nontarget=card(('Baltimore Ravens','Indianapolis Colts'),link,(('COLTS','',('QB Other Player',)),))
        for story in (duplicate,nontarget):
            with self.assertRaises(ValueError):
                nfl.parse_nfl_full_slate(article_shell(story),URL,candidate,'BAL',CAPTURED)

    def test_v4_generic_discovery_capture_and_offline_replay(self):
        candidate=game('BAL','IND')
        roster=[dict(team='BAL',gsis_id='00-0000001',full_name='Lamar Jackson',position='QB',status='ACT'),
                dict(team='IND',gsis_id='00-0000002',full_name='Anthony Richardson',position='QB',status='ACT')]
        qbs={'BAL':'00-0000001','IND':'00-0000002'}; calls=[]
        def fetch(url):
            calls.append(url)
            if url == availability.REPORT_URL:
                body=b'<title>NFL Injury Report - Week 1 of the 2026 Season</title>'
            elif url == availability.NFL_NEWS_URL:
                body=f'<a href="{URL}">NFL Week 1 inactives: Players ruled out for Sunday games</a>'.encode()
            elif url == URL:
                body=RAW
            else:
                body=b'<html></html>'
            return dict(body=body,status=200,final_url=url)
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'capture'
            result=availability.capture_availability([candidate],roster,qbs,directory,
                now='2026-09-13T15:55:00Z',fetch=fetch)
            self.assertEqual(calls.count(URL),1)
            self.assertEqual(result['parser_version'],5)
            self.assertEqual(len(result['games'][candidate['game_id']]['teams']['BAL']['observations']),7)
            self.assertEqual(result,availability.load_availability(directory))
            saved=json.loads(gzip.decompress((directory/'inputs.json.gz').read_bytes()))
            self.assertEqual(saved['parser_version'],5)


if __name__=='__main__': unittest.main()
