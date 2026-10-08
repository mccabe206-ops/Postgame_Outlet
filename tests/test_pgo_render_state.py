"""One verified season snapshot feeds a render; omission still validates disk."""
import copy
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pgo_comparison as comparison
import pgo_current_board as board
import pgo_forecast_lab as lab
import pgo_model_updates as updates
import pgo_season as season
from pgo_render_state import SEASON_UNLOADED
from tests import test_pgo_forecast_lab as lab_fixtures


class RenderStateTests(unittest.TestCase):
    def state(self):
        return dict(schema_version=1, season=2026, checked_at='2026-10-04T17:00:00Z',
                    weeks=[], results=[], rankings={}, availability_context={},
                    preserved={'issued_at': '2026-10-01T12:00:00Z', 'margin': 2.5})

    @contextmanager
    def render_fixture(self, root):
        """Keep real state plumbing; replace unrelated historical model loading."""
        candidate = root / 'evidence/forecast-lab-2026/september-09-postseason'
        candidate.mkdir(parents=True)
        (candidate / 'manifest.json').write_bytes(b'fixture manifest')
        (candidate.parent / 'weekly-postseason').mkdir()
        weekly = candidate.parent / 'weekly'
        (weekly / 'results').mkdir(parents=True)
        snapshot = candidate.parent / 'snapshot'
        (snapshot / 'results').mkdir(parents=True)
        captures = candidate.parent / 'results'
        captures.mkdir()
        with ExitStack() as stack:
            for target, value in ((updates, {'DEFAULT_DIR': candidate}),
                                  (lab, {'WEEKLY_DIR': weekly, 'SNAPSHOT_DIR': snapshot,
                                         'CAPTURE_ROOT': captures})):
                for name, replacement in value.items():
                    stack.enter_context(patch.object(target, name, replacement))
            stack.enter_context(patch('pgo_forecast_postseason.load_snapshot', return_value={'games': []}))
            stack.enter_context(patch.object(lab.pgo_forecast_weekly, 'load_weekly', return_value={'games': []}))
            stack.enter_context(patch.object(updates, 'render_updates', return_value='<div>Earlier editions</div>'))
            stack.enter_context(patch.object(updates, '_load_defense_test', return_value=None))
            stack.enter_context(patch('pgo_season_accuracy.load_models', return_value=[]))
            stack.enter_context(patch('pgo_season_accuracy.summarize', return_value={}))
            stack.enter_context(patch('pgo_market_benchmark.summarize', return_value={}))
            stack.enter_context(patch('pgo_weekly_review.links', return_value=[]))
            stack.enter_context(patch.object(comparison, 'mccabe_source_timestamp', return_value='2026-10-01T12:00:00Z'))
            stack.enter_context(patch.object(comparison, 'load_mccabe_rows', return_value=[]))
            stack.enter_context(patch('pgo_availability_view.render_current_scenario', return_value=''))
            rendered = stack.enter_context(patch('pgo_season_view.render_season',
                return_value='<section id="pgo-season">Current season</section>'))
            result_reader = stack.enter_context(patch.object(lab, 'load_results', wraps=lab.load_results))
            yield rendered, result_reader

    def test_current_updates_resolves_once_and_forwards_without_mutation(self):
        for supplied in (SEASON_UNLOADED, None, self.state()):
            with self.subTest(explicit_none=supplied is None, omitted=supplied is SEASON_UNLOADED), \
                 tempfile.TemporaryDirectory() as temp:
                state = self.state() if supplied is SEASON_UNLOADED else supplied
                before = copy.deepcopy(state)
                with self.render_fixture(Path(temp)) as (rendered, results), \
                     patch.object(season, 'load_current', return_value=state) as load:
                    kwargs = {} if supplied is SEASON_UNLOADED else {'season_state': supplied}
                    output = updates.render_current_updates(**kwargs)
                self.assertEqual(load.call_count, int(supplied is SEASON_UNLOADED))
                results.assert_called_once()
                self.assertIs(results.call_args.kwargs['season_state'], state)
                if state is None:
                    rendered.assert_not_called()
                    self.assertEqual(output, '<div>Earlier editions</div>')
                else:
                    self.assertIs(rendered.call_args.args[0], state)
                    self.assertIn('id="pgo-season"', output)
                self.assertEqual(state, before)

    def test_results_explicit_none_never_reloads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(lab, 'CAPTURE_ROOT', root), \
                 patch.object(season, 'load_current', side_effect=AssertionError('Unexpected reload')) as load:
                self.assertEqual(lab.load_results(root, {'games': []}, season_state=None), ([], []))
            load.assert_not_called()

    def test_supplied_results_still_enforce_identity_scores_and_capture_clock(self):
        lock = lab_fixtures.ForecastLabTests().synthetic_lock()
        game = lock['games'][0]
        result = dict(game_id=game['game_id'], season=game['season'], week=game['week'],
                      kickoff=game['kickoff'], game_type=game['game_type'],
                      home_team=game['home'], away_team=game['away'], home_score=24,
                      away_score=21, finalized_at='2026-09-10T04:00:00Z',
                      source={'url': 'https://example.com/verified-result'})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(lab, 'CAPTURE_ROOT', root), \
                 patch.object(season, 'load_current', side_effect=AssertionError('Unexpected reload')) as load:
                state = dict(self.state(), results=[result])
                before = copy.deepcopy(state)
                accepted, _ = lab.load_results(root, lock, season_state=state)
                self.assertEqual(accepted[0]['actual_margin'], 3)
                self.assertEqual(state, before)
                for changes in ({'home_team': 'BUF'}, {'home_score': -1},
                                {'finalized_at': '2026-10-04T17:00:01Z'}):
                    with self.subTest(changes=changes):
                        invalid = dict(state, results=[dict(result, **changes)])
                        before = copy.deepcopy(invalid)
                        with self.assertRaises(ValueError):
                            lab.load_results(root, lock, season_state=invalid)
                        self.assertEqual(invalid, before)
                load.assert_not_called()

    def test_default_results_reload_and_reject_tampered_state(self):
        state = self.state()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            captures = root / 'results'
            captures.mkdir()
            archive = root / 'season/runs/20261004T170000000000Z'
            archive.mkdir(parents=True)
            raw = season.canonical(state)
            (archive / 'state.json').write_bytes(raw)
            manifest = season.canonical({'files': {'state.json': {'sha256': season.sha(raw), 'bytes': len(raw)}}})
            (archive / 'manifest.json').write_bytes(manifest)
            (root / 'season/current.json').write_bytes(season.canonical({
                'path': 'runs/20261004T170000000000Z', 'manifest_sha256': season.sha(manifest)}))
            real_load = season.load_current
            with patch.object(lab, 'CAPTURE_ROOT', captures), \
                 patch.object(season, 'load_current', side_effect=lambda: real_load(root / 'season')) as load:
                self.assertEqual(lab.load_results(captures, {'games': []}), ([], []))
                (archive / 'state.json').write_bytes(raw + b' ')
                with self.assertRaisesRegex(ValueError, 'Season state hash differs'):
                    lab.load_results(captures, {'games': []})
            self.assertEqual(load.call_count, 2)

    def test_forecast_cli_loads_once_for_all_result_feeds_and_current_panel(self):
        fixture = lab_fixtures.ForecastLabTests()
        for state in (self.state(), None):
            with self.subTest(missing_season=state is None), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                before = copy.deepcopy(state)
                with self.render_fixture(root) as (rendered, results), ExitStack() as stack:
                    load = stack.enter_context(patch.object(season, 'load_current', return_value=state))
                    stack.enter_context(patch.object(lab, 'load_archive', return_value=fixture.synthetic_lock()))
                    stack.enter_context(patch.object(lab, '_load_snapshot', return_value=fixture.synthetic_snapshot()))
                    stack.enter_context(patch.object(lab, '_load_corrected', return_value=(None, root / 'corrected')))
                    stack.enter_context(patch.object(lab, 'load_model_sensitivity', return_value=None))
                    for name in ('_snapshot_section', '_weekly_section', '_corrected_section',
                                 '_rating_explanations', '_shared_css'):
                        stack.enter_context(patch.object(lab, name, return_value=''))
                    write = stack.enter_context(patch.object(lab, 'atomic_write_text'))
                    stack.enter_context(redirect_stdout(io.StringIO()))
                    status = lab.main(['--output', str(root / 'lab.html')])
                self.assertEqual(status, 0)
                load.assert_called_once()
                self.assertEqual(results.call_count, 4)
                self.assertTrue(all(call.kwargs['season_state'] is state for call in results.call_args_list))
                write.assert_called_once()
                if state is not None:
                    self.assertIs(rendered.call_args.args[0], state)
                else:
                    rendered.assert_not_called()
                self.assertEqual(state, before)

    @contextmanager
    def board_cli_fixture(self, root):
        output = root / 'index.html'
        output.write_text('<html>Prior published page</html>', encoding='utf-8')
        with ExitStack() as stack:
            stack.enter_context(patch.object(comparison, 'PUBLIC_OUTPUT', output))
            for name, value in (('load_config', {}), ('load_prior', {}), ('load_teams', []),
                                ('load_qbs', {}), ('build_html', '<html>Base page</html>')):
                stack.enter_context(patch.object(comparison.generate_site, name, return_value=value))
            refresh = stack.enter_context(patch.object(comparison, 'refresh_mccabe_page', return_value='<html>Refreshed</html>'))
            current = stack.enter_context(patch.object(board, 'add_current_board', side_effect=lambda page, **kw: page))
            stack.enter_context(patch.object(comparison, 'add_rating_explanations', side_effect=lambda page: page))
            stack.enter_context(patch.object(comparison, 'inject_record_block', side_effect=lambda page: page))
            write = stack.enter_context(patch.object(comparison, 'atomic_write_text'))
            yield refresh, current, write

    def test_board_cli_loads_once_and_passes_same_state_to_both_branches(self):
        for state in (self.state(), None):
            with self.subTest(missing_season=state is None), tempfile.TemporaryDirectory() as temp:
                before = copy.deepcopy(state)
                with self.board_cli_fixture(Path(temp)) as (refresh, current, write), \
                     patch.object(season, 'load_current', return_value=state) as load, \
                     redirect_stdout(io.StringIO()):
                    status = comparison.main(['--refresh-mccabe'])
                self.assertEqual(status, 0)
                load.assert_called_once()
                self.assertIs(refresh.call_args.kwargs['season_state'], state)
                self.assertIs(current.call_args.kwargs['season_state'], state)
                write.assert_called_once()
                self.assertEqual(state, before)

    def test_current_board_passes_explicit_state_through_real_nested_renderers(self):
        import pgo_forecast_corrected as corrected
        snapshot = lab_fixtures.ForecastLabTests().synthetic_snapshot()
        snapshot.update(edition=corrected.EDITION, inputs_as_of='2026-09-07T22:00:00Z')
        mccabe = [{'abbr': row['team'], 'team': row['team'], 'rank': row['rank']} for row in snapshot['teams']]
        page = '<section id="panel-comparison">Archived comparison</section>'
        for state in (self.state(), None):
            with self.subTest(missing_season=state is None), tempfile.TemporaryDirectory() as temp:
                before = copy.deepcopy((state, snapshot, mccabe))
                with self.render_fixture(Path(temp)) as (rendered, results), \
                     patch.object(comparison, 'extract_comparison_panel', side_effect=lambda value: value), \
                     patch.object(season, 'load_current', side_effect=AssertionError('Unexpected reload')) as load:
                    output = board.add_current_board(page, snapshot, mccabe, season_state=state)
                load.assert_not_called()
                results.assert_called_once()
                self.assertIs(results.call_args.kwargs['season_state'], state)
                self.assertIn('data-current-pgo-team=', output)
                if state is not None:
                    self.assertIs(rendered.call_args.args[0], state)
                    self.assertIn('id="pgo-season"', output)
                else:
                    rendered.assert_not_called()
                self.assertEqual((state, snapshot, mccabe), before)

    def test_both_clis_reject_failed_season_validation_before_writing(self):
        fixture = lab_fixtures.ForecastLabTests()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.board_cli_fixture(root) as (_, _, write), \
                 patch.object(season, 'load_current', side_effect=ValueError('Season state hash differs')), \
                 redirect_stderr(io.StringIO()):
                self.assertEqual(comparison.main(['--refresh-mccabe']), 1)
                write.assert_not_called()
            with patch.object(lab, 'load_archive', return_value=fixture.synthetic_lock()), \
                 patch.object(lab, '_load_snapshot', return_value=fixture.synthetic_snapshot()), \
                 patch.object(lab, 'load_model_sensitivity', return_value=None), \
                 patch.object(lab.pgo_forecast_weekly, 'load_weekly', return_value={'games': []}), \
                 patch.object(lab, '_load_corrected', return_value=(None, root / 'corrected')), \
                 patch.object(season, 'load_current', side_effect=ValueError('Season state hash differs')), \
                 patch.object(lab, 'atomic_write_text') as write, redirect_stderr(io.StringIO()):
                self.assertEqual(lab.main(['--output', str(root / 'lab.html')]), 1)
                write.assert_not_called()

    def test_fantasy_notes_explicit_none_does_not_reload(self):
        page = '<section id="panel-fantasy"><h2>2026 Week 4 Fantasy Rankings</h2></section>'
        with patch.object(comparison.generate_site, 'load_config', return_value={}), \
             patch.object(season, 'load_current', side_effect=AssertionError('Unexpected reload')) as load:
            self.assertEqual(comparison.add_current_injury_notes(page, season_state=None), page)
        load.assert_not_called()


if __name__ == '__main__':
    unittest.main()
