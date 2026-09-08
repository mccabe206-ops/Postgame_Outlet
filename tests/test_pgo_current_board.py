import copy
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import pgo_comparison as comparison
import pgo_current_board as board
import pgo_forecast_lab as lab
from tests import test_pgo_comparison as legacy_tests


class CurrentBoardTests(unittest.TestCase):
    def setUp(self):
        self.page = board.strip_current_board(comparison.PUBLIC_OUTPUT.read_text(encoding='utf-8'))
        self.snapshot = json.loads((lab.CORRECTED_DIR / 'snapshot.json').read_bytes())
        self.mccabe = comparison.load_mccabe_rows(comparison.MCCABE_PATH)

    def add(self, page=None):
        return board.add_current_board(self.page if page is None else page, self.snapshot, self.mccabe)

    def test_current_ratings_lead_and_archive_roundtrips_exactly(self):
        page = self.add()
        panel = comparison.extract_comparison_panel(page)
        self.assertLess(panel.index('PGO Corrected'), panel.index('July 21, 2026 comparison archive'))
        self.assertIn('<details class="pgo-july-archive">', panel)
        self.assertNotIn('<details class="pgo-july-archive" open', panel)
        self.assertEqual(board.strip_current_board(page), self.page)
        self.assertEqual(self.add(page), page)
        self.assertEqual(comparison._extract_published_fantasy_panel(page),
                         comparison._extract_published_fantasy_panel(self.page))
        self.assertLess(page.index('id="tab-ratings"'), page.index('id="tab-comparison"'))

    def test_all_current_rows_have_exact_identity_and_model_values(self):
        before = copy.deepcopy(self.snapshot)
        page = self.add()
        current = page.split(board.START, 1)[1].split(board.END, 1)[0]
        rows = re.findall(r'<tr data-current-pgo-team="([A-Z]+)">(.*?)</tr>', current, re.S)
        expected = sorted(self.snapshot['teams'], key=lambda r: r['rank'])
        self.assertEqual([team for team, _ in rows], [r['team'] for r in expected])
        human = {r['abbr']: r for r in self.mccabe}
        for (team, markup), saved in zip(rows, expected):
            self.assertIn(f'data-value="{saved["rating"]}"', markup)
            self.assertIn(f'corrected-rating-{team}', markup)
            self.assertIn(saved['qb_name'], markup)
            self.assertIn(f'>{saved["rank"] - human[team]["rank"]:+d}</td>', markup)
        self.assertNotIn('pgo-rating-trigger', current)
        self.assertNotIn('sort-button', current)
        self.assertNotIn('point gap', current.lower())
        self.assertIn('EXPERIMENTAL / HOLD', current)
        self.assertEqual(self.snapshot, before)

    def test_default_uses_latest_verified_registered_source(self):
        weekly = {'revisions': [{'source_edition': self.snapshot['edition']}]}
        with patch.object(lab.pgo_forecast_weekly, 'load_weekly', return_value=weekly) as load, \
                patch.object(lab, '_load_corrected', return_value=(self.snapshot, lab.CORRECTED_DIR)) as source:
            page = board.add_current_board(self.page)
        load.assert_called_once_with(lab.WEEKLY_DIR)
        source.assert_called_once_with(None, weekly, lab.WEEKLY_DIR)
        self.assertIn(self.snapshot['edition'], page)

    def test_legacy_refresh_and_explanations_strip_only_presentation(self):
        current = self.add()
        self.assertEqual(comparison.add_rating_explanations(current), comparison.add_rating_explanations(self.page))
        refreshed = comparison.refresh_mccabe_page(legacy_tests.ComparisonTests._base_html(), current)
        legacy = comparison.refresh_mccabe_page(legacy_tests.ComparisonTests._base_html(), self.page)
        self.assertEqual(refreshed, legacy)
        rebuilt = self.add(refreshed)
        self.assertEqual(board.strip_current_board(rebuilt), refreshed)
        self.assertIn('openDrawer(template.innerHTML, trigger)', rebuilt)

    def test_unpaired_presentation_markers_and_wrong_edition_fail(self):
        with self.assertRaises(ValueError):
            board.strip_current_board(self.add().replace(board.END, '', 1))
        self.snapshot['edition'] = 'pgo-v2'
        with self.assertRaisesRegex(ValueError, 'edition'):
            self.add()
