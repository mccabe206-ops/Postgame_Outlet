import copy
import unittest
from unittest.mock import patch

import pgo_availability_view as view


def scenario():
    return {
        'status': 'EXPERIMENTAL / HOLD', 'generated_at': '2026-09-09T17:00:00Z',
        'as_of': '2026-09-09T16:00:00Z', 'base_edition': 'saved-base',
        'teams': [{
            'team': 'NE', 'base_rating': 5.12345, 'known_out_delta': -0.25,
            'all_uncertain_out_delta': -0.5, 'known_out_rating': 4.87345,
            'all_uncertain_out_rating': 4.62345, 'status': 'COMPLETE',
            'unknown_count': 0, 'reason': None,
            'coverage': {'source_kind': 'formal_game_status', 'report_date': '2026-09-09',
                         'source_url': 'https://example.com/report', 'captured_at': '2026-09-09T16:00:00Z'},
            'players': [{'name': '<Player & one>', 'gsis_id': '00-1', 'position': 'RB',
                         'status': 'OUT', 'unit': 'offense', 'delta': -0.25, 'reason': None,
                         'source_url': 'https://example.com/report?a=1&b=2',
                         'captured_at': '2026-09-09T16:00:00Z', 'report_date': '2026-09-09',
                         'role': {'snap_share': 0.42, 'sample_count': 4,
                                  'last_observed': '2026-01-04', 'previous_team': 'BUF',
                                  'source_note': '<historical usage>'}}],
        }],
        'games': [{'home': 'NE', 'away': 'SEA', 'game_id': '2026_01_SEA_NE',
                   'kickoff': '2026-09-10T00:20:00Z', 'cutoff': '2026-09-09T23:20:00Z',
                   'base_margin': 2.3333, 'known_out_margin': 2.0833,
                   'margin_low': 1.8333, 'margin_high': 2.0833, 'status': 'COMPLETE'}],
    }


