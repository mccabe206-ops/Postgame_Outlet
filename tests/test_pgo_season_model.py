import copy
from datetime import timedelta
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_season_model as model


class SeasonModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = model.load_seed()
        cls.snapshot = json.loads((model.SOURCE_DIR / 'snapshot.json').read_bytes())
        cls.qualification = json.loads((model.SOURCE_DIR / 'postseason-qualification.json').read_bytes())

    def inputs(self):
        completed = []
        upcoming = []
        teams, players = [], []
        roster = copy.deepcopy(self.qualification['selected_roster'])
        for original in self.snapshot['games']:
            game = {k: original[k] for k in model.GAME_IDENTITY}
            game.update(home_score=24, away_score=21,
                        finalized_at=(model._utc(game['kickoff']) + timedelta(hours=5)).isoformat())
            completed.append(game)
            next_game = {k: game[k] for k in model.GAME_IDENTITY}
            next_game.update(game_id=game['game_id'].replace('_01_', '_02_'), week=2,
                             kickoff=(model._utc(game['kickoff']) + timedelta(days=7)).isoformat())
            upcoming.append(next_game)
            for side, opposite in [('home', 'away'), ('away', 'home')]:
                team = game[side]
                teams.append(dict(season=2026, week=1, team=team, game_id=game['game_id'], opponent_team=game[opposite],
                                  attempts=30, carries=25, passing_epa=1., rushing_epa=2., sacks_suffered=2,
                                  passing_interceptions=1, fumbles_lost_total=1, passing_20=3, rushing_20=1))
                players.append(dict(player_id=roster[team]['gsis_id'], position='QB', season=2026, week=1,
                                    team=team, attempts=30, sacks_suffered=2, passing_epa=1., passing_cpoe=2.,
                                    passing_interceptions=1, sack_fumbles_lost=0, carries=3, rushing_epa=.5))
        generated = (max(model._utc(g['finalized_at']) for g in completed) + timedelta(hours=1)).isoformat()
        return dict(seed=self.seed, fit=self.snapshot['fit'], completed_games=completed, team_rows=teams,
                    qb_rows=players, selected_roster=roster, upcoming_games=upcoming, season=2026,
                    completed_week=1, generated_at=generated, inputs_as_of=generated,
                    scoring_rates=self.snapshot['scoring_rates'], league_mean_total=self.snapshot['league_mean_total'])

    def test_week_one_seed_reproduces_all_issued_features_ratings_and_margins(self):
        result = model.build_week(self.seed, self.snapshot['fit'], [], [], [], self.qualification['selected_roster'],
                                  [{k:g[k] for k in model.GAME_IDENTITY} for g in self.snapshot['games']],
                                  completed_week=0, generated_at=self.snapshot['generated_at'],
                                  inputs_as_of=self.snapshot['inputs_as_of'], scoring_rates=self.snapshot['scoring_rates'],
                                  league_mean_total=self.snapshot['league_mean_total'])
        old = {t['team']:t for t in self.snapshot['teams']}
        for t in result['teams']:
            expected = old[t['team']]['features']
            self.assertEqual(t['features'].keys(), expected.keys())
            for name, value in t['features'].items():
                self.assertIs(type(value), type(expected[name]))
                if isinstance(value, float):
                    # Windows and glibc log1p differ by one ULP for six saved
                    # QB features; raw source bytes and non-floats stay exact.
                    self.assertTrue(math.isfinite(value) and math.isfinite(expected[name]))
                    self.assertLessEqual(abs(value - expected[name]),
                                         4 * max(math.ulp(value), math.ulp(expected[name])), (t['team'], name))
                else:
                    self.assertEqual(value, expected[name])
            self.assertAlmostEqual(t['rating'], old[t['team']]['rating'], places=12)
            self.assertEqual(t['rank'], old[t['team']]['rank'])
        games = {g['game_id']:g for g in self.snapshot['games']}
        for g in result['games']:
            self.assertAlmostEqual(g['margin'], games[g['game_id']]['margin'], places=12)
            self.assertEqual(g['total'], games[g['game_id']]['total'])

    def test_replay_is_idempotent_does_not_mutate_and_applies_retention_once(self):
        args = self.inputs(); before = copy.deepcopy(args)
        first = model.build_week(**args); second = model.build_week(**args)
        self.assertEqual(first, second); self.assertEqual(args, before)
        ratings = {t:v*.5 for t,v in model._context()['ratings'].items()}
        for g in sorted(args['completed_games'],key=lambda g:(model._utc(g['kickoff']),g['game_id'])):
            residual = max(-20.,min(20.,g['home_score']-g['away_score']-(ratings[g['home']]-ratings[g['away']]+(0. if g['location']=='Neutral' else 2.5))))
            ratings[g['home']] += .15*residual/2.; ratings[g['away']] -= .15*residual/2.
        self.assertEqual(first['state']['ratings'], ratings)
        self.assertEqual(first['coverage']['completed_games'], 16)
        self.assertEqual(first['week'], 2)
        with self.assertRaises(ValueError): model.build_week(**{**args,'seed':first['state']})

    def test_later_week_production_cannot_change_features(self):
        args = self.inputs(); expected = model.build_week(**args)
        args['team_rows'] += [{**args['team_rows'][0], 'week':2, 'passing_epa':99999}]
        args['qb_rows'] += [{**args['qb_rows'][0], 'week':2, 'passing_epa':99999}]
        self.assertEqual(model.build_week(**args), expected)

    def test_full_synthetic_week_one_advances_real_week_two_without_changing_issued_bytes(self):
        from pgo_season import parse_schedule
        args = self.inputs()
        schedule = parse_schedule((model.SOURCE_DIR / 'schedule.csv.gz').read_bytes())
        args['upcoming_games'] = [g for g in schedule if g['week'] == 2]
        self.assertEqual((len(args['completed_games']), len(args['team_rows']), len(args['qb_rows'])), (16,32,32))
        self.assertEqual(len(args['upcoming_games']),16)
        protected = [p for p in model.SOURCE_DIR.iterdir() if p.is_file()]
        protected += [p for name in ('week1-remaining','week1-full')
                      for p in (model.ROOT / 'docs/evidence/confidence-pool-2026' / name).iterdir() if p.is_file()]
        before = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
        with patch.object(model.ch,'fit_huber_ridge',side_effect=AssertionError('No refit')):
            result = model.build_week(**args)
        self.assertEqual(len(result['teams']),32)
        self.assertEqual(sorted(t['rank'] for t in result['teams']),list(range(1,33)))
        self.assertEqual(len(result['games']),16)
        self.assertEqual({g['game_id'] for g in result['games']},{g['game_id'] for g in args['upcoming_games']})
        ratings={t['team']:t['rating'] for t in result['teams']}
        for game in result['games']:
            e=game['explanation']
            self.assertAlmostEqual(ratings[game['home']]-ratings[game['away']]+e['home_adjustment']+e['rest_adjustment'],game['margin'],places=12)
            self.assertAlmostEqual(game['home_points']-game['away_points'],game['margin'],places=12)
            self.assertAlmostEqual(game['home_points']+game['away_points'],game['total'],places=12)
        self.assertEqual({p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected},before)

    def test_missing_mismatched_or_incomplete_production_blocks(self):
        for change in ('missing_team','wrong_game','missing_qb','wrong_attempts','missing_epa','duplicate_qb'):
            args = self.inputs()
            if change=='missing_team': args['team_rows'].pop()
            if change=='wrong_game': args['team_rows'][0]['game_id']='wrong'
            if change=='missing_qb': args['qb_rows'].pop()
            if change=='wrong_attempts': args['qb_rows'][0]['attempts']=29
            if change=='missing_epa': args['team_rows'][0]['passing_epa']=None
            if change=='duplicate_qb': args['qb_rows'].append(copy.deepcopy(args['qb_rows'][0]))
            with self.subTest(change=change), self.assertRaises(ValueError): model.build_week(**args)

    def test_future_final_later_week_or_locked_next_game_blocks(self):
        for change in ('future_final','later_week','locked','duplicate_game'):
            args = self.inputs()
            if change=='future_final': args['completed_games'][0]['finalized_at']='2026-12-31T23:00:00Z'
            if change=='later_week': args['completed_games'][0]['week']=2
            if change=='locked': args['generated_at']=args['upcoming_games'][0]['kickoff'];args['inputs_as_of']=args['generated_at']
            if change=='duplicate_game': args['completed_games'].append(copy.deepcopy(args['completed_games'][0]))
            with self.subTest(change=change), self.assertRaises(ValueError): model.build_week(**args)

    def test_seed_hash_and_new_fit_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'seed.json';path.write_text('{}')
            with self.assertRaises(ValueError):model.load_seed(path)
        args=self.inputs();args['fit']=copy.deepcopy(args['fit']);args['fit']['coefficients'][0]+=.1
        with self.assertRaises(ValueError):model.build_week(**args)
        args=self.inputs();args['scoring_rates']=copy.deepcopy(args['scoring_rates']);args['scoring_rates']['NE']['pf']+=1
        with self.assertRaises(ValueError):model.build_week(**args)

    def test_ratings_contributions_venue_rest_and_scores_reconcile(self):
        args=self.inputs();args['upcoming_games'][0].update(location='Neutral',home_rest=10,away_rest=6)
        result=model.build_week(**args);teams={t['team']:t for t in result['teams']}
        for team in teams.values():
            self.assertAlmostEqual(math.fsum(team['contributions'].values()),team['rating'],places=12)
        for game in result['games']:
            e=game['explanation']
            self.assertAlmostEqual(teams[game['home']]['rating']-teams[game['away']]['rating'],e['neutral_margin'],places=12)
            self.assertAlmostEqual(e['neutral_margin']+e['home_adjustment']+e['rest_adjustment'],game['margin'],places=12)
            self.assertAlmostEqual(game['home_points']-game['away_points'],game['margin'],places=12)
            self.assertAlmostEqual(game['home_points']+game['away_points'],game['total'],places=12)
        self.assertEqual(result['games'][0]['explanation']['home_adjustment'],0.)
        self.assertNotEqual(result['games'][0]['explanation']['rest_adjustment'],0.)

    def test_qb_calendar_accumulator_matches_independent_elapsed_time_sum(self):
        args=self.inputs();result=model.build_week(**args);row=args['qb_rows'][0];player=row['player_id']
        prior=model._context()['current_strength'];end=model._utc(args['inputs_as_of'])
        factor=2**(-(end-model._utc(prior['last_kickoff'])).total_seconds()/86400/365.25)
        expected=prior['qb_history'][player]['passing_epa']*factor
        by_period={(g['week'],t):g for g in args['completed_games'] for t in (g['home'],g['away'])}
        for r in args['qb_rows']:
            if r['player_id']==player:
                kickoff=model._utc(by_period[r['week'],r['team']]['kickoff'])
                expected+=r['passing_epa']*2**(-(end-kickoff).total_seconds()/86400/365.25)
        self.assertAlmostEqual(result['state']['current_strength']['qb_history'][player]['passing_epa'],expected,places=10)

    def test_after_week_eighteen_returns_final_rankings_without_future_games(self):
        args=self.inputs();base=copy.deepcopy(args);args['completed_games']=[];args['team_rows']=[];args['qb_rows']=[]
        for week in range(1,19):
            delta=timedelta(days=7*(week-1))
            for source in base['completed_games']:
                args['completed_games'].append({**source,'week':week,'game_id':source['game_id'].replace('_01_',f'_{week:02d}_'),
                    'kickoff':(model._utc(source['kickoff'])+delta).isoformat(),
                    'finalized_at':(model._utc(source['finalized_at'])+delta).isoformat()})
            args['team_rows'] += [{**r,'week':week,'game_id':r['game_id'].replace('_01_',f'_{week:02d}_')}for r in base['team_rows']]
            args['qb_rows'] += [{**r,'week':week}for r in base['qb_rows']]
        args.update(upcoming_games=[],completed_week=18)
        args['generated_at']=args['inputs_as_of']=(max(model._utc(g['finalized_at'])for g in args['completed_games'])+timedelta(hours=1)).isoformat()
        result=model.build_week(**args)
        self.assertTrue(result['season_complete']);self.assertEqual(result['week'],18)
        self.assertEqual(len(result['teams']),32);self.assertEqual(result['games'],[])

    def test_no_training_api_called_and_unknown_qb_uses_trained_prior(self):
        args=self.inputs();team=sorted(args['selected_roster'])[0]
        args['selected_roster'][team]['gsis_id']='00-0999999'
        with patch.object(model.ch,'fit_huber_ridge',side_effect=AssertionError('No fit')):
            result=model.build_week(**args)
        row=next(t for t in result['teams'] if t['team']==team)
        self.assertEqual(row['features']['qb_log_dropbacks'],0.)
        self.assertIsNotNone(row['features']['qb_epa_per_dropback'])
        self.assertFalse(row['qb_history_observed'])


if __name__ == '__main__':
    unittest.main()
