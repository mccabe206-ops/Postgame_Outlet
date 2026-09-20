import copy
import importlib.util
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import timedelta


SPEC = importlib.util.find_spec('pgo_season_availability')
if SPEC:
    import pgo_season_availability as availability


class SeasonAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(SPEC, 'The season availability module must exist')
        self.game = dict(game_id='2026_02_NE_SEA', season=2026, week=2, game_type='REG',
                         home='SEA', away='NE', kickoff='2026-09-20T17:00:00Z', lock_at='2026-09-20T16:00:00Z')
        self.now = '2026-09-20T15:40:00Z'
        self.roster = [dict(team='NE',gsis_id='00-0000001',full_name='Alex Quarterback',position='QB',status='ACT'),
                       dict(team='SEA',gsis_id='00-0000002',full_name='Sam Quarterback',position='QB',status='ACT'),
                       dict(team='NE',gsis_id='00-0000003',full_name='Efton Receiver III',position='WR',status='ACT')]
        self.qbs = {'NE':'00-0000001','SEA':'00-0000002'}

    def report(self, *, week=2, status='Out', name='Alex Quarterback'):
        return ('<title>NFL Injury Report - Week '+str(week)+' of the 2026 Season</title>'
                '<h2 class="d3-o-section-sub-title"><span>Patriots</span></h2><table>'
                '<tr><th>Player</th><th>Position</th><th>Injuries</th><th>Practice Status</th><th>Game Status</th></tr>'
                '<tr><td>'+name+'</td><td>QB</td><td>Knee</td><td>Did Not Participate</td><td>'+status+'</td></tr></table>')

    def article(self, *, published='2026-09-20T15:30:00Z', body=None, headline=None):
        return '<script type="application/ld+json">'+json.dumps(dict(
            **{'@type':'NewsArticle'}, datePublished=published, dateModified=published,
            headline=headline or 'Week 2 Inactives: Patriots at Seahawks',
            articleBody=body or 'NEW ENGLAND PATRIOTS INACTIVESWR Efton Receiver\nQB Alex Quarterback (emergency third quarterback)'))+'</script>'

    def source(self, raw, *, kind='official_report', team=None, url=None):
        return dict(kind=kind,team=team,url=url or availability.REPORT_URL,
                    final_url=url or availability.REPORT_URL,status=200,
                    started_at=self.now,captured_at=self.now,body=raw.encode())

    def build(self, sources):
        return availability.build_availability([self.game],self.roster,self.qbs,sources,checked_at=self.now)

    def test_formal_qb_out_blocks_without_turning_missing_reports_into_healthy(self):
        result=self.build([self.source(self.report())])['games'][self.game['game_id']]
        self.assertEqual(result['qb_gate'],'BLOCKED_EXPECTED_QB_UNAVAILABLE')
        self.assertIn('Alex Quarterback',result['blocked_reason'])
        self.assertEqual(result['teams']['SEA']['report_status'],'UNKNOWN')
        self.assertEqual(result['teams']['SEA']['expected_qb_status'],'UNKNOWN')
        self.assertNotIn('rating',json.dumps(result))

    def test_practice_only_and_stale_week_never_confirm_absence(self):
        for raw in (self.report(status=''),self.report(week=1)):
            result=self.build([self.source(raw)])['games'][self.game['game_id']]
            self.assertEqual(result['qb_gate'],'CONDITIONAL')
            self.assertEqual(result['teams']['NE']['expected_qb_status'],'UNKNOWN')

    def test_official_inactives_preserve_emergency_language_and_resolve_unique_suffix_alias(self):
        source=self.source(self.article(),kind='official_inactives',team='NE',url='https://www.patriots.com/news/week-2-inactives')
        game=self.build([source])['games'][self.game['game_id']]
        team=game['teams']['NE']
        self.assertEqual(team['final_inactives_status'],'VERIFIED_LIST')
        self.assertEqual({o['gsis_id'] for o in team['observations']},{'00-0000001','00-0000003'})
        self.assertEqual(team['expected_qb_status'],'EMERGENCY_QB')
        self.assertIn('emergency third quarterback',json.dumps(team))
        self.assertEqual(game['qb_gate'],'BLOCKED_EXPECTED_QB_UNAVAILABLE')

    def test_future_or_other_matchup_article_is_not_admitted(self):
        for raw in (self.article(published='2026-09-20T17:40:00Z'),
                    self.article(headline='Week 2 Inactives: Patriots at Bills'),
                    self.article(headline='Week 1 Inactives: Patriots at Seahawks')):
            source=self.source(raw,kind='official_inactives',team='NE',url='https://www.patriots.com/news/inactives')
            game=self.build([source])['games'][self.game['game_id']]
            self.assertEqual(game['qb_gate'],'CONDITIONAL')
            self.assertEqual(game['teams']['NE']['final_inactives_status'],'UNKNOWN')
            self.assertTrue(game['teams']['NE']['source_errors'])

    def test_unknown_name_stays_unpriced_and_partial(self):
        source=self.source(self.article(body='NEW ENGLAND PATRIOTS INACTIVESWR Unknown Receiver'),kind='official_inactives',team='NE',url='https://www.patriots.com/news/inactives')
        team=self.build([source])['games'][self.game['game_id']]['teams']['NE']
        self.assertEqual(team['final_inactives_status'],'PARTIAL')
        self.assertIsNone(team['observations'][0]['gsis_id'])
        self.assertEqual(team['observations'][0]['identity_status'],'UNRESOLVED')

    def test_invalid_game_roster_source_or_clock_rejected(self):
        cases=[]
        roster=copy.deepcopy(self.roster);roster.append(roster[0]);cases.append((self.game,roster,self.now,[]))
        game={**self.game,'lock_at':'2026-09-20T16:30:00Z'};cases.append((game,self.roster,self.now,[]))
        cases.append((self.game,self.roster,'2026-09-20T16:00:00Z',[]))
        source=self.source(self.report());source['captured_at']='2026-09-20T15:41:00Z';cases.append((self.game,self.roster,self.now,[source]))
        source=self.source(self.report());source['url']='https://evil.example/injuries';cases.append((self.game,self.roster,self.now,[source]))
        for game,roster,now,sources in cases:
            with self.subTest(game=game,now=now,sources=sources), self.assertRaises(ValueError):
                availability.build_availability([game],roster,self.qbs,sources,checked_at=now)

    def test_capture_append_only_offline_replay_and_hash_tamper(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            raw=(self.report(status='Questionable') if url==availability.REPORT_URL else
                 self.article() if 'week-2-inactives' in url else
                 '<a href="/news/week-2-inactives-patriots-at-seahawks">Week 2 Inactives: Patriots at Seahawks</a>' if 'patriots.com' in url else '<html></html>')
            return {'body':raw.encode(),'status':200,'final_url':url}
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'capture'
            result=availability.capture_availability([self.game],self.roster,self.qbs,directory,now=self.now,fetch=fetch)
            self.assertEqual(calls.count(availability.REPORT_URL),1)
            self.assertEqual(result,availability.load_availability(directory))
            with self.assertRaises(FileExistsError):
                availability.capture_availability([self.game],self.roster,self.qbs,directory,now=self.now,fetch=fetch)
            raw=next((directory/'raw').iterdir());raw.write_bytes(raw.read_bytes()+b'x')
            with self.assertRaises(ValueError):availability.load_availability(directory)

    def test_current_matchup_link_beats_four_old_or_wrong_links_and_untrusted_link(self):
        actual='https://www.patriots.com/news/2026-week-2-inactives-patriots-at-seahawks'
        skipped={
            'https://www.patriots.com/news/2025-week-2-inactives-patriots-at-seahawks',
            'https://www.patriots.com/news/2026-week-1-inactives-patriots-at-seahawks',
            'https://www.patriots.com/news/2026-week-2-inactives-patriots-at-bills',
        }
        homepage=''.join([
            '<a href="/news/2025-week-2-inactives-patriots-at-seahawks">2025 Week 2 Inactives: Patriots at Seahawks</a>',
            '<a href="/news/2026-week-1-inactives-patriots-at-seahawks">2026 Week 1 Inactives: Patriots at Seahawks</a>',
            '<a href="/news/2026-week-2-inactives-patriots-at-bills">2026 Week 2 Inactives: Patriots at Bills</a>',
            '<a href="/news/inactives-archive">Patriots inactives archive</a>',
            f'<a href="{actual}">2026 Week 2 Inactives: Patriots at Seahawks</a>',
            '<a href="https://evil.example/news/2026-week-2-inactives-patriots-at-seahawks">Inactives: Patriots at Seahawks</a>',
        ])
        calls=[]
        def fetch(url):
            calls.append(url)
            raw=(self.report(status='Questionable') if url==availability.REPORT_URL else
                 homepage if url=='https://www.patriots.com/news/' else
                 self.article() if url==actual else
                 self.article(headline='Week 2 Inactives: Patriots at Bills')
                 if url.startswith('https://www.patriots.com/news/') else '<html></html>')
            return {'body':raw.encode(),'status':200,'final_url':url}
        with tempfile.TemporaryDirectory() as tmp:
            out=availability.capture_availability([self.game],self.roster,self.qbs,
                Path(tmp)/'capture',now=self.now,fetch=fetch)
        self.assertIn(actual,calls)
        self.assertTrue(skipped.isdisjoint(calls))
        self.assertNotIn('https://evil.example/news/2026-week-2-inactives-patriots-at-seahawks',calls)
        self.assertLessEqual(sum(url.startswith('https://www.patriots.com/news/')
                                 and url != 'https://www.patriots.com/news/' for url in calls),4)
        self.assertEqual(out['games'][self.game['game_id']]['teams']['NE']['final_inactives_status'],
                         'VERIFIED_LIST')

    def test_generic_official_team_inactive_link_remains_a_fallback(self):
        article='https://www.patriots.com/news/inactives-roster-update'
        calls=[]
        def fetch(url):
            calls.append(url)
            raw=(self.report(status='Questionable') if url==availability.REPORT_URL else
                 '<a href="/news/inactives-roster-update">Patriots inactives</a>'
                 if url=='https://www.patriots.com/news/' else
                 self.article() if url==article else '<html></html>')
            return {'body':raw.encode(),'status':200,'final_url':url}
        with tempfile.TemporaryDirectory() as tmp:
            out=availability.capture_availability([self.game],self.roster,self.qbs,
                Path(tmp)/'capture',now=self.now,fetch=fetch)
        self.assertIn(article,calls)
        self.assertEqual(out['games'][self.game['game_id']]['teams']['NE']['final_inactives_status'],
                         'VERIFIED_LIST')

    def test_club_links_matching_another_slate_game_do_not_outrank_own_fallback(self):
        other=dict(self.game,game_id='2026_02_ATL_BUF',home='BUF',away='ATL')
        roster=self.roster+[
            dict(team='ATL',gsis_id='00-0000004',full_name='Atlanta Quarterback',position='QB',status='ACT'),
            dict(team='BUF',gsis_id='00-0000005',full_name='Buffalo Quarterback',position='QB',status='ACT'),
        ]
        qbs={**self.qbs,'ATL':'00-0000004','BUF':'00-0000005'}
        generic='https://www.patriots.com/news/inactives-roster-update'
        wrong=[f'https://www.patriots.com/news/week-2-inactives-falcons-at-bills-{i}' for i in range(4)]
        homepage=''.join(f'<a href="{url}">Week 2 Inactives: Falcons at Bills</a>' for url in wrong)
        homepage+='<a href="/news/inactives-roster-update">Patriots inactives</a>'
        calls=[]
        def fetch(url):
            calls.append(url)
            raw=(self.report(status='Questionable') if url==availability.REPORT_URL else
                 homepage if url=='https://www.patriots.com/news/' else
                 self.article() if url==generic else '<html></html>')
            return {'body':raw.encode(),'status':200,'final_url':url}
        with tempfile.TemporaryDirectory() as tmp:
            out=availability.capture_availability([self.game,other],roster,qbs,
                Path(tmp)/'capture',now=self.now,fetch=fetch)
        self.assertIn(generic,calls)
        self.assertTrue(set(wrong).isdisjoint(calls))
        self.assertEqual(out['games'][self.game['game_id']]['teams']['NE']['final_inactives_status'],
                         'VERIFIED_LIST')

    def test_capture_that_crosses_lock_during_write_is_failed_and_unloadable(self):
        clock=[availability._utc(self.now)]
        def fetch(url):
            return {'body':self.report(status='').encode() if url==availability.REPORT_URL else b'<html></html>',
                    'status':200,'final_url':url}
        write=availability._write
        def slow_write(path,raw):
            write(path,raw)
            if path.name=='manifest.json':clock[0]=availability._utc(self.game['lock_at'])
        with tempfile.TemporaryDirectory() as tmp, patch.object(availability,'_clock',side_effect=lambda now=None:clock[0]), patch.object(availability,'_write',side_effect=slow_write):
            directory=Path(tmp)/'capture'
            with self.assertRaisesRegex(ValueError,'T-60'):
                availability.capture_availability([self.game],self.roster,self.qbs,directory,fetch=fetch)
            self.assertTrue((directory/'failure.json').exists())
            with self.assertRaisesRegex(ValueError,'failed'):availability.load_availability(directory)

    def test_loader_rejects_windows_drive_paths_even_with_valid_other_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/'manifest.json').write_text(json.dumps({'schema_version':1,'members':[{'file':'C:/outside.json','bytes':0,'sha256':'0'*64}]}))
            with self.assertRaisesRegex(ValueError,'member'):
                availability.load_availability(directory)

    def test_duplicate_report_identity_and_invalid_gsis_rejected(self):
        raw=self.report()
        player=raw.split('<tr><td>',1)[1].split('</tr>',1)[0]
        duplicate=raw.replace('</table>','<tr><td>'+player+'</tr></table>')
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            self.build([self.source(duplicate)])
        self.roster[0]['gsis_id']='not-a-gsis-id';self.qbs['NE']='not-a-gsis-id'
        with self.assertRaisesRegex(ValueError,'GSIS'):
            self.build([])

    def test_structured_mascot_header_is_bound_to_the_club_and_matchup(self):
        parsed=availability.parse_final_inactives(self.article(body="Patriots' inactives:\nWR Efton Receiver").encode(),self.game,'NE',self.now)
        self.assertEqual([r['name'] for r in parsed['observations']],['Efton Receiver'])

    def test_raw_provider_la_alias_is_normalized_without_mutating_roster(self):
        self.roster.append(dict(team='LA',gsis_id='00-0000004',full_name='Rams Player',position='WR',status='ACT'))
        before=copy.deepcopy(self.roster)
        self.assertEqual(self.build([])['games'][self.game['game_id']]['qb_gate'],'CONDITIONAL')
        self.assertEqual(self.roster,before)

    def test_existing_all_team_source_capture_and_provider_game_ids_replay(self):
        import pgo_sources
        root=Path(__file__).resolve().parents[1]/'docs/evidence/forecast-lab-2026/september-09-postseason'
        snapshot=json.loads((root/'snapshot.json').read_bytes())
        record=next(r for r in json.loads((root/'capture.json').read_bytes())['sources'] if r['file']=='nfl-injuries.html')
        games=[dict(g,lock_at=(availability._utc(g['kickoff'])-timedelta(minutes=60)).isoformat()) for g in snapshot['games']]
        roster=list(pgo_sources.open_csv(root/'roster.csv.gz'))
        qbs={t['team']:t['qb_gsis_id'] for t in snapshot['teams']}
        result=availability.build_availability(games,roster,qbs,[dict(record,kind='official_report',team=None,body=(root/'nfl-injuries.html').read_bytes())],checked_at=snapshot['inputs_as_of'])
        self.assertEqual(set(result['games']),{g['game_id'] for g in games})
        self.assertEqual(len(result['games']),16)
        self.assertEqual(result['games']['2026_01_SF_LA']['home'],'LAR')
        self.assertTrue(all(g['qb_gate']=='CONDITIONAL' for g in result['games'].values()))

    def test_real_saved_club_lists_have_seven_players_each(self):
        root=Path(__file__).resolve().parents[1]
        fixture=root/'research/pgo_defensive_depth_candidate/source-review-20260909/inactives-20260909T225151Z'
        game={**self.game,'game_id':'2026_01_NE_SEA','week':1,'kickoff':'2026-09-10T00:20:00Z','lock_at':'2026-09-09T23:20:00Z'}
        for team,file in [('NE','patriots-inactives.html'),('SEA','seahawks-inactives.html')]:
            parsed=availability.parse_final_inactives((fixture/file).read_bytes(),game,team,'2026-09-09T23:15:00Z')
            self.assertEqual(len(parsed['observations']),7)
            self.assertEqual(parsed['unparsed_lines'],[])
        self.assertIn('emergency third quarterback',json.dumps(parsed))

    def real_sf_lar(self):
        # Exact relevant JSON-LD fields from the September 11 official captures.
        # nfl.html SHA256 5eb2a5d2925862c28e0b9f36a6fcf68f5a2cdc91045173d381199560f057702a
        # 49ers.html SHA256 8d1e991106ea22bb563bd3ddf8c19b948c71ae5e919a0aaebe68786c3d3c6711
        game=dict(game_id='2026_01_SF_LA',season=2026,week=1,game_type='REG',home='LAR',away='SF',
                  kickoff='2026-09-11T00:35:00Z',lock_at='2026-09-10T23:35:00Z')
        nfl=dict(headline='Australia game inactives: San Francisco 49ers at Los Angeles Rams',
                 datePublished='2026-09-10T23:26:21.831Z',dateModified='2026-09-10T23:26:21.831Z',
                 articleBody='WHERE:\u00a0Melbourne\u00a0Cricket\u00a0Ground\u00a0(Melbourne,\u00a0Australia)\n'
                 'WHEN:\u00a08:35 p.m. ET | Netflix, NFL+\n\nNINERS\n\nQB Kurtis Rourke\nCB Ephesians Prysock\n'
                 'RB Jordan James\nWR Jordan Watkins\nLB Tatum Bethune\nOT Enrique Cruz Jr.\n\nRAMS\n\n'
                 'QB\u00a0Ty Simpson (emergency third QB)\nWR CJ Daniels\nWR Tutu Atwell\nOL Bill Murray\nTE Max Klare')
        club=dict(headline='Tatum Bethune, Jordan Watkins OUT vs. Rams; Inactives for Week 1 #SFvsLAR',
                  datePublished='2026-09-10T23:37:43.628Z',dateModified='2026-09-10T23:38:24.546Z',
                  articleBody='The San Francisco 49ers have finalized their inactive list ahead of the Week 1 matchup '
                  'against the Los Angeles Rams at the Melbourne Cricket Ground. With rosters limited to 48 active players '
                  'on gameday, several players will be sidelined for the primetime contest.\n\n'
                  'Earlier in the week, the 49ers ruled out DL Alfred Collins after suffering a torn patellar injury '
                  'during practice in Melbourne. He will be sidelined for the rest of the 2026 season.\n\n'
                  'The 49ers enter Week 1 with several players returning to full participation after working through '
                  'injuries during the week. DL Nick Bosa (knee), TE George Kittle\u00a0(achilles), and FB Kyle Juszczyk '
                  '(finger) did not receive game designations Thursday, and today are available for the season opener. '
                  'DL James Thompson Jr.\u00a0(hamstring), who was listed as questionable on the final injury report, '
                  "is also active for Friday's matchup.\n\n"
                  'Here are the 49ers inactives for Week 1 against the Rams:\n\n\nCB Ephesians Prysock\n'
                  'RB Jordan James\nWR Jordan Watkins\nLB Tatum Bethune\nOL Enrique Cruz Jr.\nQB Kurtis Rourke')
        def raw(article):
            return ('<script type="application/ld+json">'+json.dumps(dict(article,**{'@type':'NewsArticle'}))+'</script>').encode()
        return game,nfl,club,raw

    def test_v2_real_nfl_team_sections_and_49ers_intro(self):
        game,nfl,club,raw=self.real_sf_lar();captured='2026-09-11T00:31:36Z'
        sf=availability.parse_final_inactives(raw(nfl),game,'SF',captured)
        lar=availability.parse_final_inactives(raw(nfl),game,'LAR',captured)
        self.assertEqual([r['name'] for r in sf['observations']],['Kurtis Rourke','Ephesians Prysock','Jordan James','Jordan Watkins','Tatum Bethune','Enrique Cruz Jr.'])
        self.assertEqual([r['name'] for r in lar['observations']],['Ty Simpson','CJ Daniels','Tutu Atwell','Bill Murray','Max Klare'])
        self.assertEqual(lar['observations'][0]['status'],'EMERGENCY_QB')
        self.assertEqual(sf['unparsed_lines'],[]);self.assertEqual(lar['unparsed_lines'],[])
        club_list=availability.parse_final_inactives(raw(club),game,'SF',captured)
        self.assertEqual({r['name'] for r in sf['observations']},{r['name'] for r in club_list['observations']})
        self.assertEqual(club_list['unparsed_lines'],[])
        for article in (nfl,club):
            with self.assertRaises(ValueError):availability.parse_final_inactives(raw(article),game,'SF',captured,parser_version=1)

    def v3_articles(self):
        fixture=Path(__file__).parent/'fixtures/pgo_availability_v3_articles.json'
        return json.loads(fixture.read_bytes())

    def v3_game(self, game_id):
        season,week,away,home=game_id.split('_')
        return dict(game_id=game_id,season=int(season),week=int(week),game_type='REG',home=home,away=away,
                    kickoff='2026-09-13T17:00:00Z',lock_at='2026-09-13T16:00:00Z')

    def v3_raw(self, article, list_items=()):
        page='<script type="application/ld+json">'+json.dumps(
            dict(article,**{'@type':'NewsArticle'}),ensure_ascii=False)+'</script>'
        return (page+'<article><ul>'+''.join('<li>'+item+'</li>' for item in list_items)+'</ul></article>').encode('utf-8')

    def test_v3_actual_club_articles_are_team_bound_and_exactly_bounded(self):
        expected_counts={'ATL':6,'BUF':7,'CLE':7,'CIN':7,'HOU':6,'NYJ':5,
                         'IND':6,'CAR':7,'TB':7,'PIT':6,'NO':7,'TEN':7,'JAX':6}
        parsed={}
        for row in self.v3_articles():
            value=availability.parse_final_inactives(self.v3_raw(row['article'],row.get('list_items',())),self.v3_game(row['game_id']),
                row['source_team'],row['captured_at'],parser_version=3,source_team=row['source_team'])
            with self.subTest(team=row['source_team']):
                self.assertEqual(len(value['observations']),expected_counts[row['source_team']])
                self.assertEqual(value['unparsed_lines'],[])
                self.assertTrue(all(r['position'] in availability.POSITIONS for r in value['observations']))
            parsed[row['source_team']]=value
        nyj=parsed['NYJ']
        self.assertEqual([(r['position'],r['name']) for r in nyj['observations']],[
            ('K','Blake Grupe'),('RB','Kene Nwangwu'),('EDGE','Joseph Ossai'),
            ('CB',"D'Angelo Ponds"),('LB','Trevin Wallace')])
        self.assertNotIn('Jason Sanders',json.dumps(nyj))
        self.assertEqual(nyj['published_at'],'2026-09-13T15:30:00+00:00')
        self.assertEqual(nyj['modified_at'],'2026-09-13T15:29:19.748000+00:00')
        self.assertLess(availability._utc(nyj['modified_at']),availability._utc(nyj['published_at']))
        jax=parsed['JAX']
        self.assertEqual([r['name'] for r in jax['observations']],
            ['Quinn Ewers','Tanner Koziol','Daniel Faalele','Wesley Williams','Bryan Thomas Jr.','Jalen Huskey'])
        self.assertFalse({'LeQuint Allen Jr.','Nick Mullens'} & {r['name'] for r in jax['observations']})
        row=next(r for r in self.v3_articles() if r['source_team']=='NYJ')
        with self.assertRaises(ValueError):
            availability.parse_final_inactives(self.v3_raw(row['article']),self.v3_game(row['game_id']),'NYJ',
                row['captured_at'],parser_version=2)

    def test_v3_club_admission_rejects_bad_binding_matchup_and_each_clock(self):
        row=next(r for r in self.v3_articles() if r['source_team']=='NYJ')
        raw=self.v3_raw(row['article']);game=self.v3_game(row['game_id'])
        for team,source_team,candidate,captured in (
            ('NYJ',None,game,row['captured_at']),
            ('TEN','NYJ',game,row['captured_at']),
            ('NYJ','NYJ',{**game,'game_id':'2026_01_NYJ_JAX','home':'JAX'},row['captured_at']),
            ('NYJ','NYJ',game,'2026-09-13T15:29:59Z'),
        ):
            with self.subTest(team=team,source_team=source_team,game=candidate['game_id'],captured=captured), self.assertRaises(ValueError):
                availability.parse_final_inactives(raw,candidate,team,captured,parser_version=3,source_team=source_team)
        article={**row['article'],'dateModified':'2026-09-12T16:59:59Z'}
        with self.assertRaises(ValueError):
            availability.parse_final_inactives(self.v3_raw(article),game,'NYJ',row['captured_at'],
                parser_version=3,source_team='NYJ')
        article={**row['article'],'datePublished':game['kickoff'],'dateModified':game['kickoff']}
        with self.assertRaises(ValueError):
            availability.parse_final_inactives(self.v3_raw(article),game,'NYJ','2026-09-13T17:00:01Z',
                parser_version=3,source_team='NYJ')

    def test_v3_explicit_opponent_sections_parse_but_tba_sections_do_not(self):
        rows={r['source_team']:r for r in self.v3_articles()}
        for source_team,target,count in (('CAR','CAR',7),('CAR','CHI',6),('NO','NO',7),('NO','DET',5)):
            row=rows[source_team]
            parsed=availability.parse_final_inactives(self.v3_raw(row['article']),self.v3_game(row['game_id']),
                target,row['captured_at'],parser_version=3,source_team=source_team)
            with self.subTest(source=source_team,target=target):
                self.assertEqual(len(parsed['observations']),count)
                self.assertEqual(parsed['unparsed_lines'],[])
        for source_team,target in (('TB','CIN'),('TEN','NYJ')):
            row=rows[source_team]
            with self.subTest(source=source_team,target=target), self.assertRaises(ValueError):
                availability.parse_final_inactives(self.v3_raw(row['article']),self.v3_game(row['game_id']),
                    target,row['captured_at'],parser_version=3,source_team=source_team)

    def test_v3_own_club_list_precedes_later_opponent_supplement(self):
        rows={r['source_team']:r for r in self.v3_articles()}
        game=self.v3_game('2026_01_ATL_PIT')
        roster=[dict(team='ATL',gsis_id='00-0000001',full_name='Cooper Rush',position='QB',status='ACT'),
                dict(team='PIT',gsis_id='00-0000002',full_name='Aaron Rodgers',position='QB',status='ACT')]
        qbs={'ATL':'00-0000001','PIT':'00-0000002'}
        def source(team):
            row=rows[team]
            return dict(kind='official_inactives',team=team,url=row['url'],final_url=row['url'],status=200,
                        started_at=row['captured_at'],captured_at=row['captured_at'],body=self.v3_raw(row['article']))
        checked='2026-09-13T15:40:00Z'
        opponent_only=availability.build_availability([game],roster,qbs,[source('PIT')],checked_at=checked,parser_version=3)
        names=[r['name'] for r in opponent_only['games'][game['game_id']]['teams']['ATL']['observations']]
        self.assertIn('Malcolm DeWalt',names)
        both=availability.build_availability([game],roster,qbs,[source('ATL'),source('PIT')],checked_at=checked,parser_version=3)
        names=[r['name'] for r in both['games'][game['game_id']]['teams']['ATL']['observations']]
        self.assertIn('Malcom DeWalt IV',names)
        self.assertNotIn('Malcolm DeWalt',names)

    def test_v3_club_only_in_and_out_discovery_uses_actual_list_boundaries(self):
        row=next(r for r in self.v3_articles() if r['source_team']=='JAX')
        game=self.v3_game(row['game_id'])
        players=[('JAX','QB','Trevor Lawrence'),('CLE','QB','Deshaun Watson'),
                 *[('JAX',position,name) for position,name in (
                     ('QB','Quinn Ewers'),('TE','Tanner Koziol'),('OL','Daniel Faalele'),
                     ('DE','Wesley Williams'),('DE','Bryan Thomas Jr.'),('S','Jalen Huskey'))]]
        roster=[dict(team=team,position=position,full_name=name,gsis_id=f'00-{index:07d}',status='ACT')
                for index,(team,position,name) in enumerate(players,1)]
        qbs={'JAX':roster[0]['gsis_id'],'CLE':roster[1]['gsis_id']}
        league='https://www.nfl.com/news/in-and-out-2026-week-1-allen-active'
        calls=[]
        def fetch(url):
            calls.append(url)
            body=(b'<title>NFL Injury Report - Week 1 of the 2026 Season</title>' if url==availability.REPORT_URL else
                  f'<a href="{row["url"]}">In and Out, 2026 Week 1: Allen Active for Opener</a>'.encode()
                  if url=='https://www.jaguars.com/news/' else
                  f'<a href="{league}">In and Out, 2026 Week 1</a>'.encode() if url==availability.NFL_NEWS_URL else
                  self.v3_raw(row['article'],row['list_items']) if url==row['url'] else b'<html></html>')
            return dict(body=body,status=200,final_url=url)
        with tempfile.TemporaryDirectory() as tmp:
            result=availability.capture_availability([game],roster,qbs,Path(tmp)/'capture',
                now='2026-09-13T15:41:00Z',fetch=fetch)
        self.assertIn(row['url'],calls)
        self.assertNotIn(league,calls)
        team=result['games'][game['game_id']]['teams']['JAX']
        self.assertEqual(team['final_inactives_status'],'VERIFIED_LIST')
        self.assertEqual({r['name'] for r in team['observations']},
            {'Quinn Ewers','Tanner Koziol','Daniel Faalele','Wesley Williams','Bryan Thomas Jr.','Jalen Huskey'})

    def test_context_time_window_keeps_default_lock_and_pregame_article_limits(self):
        args=([self.game],self.roster,self.qbs,[])
        with self.assertRaisesRegex(ValueError,'T-60'):
            availability.build_availability(*args,checked_at='2026-09-20T17:20:00Z')
        before=copy.deepcopy(args)
        for now in ('2026-09-20T17:20:00Z','2026-09-20T23:00:00Z'):
            out=availability.build_availability(*args,checked_at=now,purpose='context')
            self.assertEqual(out['purpose'],'context');self.assertEqual(out['parser_version'],2)
            self.assertEqual(out['games'][self.game['game_id']]['qb_gate'],'CONDITIONAL')
        self.assertEqual(args,before)
        with self.assertRaisesRegex(ValueError,'context'):
            availability.build_availability(*args,checked_at='2026-09-20T23:00:01Z',purpose='context')
        with self.assertRaises(ValueError):availability.build_availability(*args,checked_at=self.now,purpose='anything')
        with self.assertRaises(ValueError):availability.build_availability(*args,checked_at=self.now,parser_version=99)
        source=self.source(self.article(published='2026-09-20T17:01:00Z'),kind='official_inactives',team='NE',url='https://www.patriots.com/news/inactives')
        source.update(started_at='2026-09-20T17:20:00Z',captured_at='2026-09-20T17:20:00Z')
        out=availability.build_availability([self.game],self.roster,self.qbs,[source],checked_at=source['captured_at'],purpose='context')
        self.assertEqual(out['games'][self.game['game_id']]['teams']['NE']['final_inactives_status'],'UNKNOWN')

    def test_context_discovers_nfl_article_once_and_replays_versioned_capture(self):
        game,nfl,club,raw=self.real_sf_lar();calls=[]
        url='https://www.nfl.com/news/australia-game-inactives-san-francisco-49ers-at-los-angeles-rams'
        players=[('SF','QB','Kurtis Rourke'),('SF','CB','Ephesians Prysock'),('SF','RB','Jordan James'),
                 ('SF','WR','Jordan Watkins'),('SF','LB','Tatum Bethune'),('SF','OT','Enrique Cruz Jr.'),
                 ('LAR','QB','Ty Simpson'),('LAR','WR','CJ Daniels'),('LAR','WR','Tutu Atwell'),
                 ('LAR','OL','Bill Murray'),('LAR','TE','Max Klare'),('SF','QB','Brock Purdy'),('LAR','QB','Matthew Stafford')]
        roster=[dict(team=t,position=p,full_name=n,gsis_id=f'00-{i:07d}',status='ACT') for i,(t,p,n) in enumerate(players,1)]
        qbs={'SF':roster[-2]['gsis_id'],'LAR':roster[-1]['gsis_id']}
        def fetch(target):
            calls.append(target)
            body=(raw(nfl) if target==url else
                  f'<a href="{url}">{nfl["headline"]}</a>'.encode() if target==availability.NFL_NEWS_URL else b'<html></html>')
            return dict(body=body,status=200,final_url=target)
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'context'
            out=availability.capture_availability([game],roster,qbs,directory,purpose='context',now='2026-09-11T01:00:00Z',fetch=fetch)
            self.assertEqual(calls.count(availability.NFL_NEWS_URL),1);self.assertEqual(calls.count(url),1)
            self.assertEqual(out,availability.load_availability(directory))
            inputs=json.loads(gzip.decompress((directory/'inputs.json.gz').read_bytes()))
            self.assertEqual((inputs['purpose'],inputs['parser_version']),('context',5))
            for team in out['games'][game['game_id']]['teams'].values():
                self.assertEqual(team['final_inactives_status'],'VERIFIED_LIST')
                self.assertEqual(team['expected_qb_status'],'UNKNOWN')
            self.assertNotIn('margin',out['games'][game['game_id']])

    def test_legacy_capture_missing_version_replays_original_shape(self):
        directory=Path(__file__).resolve().parents[1]/'docs/evidence/season-2026/availability-v2/20260910T232558473366Z'
        expected=json.loads((directory/'availability.json').read_bytes())
        self.assertNotIn('purpose',expected);self.assertNotIn('parser_version',expected)
        self.assertEqual(availability.load_availability(directory),expected)

    def test_context_capture_crossing_six_hour_write_bound_is_failed(self):
        clock=[availability._utc('2026-09-20T22:59:59Z')]
        def fetch(url):return dict(body=b'<html></html>',status=200,final_url=url)
        write=availability._write
        def slow_write(path,raw):
            write(path,raw)
            if path.name=='manifest.json':clock[0]=availability._utc('2026-09-20T23:00:01Z')
        with tempfile.TemporaryDirectory() as tmp, patch.object(availability,'_clock',side_effect=lambda now=None:clock[0]), patch.object(availability,'_write',side_effect=slow_write):
            directory=Path(tmp)/'context'
            with self.assertRaisesRegex(ValueError,'context'):
                availability.capture_availability([self.game],self.roster,self.qbs,directory,purpose='context',fetch=fetch)
            self.assertTrue((directory/'failure.json').exists())
            with self.assertRaisesRegex(ValueError,'failed'):availability.load_availability(directory)


if __name__=='__main__':unittest.main()
