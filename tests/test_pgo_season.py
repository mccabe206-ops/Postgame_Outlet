import copy
import importlib.util
import tempfile
import unittest
from unittest import mock
from pathlib import Path


class SeasonTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('pgo_season'), 'Automatic season lifecycle is missing')
        import pgo_season
        return pgo_season

    def game(self, week=1):
        return dict(game_id=f'2026_{week:02}_NE_SEA', season=2026, week=week, game_type='REG',
                    home='SEA', away='NE', kickoff=f'2026-09-{9+7*(week-1):02}T20:00:00Z',
                    location='Home', home_rest=7, away_rest=7)

    def board(self, completed=True, score=24):
        return dict(season={'year':2026,'type':2}, week={'number':1}, events=[dict(id='1',
                    date='2026-09-09T20:00Z', season={'year':2026,'type':2},week={'number':1},
                    competitions=[dict(id='1',status={'type':{'completed':completed,'state':'post' if completed else 'in','name':'STATUS_FINAL' if completed else 'STATUS_HALFTIME'}},competitors=[
                        dict(homeAway='home',team={'abbreviation':'SEA'},score=str(score)),
                        dict(homeAway='away',team={'abbreviation':'NE'},score='21')])])])

    def test_only_verified_finals_and_exact_identity_are_admitted(self):
        api=self.api();g=self.game();now='2026-09-09T23:00:00Z'
        self.assertEqual(api.parse_scoreboard(self.board(False),[g],now)['results'],[])
        r=api.parse_scoreboard(self.board(),[g],now)['results']
        self.assertEqual(r[0]['actual_margin'],3)
        saved=api.merge_results([],r)
        self.assertEqual(api.merge_results(saved,r),saved)
        with self.assertRaises(ValueError): api.merge_results(saved,[dict(r[0],home_score=25,actual_margin=4)])
        with self.assertRaises(ValueError): api.parse_scoreboard(self.board(),[dict(g,away='NYJ')],now)
        with self.assertRaises(ValueError): api.parse_scoreboard(self.board(),[g],'2026-09-09T19:00:00Z')
        with self.assertRaises(ValueError): api.parse_scoreboard(self.board(score=-1),[g],now)

    def test_week_completeness_and_records_do_not_count_pending_or_tie_as_win(self):
        api=self.api();g=self.game();g2=self.game(2)
        r=api.parse_scoreboard(self.board(score=21),[g],'2026-09-09T23:00:00Z')['results']
        self.assertEqual(api.completed_week([g,g2],r),1)
        self.assertEqual(api.completed_week([g,g2],[]),0)
        record=api.record([dict(g,margin=3),dict(g2,margin=-2)],r)
        self.assertEqual((record['wins'],record['losses'],record['ties'],record['pending']),(0,0,1,1))
        self.assertEqual(api.record([dict(g,margin=0)],r)['no_pick'],1)

    def test_deadline_and_confidence_reconcile(self):
        api=self.api();g=dict(self.game(),margin=3,total=45,home_points=24,away_points=21)
        self.assertEqual(api.forecast_status(g,'2026-09-09T18:59:59Z'),'DRAFT')
        self.assertEqual(api.forecast_status(g,'2026-09-09T19:00:00Z'),'LOCKED')
        self.assertEqual(api.forecast_status(dict(g,margin=None),'2026-09-09T19:00:00Z'),'BLOCKED')
        rows=api.allocate_confidence([g,dict(self.game(2),margin=-8,total=44,home_points=18,away_points=26)],{'slope':.15,'tie_probability':.004})
        self.assertEqual(sorted(x['confidence']['points'] for x in rows),[1,2])
        self.assertEqual(rows[1]['confidence']['points'],2)
        for x in rows:
            c=x['confidence'];self.assertAlmostEqual(c['expected_points'],c['points']*c['win_probability'])
            self.assertAlmostEqual(sum(c['probabilities'].values()),1)

    def test_revision_after_cutoff_cannot_replace_saved_prediction(self):
        api=self.api();g=dict(self.game(),margin=3,total=45,home_points=24,away_points=21,issued_at='2026-09-09T18:00:00Z')
        revised=dict(g,margin=-3,home_points=21,away_points=24,issued_at='2026-09-09T19:01:00Z')
        with self.assertRaises(ValueError): api.revise_game(g,revised,'2026-09-09T19:01:00Z')
        before=copy.deepcopy(g)
        newer=api.revise_game(g,dict(revised,issued_at='2026-09-09T18:59:00Z'),'2026-09-09T18:59:00Z')
        self.assertEqual(newer['margin'],-3);self.assertEqual(g,before)

    def test_saved_state_hashes_are_verified(self):
        api=self.api()
        state=dict(schema_version=1,season=2026,current_week=1,status='READY',checked_at='2026-09-09T18:00:00Z',weeks=[],rankings={},results=[],sources=[])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            api.save_state(state,root)
            self.assertEqual(api.load_current(root),state)
            pointer=api.read_json(root/'current.json')
            self.assertTrue(pointer['path'].startswith('runs-v2/'))
            self.assertTrue(pointer['state_url'].startswith('https://raw.githubusercontent.com/'))
            self.assertTrue(pointer['state_url'].endswith('/state.json.gz'))
            (root/pointer['path']/'state.json.gz').write_bytes(b'{}')
            with self.assertRaises(ValueError):api.load_current(root)


    def test_decorate_grades_all_models_and_preserves_fixed_pool_points(self):
        api=self.api();g=dict(self.game(),margin=3,total=45,home_points=24,away_points=21,issued_at='2026-09-09T18:00:00Z')
        g=api.allocate_confidence([g],{'slope':.15,'tie_probability':.004})[0]
        state=dict(schema_version=1,season=2026,current_week=1,status='READY',checked_at='2026-09-09T23:00:00Z',
                   weeks=[dict(week=1,games=[g])],rankings={},results=[],sources=[])
        finals=api.parse_scoreboard(self.board(),[g],state['checked_at'])['results']
        with unittest.mock.patch.object(api,'legacy_models',return_value=[{'name':'Earlier model','edition':'old','games':[dict(g,margin=-1)]}]):
            api.decorate(state,finals)
        self.assertEqual(state['weeks'][0]['games'][0]['grade'],'W')
        self.assertEqual(state['weeks'][0]['games'][0]['confidence']['earned_points'],1)
        self.assertEqual(state['weeks'][0]['games'][0]['forecast_status'],'FINAL')
        self.assertEqual(state['model_records'][0]['wins'],1)
        self.assertEqual(state['model_records'][1]['losses'],1)

    def test_refresh_checks_finals_without_advancing_an_incomplete_week(self):
        api=self.api();from unittest.mock import patch
        g=dict(self.game(),margin=3,total=45,home_points=24,away_points=21,issued_at='2026-09-09T18:00:00Z')
        other=dict(g,game_id='2026_01_NYJ_BUF',home='BUF',away='NYJ',kickoff='2026-09-13T17:00:00Z')
        state=dict(schema_version=1,season=2026,current_week=1,status='READY',checked_at='2026-09-09T18:00:00Z',
                   weeks=[dict(week=1,games=[g,other])],rankings={'completed_week':0},results=[],sources=[])
        finals=api.parse_scoreboard(self.board(),[g],'2026-09-09T23:00:00Z')['results']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);api.save_state(state,root)
            with patch.object(api,'fetch_inputs',return_value=([g,other],finals,[],{})), patch.object(api,'legacy_models',return_value=[]), patch.object(api,'build_next') as build, patch.object(api,'refresh_availability',return_value=[]):
                updated=api.refresh(root)
            build.assert_not_called()
            self.assertEqual(updated['current_week'],1)
            self.assertEqual(updated['model_records'][0]['wins'],1)
            self.assertEqual(updated['weeks'][0]['games'][0]['margin'],3)
            self.assertEqual(api.load_current(root),updated)


if __name__=='__main__':unittest.main()
