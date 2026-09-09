import unittest

from research.pgo_nonqb_availability_20260909.prepare_roles import role_observations


class AvailabilityRoleTests(unittest.TestCase):
    def test_absence_is_not_a_zero_playing_role(self):
        rosters = [dict(season='2025', week=str(w), team='NE', status='ACT',
                        gsis_id='A', pfr_id='Alpha00', full_name='Alpha Player') for w in (1, 2, 3)]
        snaps = [dict(season='2025', week=str(w), team='NE', game_type='REG',
                      game_id=f'2025_{w:02}_NE_SEA', player='Alpha Player',
                      pfr_player_id='Alpha00', offense_snaps=str(n), defense_snaps='0')
                 for w, n in ((1, 40), (2, 0))]
        observations = role_observations(rosters, snaps, [])
        self.assertEqual([r['week'] for r in observations['A', 'offense']], [1])
        self.assertEqual(observations['A', 'offense'][0]['share'], 1)
        self.assertNotIn(('A', 'defense'), observations)

    def test_duplicate_snap_identity_stops_role_inference(self):
        roster = dict(season='2025', week='1', team='NE', status='ACT',
                      gsis_id='A', pfr_id='Alpha00', full_name='Alpha Player')
        snap = dict(season='2025', week='1', team='NE', game_type='REG',
                    game_id='2025_01_NE_SEA', player='Alpha Player',
                    pfr_player_id='Alpha00', offense_snaps='40', defense_snaps='0')
        with self.assertRaisesRegex(ValueError, 'Duplicate historical snap'):
            role_observations([roster], [snap, snap], [])


if __name__ == '__main__':
    unittest.main()
