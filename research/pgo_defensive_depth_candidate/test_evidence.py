import copy
import unittest

from research.pgo_defensive_depth_candidate import evidence as ev


def roster(pid='one', name='One Player', team='NE', season='2025', week='1', **kw):
    return dict(gsis_id=pid, pfr_id=pid, full_name=name, first_name=name.split()[0],
                last_name=name.split()[-1], football_name='', smart_id=pid,
                status='ACT', position='LB', team=team, season=season, week=week,
                years_exp='2', **kw)


def snap(pid='one', name='One Player', week='1', team='NE', game_type='REG', count=40):
    return dict(pfr_player_id=pid, player=name, week=week, team=team,
                season='2025', game_type=game_type, defense_snaps=str(count),
                game_id=f'2025_{week}_{team}_X')


def stat(pid='one', week='1', team='NE', sacks=1, kind='REG'):
    return dict(player_id=pid, team=team, week=week, season='2025',
                season_type=kind, **{k:str(sacks if k=='def_sacks' else 2)
                                    for k in ev.STATS})


class EvidenceTests(unittest.TestCase):
    def test_postseason_and_transferred_player_history(self):
        rr=[roster(),roster(week='22')]
        ss=[snap(),snap(week='22',game_type='SB',count=20)]
        pp=[stat(),stat(week='22',kind='POST',sacks=2)]
        histories,audit=ev.build_history(rr,ss,pp,2025,set())
        p=histories['one']
        self.assertEqual(60,p['defensive_snaps'])
        self.assertEqual(3,p['def_sacks'])
        self.assertEqual(5,p['rates_per_100_defensive_snaps']['def_sacks'])
        self.assertEqual(1,audit['resolved_postseason_rows'])
        current=roster(team='SEA',season='2026')
        result=ev.current_teams([current],[],histories,'2026-09-09T21:00:00+00:00',{'SEA'})
        self.assertEqual(3,result[0]['players'][0]['def_sacks'])
        self.assertEqual(['NE'],result[0]['players'][0]['previous_teams'])

    def test_unknown_rookie_is_not_zero_quality(self):
        result=ev.current_teams([roster(season='2026')],[],{},'2026-09-09T21:00:00+00:00',{'NE'})
        player=result[0]['players'][0]
        self.assertIsNone(player['defensive_snaps'])
        self.assertIsNone(player['def_sacks'])
        self.assertEqual('NO_OBSERVED_PRIOR_DEFENSIVE_SNAPS',player['history_status'])

    def test_missing_stat_row_does_not_become_zero(self):
        histories,_=ev.build_history([roster(),roster(week='2')],[snap(),snap(week='2')],[stat()],2025,set())
        player=histories['one']
        self.assertEqual(80,player['defensive_snaps'])
        self.assertIsNone(player['def_sacks'])
        self.assertIsNone(player['rates_per_100_defensive_snaps']['def_sacks'])
        self.assertEqual(40,player['matched_stat_defensive_snaps'])

    def test_conflicting_snap_id_name_rejected(self):
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            ev.build_history([roster(),roster('two','Two Player')],
                             [snap(name='Two Player')],[stat()],2025,set())

    def test_duplicate_stat_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            ev.build_history([roster()],[snap()],[stat(),stat()],2025,set())

    def test_future_depth_is_not_used_and_backups_count_once(self):
        rr=[roster(season='2026'),roster('two','Two Player',season='2026')]
        rows=[dict(team='NE',gsis_id='one',player_name='One Player',pos_abb='OLB',
                   pos_rank='2',pos_grp='defense',dt='2026-09-09T12:00:00Z')]
        rows.append(dict(rows[0],pos_abb='LB'))
        rows.append(dict(rows[0],pos_rank='1',dt='2026-09-10T12:00:00Z'))
        result=ev.current_teams(rr,rows,{},'2026-09-09T21:00:00+00:00',{'NE'})[0]
        self.assertEqual(1,result['listed_backups'])
        self.assertEqual(0,result['listed_starters'])
        self.assertEqual(1,result['unlisted_defenders'])
        self.assertEqual(1,result['backups_without_prior_defensive_snaps'])

    def test_actual_provider_base_defense_group_is_supported(self):
        row=dict(team='NE',gsis_id='one',player_name='One Player',pos_abb='OLB',
                 pos_rank='1',pos_grp='Base 3-4 D',dt='2026-09-09T12:00:00Z')
        result=ev.current_teams([roster(season='2026')],[row],{},'2026-09-09T21:00:00+00:00',{'NE'})[0]
        self.assertEqual(1,result['listed_starters'])

    def test_current_depth_name_mismatch_is_explicit_unknown(self):
        depth=[dict(team='NE',gsis_id='one',player_name='Someone Else',pos_abb='LB',
                    pos_rank='2',pos_grp='defense',dt='2026-09-09T12:00:00Z')]
        result=ev.current_teams([roster(season='2026')],depth,{},'2026-09-09T21:00:00+00:00',{'NE'})[0]
        self.assertEqual(0,result['listed_backups'])
        self.assertEqual('NAME_MISMATCH',result['players'][0]['depth_status'])


if __name__=='__main__':
    unittest.main()
