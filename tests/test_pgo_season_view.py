import copy
import unittest

import generate_site
import pgo_season_view as view


def state():
    codes = sorted(row[0] for row in generate_site.TEAM.values())
    teams = [dict(team=team, rank=i + 1, rating=15.5 - i, prior_rank=32-i,
                  qb_name='QB <source>', features={'pgo_v0': 15.5-i},
                  contributions={'pgo_v0': 15.5-i}) for i, team in enumerate(codes)]
    def game(key, week, grade, result, **changes):
        row = dict(game_id=key, season=2026, week=week, home='SEA', away='NE',
                   kickoff='2026-09-16T23:00:00Z', lock_at='2026-09-16T22:00:00Z',
                   margin=.2, total=50.2, home_points=25.2, away_points=25.0,
                   pick='SEA', grade=grade, result=result, forecast_status='LOCKED',
                   blocked_reason=None, availability={'checked_at':'2026-09-16T21:00:00Z',
                   'summary':'Expected QB verified; other injuries are context', 'blocked_reason':None},
                   confidence={'points':1, 'win_probability':.51, 'expected_points':.51,
                               'earned_points':None, 'added_after_lock':False})
        row.update(changes)
        return row
    old = game('old', 1, 'W', {'home_score':24, 'away_score':20}, forecast_status='FINAL',
               confidence={'points':1,'win_probability':.6,'expected_points':.6,
                           'earned_points':1,'added_after_lock':True})
    return dict(schema_version=1, season=2026, current_week=2, checked_at='2026-09-16T22:30:00Z',
                status='READY', blocked_reason=None, freshness='Sources checked; no new final results',
                rankings=dict(edition='pgo-2026-week2', generated_at='2026-09-16T21:00:00Z',
                              inputs_as_of='2026-09-16T21:00:00Z',history_through='2026-09-15T23:00:00Z',teams=teams),
                model_records=[dict(name='Weekly model',edition='pgo-weekly',wins=1,losses=0,ties=0,no_pick=0,pending=1)],
                sources=[dict(label='Saved <source>',href='evidence/season-2026/week2.json')],
                weeks=[dict(week=1,status='COMPLETE',source_edition='old',generated_at='2026-09-09T21:00:00Z',
                            inputs_as_of='2026-09-09T21:00:00Z',games=[old]),
                       dict(week=2,status='UPCOMING',source_edition='pgo-2026-week2',generated_at='2026-09-16T21:00:00Z',
                            inputs_as_of='2026-09-16T21:00:00Z',games=[game('current',2,'PENDING',None)])])


