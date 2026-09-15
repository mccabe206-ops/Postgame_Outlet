"""An unrelated roster conflict must not stop an unchanged game's news check."""
import copy
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_season as api
import pgo_expected_starters as starters


class AvailabilityScopeTests(unittest.TestCase):
    def setUp(self):
        self.clock = '2026-09-14T17:00:00Z'
        self.roster = [dict(season=2026, team=t, position='QB', status='ACT',
                            gsis_id=f'00-{i:07d}', full_name=t+' Starter')
                       for i, t in enumerate(sorted(api.pgo_sources.CURRENT_TEAMS), 1)]
        self.depth = [dict(team=r['team'], gsis_id=r['gsis_id'], pos_abb='QB',
                           pos_rank='1', dt='2026-09-14T13:53:31Z') for r in self.roster]
        self.ids = {r['team']:r['gsis_id'] for r in self.roster}
        next(r for r in self.roster if r['team']=='ATL')['status']='INA'
        self.game = dict(game_id='2026_01_DEN_KC', season=2026, week=1, game_type='REG',
                         home='KC', away='DEN', kickoff='2026-09-15T00:15:00Z',
                         lock_at='2026-09-14T23:15:00Z', margin=-.1, pick='DEN',
                         confidence={'points':1}, expected_qbs={'DEN':'DEN Starter','KC':'KC Starter'})
        old = dict(self.game, game_id='2026_01_ATL_PIT', home='PIT', away='ATL',
                   kickoff='2026-09-13T17:00:00Z', lock_at='2026-09-13T16:00:00Z',
                   starter_announcements=[{'team':'ATL','gsis_id':self.ids['ATL']}])
        self.state = dict(rankings={'completed_week':0, 'teams':[
            dict(team=t,qb_gsis_id=pid) for t,pid in self.ids.items()]},
            weeks=[dict(week=1,games=[old,self.game])], results=[{'game_id':old['game_id']}])

    def test_scoped_selection_ignores_only_unrequested_teams(self):
        selected=api.select_roster(self.roster,self.depth,self.clock,teams={'DEN','KC'})
        self.assertEqual(set(selected),{'DEN','KC'})
        with self.assertRaisesRegex(ValueError,'ATL'):
            api.select_roster(self.roster,self.depth,self.clock)
        for team in ('DEN','KC'):
            roster=copy.deepcopy(self.roster)
            next(r for r in roster if r['team']==team)['status']='INA'
            with self.assertRaisesRegex(ValueError,team):
                api.select_roster(roster,self.depth,self.clock,teams={'DEN','KC'})

    def test_scoped_selection_rejects_ambiguous_missing_stale_or_invalid_scope(self):
        den=next(r for r in self.depth if r['team']=='DEN')
        cases=[self.depth+[den], [r for r in self.depth if r['team']!='DEN'],
               [dict(r,dt='2026-09-01T13:00:00Z') for r in self.depth]]
        for depth in cases:
            with self.subTest(depth=len(depth)), self.assertRaises(ValueError):
                api.select_roster(self.roster,depth,self.clock,teams={'DEN','KC'})
        for teams in (set(),{'UNKNOWN'}):
            with self.assertRaises(ValueError):
                api.select_roster(self.roster,self.depth,self.clock,teams=teams)

    def run_refresh(self, *, context=False, changed=False):
        if context: self.clock='2026-09-14T23:30:00Z'
        if changed:
            next(r for r in self.state['rankings']['teams'] if r['team']=='DEN')['qb_gsis_id']='00-9999999'
            # This case has no reviewed authority for the conflicting default.
            self.state['weeks'][0]['games'][0].pop('starter_announcements')
        observation=dict(game_id=self.game['game_id'],checked_at=self.clock,blocked_reason=None,
                         teams={t:{'final_inactives_status':'VERIFIED_LIST'} for t in ('DEN','KC')})
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(api,'now',return_value=self.clock))
            stack.enter_context(patch.object(api,'fetch_source',side_effect=lambda url,root:
                (url,{'url':url,'captured_at':self.clock})))
            stack.enter_context(patch.object(api,'csv_rows',side_effect=lambda raw:
                self.roster if raw==api.URLS['roster'] else self.depth))
            stack.enter_context(patch.object(starters,'CONFIG',Path(tmp)/'absent.json'))
            verify=stack.enter_context(patch.object(starters,'verify',side_effect=AssertionError('Unrelated locked announcement checked')))
            build=stack.enter_context(patch.object(api,'build_next',side_effect=AssertionError('Unexpected model rebuild')))
            capture=stack.enter_context(patch('pgo_season_availability.capture_availability',
                return_value={'games':{self.game['game_id']:observation}}))
            before=copy.deepcopy(self.state)
            if changed:
                with self.assertRaisesRegex(ValueError,'ATL'):
                    api.refresh_forecast_availability(self.state,Path(tmp))
                self.assertEqual(self.state,before)
            else:
                refs=api.refresh_availability(self.state,Path(tmp))
                self.assertTrue(refs)
                self.assertEqual(set(capture.call_args.args[2]),{'DEN','KC'})
                self.assertEqual(self.state['rankings'],before['rankings'])
                self.assertEqual(self.state['weeks'][0]['games'][0],before['weeks'][0]['games'][0])
                if context:
                    self.assertEqual(capture.call_args.kwargs['purpose'],'context')
                    self.assertEqual(self.state['weeks'],before['weeks'])
                    self.assertEqual(self.state['availability_context_check']['status'],'READY')
                else:
                    for field in ('margin','pick','confidence','expected_qbs'):
                        self.assertEqual(self.game[field],before['weeks'][0]['games'][1][field])
            build.assert_not_called()
            verify.assert_not_called()

    def test_unchanged_forecast_refresh_is_scoped_and_preserves_issued_values(self):
        self.run_refresh()

    def test_post_lock_context_is_scoped_and_cannot_rewrite_forecast(self):
        self.run_refresh(context=True)

    def test_actual_forecast_revision_still_requires_complete_roster(self):
        self.run_refresh(changed=True)

    def test_reviewed_announcement_accepts_explicit_scope_only(self):
        selected={r['team']:r for r in self.roster if r['team'] in ('DEN','KC')}
        decision=dict(team='DEN',gsis_id=self.ids['DEN'],full_name='DEN Starter')
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'config.json'
            config.write_text('{"schema_version":1,"announcements":[{"game_id":"2026_01_DEN_KC","source":{}}]}')
            with patch.object(starters,'CONFIG',config), patch.object(starters,'_announcement',return_value=decision):
                result,annotations=starters.apply(selected,self.roster,[self.game],Path(tmp),self.clock,teams={'DEN','KC'})
                self.assertEqual(set(result),{'DEN','KC'})
                self.assertEqual(annotations[self.game['game_id']][0]['gsis_id'],self.ids['DEN'])
                with self.assertRaises(ValueError):
                    starters.apply(selected,self.roster,[self.game],Path(tmp),self.clock)


if __name__=='__main__':
    unittest.main()
