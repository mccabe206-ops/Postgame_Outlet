# PGO publication release repair

Base: published commit `795edfc9939e7b4a144147e66762770d03b34b92`

## Changes

- Normalized both sides of the Fantasy-panel preservation assertions with `strip_current_injury_notes()`. The tests still compare the complete stripped payload byte for byte and separately require annotation injection to be idempotent.
- Added `?v=20260909` to the existing `pgo-theme.css` links produced by `generate_site.py` and `pgo_forecast_lab.py`, so Shopify/direct-page caches request the published dark theme revision.
- Updated the two existing stylesheet-link assertions. No asset pipeline, model, evidence, data, or generated public HTML changed.

## Verification

- Reproduced the published fixture failures: the two named CI tests failed because the checked-in reference already contained current injury annotations while only the newly rendered side was stripped.
- Targeted repaired fixtures and stylesheet contracts: 4 passed in 0.457 seconds.
- Affected renderer/editorial/injury set: `python -m unittest tests.test_mccabe_opening_night tests.test_ratings_release tests.test_pgo_comparison tests.test_pgo_current_board tests.test_pgo_forecast_lab tests.test_pgo_current_injury_notes` — 126 passed in 47.566 seconds.
- `git diff --check` passed. Git status listed only the six intended source/test files before this report; `docs/index.html` and `docs/pgo-theme.css` were unchanged.

Root owns artifact regeneration, full CI, live browser verification, and publication.