class SeasonViewTests(unittest.TestCase):
    def test_current_rankings_week_and_archived_grades_preserve_input(self):
        data = state(); before = copy.deepcopy(data)
        page = view.render_season(data)
        self.assertEqual(data,before)
        self.assertEqual(page.count('data-season-team='),32)
        self.assertEqual(page.count('data-season-game-id='),2)
        self.assertLess(page.index('data-season-game-id="current"'),page.index('data-season-game-id="old"'))
        self.assertIn('Week 2',page)
        self.assertIn('Week 1',page)
        self.assertIn('Model records',page)
        self.assertIn('data-season-checked-at="2026-09-16T22:30:00Z"',page)
        self.assertIn('About 25 points each',page)
        self.assertIn('SEA by 0.2 points',page)
        self.assertIn('SEA 25.2',page)
        self.assertIn('Fixed confidence points',page)
        self.assertIn('Added after lock',page)
        self.assertIn('QB &lt;source&gt;',page)
        self.assertIn('Saved &lt;source&gt;',page)
        self.assertIn('What lifts this rating',page)
        self.assertIn('What holds this rating back',page)
        self.assertNotIn('<section',page)
        self.assertNotIn('<style',page)
        self.assertNotIn('data-weekly-game-id=',page)

    def test_blocked_and_unknown_values_are_not_invented(self):
        data = state(); data.update(status='BLOCKED',blocked_reason='QB identity <missing>')
        game = data['weeks'][1]['games'][0]
        for status in ('DRAFT','LOCKED'):
            game['forecast_status']=status
            self.assertIn('data-weekly-cutoff="2026-09-16T22:00:00Z"',view.render_season(data))
        game.update(forecast_status='BLOCKED',blocked_reason='Awaiting official source',pick=None,
                    margin=None,total=None,home_points=None,away_points=None,confidence=None)
        page = view.render_season(data)
        self.assertIn('QB identity &lt;missing&gt;',page)
        self.assertIn('Awaiting official source',page)
        self.assertIn('Forecast unavailable',page)
        self.assertIn('Confidence unavailable',page)
        self.assertIn('2026-09-16T22:00:00Z',page)
        self.assertNotIn('data-weekly-cutoff=',page)
        game.update(margin=.2,total=50.2,home_points=25.2,away_points=25.0)
        before=copy.deepcopy(data)
        page=view.render_season(data)
        self.assertIn('Saved conditional estimate',page)
        self.assertIn('This estimate is withheld as a pick until the blocking issue is resolved.',page)
        self.assertEqual(data,before)

    def test_grades_ties_no_pick_and_zero_earned_remain_distinct(self):
        data = state(); game=data['weeks'][1]['games'][0]
        game.update(grade='T',result={'home_score':20,'away_score':20},forecast_status='FINAL')
        game['confidence']['earned_points']=0
        page=view.render_season(data)
        self.assertIn('data-grade="T">T',page)
        self.assertIn('SEA 20',page)
        self.assertIn('Earned: 0',page)
        game.update(pick=None,grade='NO_PICK')
        page=view.render_season(data)
        self.assertIn('No pick',page)
        self.assertNotIn('data-grade="W">W',page.split('data-season-game-id="current"')[1].split('</tr>')[0])

    def test_optional_matchup_chain_reconciles_and_units_stay_distinct(self):
        data=state(); game=data['weeks'][1]['games'][0]
        game['explanation']={'neutral_margin':-.3,'home_adjustment':.5,'rest_adjustment':0}
        game['explanation'].update(home_rating=1.2,away_rating=1.5,rating_inputs_as_of='2026-09-16T20:00:00Z')
        game.update(issued_at='2026-09-16T21:00:00Z',inputs_as_of='2026-09-16T20:00:00Z',
                    expected_qbs={'SEA':'Saved <QB>', 'NE':'Other QB'},source_edition='saved-game-edition')
        page=view.render_season(data)
        self.assertIn('Neutral matchup: -0.30 points',page)
        self.assertIn('Home/venue adjustment: +0.50 points',page)
        self.assertIn('Win probability is a percentage',page)
        self.assertIn('pool points, not NFL scoreboard points',page)
        self.assertIn('Ratings saved for this forecast: SEA +1.200; NE +1.500',page)
        self.assertIn('Saved &lt;QB&gt;',page)
        self.assertIn('Edition: saved-game-edition',page)
        self.assertIn('Issued <time datetime="2026-09-16T21:00:00Z"',page)
        game['explanation']['home_rating']=1.3
        with self.assertRaisesRegex(ValueError,'rating inputs'): view.render_season(data)
        game['explanation']['home_rating']=1.2
        game['explanation']['home_adjustment']=.6
        with self.assertRaisesRegex(ValueError,'matchup explanation'): view.render_season(data)

    def test_invalid_identity_numbers_status_and_sources_raise(self):
        cases = []
        data=state(); data['rankings']['teams'][0]['rating']=float('nan'); cases.append(data)
        data=state(); data['rankings']['teams']=data['rankings']['teams'][:-1]; cases.append(data)
        data=state(); data['weeks'][1]['games'][0]['grade']='WIN'; cases.append(data)
        data=state(); data['weeks'][1]['games'][0]['forecast_status']='ASSUMED'; cases.append(data)
        data=state(); data['weeks'][1]['games'][0]['confidence']['win_probability']=1.1; cases.append(data)
        for href in ('javascript:alert(1)','//example.com','../secret','https://example.com/\\x'):
            data=state(); data['sources'][0]['href']=href; cases.append(data)
        for data in cases:
            with self.subTest(data=data['sources']), self.assertRaises(ValueError): view.render_season(data)


if __name__ == '__main__': unittest.main()
