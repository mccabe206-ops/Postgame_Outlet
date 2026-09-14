import copy
import csv
import gzip
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_season as season
import pgo_statistics_review as review


class StatisticsReviewTests(unittest.TestCase):
    def fixture(self):
        game=dict(game_id='2026_01_NE_SEA',season=2026,week=1,game_type='REG',home='SEA',away='NE',
                  kickoff='2026-09-09T00:00:00Z',location='Home',home_rest=7,away_rest=7)
        teams=[];players=[]
        for i,(team,opponent) in enumerate((('NE','SEA'),('SEA','NE')),1):
            row=dict(season=2026,week=1,season_type='REG',team=team,opponent_team=opponent,game_id=game['game_id'],
                     attempts=30,sacks_suffered=2,carries=25,passing_interceptions=1,
                     fumbles_lost_total=1,passing_20=3,rushing_20=1,passing_epa=1.,rushing_epa=2.)
            teams.append(row)
            players.append(dict(row,player_id=f'00-{i:07d}',position='QB',sack_fumbles_lost=0,passing_cpoe=2.))
        return [game],teams,players

    def test_numeric_format_and_future_weeks_do_not_create_corrections(self):
        games,teams,players=self.fixture()
        expected=review.project(games,teams,players)
        teams[0]['passing_epa']='1.00'
        teams.append(dict(teams[0],week=2,passing_epa=99999))
        players.append(dict(players[0],week=2,passing_epa=99999))
        self.assertEqual(review.project(games,teams,players),expected)

    def test_reconciled_penalty_pool_remains_unattributed(self):
        from tests.test_pgo_season_statistics import StatisticsTests
        StatisticsTests.setUpClass()
        args=StatisticsTests().inputs()
        result=review.project(args['completed_games'],args['team_rows'],args['qb_rows'])
        self.assertEqual(len(result['unattributed_penalties']),1)
        self.assertEqual(len(result['rows']),64)
        self.assertTrue(all(r['player_id'] for r in result['rows'].values() if r['kind']=='player'))

    def test_team_and_qb_input_changes_have_exact_old_new_values(self):
        games,teams,players=self.fixture()
        before=review.project(games,teams,players)
        teams[0]['passing_epa']=2.
        players[0]['passing_cpoe']=3.
        changes=review.differences(before,review.project(games,teams,players))
        self.assertEqual([(r['field'],r['before'],r['after']) for r in changes],
                         [('passing_cpoe',2.,3.),('passing_epa',1.,2.)])
        self.assertEqual({r['team'] for r in changes},{'NE'})

    def test_missing_duplicate_conflicting_and_unknown_production_cannot_pass(self):
        for fault in ('team_missing','player_missing','duplicate','missing_number','identity'):
            games,teams,players=self.fixture()
            if fault=='team_missing':teams.pop()
            if fault=='player_missing':players.pop()
            if fault=='duplicate':players.append(copy.deepcopy(players[0]))
            if fault=='missing_number':teams[0]['passing_epa']=None
            if fault=='identity':players[0]['game_id']='wrong'
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                review.project(games,teams,players)
        games,teams,players=self.fixture()
        with patch.object(review.model,'_context',return_value={'inputs':{'colliding_gsis':[players[0]['player_id']]}}):
            with self.assertRaisesRegex(ValueError,'Ambiguous historical'):
                review.project(games,teams,players)

    def archive(self,root,kind,rows,clock):
        text=io.StringIO(newline='');writer=csv.DictWriter(text,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
        raw=gzip.compress(text.getvalue().encode(),mtime=0);digest=season.sha(raw)
        path='source-archive/'+digest+'.csv.gz';(root/'source-archive').mkdir(exist_ok=True)
        (root/path).write_bytes(raw)
        return raw,dict(url=season.URLS[kind],path=path,sha256=digest,bytes=len(raw),captured_at=clock)

    def test_refresh_is_bounded_source_backed_and_preserves_issued_state(self):
        games,teams,players=self.fixture();clock='2026-09-10T12:00:00Z'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            refs=[self.archive(root,k,rows,'2026-09-10T06:00:00Z')[1] for k,rows in (('team',teams),('player',players))]
            state=dict(season=2026,checked_at=clock,schedule=games,results=[dict(games[0],finalized_at='2026-09-09T05:00:00Z')],
                       rankings=dict(edition='saved',completed_week=1,inputs_as_of='2026-09-10T07:00:00Z',source_captures=refs),
                       weeks=[dict(week=1,games=[dict(games[0],margin=3.,grade='W')])])
            original=copy.deepcopy(state)
            def fetch(url,root):
                kind='team' if url==season.URLS['team'] else 'player'
                return self.archive(root,kind,teams if kind=='team' else players,clock)
            with patch.object(season,'fetch_source',side_effect=fetch) as capture,patch.object(season,'now',side_effect=lambda:clock):
                result=review.refresh_review(state,None,root,clock)
                self.assertEqual(result['status'],'CLEAR')
                self.assertEqual(capture.call_count,2)
                self.assertEqual(state,original)
                saved=dict(state,statistics_review=result)
                clock='2026-09-10T17:59:59Z'
                self.assertEqual(review.refresh_review(state,saved,root,clock),result)
                self.assertEqual(capture.call_count,2)
                clock='2026-09-10T18:00:00Z';teams[0]['passing_epa']=4.
                updated=review.refresh_review(state,saved,root,clock)
                self.assertEqual(updated['status'],'REVIEW')
                self.assertEqual(updated['report']['changes'][0]['after'],4.)
                self.assertEqual(state,original)
                self.assertEqual(result['report']['changes'],[])
                newer=copy.deepcopy(state);newer['rankings']['edition']='new-edition'
                immediate=review.refresh_review(newer,dict(state,statistics_review=updated),root,clock)
                self.assertEqual(immediate['report']['basis_edition'],'new-edition')
                self.assertEqual(capture.call_count,6)
                review.verify_saved(updated,root,clock)
                changed=dict(updated);changed['report']=copy.deepcopy(updated['report'])
                changed['report']['changes'][0]['after']=999
                with self.assertRaises(ValueError):review.verify_saved(changed,root,clock)
                for field,value in (('completed_week',2),('compared_at','2026-09-10T18:01:00Z')):
                    changed=copy.deepcopy(updated);changed['report'][field]=value
                    with self.subTest(field=field),self.assertRaises(ValueError):
                        review.verify_saved(changed,root,'2026-09-10T19:00:00Z')
                changed=copy.deepcopy(state);changed['schedule'][0]['away_rest']=8
                with self.assertRaises(ValueError):review.verify_saved(updated,root,clock,state=changed)
                changed=copy.deepcopy(updated);changed['report']['basis_sources'][0]['captured_at']='2026-09-10T06:30:00Z'
                with self.assertRaisesRegex(ValueError,'basis differs'):
                    review.verify_saved(changed,root,clock,state=state)
                clock='2026-09-11T00:00:00Z';teams.pop()
                failed=review.refresh_review(state,dict(state,statistics_review=updated),root,clock)
                self.assertEqual(failed['status'],'BLOCKED')
                self.assertEqual(failed['report'],updated['report'])

    def test_view_explains_waiting_and_corrections_without_changing_model_claims(self):
        from pgo_season_view import _statistics_review
        waiting=_statistics_review({'statistics_review':{'status':'WAITING'}})
        self.assertIn('No completed comparison yet',waiting)
        html=_statistics_review({'statistics_review':dict(status='REVIEW',report=dict(
            compared_at='2026-09-10T18:00:00Z',completed_week=1,basis_edition='saved',games=[{}],
            changes=[dict(kind='team',game_id='2026_01_NE_SEA',team='NE',field='passing_epa',before=1.,after=4.)]))})
        self.assertIn('does not change issued picks',html)
        self.assertIn('1.0 to 4.0',html)
        self.assertNotIn('&lt;time',html)

    def test_waits_for_completed_week_and_missing_source_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(season,'fetch_source',side_effect=AssertionError('No fetch')):
            state={'rankings':{'completed_week':0}}
            result=review.refresh_review(state,None,Path(tmp),'2026-09-10T12:00:00Z')
            self.assertEqual(result['status'],'WAITING')
            state['rankings'].update(completed_week=1,edition='legacy',inputs_as_of='2026-09-10T07:00:00Z')
            self.assertEqual(review.refresh_review(state,None,Path(tmp),'2026-09-10T12:00:00Z')['status'],'BLOCKED')


if __name__=='__main__':unittest.main()
