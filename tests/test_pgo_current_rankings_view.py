import copy
import unittest

import pgo_season_view as view
from tests.test_pgo_current_projection_view import projection_fixture


def fixture():
    data, _, projection = projection_fixture()
    data['rankings']['completed_week'] = 1
    snapshot = copy.deepcopy(data['rankings'])
    snapshot.update(edition='current-lineup', generated_at=projection['issued_at'])
    teams = snapshot['teams']
    teams[0]['rating'], teams[1]['rating'] = teams[1]['rating'], teams[0]['rating']
    teams[0]['contributions'], teams[1]['contributions'] = teams[1]['contributions'], teams[0]['contributions']
    teams[0]['rank'], teams[1]['rank'] = 2, 1
    teams[0]['qb_name'] = 'Newest quarterback'
    projection['rankings'] = snapshot
    return data, snapshot


class CurrentRankingsViewTests(unittest.TestCase):
    def test_one_newest_snapshot_drives_rows_explanations_comparison_and_freshness(self):
        data, snapshot = fixture()
        older = copy.deepcopy(data['current_projections']['current'])
        older['rankings'] = copy.deepcopy(snapshot)
        older['rankings'].update(generated_at='2026-09-16T22:20:00Z', edition='older-lineup')
        older['rankings']['teams'][0]['qb_name'] = 'Older quarterback'
        older['game_id'] = 'old'
        data['current_projections']['old'] = older
        # Select directly so another game's forecast presentation is outside this test.
        self.assertIs(view._ranking_snapshot(data), snapshot)
        del data['current_projections']['old']
        mccabe = dict(as_of=data['checked_at'], rows=[dict(abbr=t['team'], rank=t['rank'],
                       qb_name=t['qb_name']) for t in data['rankings']['teams']])
        before = copy.deepcopy(data)
        page = view.render_season(data, mccabe=mccabe)
        ranking = page.split('id="season-rankings"', 1)[1].split('<h3 id="season-records"', 1)[0]
        code = snapshot['teams'][0]['team']
        self.assertIn(f'data-season-team="{code}"><td class="pgo-rank">2</td>', ranking)
        self.assertIn(f'#{2} {code}: why this rating', ranking)
        self.assertIn('Expected quarterback: Newest quarterback.', ranking)
        self.assertIn('PGO: Newest quarterback', ranking)
        self.assertIn('Different QB assumptions', ranking)
        self.assertIn('current-lineup', ranking)
        self.assertIn('Current-lineup calculation', ranking)
        self.assertIn('separate from original weekly forecasts and grades', ranking)
        freshness = page.split('Rankings calculated', 1)[1].split('</dd>', 1)[0]
        self.assertIn(snapshot['generated_at'], freshness)
        self.assertEqual(data, before)

    def test_incompatible_old_or_future_calculations_keep_weekly_fallback(self):
        for changes in (dict(completed_week=0), dict(generated_at='2026-09-16T20:00:00Z'),
                        dict(generated_at='2026-09-16T23:00:00Z')):
            data, snapshot = fixture()
            snapshot.update(changes)
            with self.subTest(changes=changes):
                self.assertIs(view._ranking_snapshot(data), data['rankings'])
        data, _ = fixture()
        data['current_projections']['current']['week'] = 1
        self.assertIs(view._ranking_snapshot(data), data['rankings'])
        del data['current_projections']['current']['rankings']
        self.assertIs(view._ranking_snapshot(data), data['rankings'])

    def test_malformed_order_or_contributions_fail_closed(self):
        for change in (lambda s: s['teams'][0].update(rank=1),
                       lambda s: s['teams'][0].update(rating=99., contributions={'pgo_v0':99.}),
                       lambda s: s['teams'][0].update(rating=99.),
                       lambda s: s['teams'].pop(),
                       lambda s: s['teams'][0].update(contributions={'pgo_v0':99.})):
            data, snapshot = fixture()
            change(snapshot)
            with self.subTest(change=change), self.assertRaises(ValueError):
                view.render_season(data)

    def test_equally_recent_conflicting_calculations_fail_closed(self):
        data, snapshot = fixture()
        duplicate = copy.deepcopy(data['current_projections']['current'])
        data['current_projections']['old'] = duplicate
        self.assertIs(view._ranking_snapshot(data), snapshot)
        duplicate['rankings']['teams'][0]['qb_name'] = 'Conflicting quarterback'
        with self.assertRaises(ValueError):
            view._ranking_snapshot(data)
