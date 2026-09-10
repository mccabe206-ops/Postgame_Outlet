import copy
import importlib.util
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


if __name__=='__main__':unittest.main()
