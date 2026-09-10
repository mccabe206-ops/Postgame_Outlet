# Task 1 report: McCabe opening-night theme and grades

Status: implementation and source verification complete at local source checkpoint `be46e76`. The final integrated private-preview generation, hashes, and browser freeze remain root-owned. Nothing was pushed, published, or written to Shopify.

## Changes

- Reworked the ratings renderer into the approved dark-slate/Cobalt compact board without adding a dependency. The total is the strongest numeric field; each row has a signed, zero-centered `-8` to `+8` bar with a programmatic text alternative.
- Added team-color markers while retaining abbreviation chips, full Offense/Defense headings, sortable columns, snapshot selection, keyboard focus behavior, the Escape-closing drawer, comparison, current-board, forecast, fantasy, source, and `EXPERIMENTAL / HOLD` surfaces.
- On narrow screens, the board defaults to rank, team, rating, and quarterback. Its native `Show all columns` control reveals movement, component, prior-rating, and scale columns in the existing scrolling shell.
- Added an optional, fail-closed injury report surface driven by `injury_checked_at`, `injury_status`, and an HTTPS `injury_source_url`. It validates a timezone-bearing timestamp, displays a human-readable Eastern clock distinct from page-generation time, and keeps final-inactives-pending visible in a compact native disclosure.
- Extended the safe Markdown subset with HTTPS-only links for dated official sources in writeups. Other link schemes remain plain text.
- Updated comparison loading to use and validate the active edition from `data/config.csv`, retaining historical snapshots and validation messages. Refresh remains idempotent across deliberate McCabe rank changes.
- Added current official injury annotations to the saved Fantasy Week 1 panel without changing its frozen projections, source cells, inactive flags, scoring JSON, or issued evidence. The intro and per-player annotations distinguish saved projection inputs from the current report.
- Fixed two browser-discovered integration defects: duplicate quarterback names no longer mix the approved starter with the old depth-table backup, and Forecast Lab row headers now use the dark panel/text colors. ATL's displayed Tua Tagovailoa metadata uses the existing depth record's age/experience (`28/6`) while the approved name and grades remain unchanged.

Root imported the 32 supplied grades and writeups through the existing data path, then applied only documented injury corrections. The receipts are `research/pgo_opening_night_20260909/editorial-import.json`, `research/pgo_opening_night_20260909/injuries/editorial-application.json`, and `research/pgo_opening_night_20260909/editorial-metadata-followup.json`. The reference parity test pins SHA-256 `164f9b55a42064ef3107f4e089cb32cd99acec93ac8dd20342d9afd37ca8dae7` and checks all 32 names, quarterbacks, component grades, and totals. The test deliberately accepts San Francisco offense at the supplied displayed precision, `+0.2`.

## Verification

- Baseline: `python -m unittest tests.test_ratings_release tests.test_pgo_comparison` — 74 passed before renderer changes.
- New-contract red check: `python -m unittest tests.test_mccabe_opening_night` failed before implementation/import on the missing theme, signed-scale, and source-grade contracts.
- Final supported repository discovery: `python -m unittest discover -s tests` — **572 tests ran in 607.408 seconds; 1 skipped, all remaining tests passed; exit 0**. Exact merged output: `output/opening-night/tasks/task-1-tests.log`, SHA-256 `c815d48937e7407862ca96017847d377bfa5cbd2401b81413fd462a70a9ad4ca`.
- Corrected-roster verification, without replaying the spent study: `python -m unittest research.pgo_corrected_roster_candidate.test_candidate research.pgo_corrected_roster_candidate.test_temporal research.pgo_corrected_roster_candidate.test_verify` — **15 passed in 0.177 seconds; exit 0**. Exact merged output: `output/opening-night/tasks/task-1-research-tests.log`, SHA-256 `b1a2a2519b89f0ba3bb8e0c2a98063cb379200b6aedcedd7a2e3a7f7e2bb822d`.
- Final affected modules after the duplicate-QB guard and Tua metadata correction: `python -m unittest tests.test_mccabe_opening_night tests.test_ratings_release tests.test_pgo_comparison tests.test_pgo_current_injury_notes` — **82 passed in 49.571 seconds**. These tests cover the `28/6` metadata, duplicate-name guard, signed bars, grade parity, comparison integration, and current injury annotations.
- The Forecast Lab color correction is CSS-only and was checked in a fresh browser tab: row-header background `rgb(23, 28, 36)`, text `rgb(230, 237, 243)`.
- Browser QA before final freeze confirmed desktop board fit, 375-pixel mobile fit, team-drawer interaction, and Escape focus restoration. The repository suite left `docs/index.html` unchanged at its preserved SHA-256 prefix `2b249015`; root owns the final integrated preview/browser receipt.

## Private preview

Use the repository's private-preview integration path:

```powershell
python output/opening-night/build_preview.py
Copy-Item -LiteralPath docs\pgo-theme.css -Destination output\opening-night\site\pgo-theme.css -Force
python -m http.server 8769 --bind 127.0.0.1 --directory output/opening-night/site
```

Open `http://127.0.0.1:8769/`. Root will record the final `index.html` and CSS hashes after regenerating from the frozen source checkpoint. The preview is private and must preserve the existing Fantasy Week 1 panel.

## Remaining concerns

- Final inactive lists have not been released; the preview must continue to say they are pending.
- Formal injury-table coverage is four teams, with 28 explicitly unknown. Practice participation alone is not a final game designation.
- Current fantasy injury annotations supersede availability display only. They do not revise frozen projections or issued PGO forecasts.
- Public `docs/index.html`, publication workflows, Shopify, and remote branches remain outside this task.
