import gzip
import hashlib
import json
from pathlib import Path
import unittest

import pgo_inactive_nfl as nfl
import pgo_season_availability as availability
import pgo_inactive_club as club

FIXTURE = Path(__file__).parent/'fixtures/pgo_availability_v5_nfl.html.gz'
RAW = gzip.decompress(FIXTURE.read_bytes())
META = json.loads(FIXTURE.with_suffix('').with_suffix('.json').read_bytes())


def game(away,home):
    return dict(away=away,home=home,season=2026,week=2,kickoff='2026-09-20T17:00:00Z')


def parse(raw=RAW, candidate=None, team='MIN', version=5, url=None, captured=None):
    return availability.parse_final_inactives(raw,candidate or game('MIN','CHI'),team,
        captured or META['captured_at'],parser_version=version,source_url=url or META['url'])


class InactiveV5Tests(unittest.TestCase):
    def test_exact_current_official_lists(self):
        self.assertEqual(hashlib.sha256(RAW).hexdigest(),META['sha256'])
        for away,home,counts in [('NO','BAL',(7,6)),('MIN','CHI',(7,5)),('CIN','HOU',(7,7)),('PHI','TEN',(5,6))]:
            for team,count in zip((away,home),counts):
                with self.subTest(team=team):
                    self.assertEqual(len(parse(candidate=game(away,home),team=team)['observations']),count)

    def test_actual_malformed_and_wrong_game_links_remain_rejected(self):
        for away,home in [('CAR','ATL'),('CLE','TB')]:
            for team in (away,home):
                with self.subTest(team=team),self.assertRaises(ValueError):
                    parse(candidate=game(away,home),team=team)

    def test_untrusted_structure_cannot_supply_or_truncate_list(self):
        replacements = [
            (b'<li>QB Kyler Murray</li>',b'<li>QB Kyler Murray<ul><li>QB Max Brosmer</li></ul></li>'),
            (b'<li>QB Kyler Murray</li>',b'<li>Unknown row</li>'),
            (b'<h3>VIKINGS</h3>',b'<h3>BEARS</h3>'),
            (b'<h3>VIKINGS</h3>',b'<ul><li>QB Max Brosmer</li></ul><h3>VIKINGS</h3>'),
            (b'https://www.nfl.com/games/vikings-at-bears-2026-reg-2',b'https://www.nfl.com/games/vikings-at-bears-2026-reg-1'),
            (b'<h3>VIKINGS</h3>',b'<p>Unrelated content</p><h3>VIKINGS</h3>'),
        ]
        for old,new in replacements:
            with self.subTest(new=new),self.assertRaises(ValueError):
                self.assertIn(old,RAW)
                parse(RAW.replace(old,new))

    def test_period_capture_url_and_legacy_gates(self):
        for kwargs in [dict(version=4),dict(url=META['url'].replace('week-2','week-1')),
                       dict(captured='2026-09-20T15:00:00Z'),dict(team='ATL')]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                parse(**kwargs)
        from tests.test_pgo_inactive_nfl import RAW as old_raw,URL as old_url,CAPTURED,game as old_game
        for version in (4,5):
            self.assertEqual(availability.parse_final_inactives(old_raw,old_game('BAL','IND'),'BAL',CAPTURED,
                parser_version=version,source_url=old_url),nfl.parse_nfl_full_slate(old_raw,old_url,old_game('BAL','IND'),'BAL',CAPTURED))

    def test_singular_footer_is_only_new_version_and_names_existing_row(self):
        candidate=game('CLE','TB')
        body='BUCCANEERS INACTIVES\nCB Jacob Parrish\nG Billy Schrauth\nParrish is out due to injury.'
        self.assertEqual(len(club.parse_club_body(body,'Browns Buccaneers Week 2 inactives','TB','TB',candidate,version=5)['observations']),2)
        for version,article in [(3,body),(5,body.replace('Parrish is','Unknown is'))]:
            with self.assertRaises(ValueError):
                club.parse_club_body(article,'Browns Buccaneers Week 2 inactives','TB','TB',candidate,version=version)

    def test_complete_alternate_never_erases_resolved_club_qb_fact(self):
        from unittest.mock import patch
        from tests.test_pgo_season_availability import SeasonAvailabilityTests
        fixture=SeasonAvailabilityTests(); fixture.setUp()
        own=fixture.source('club',kind='official_inactives',team='NE',url='https://www.patriots.com/news/inactives')
        league=fixture.source('league',kind='official_inactives',url='https://www.nfl.com/news/inactives')
        row=lambda name,pos,status:dict(name=name,position=pos,status=status)
        receiver=row('Efton Receiver','WR','INACTIVE')
        qb=row('Alex Quarterback','QB','EMERGENCY_QB')
        for own_rows,league_rows,partial,expected in [
                ([receiver],[receiver],True,'VERIFIED_LIST'),
                ([receiver,qb],[receiver],True,'PARTIAL'),
                ([receiver,qb],[receiver,qb],True,'VERIFIED_LIST'),
                ([receiver],[row('Unknown Person','WR','INACTIVE')],True,'PARTIAL')]:
            def parsed(raw,game,team,captured,**kwargs):
                if team!='NE': raise ValueError('other team')
                return dict(observations=own_rows if raw==b'club' else league_rows,
                    unparsed_lines=['malformed club row'] if raw==b'club' and partial else [],
                    published_at=fixture.now,modified_at=fixture.now,headline='inactives')
            with self.subTest(own_rows=own_rows,league_rows=league_rows),patch.object(availability,'parse_final_inactives',side_effect=parsed):
                result=availability.build_availability([fixture.game],fixture.roster,fixture.qbs,[own,league],checked_at=fixture.now,parser_version=5)
                self.assertEqual(result['games'][fixture.game['game_id']]['teams']['NE']['final_inactives_status'],expected)

    def test_pinned_real_context_repairs_preserve_unresolved_identities(self):
        base=Path(__file__).resolve().parents[1]/'docs/evidence/season-2026/availability-v2/20260920T154557557012Z'
        old=availability.load_availability(base)
        capture=json.loads((base/'capture.json').read_bytes())
        inputs=json.loads(gzip.decompress((base/'inputs.json.gz').read_bytes()))
        inputs.update(parser_version=5,purpose='context')
        sources=[dict(source,body=gzip.decompress((base/source['file']).read_bytes())) if 'file' in source else source for source in capture['sources']]
        sources.append(dict(kind='official_inactives',team=None,url=META['url'],final_url=META['url'],
            started_at=META['captured_at'],captured_at=META['captured_at'],status=200,body=RAW))
        result=availability.build_availability(**inputs,sources=sources,checked_at=META['captured_at'])
        teams={t:v for g in result['games'].values() for t,v in g['teams'].items()}
        for team in ('TB','MIN','CHI','PHI','BAL'):
            self.assertEqual(teams[team]['final_inactives_status'],'VERIFIED_LIST',team)
        for team,name in [('CAR','Pat Jones'),('HOU','Nate Thomas'),('TEN','Cor\u2019Dale Flott')]:
            self.assertEqual(teams[team]['final_inactives_status'],'PARTIAL',team)
            self.assertIn(name,[r['name'] for r in teams[team]['observations'] if r['identity_status']=='UNRESOLVED'])
        self.assertEqual(old['parser_version'],4)

    def test_baltimore_category_and_dom_boundaries_keep_period_and_clock_guards(self):
        base=Path(__file__).resolve().parents[1]/'docs/evidence/season-2026/availability-v2/20260920T154557557012Z'
        capture=json.loads((base/'capture.json').read_bytes())
        source=next(s for s in capture['sources'] if s.get('team')=='BAL' and s['kind']=='official_inactives')
        raw=gzip.decompress((base/source['file']).read_bytes())
        candidate=game('NO','BAL')
        def read(payload,version=5):
            return availability.parse_final_inactives(payload,candidate,'BAL',source['captured_at'],parser_version=version,source_team='BAL',source_url=source['url'])
        result=read(raw)
        self.assertEqual(len(result['observations']),6)
        self.assertIn('Andrew Vorhees',[r['name'] for r in result['observations']])
        with self.assertRaises(ValueError): read(raw,4)
        with self.assertRaises(ValueError): read(raw+b'<ul><li>WR Zay Flowers</li></ul>')
        import re
        with self.assertRaises(ValueError): read(re.sub(rb'<(/?)li\b',rb'<\1span',raw))
        text=raw.decode()
        for script in availability._Page(text.split('<article',1)[0]).scripts:
            value=json.loads(script)
            if isinstance(value,dict) and value.get('articleBody'):
                original=value
                break
        else: self.fail('missing article')
        for changes in [dict(articleSection='News'),dict(headline='Week 1 Ravens Saints Inactives'),
                        dict(headline='Week 2 Cardinals Seahawks Inactives'),
                        dict(dateModified='2026-09-20T16:59:00Z')]:
            changed=dict(original,**changes)
            payload=text.replace(script,json.dumps(changed)).encode()
            with self.subTest(changes=changes),self.assertRaises(ValueError): read(payload)
