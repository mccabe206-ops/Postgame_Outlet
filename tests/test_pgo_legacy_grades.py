import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import pgo_season as season


class LegacyGradeTests(unittest.TestCase):
    def setUp(self):
        self.game = dict(game_id='2026_05_CHI_GB', season=2026, week=5, game_type='REG',
            home='GB', away='CHI', kickoff='2026-10-11T17:00:00+00:00', margin=3, total=48,
            home_points=25.5, away_points=22.5, issued_at='2026-10-06T14:27:10+00:00',
            source_edition='weekly', inputs_as_of='2026-10-06T14:27:10+00:00', confidence=None,
            lock_at='2026-10-11T16:00:00+00:00')
        self.final = dict(game_id=self.game['game_id'], season=2026, week=5, game_type='REG',
            home_team='GB', away_team='CHI', kickoff=self.game['kickoff'], home_score=24,
            away_score=20, actual_margin=4, finalized_at='2026-10-11T21:00:00Z')
        self.model = dict(name='Legacy', edition='legacy', issued_at=self.game['issued_at'],
            games=[dict(self.game, kickoff='2026-10-11T20:25:00+00:00', lock_at='2026-10-11T19:25:00Z')])
        self.loader = patch.object(season, 'legacy_models', return_value=[self.model])
        self.loader.start(); self.addCleanup(self.loader.stop)

    def state(self, checked='2026-10-11T22:00:00Z'):
        return dict(schema_version=1, season=2026, status='READY', checked_at=checked,
            current_week=5, rankings={}, sources=[], results=[],
            weeks=[dict(week=5, games=[copy.deepcopy(self.game)])])

    def test_kickoff_hold_preserves_weekly_grading_and_direct_record_is_strict(self):
        with self.assertRaisesRegex(ValueError, 'Grade identity differs'):
            season.record(self.model['games'], [self.final])
        state = self.state()
        season.decorate(state, [self.final])
        self.assertEqual(state['weeks'][0]['games'][0]['grade'], 'W')
        self.assertIsNone(state['model_records'][1]['wins'])
        self.assertEqual(state['legacy_grading_check']['models']['legacy']['game_ids'], [self.game['game_id']])

    def saved_hold(self, root):
        previous = self.state('2026-10-11T16:00:00Z')
        season.decorate(previous, [])
        with patch.object(season, 'now', return_value='2026-10-11T16:01:00Z'):
            season.save_state(previous, root)
        pointer = season.read_json(root / 'current.json')
        state = self.state()
        season.decorate(state, [self.final], previous=previous, previous_pointer=pointer)
        return previous, pointer, state

    def test_first_and_repeated_hold_save_load_preserve_exact_source_and_original_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); previous, pointer, state = self.saved_hold(root)
            row = copy.deepcopy(previous['model_records'][1])
            self.assertEqual(state['model_records'][1], row)
            hold = copy.deepcopy(state['legacy_grading_check']['models']['legacy'])
            self.assertEqual(hold['record_checked_at'], previous['checked_at'])
            self.assertEqual(hold['record_source'], {k:pointer[k] for k in ('path','manifest_sha256','checked_at')})
            original = copy.deepcopy(state['weeks'][0]['games'][0])
            with patch.object(season, 'now', return_value='2026-10-11T22:01:00Z'):
                season.save_state(state, root)
            self.assertEqual(season.load_current(root), state)
            again = copy.deepcopy(state); again['checked_at'] = '2026-10-11T23:00:00Z'
            season.decorate(again, [self.final], previous=state,
                previous_pointer=season.read_json(root / 'current.json'))
            self.assertEqual(again['legacy_grading_check']['models']['legacy'], hold)
            self.assertEqual(again['model_records'][1], row)
            self.assertEqual(again['weeks'][0]['games'][0], original)
            self.assertEqual(again['results'], [self.final])
            with patch.object(season, 'now', return_value='2026-10-11T23:01:00Z'):
                season.save_state(again, root)
            self.assertEqual(season.load_current(root), again)

    def test_healthy_and_wrong_team_and_primary_conflicts(self):
        state = self.state()
        season.decorate(state, [])
        self.assertEqual(state['legacy_grading_check']['status'], 'READY')
        self.assertEqual(state['model_records'][1]['pending'], 1)
        self.model['games'][0]['home'] = 'BUF'
        with self.assertRaisesRegex(ValueError, 'Grade identity differs'):
            season.decorate(self.state(), [self.final])
        self.model['games'][0]['home'] = 'GB'
        state = self.state(); state['weeks'][0]['games'][0]['kickoff'] = self.model['games'][0]['kickoff']
        with self.assertRaisesRegex(ValueError, 'Grade identity differs'):
            season.decorate(state, [self.final])

    def test_custody_rejects_forged_counts_sources_clocks_and_missing_holds(self):
        import pgo_legacy_grades as legacy
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); previous, pointer, good = self.saved_hold(root)
            mutations = [lambda s:s['model_records'][1].update(wins=99),
                lambda s:s['legacy_grading_check']['models']['legacy'].update(record_checked_at=s['checked_at']),
                lambda s:s['legacy_grading_check']['models']['legacy']['record_source'].update(manifest_sha256='0'*64),
                lambda s:s['legacy_grading_check']['models']['legacy']['record_source'].update(checked_at=s['checked_at']),
                lambda s:s['legacy_grading_check']['models']['legacy'].update(game_ids=[]),
                lambda s:s['legacy_grading_check'].update(models={}),
                lambda s:s.pop('legacy_grading_check'),
                lambda s:s['legacy_grading_check']['models'].update({'pgo-weekly-2026':{}}),
                lambda s:s['model_records'].append(copy.deepcopy(s['model_records'][1])),
                lambda s:s['legacy_grading_check'].update(status='READY'),
                lambda s:s['legacy_grading_check'].update(checked_at=previous['checked_at']),
                lambda s:s['legacy_grading_check']['models']['legacy'].update(record_source=None)]
            for mutate in mutations:
                bad = copy.deepcopy(good); mutate(bad)
                with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                    legacy.validate(bad, root, pointer, durable='2026-10-11T22:01:00Z')
            bad = copy.deepcopy(good); bad['model_records'][1]['pending'] = 50
            before = (root / 'current.json').read_bytes()
            with self.assertRaises(ValueError), patch.object(season, 'now', return_value='2026-10-11T22:01:00Z'):
                season.save_state(bad, root)
            self.assertEqual((root / 'current.json').read_bytes(), before)

    def test_unavailable_record_has_no_verified_counts_and_remains_unavailable(self):
        import pgo_legacy_grades as legacy
        state = self.state(); season.decorate(state, [self.final])
        self.assertTrue(all(state['model_records'][1][k] is None for k in legacy.COUNTS))
        with tempfile.TemporaryDirectory() as tmp:
            legacy.validate(state, tmp, None)
            with patch.object(season, 'now', return_value='2026-10-11T22:01:00Z'):
                season.save_state(state, tmp)
            again = self.state('2026-10-11T23:00:00Z')
            season.decorate(again, [self.final], previous=state,
                previous_pointer=season.read_json(Path(tmp) / 'current.json'))
            self.assertEqual(again['model_records'][1], state['model_records'][1])
            self.assertIsNone(again['legacy_grading_check']['models']['legacy']['record_source'])
            bad = copy.deepcopy(state); bad['model_records'][1]['wins'] = 0
            with self.assertRaises(ValueError): legacy.validate(bad, tmp, None)

    def test_accuracy_excludes_held_legacy_but_keeps_healthy_models(self):
        import pgo_season_accuracy as accuracy
        state = self.state(); season.decorate(state, [self.final])
        state['accuracy_models'] = [self.model, dict(name='Healthy', edition='healthy', games=[self.game])]
        summary = accuracy.summarize(state)
        self.assertEqual(summary['primary']['record']['wins'], 1)
        self.assertEqual([m['edition'] for m in summary['models']], ['pgo-weekly-2026', 'healthy'])
        self.assertEqual([m['model_edition'] for m in summary['comparisons']], ['healthy'])
        self.assertEqual(summary['held_models'], state['legacy_grading_check']['models'])
        state['legacy_grading_check']['models']['pgo-weekly-2026'] = {}
        with self.assertRaises(ValueError): accuracy.summarize(state)

    def test_healthy_count_types_are_validated(self):
        import pgo_legacy_grades as legacy
        state = self.state(); season.decorate(state, [])
        state['model_records'][1]['wins'] = False
        with self.assertRaises(ValueError): legacy.validate(state, '.', None)

    def test_present_malformed_component_is_not_an_old_optional_state(self):
        import pgo_legacy_grades as legacy
        state = self.state(); season.decorate(state, [])
        for malformed in (None, [], 'READY', {'status':'READY'}, dict(state['legacy_grading_check'], extra=True)):
            bad = dict(state, legacy_grading_check=malformed)
            with self.subTest(component=malformed), self.assertRaises(ValueError):
                legacy.validate(bad, '.', None)

    def test_old_states_read_without_component_only_when_no_kickoff_conflict(self):
        import pgo_legacy_grades as legacy
        state = self.state(); season.decorate(state, [])
        state.pop('legacy_grading_check')
        legacy.validate(state, '.', None)
        state['results'] = [self.final]
        with self.assertRaisesRegex(ValueError, 'omitted'):
            legacy.validate(state, '.', None)

    def test_old_empty_state_needs_no_legacy_snapshot_io(self):
        import pgo_legacy_grades as legacy
        with patch.object(season, 'legacy_models', side_effect=AssertionError('Unexpected legacy I/O')):
            legacy.validate(self.state(), '.', None)

    def test_load_rejects_rehashed_forgery_and_omitted_component(self):
        import gzip
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); previous, pointer, good = self.saved_hold(root)
            with patch.object(season, 'now', return_value='2026-10-11T22:01:00Z'):
                directory = season.save_state(good, root)
            for change in ('counts', 'component', 'clock', 'source'):
                bad = copy.deepcopy(good)
                if change == 'counts': bad['model_records'][1]['pending'] = 999
                if change == 'component': bad.pop('legacy_grading_check')
                if change == 'clock': bad['legacy_grading_check']['models']['legacy']['record_checked_at'] = bad['checked_at']
                if change == 'source': bad['legacy_grading_check']['models']['legacy']['record_source'] = season.read_json(root/'current.json')
                payload = gzip.compress(season.canonical(bad), mtime=0)
                (directory/'state.json.gz').write_bytes(payload)
                manifest = season.read_json(directory/'manifest.json')
                manifest['files']['state.json.gz'] = dict(sha256=season.sha(payload), bytes=len(payload))
                raw = season.canonical(manifest); (directory/'manifest.json').write_bytes(raw)
                current = season.read_json(root/'current.json'); current['manifest_sha256'] = season.sha(raw)
                (root/'current.json').write_bytes(season.canonical(current))
                with self.subTest(change=change), self.assertRaises(ValueError): season.load_current(root)

    def test_shared_source_reads_are_deduplicated_and_repeated_source_cannot_change(self):
        import pgo_legacy_grades as legacy
        import pgo_season_rollover as rollover
        models = [self.model, dict(self.model, name='Second legacy', edition='second-legacy')]
        with patch.object(season, 'legacy_models', return_value=models), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); previous, pointer, good = self.saved_hold(root)
            with patch.object(rollover, 'load_archive', wraps=rollover.load_archive) as read:
                legacy.validate(good, root, pointer)
            self.assertEqual(read.call_count, 1)
            with patch.object(season, 'now', return_value='2026-10-11T22:01:00Z'):
                season.save_state(good, root)
            again = self.state('2026-10-11T23:00:00Z'); latest = season.read_json(root/'current.json')
            season.decorate(again, [self.final], previous=good, previous_pointer=latest)
            again['legacy_grading_check']['models']['legacy']['record_source'] = {k:latest[k] for k in legacy.POINTER_FIELDS}
            with self.assertRaises(ValueError): legacy.validate(again, root, latest)

    def test_previous_counts_must_replay_and_source_clock_is_authenticated(self):
        import pgo_legacy_grades as legacy
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); previous, pointer, good = self.saved_hold(root)
            previous['model_records'][1]['wins'] = 1
            with self.assertRaisesRegex(ValueError, 'does not replay'):
                season.decorate(self.state(), [self.final], previous=previous, previous_pointer=pointer)
            bad = copy.deepcopy(good)
            bad['checked_at'] = '2026-10-11T15:00:00Z'
            bad['legacy_grading_check']['checked_at'] = bad['checked_at']
            with self.assertRaisesRegex(ValueError, 'not historical'):
                legacy.validate(bad, root, pointer)

    def test_bootstrap_refresh_component_uses_final_check_clock(self):
        from contextlib import ExitStack
        state = self.state('2026-10-11T16:00:00Z'); state['rankings']['completed_week'] = 0
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(season, 'bootstrap', return_value=state))
            stack.enter_context(patch.object(season, 'now', side_effect=['2026-10-11T16:01:00Z',
                '2026-10-11T16:02:00Z', '2026-10-11T16:03:00Z', '2026-10-11T16:04:00Z']))
            stack.enter_context(patch.object(season, 'fetch_inputs', return_value=([self.game], [], [], {})))
            for name in ('refresh_availability', 'refresh_replacement_sources', 'refresh_offensive_identity_source', 'refresh_experiments'):
                stack.enter_context(patch.object(season, name, return_value=[]))
            stack.enter_context(patch('pgo_current_projection.refresh', return_value=[]))
            stack.enter_context(patch('pgo_statistics_review.refresh_review', return_value={}))
            result = season.refresh(tmp)
            self.assertEqual(result['legacy_grading_check']['checked_at'], result['checked_at'])
            self.assertEqual(season.load_current(tmp), result)



if __name__ == '__main__':
    unittest.main()
