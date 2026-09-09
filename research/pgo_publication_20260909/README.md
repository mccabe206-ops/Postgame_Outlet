# September 9 publication

The user explicitly authorized publication of the reviewed McCabe theme and grades, extension of the ranking style to PGO models, conflict reconciliation, and a model readiness check.

The release integrates canonical upstream `951ec61`, reviewed opening-night work `438878b`, and presentation `c859c50` (integrated as `0f42ba0`). All 32 approved numerical grades remain intact, including SF offense `0.2`; 20 updated upstream notes are retained. The final browser pass also left-aligns the team header and centers the rank header in both PGO tables.

## Verification

- Full repository discovery: **576 tests passed, one skipped**, 484.034 seconds. The log includes expected error output from negative-path tests.
- Required candidate/temporal tests: **14 passed**.
- Final current-board/Forecast Lab renderer checks after header alignment: **44 passed**.
- Corrected snapshot verifier: **32 teams, 16 games verified; HOLD**.
- Weekly verifier: **two immutable revisions, 16 games verified**.
- Independent presentation and merge review: PASS; receipts are alongside this file.
- Browser: current and September PGO tables fit a 375-pixel phone viewport; three essential columns remain visible, and optional columns scroll within the table. Desktop visual checks passed, including the September negative-rating range. Header alignment, exact values, 32-row counts and source limitations were checked. Both preview pages had no browser error or warning logs. Temporary preview tabs were closed after review.

The public HTML is regenerated with `pgo_comparison.py --refresh-mccabe` and `pgo_forecast_lab.py`. `release-verification.json` records generated artifacts, equivalence to the reviewed preview, and preservation of issued evidence and the saved Fantasy panel. Deployment and live verification are separate, later evidence.

## Publication follow-up

Initial release `795edfc` deployed successfully through Pages, but Update board run `34376330141` failed two tests whose reference fixtures assumed the published page had no current injury annotations. The preserved failed-run log documents this. Repair `d7ce3ae` (integrated as `05e49c2`) strips the separately marked annotations from both sides of those comparisons; full saved-payload equality and independent idempotence checks remain enforced. Both stylesheet links now request `pgo-theme.css?v=20260909`, because the existing Shopify iframe retained the old unversioned CSS in its browser cache.

After regenerating both public pages, the complete affected set passed again: **126 tests, 39.973 seconds**. `cache-repair-verification.json` confirms the public artifact changes are only the stylesheet URL and main header render clock. All ratings data, issued evidence and active model code remain unchanged. The next GitHub run must independently pass before the release is reported complete.

The active Shopify Power Ratings template (`159107678440`, page `124696264936`) was also updated through its existing fields: edition `Week 1 2026 · Sean McCabe`, Data as of `September 9, 2026`, and Updated time `September 9, 2026`. Its application URL uses an explicit release query to refresh returning readers' cached HTML; this remains the latest generated application, not a frozen forecast URL. Author, methodology, accountability, archive links and model limitations were preserved. Live deployment receipts are retained in `output/pgo-publication-20260909/` after the final checks.

## Model and availability limits

The saved model is operationally reproducible and remains **EXPERIMENTAL / HOLD**. Predictive utility is unproved. Publication does not adopt the failed corrected-plus-v2 candidate, refit any model, change issued forecasts, or apply uncalibrated injury penalties.

Four official injury sources were rechecked September 9 at **11:57 AM Eastern**, with no material change to the reviewed availability notes. The global recheck clock is separate from each annotation's original capture clock. Final inactives are pending. The opener's last eligible weekly forecast locks at **7:20 PM Eastern**, one hour before kickoff; another official availability review is needed before that cutoff. A lock badge does not mean final inactives were fetched.

See `readiness.md` for exact input dates, verified source hashes, model evaluation limits, and the existing append-only process if a supported new forecast is issued before its deadline.
