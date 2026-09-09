# PGO model ranking presentation report

## Result

The existing PGO current board and Forecast Lab September ranking table now use the approved compact slate/Cobalt pattern: rank, team marker/chip, bold signed rating, and a zero-centered rating bar. The PGO scale is `-14` to `+14`, covering both issued snapshots including the September 7 minimum near `-12.325`; future out-of-range values clamp visually and announce that clipping in the accessible label. This is a presentation-only extension. It does not alter model values, precision, order, IDs, source dates, status labels, forecasts, or research artifacts.

At widths up to 680 pixels, rank, team, and rating remain visible. Native checkboxes reveal the signed scale and the existing QB/McCabe or prior-selector comparison columns in the same horizontally scrollable table.

The historical comparison table remains structurally unchanged and inside its existing July archive disclosure. Shared theme CSS keeps its numeric cells compact and tabular. Forecast Lab ranking explanations receive the same numeric emphasis without changing their content.

## Files

- `pgo_current_board.py`: shared team identity and exact three-decimal PGO bar helpers; compact current-board markup and mobile column control.
- `pgo_forecast_lab.py`: uses the shared presentation for the saved September 32-team ranking table.
- `docs/pgo-theme.css`: shared current/snapshot/archive-compatible model-table styles and responsive behavior.
- `tests/test_pgo_current_board.py`, `tests/test_pgo_forecast_lab.py`: exact rating, signed direction, accessible-label, identity, and responsive-contract coverage.

## Verification

- Red: `python -m unittest tests.test_pgo_current_board tests.test_pgo_forecast_lab` — 43 tests ran; two failures and one error confirmed the presentation contracts were absent.
- Focused after the independent range review and `-14` to `+14` correction: the same command — 44 passed in 1.558 seconds. The final test set pins that both issued snapshot ranges avoid clipping and that a future out-of-range value reports clipping.
- Affected integration: `python -m unittest tests.test_mccabe_opening_night tests.test_ratings_release tests.test_pgo_comparison tests.test_pgo_current_board tests.test_pgo_forecast_lab tests.test_pgo_current_injury_notes` — 125 passed in 38.300 seconds.
- Publisher workflow/snapshot: `python -m unittest tests.test_public_board_workflow tests.test_pgo_forecast_snapshot` — 5 passed in 2.146 seconds.
- `git diff --check` passed. The test harness printed generated-output messages, but Git status confirmed no generated public artifact changed.

Root owns integration into the publication worktree, final browser QA, artifact verification, full CI, and publication.
