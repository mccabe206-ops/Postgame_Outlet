"""A pending week's reviewed starter must survive real rollover and archive replay."""
import copy
from contextlib import ExitStack
import csv
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_expected_starters as starters
import pgo_season as season
import pgo_season_model as model
import pgo_season_rollover as rollover
import pgo_starter_capture as capture
from tests import test_pgo_season_boundaries as boundaries
from tests import test_pgo_season_model as fixtures


def packed(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=sorted({k for row in rows for k in row}))
    writer.writeheader(); writer.writerows(rows)
    return gzip.compress(stream.getvalue().encode(), mtime=0)


class PendingStarterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SeasonModelTests.setUpClass()

    def test_official_starter_resolves_held_next_week_and_preserves_prior_evidence(self):
        args = fixtures.SeasonModelTests().inputs()
        schedule_rows = season.csv_rows((model.SOURCE_DIR / 'schedule.csv.gz').read_bytes())
        for row in schedule_rows:
            if row['week'] == '1' and row['game_type'] == 'REG':
                row.update(home_score='24', away_score='21')
        schedule_raw = packed(schedule_rows)
        schedule = season.parse_schedule(schedule_raw)
        old_games = [g for g in schedule if g['week'] == 1]
        upcoming = next(g for g in schedule if g['game_id'] == '2026_02_CAR_ATL')
        clock = [args['generated_at']]
        roster = copy.deepcopy(list(args['selected_roster'].values()))
        next(r for r in roster if r['team'] == 'ATL')['status'] = 'INA'
        roster.append(next(r for r in season.csv_rows((model.SOURCE_DIR / 'roster.csv.gz').read_bytes())
                           if r['gsis_id'] == '00-0033662'))
        depth = [dict(team=t, gsis_id=r['gsis_id'], pos_abb='QB', pos_rank='1', dt=clock[0])
                 for t, r in args['selected_roster'].items()]
        responses = {season.URLS['schedule']: schedule_raw, season.URLS['team']: packed(args['team_rows']),
                     season.URLS['player']: packed(args['qb_rows']), season.URLS['roster']: packed(roster),
                     season.URLS['depth']: packed(depth)}
        for week in (1, 2):
            events = [dict(id=g['espn_id'], date=g['kickoff'], season=dict(year=2026, type=2),
                           week=dict(number=week), competitions=[dict(id=g['espn_id'],
                           status=dict(type=dict(completed=week == 1, state='post' if week == 1 else 'pre',
                                                 name='STATUS_FINAL' if week == 1 else 'STATUS_SCHEDULED')),
                           competitors=[dict(homeAway=side, team=dict(abbreviation=g[side]), score=score)
                                        for side, score in [('home', '24'), ('away', '21')]])])
                      for g in schedule if g['week'] == week]
            responses[season.SCOREBOARD.format(season=2026, week=week)] = season.canonical(
                dict(season=dict(year=2026, type=2), week=dict(number=week), events=events))
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary) / 'season'
            config = Path(temporary) / 'data/pgo_starter_announcements.json'
            stack.enter_context(patch.object(starters, 'CONFIG', config))
            stack.enter_context(patch.object(model.ch, 'fit_huber_ridge', side_effect=AssertionError('No fitting')))
            stack.enter_context(patch('urllib.request.urlopen', side_effect=AssertionError('No live network')))
            builder = boundaries.SeasonBoundaryTests()
            issued = [builder.game(g['game_id'], g['home'], g['away'], g['kickoff']) for g in old_games]
            before = builder.state(issued)
            before['checked_at'] = (min(season.utc(g['kickoff']) for g in old_games) - season.timedelta(hours=2)).isoformat()
            before['weeks'][0]['games'] = season.allocate_confidence(issued, before['calibration'])
            with patch.object(season, 'now', return_value=before['checked_at']):
                season.save_state(before, root)

            def fetch(url, destination):
                raw = responses[url]
                suffix = '.csv.gz' if url in season.URLS.values() else '.json'
                relative = 'source-archive/' + season.sha(raw) + suffix
                path = destination / relative; path.parent.mkdir(exist_ok=True)
                if not path.exists(): path.write_bytes(raw)
                return raw, dict(url=url, path=relative, sha256=season.sha(raw), bytes=len(raw), captured_at=clock[0])

            stack.enter_context(patch.object(season, 'fetch_source', side_effect=fetch))
            stack.enter_context(patch.object(season, 'now', side_effect=lambda: clock[0]))
            stack.enter_context(patch.object(season, 'legacy_models', return_value=[]))
            stack.enter_context(patch.object(season, 'refresh_availability', return_value=[]))
            for name in ('refresh_replacement_sources', 'refresh_offensive_identity_source', 'refresh_experiments'):
                stack.enter_context(patch.object(season, name))
            held = season.refresh(root)
            self.assertEqual((held['status'], held['current_week']), ('BLOCKED', 1))
            self.assertIn('ATL', held['blocked_reason'])
            self.assertTrue(any(r['url'] == season.URLS['roster'] for r in held['source_captures']),
                            'Failed rollover must retain the captured current roster for starter review')
            self.assertEqual(season.load_current(root), held)
            protected = {p: p.read_bytes() for p in root.rglob('*') if p.is_file() and p.name != 'current.json'}

            for invalid in ('incomplete', 'wrong_week', 'duplicate', 'tampered_final'):
                with self.subTest(invalid=invalid):
                    bad = copy.deepcopy(held)
                    if invalid == 'incomplete': bad['results'].pop()
                    elif invalid == 'wrong_week':
                        next(g for g in bad['schedule'] if g['game_id'] == upcoming['game_id'])['week'] = 3
                    elif invalid == 'duplicate': bad['schedule'].append(copy.deepcopy(upcoming))
                    else: bad['results'][0]['home_score'] += 1
                    with patch.object(capture, 'load_current', return_value=bad), self.assertRaises(ValueError):
                        capture._context(root, upcoming['game_id'])

            # Explicitly synthetic official response for this offline regression only.
            published = clock[0]
            clock[0] = (season.utc(clock[0]) + season.timedelta(minutes=1)).isoformat()
            statement = 'Cooper Rush will start for the Atlanta Falcons against the Carolina Panthers in Week 2.'
            article = dict(**{'@type': 'NewsArticle'}, headline='Falcons starter against Panthers in Week 2',
                           articleBody=statement, datePublished=published, dateModified=published)
            body = ('<script type="application/ld+json">' + json.dumps(article) + '</script>').encode()
            url = 'https://www.atlantafalcons.com/news/offline-week2-starter-fixture'
            draft = capture.capture(url, upcoming['game_id'], 'ATL', '00-0033662', statement, root=root,
                                    clock=lambda: clock[0], fetch=lambda _: dict(
                                        status=200, final_url=url, headers={}, body=body))
            reviewed = capture.review(draft, root=root, config=config, clock=lambda: clock[0])
            capture.activate(reviewed, root=root, config=config, clock=lambda: clock[0])
            self.assertEqual(season.load_current(root), held, 'Starter activation cannot write forecasts')
            clock[0] = (season.utc(clock[0]) + season.timedelta(minutes=1)).isoformat()
            updated = season.refresh(root)
            self.assertEqual((updated['status'], updated['current_week']), ('READY', 2), updated.get('blocked_reason'))
            self.assertEqual(season.load_current(root), updated)
            self.assertEqual(rollover.check_preserved(held, updated), 16)
            self.assertEqual({p: p.read_bytes() for p in protected}, protected)
            observation = rollover.observe(root)
            self.assertEqual(observation['status'], 'VERIFIED', observation)
            self.assertEqual(observation['checks']['next_fixtures'], 16)
            self.assertEqual(len(updated['rankings']['teams']), 32)
            week = next(w for w in updated['weeks'] if w['week'] == 2)
            game = next(g for g in week['games'] if g['game_id'] == upcoming['game_id'])
            self.assertEqual(game['expected_qbs']['ATL'], 'Cooper Rush')
            starters.verify(game, game['starter_announcements'], root)
            ref = game['starter_announcements'][0]['source']
            self.assertIn(ref, updated['rankings']['source_captures'])
            self.assertEqual(sum(g['confidence']['points'] for g in week['games']), 136)


if __name__ == '__main__':
    unittest.main()
