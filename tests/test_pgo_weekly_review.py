import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_season as season
from tests import test_pgo_market_benchmark


class WeeklyReviewTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('pgo_weekly_review'),
                             'Automatic immutable completed-week reviews are missing')
        import pgo_weekly_review
        return pgo_weekly_review

    def fixture(self):
        state = test_pgo_market_benchmark.MarketBenchmarkTests().fixture()
        game = state['weeks'][0]['games'][0]
        game['total'] = 45
        game['confidence'] = dict(points=10, win_probability=.6,
            probabilities=dict(home=.6, away=.39, tie=.01), expected_points=6,
            added_after_lock=True)
        return state

    def test_full_scheduled_week_required_and_future_week_does_not_leak_in(self):
        api = self.api(); state = self.fixture()
        pending = copy.deepcopy(state); pending['results'] = []
        self.assertIsNone(api.summarize_week(pending, 1))
        missing = copy.deepcopy(state); missing['schedule'].append(dict(missing['schedule'][0], game_id='missing'))
        self.assertIsNone(api.summarize_week(missing, 1))
        missing['results'].append(dict(missing['results'][0], game_id='missing'))
        with self.assertRaisesRegex(ValueError, 'forecast inventory'):
            api.summarize_week(missing, 1)
        state['schedule'].append(dict(state['schedule'][0], week=2, game_id='next'))
        out = api.summarize_week(state, 1)
        self.assertEqual(out['games_total'], 1)  # Scheduled inventory, never a hardcoded 16.
        self.assertEqual(out['accuracy']['record']['wins'], 1)
        self.assertIsNone(api.summarize_week(state, 2))

    def test_timing_and_metric_denominators_recompute_without_mutation(self):
        api = self.api(); state = self.fixture(); before = copy.deepcopy(state)
        state['weeks'][0]['games'][0]['grade'] = 'L'
        out = api.summarize_week(state, 1)
        self.assertEqual(out['accuracy']['record']['wins'], 1)
        self.assertEqual(out['accuracy']['probabilities']['n'], 0)
        self.assertEqual(out['accuracy']['probabilities']['reasons'], {'late_confidence': 1})
        self.assertEqual(out['accuracy']['confidence']['earned_points'], 10)
        self.assertEqual(out['accuracy']['confidence']['late_count'], 1)
        self.assertEqual(out['market']['ats']['wins'], 1)
        self.assertAlmostEqual(out['accuracy']['margin_mae']['value'], 1.75)
        del state['weeks'][0]['games'][0]['grade']
        self.assertEqual(state, before)
        for kind in ('missing', 'late'):
            bad = copy.deepcopy(state)
            if kind == 'missing': bad['ats']['games'] = []
            else: bad['ats']['games'][0]['issued_at'] = bad['ats']['games'][0]['lock_at']
            self.assertEqual(api.summarize_week(bad, 1)['market']['ats']['unavailable'], 1)

    def test_duplicate_final_and_identity_mismatch_fail_closed(self):
        api = self.api(); state = self.fixture()
        state['results'].append(copy.deepcopy(state['results'][0]))
        with self.assertRaises(ValueError): api.summarize_week(state, 1)
        state['results'].pop(); state['results'][0]['week'] = 2
        with self.assertRaises(ValueError): api.summarize_week(state, 1)

    def archive(self, root, state, stamp='20260914T000000000000Z'):
        state = dict(state, schema_version=1)
        archive = root / 'docs/evidence/season-2026'
        directory = archive / ('runs-v2/' + stamp); directory.mkdir(parents=True)
        raw = season.canonical(state)
        (directory/'state.json').write_bytes(raw)
        manifest = season.canonical(dict(files={'state.json':dict(sha256=season.sha(raw), bytes=len(raw))}))
        (directory/'manifest.json').write_bytes(manifest)
        pointer = dict(path='runs-v2/' + stamp, manifest_sha256=season.sha(manifest))
        (archive/'current.json').write_bytes(season.canonical(pointer))
        return pointer

    def test_generation_is_idempotent_and_old_report_and_provisional_stay_frozen(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); state = self.fixture(); self.archive(root, state)
            provisional = root/'docs/analysis/2026-week1-20260914.html'
            provisional.parent.mkdir(parents=True); provisional.write_bytes(b'original provisional')
            with patch.object(api, 'verify_sources'):
                paths = api.publish(root)
                self.assertEqual(len(paths), 2)
                first = {name: (root/name).read_bytes() for name in paths}
                self.assertEqual(api.publish(root), [])
                newer = copy.deepcopy(state); newer['checked_at'] = '2026-09-14T02:00:00Z'
                self.archive(root, newer, '20260914T020000000000Z')
                self.assertEqual(api.publish(root), [])
                self.assertEqual({name:(root/name).read_bytes() for name in paths}, first)
                self.assertEqual(provisional.read_bytes(), b'original provisional')
                html = next(root/name for name in paths if name.endswith('.html'))
                self.assertIn('Late pool entries', html.read_text())
                self.assertIn('Probability accuracy', html.read_text())
                html.write_bytes(html.read_bytes() + b'tampered')
                with self.assertRaisesRegex(ValueError, 'report differs'):
                    api.publish(root)

    def test_new_report_pairs_require_exact_replay_and_source_hash(self):
        api = self.api()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.archive(root, self.fixture())
            with patch.object(api, 'verify_sources'):
                paths = api.publish(root)
                api.verify_publication(root, paths)
                with self.assertRaisesRegex(ValueError, 'pair'):
                    api.verify_publication(root, paths[:1])
                receipt_path = next(root/name for name in paths if name.endswith('.json'))
                receipt = json.loads(receipt_path.read_bytes()); receipt['source_pointer']['manifest_sha256'] = '0'*64
                receipt_path.write_bytes(season.canonical(receipt))
                with self.assertRaisesRegex(ValueError, 'manifest hash'):
                    api.verify_publication(root, paths)

    def test_source_replay_rejects_missing_slate_changed_final_and_quote(self):
        api = self.api()
        from tests.test_pgo_ats import ATSTests
        helper = ATSTests()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); state, payload = helper.fixture()
            helper.archive(root, state, payload)
            state['ats'] = api.pgo_ats.refresh(state, None, root, state['checked_at'])
            schedule = copy.deepcopy(state['schedule'])
            final_payload = copy.deepcopy(payload)
            comp = final_payload['events'][0]['competitions'][0]
            comp['status']['type'].update(completed=True, state='post', name='STATUS_FINAL')
            for side in comp['competitors']: side['score'] = '24' if side['homeAway'] == 'home' else '21'
            ref = helper.archive(root, state, final_payload, '2026-09-13T21:00:00Z')
            state['results'] = [dict(r, source=ref) for r in season.parse_scoreboard(final_payload, schedule, ref['captured_at'])['results']]
            state['checked_at'] = '2026-09-13T22:00:00Z'
            schedule_raw = b'Captured schedule fixture'
            schedule_ref = dict(url=season.URLS['schedule'], path='source-archive/'+season.sha(schedule_raw)+'.csv.gz',
                sha256=season.sha(schedule_raw), bytes=len(schedule_raw), captured_at=state['checked_at'])
            (root/schedule_ref['path']).write_bytes(schedule_raw)
            state['source_captures'].append(schedule_ref)
            with patch.object(season, 'parse_schedule', return_value=schedule):
                api.verify_sources(state, 1, root)
                bad = copy.deepcopy(state); bad['results'][0]['home_score'] += 1
                with self.assertRaisesRegex(ValueError, 'explicit provider FINAL'): api.verify_sources(bad, 1, root)
                bad = copy.deepcopy(state); bad['ats']['games'][0]['home_handicap'] = -7
                with self.assertRaisesRegex(ValueError, 'sportsbook line'): api.verify_sources(bad, 1, root)
                bad = copy.deepcopy(state); bad['schedule'] = []
                with self.assertRaisesRegex(ValueError, 'slate differs'): api.verify_sources(bad, 1, root)
                (root/ref['path']).write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'Source hash'): api.verify_sources(state, 1, root)

    def test_all_publishers_generate_before_views_and_stage_report_pairs(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('update-board.yml', 'update-season.yml', 'publish-edition.yml'):
            workflow = (root/'.github/workflows'/name).read_text(encoding='utf-8')
            with self.subTest(workflow=name):
                self.assertIn('python pgo_weekly_review.py', workflow)
                self.assertLess(workflow.index('python pgo_weekly_review.py'), workflow.index('python pgo_comparison.py --refresh-mccabe'))
                self.assertIn('if [ -d docs/analysis/weekly ]; then git add docs/analysis/weekly; fi', workflow)
        self.assertIn('tests.test_pgo_weekly_review', (root/'.github/workflows/update-season.yml').read_text())

    def test_ats_side_and_line_are_named_in_the_report(self):
        api = self.api(); report = api.summarize_week(self.fixture(),1)
        rendered = api.render(report, dict(state_url='https://example.test/state',state_sha256='a'*64,
                              manifest_url='https://example.test/manifest',manifest_sha256='b'*64)).decode()
        self.assertIn('SEA -3.5', rendered)

    def test_accuracy_links_include_completed_and_preserved_provisional_reports(self):
        import pgo_season_accuracy
        import pgo_season_view
        summary = pgo_season_accuracy.summarize(self.fixture())
        self.assertIn('weekly_reviews', __import__('inspect').signature(pgo_season_view._accuracy).parameters)
        rendered = pgo_season_view._accuracy(summary, weekly_reviews=[dict(
            href='analysis/weekly/2026-week1-final.html', label='Week 1: completed review')])
        self.assertIn('analysis/weekly/2026-week1-final.html', rendered)
        self.assertIn('analysis/2026-week1-20260914.html', rendered)


if __name__ == '__main__':
    unittest.main()
