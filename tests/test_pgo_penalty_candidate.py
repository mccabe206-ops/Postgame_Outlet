import copy
import importlib
import math
import unittest


def game(key, week, kickoff, home='NE', away='SEA', season=2025, kind='REG'):
    return dict(game_id=key, season=season, week=week, kickoff=kickoff,
                home=home, away=away, game_type=kind)


def production(g, home_yards, away_yards):
    return [dict(game_id=g['game_id'], season=str(g['season']), week=str(g['week']),
                 team=g[side], opponent_team=g[other], season_type='REG' if g['game_type']=='REG' else 'POST',
                 penalty_yards=str(yards), penalties='0' if yards==0 else '3')
            for side,other,yards in [('home','away',home_yards),('away','home',away_yards)]]


class PenaltyCandidateTests(unittest.TestCase):
    def api(self):
        return importlib.import_module('research.pgo_penalty_candidate.candidate')

    def test_prior_only_decay_zero_postseason_carry_and_seeded_replay(self):
        c=self.api()
        games=[game('a',18,'2025-12-28T18:00Z'),game('b',19,'2026-01-04T18:00Z',kind='WC'),
               game('c',1,'2026-09-10T18:00Z',season=2026)]
        rows=production(games[0],0,40)+production(games[1],20,60)+production(games[2],90,10)
        before=copy.deepcopy((games,rows))
        result=c.penalty_history(games,rows)
        self.assertIsNone(result['pregame']['a']['difference'])
        self.assertEqual(result['pregame']['b'],dict(home=0.,away=40.,difference=-40.))
        self.assertAlmostEqual(result['pregame']['c']['home'],20/(c.DECAY+1))
        first=c.penalty_history(games[:2],rows[:4])
        later=c.penalty_history(games[2:],rows[4:],initial=first['states'])
        self.assertEqual(later['pregame']['c'],result['pregame']['c'])
        self.assertEqual(later['states'],result['states'])
        self.assertEqual(c.penalty_history([],[],initial=later['states'])['states'],later['states'])
        self.assertEqual((games,rows),before)
        rows[-1]['penalty_yards']='999'
        self.assertEqual(c.penalty_history(games,rows)['pregame'],result['pregame'])

    def test_same_kickoff_order_and_future_perturbation(self):
        c=self.api()
        a=game('a',1,'2025-09-01T18:00Z');b=game('b',1,a['kickoff'],'BUF','NYJ')
        future=game('c',2,'2025-09-08T18:00Z')
        rows=production(a,10,20)+production(b,30,40)+production(future,50,60)
        self.assertEqual(c.penalty_history([a,b,future],rows),c.penalty_history([future,b,a],list(reversed(rows))))
        old=c.penalty_history([a,b],rows[:4])
        new=c.penalty_history([a,b,future],rows)
        self.assertEqual(old['pregame'],{k:new['pregame'][k] for k in old['pregame']})

    def test_identity_missing_negative_fractional_and_duplicate_fail_closed(self):
        c=self.api();g=game('a',1,'2025-09-01T18:00Z');rows=production(g,0,20)
        for field,value in [('opponent_team','BUF'),('game_id','wrong'),('season','2024'),
                            ('season_type','POST'),('penalty_yards',''),('penalty_yards','-1'),
                            ('penalty_yards','1.5'),('penalties','nan')]:
            bad=copy.deepcopy(rows);bad[0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError): c.penalty_history([g],bad)
        for games,source in [([g],rows[:1]),([g],rows+[rows[0]]),([g,g],rows)]:
            with self.assertRaises(ValueError):c.penalty_history(games,source)
        with self.assertRaises(ValueError):c.penalty_history([],[],initial={'NE':[1,0]})

    def test_feature_append_preserves_every_baseline_field_and_symmetry(self):
        c=self.api()
        originals=[dict(game_id='a',season=2025,week=1,kickoff='2025-09-01T18:00Z',actual_margin=3.,
                        features={'home_field':1.,'old_missing':None},subgroup_flags={'x':True})]
        before=copy.deepcopy(originals)
        rows=c.augment_rows(originals,{'a':dict(home=10.,away=20.,difference=-10.)})
        self.assertEqual(originals,before)
        self.assertEqual(rows[0].features[c.FEATURE],-10.)
        from dataclasses import asdict
        restored=asdict(rows[0]);restored['features'].pop(c.FEATURE)
        self.assertEqual(restored,originals[0])
        from research.pgo_input_audit.audit_model import symmetric_rows
        mirrored=symmetric_rows(rows)
        self.assertEqual(mirrored[1].features[c.FEATURE],10.)
        self.assertIsNone(mirrored[1].features['old_missing'])

    def test_frozen_baseline_replays_without_fitting(self):
        c=self.api()
        from unittest.mock import patch
        with patch('research.pgo_week1_corrected.train.fit_combined',side_effect=AssertionError('No fitting')):
            data=c.load_baseline()
        self.assertEqual(len(data['originals']),3407)
        self.assertEqual(data['replay']['games'],2127)
        self.assertLessEqual(data['replay']['maximum_error'],1e-10)

    def test_locked_screen_thresholds(self):
        c=self.api()
        def metrics(improvement,wins):
            return {'postseason':{'overall':{'mae':10.},'seasons':[{'season':s,'mae':10.} for s in range(2018,2026)]},
                    'candidate':{'overall':{'mae':10.-improvement},'seasons':[{'season':s,'mae':9. if s-2018<wins else 11.} for s in range(2018,2026)]}}
        self.assertEqual(c.screen(metrics(.06,5),{'lower':.001})['status'],'PASS')
        for delta,wins,lower in [(.049,8,.1),(.06,4,.1),(.06,8,0.)]:
            self.assertEqual(c.screen(metrics(delta,wins),{'lower':lower})['status'],'FAIL')

    def test_raw_yard_weight_uses_saved_scale_and_feature_order(self):
        c=self.api()
        fit={'preprocessor':{'feature_names':['other',c.FEATURE], 'scales':[3.,4.]},
             'coefficients':[0.,9.,-2.]}
        self.assertEqual(c.raw_yard_weight(fit),-.5)


if __name__=='__main__':unittest.main()