class AvailabilityViewTests(unittest.TestCase):
    def test_complete_values_sources_and_role_are_escaped_without_mutation(self):
        value = scenario()
        before = copy.deepcopy(value)
        markup = view.render_scenario(value)
        self.assertEqual(value, before)
        for text in ['EXPERIMENTAL / HOLD', '+5.123', '-0.250', '+4.873',
                     '&lt;Player &amp; one&gt;', '42.0%', '4 observations',
                     'BUF', '2026-01-04', '&lt;historical usage&gt;',
                     'not a confidence interval', 'replacement quality',
                     '<details>', 'class="table-shell"', 'tabindex="0"',
                     '+1.833 to +2.083']:
            self.assertIn(text, markup)
        self.assertNotIn('<Player', markup)
        self.assertIn('href="https://example.com/report?a=1&amp;b=2"', markup)
        self.assertNotIn('<th scope="col">Rank', markup)

    def test_partial_unknown_and_cutoff_never_show_adjusted_ratings(self):
        value = scenario()
        row = value['teams'][0]
        row.update(status='PARTIAL', unknown_count=1, reason='Missing role <unknown>')
        row['players'][0]['role'].update(snap_share=None, source_note='Current backup listing: <prior usage>')
        value['games'][0]['status'] = 'CUTOFF_PASSED'
        markup = view.render_scenario(value)
        self.assertIn('Partial subtotal', markup)
        self.assertIn('Missing role &lt;unknown&gt;', markup)
        self.assertIn('Current backup listing: &lt;prior usage&gt;', markup)
        self.assertNotIn('+4.873', markup)
        self.assertNotIn('+2.083', markup)
        self.assertIn('Cutoff passed', markup)
        row.update(status='UNKNOWN', known_out_delta=None, all_uncertain_out_delta=None)
        markup = view.render_scenario(value)
        self.assertIn('Unknown', markup)
        self.assertNotIn('data-value="0.0"', markup)

    def test_invalid_status_numbers_and_source_urls_fail_closed(self):
        for key, bad in [('status', 'APPROVED'), ('base_rating', float('nan'))]:
            value = scenario()
            value['teams'][0][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                view.render_scenario(value)
        value = scenario()
        value['teams'][0]['players'][0]['source_url'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError):
            view.render_scenario(value)

    def test_teams_without_coverage_are_collapsed_below_reported_subtotals(self):
        value = scenario()
        unknown = copy.deepcopy(value['teams'][0])
        unknown.update(team='BUF', status='UNKNOWN', players=[], known_out_delta=None,
                       all_uncertain_out_delta=None, known_out_rating=None, all_uncertain_out_rating=None)
        value['teams'].append(unknown)
        unknown_game = copy.deepcopy(value['games'][0])
        unknown_game.update(home='BUF', away='MIA', status='UNKNOWN')
        value['games'].append(unknown_game)
        markup = view.render_scenario(value)
        self.assertIn('<details><summary>1 team with unknown coverage</summary>', markup)
        self.assertIn('<details><summary>1 matchup with unknown coverage</summary>', markup)
        self.assertLess(markup.index('Known-out delta'), markup.index('1 team with unknown coverage'))
        self.assertIn('does not refresh automatically', markup)

    def test_excluded_reserve_observations_remain_named_with_their_reasons(self):
        value = scenario()
        value['teams'][0]['excluded'] = [{'name': '<Reserve player>', 'status': 'NFI',
                                         'reason': 'Identity & team unresolved',
                                         'source_file': 'reserve-source.html'}]
        markup = view.render_scenario(value)
        for expected in ('Excluded observations', '&lt;Reserve player&gt;', 'NFI',
                         'Identity &amp; team unresolved', 'reserve-source.html'):
            self.assertIn(expected, markup)

    def test_missing_package_skips_and_invalid_package_propagates(self):
        with patch('pgo_nonqb_availability.load_package', return_value=None):
            self.assertEqual(view.render_current_scenario(), '')
        with patch('pgo_nonqb_availability.load_package', side_effect=ValueError('invalid package')):
            with self.assertRaisesRegex(ValueError, 'invalid package'):
                view.render_current_scenario()

    def test_board_hook_preserves_existing_base_rows_and_legacy_page(self):
        from tests.test_pgo_current_board import CurrentBoardTests
        from pgo_current_board import strip_current_board
        fixture = CurrentBoardTests()
        fixture.setUp()
        with patch.object(view, 'render_current_scenario', return_value=''):
            baseline = fixture.add()
        addition = view.render_scenario(scenario())
        with patch.object(view, 'render_current_scenario', return_value=addition):
            enriched = fixture.add()
        self.assertEqual(enriched.replace(addition, '', 1), baseline)
        self.assertEqual(strip_current_board(enriched), fixture.page)
        self.assertLess(enriched.index('data-current-pgo-team='), enriched.index('id="nonqb-availability"'))

    def test_lab_hook_preserves_all_other_markup(self):
        from tests.test_pgo_forecast_lab import ForecastLabTests
        import pgo_forecast_lab as lab
        fixture = ForecastLabTests()
        kwargs = dict(snapshot=fixture.synthetic_snapshot(), weekly={'games': [], 'revisions': []})
        with patch.object(view, 'render_current_scenario', return_value=''):
            baseline = lab.render_lab(fixture.synthetic_lock(), [], [], **kwargs)
        addition = view.render_scenario(scenario())
        with patch.object(view, 'render_current_scenario', return_value=addition):
            enriched = lab.render_lab(fixture.synthetic_lock(), [], [], **kwargs)
        self.assertEqual(enriched.replace(addition, '', 1), baseline)
        self.assertEqual(enriched.count('id="nonqb-availability"'), 1)

    def test_fantasy_injection_keeps_scenario_comparison_and_fantasy_as_siblings(self):
        from tests.test_pgo_current_board import CurrentBoardTests
        from tests.test_pgo_comparison import ComparisonTests
        import pgo_comparison as comparison
        import pgo_current_board as board
        fixture = CurrentBoardTests()
        fixture.setUp()
        plain = comparison.inject_comparison(
            ComparisonTests._base_html(),
            comparison.render_comparison_panel([], ComparisonTests._held_receipt()))
        with patch.object(view, 'render_current_scenario', return_value=view.render_scenario(scenario())):
            current = board.add_current_board(plain, fixture.snapshot, fixture.mccabe)
        fantasy = comparison.render_fantasy_panel(ComparisonTests._fantasy_preview())
        enriched = comparison.inject_fantasy_preview(current, fantasy)
        panel = comparison.extract_comparison_panel(enriched)
        self.assertIn(board.ARCHIVE_CLOSE, panel)
        self.assertNotIn('id="panel-fantasy"', panel)
        self.assertLess(enriched.index(board.ARCHIVE_CLOSE), enriched.index('id="panel-fantasy"'))
        self.assertEqual(board.strip_current_board(enriched), comparison.inject_fantasy_preview(plain, fantasy))


if __name__ == '__main__':
    unittest.main()
