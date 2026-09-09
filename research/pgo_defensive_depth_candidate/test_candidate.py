import copy
import unittest

from research.pgo_defensive_depth_candidate import candidate as c
from research.pgo_defensive_depth_candidate import evidence as ev
from research.pgo_defensive_depth_candidate.test_evidence import roster, snap, stat


class CandidateTests(unittest.TestCase):
    def histories(self):
        rr=[roster(),roster('two','Two Player')]
        ss=[snap(count=40),snap('two','Two Player',count=20)]
        pp=[stat(),stat('two')]
        pp[1]['def_pass_defended']=''
        return ev.build_history(rr,ss,pp,2025,set())[0]

    def test_four_fixed_formulas_and_stat_specific_exposure(self):
        rows=[roster(season='2026'),roster('two','Two Player',season='2026'),
              roster('rookie','New Rookie',season='2026')]
        values,coverage=c.team_features(rows,self.histories(),2026)
        self.assertEqual(set(c.FEATURES),set(values))
        self.assertAlmostEqual(100*4/60,values[c.FEATURES[0]])
        self.assertAlmostEqual(100*2/40,values[c.FEATURES[1]])
        self.assertAlmostEqual(1.8,values[c.FEATURES[2]])
        self.assertAlmostEqual(2/3,values[c.FEATURES[3]])
        self.assertEqual(20,coverage['exposure']['def_pass_defended']['excluded_defensive_snaps'])

    def test_history_unavailable_and_rookie_history_are_distinct(self):
        rows=[roster(season='2013')]
        values,coverage=c.team_features(rows,None,2013)
        self.assertTrue(all(v is None for v in values.values()))
        self.assertEqual('PRIOR_SEASON_SOURCE_UNAVAILABLE',coverage['status'])
        values,coverage=c.team_features([roster(season='2026')],{},2026)
        self.assertTrue(all(values[k] is None for k in c.FEATURES[:3]))
        self.assertEqual(0,values[c.FEATURES[3]])
        self.assertEqual(1,coverage['without_observed_history'])

    def test_nonactive_and_future_history_rejected(self):
        row=roster(season='2026');row['status']='RES'
        with self.assertRaisesRegex(ValueError,'ACT'):
            c.team_features([row],self.histories(),2026)
        future=self.histories();future['one']['observations'][0]['season']=2026
        with self.assertRaisesRegex(ValueError,'prior season'):
            c.team_features([roster(season='2026')],future,2026)

    def test_transferred_history_identical_and_duplicates_rejected(self):
        a,_=c.team_features([roster(season='2026')],self.histories(),2026)
        b,_=c.team_features([roster(season='2026',team='SEA')],self.histories(),2026)
        self.assertEqual(a,b)
        row=roster(season='2026')
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            c.team_features([row,row],self.histories(),2026)

    def test_signed_differences_preserve_missingness(self):
        a={k:float(i) for i,k in enumerate(c.FEATURES)}
        b={k:float(2*i) for i,k in enumerate(c.FEATURES)}
        b[c.FEATURES[0]]=None
        forward=c.difference(a,b);reverse=c.difference(b,a)
        self.assertIsNone(forward[c.FEATURES[0]])
        for key in c.FEATURES[1:]:self.assertEqual(forward[key],-reverse[key])

    def test_current_season_production_cannot_enter_prior_features(self):
        history=self.histories()
        changed=copy.deepcopy(history)
        # An arbitrary current-season result is forbidden, never rolled into a prior.
        extra=copy.deepcopy(changed['one']['observations'][0]);extra['season']=2026
        extra['stats']['def_qb_hits']=1000;changed['one']['observations'].append(extra)
        with self.assertRaisesRegex(ValueError,'prior season'):
            c.team_features([roster(season='2026')],changed,2026)


if __name__=='__main__':unittest.main()
