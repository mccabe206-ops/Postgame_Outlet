# PGO automatic season updates implementation plan

Approved flow: [design](../specs/2026-09-09-pgo-season-automation-design.md). Existing isolated publication worktree, starting at ef7c175. Reuse standard-library capture, the frozen model and current renderer.

- [x] Halley: pgo_season_model.py, focused tests, and a verified compact historical accumulator seed. Expose prepare_seed and build_week, with no fitting; verify the seed reproduces issued feature values and chronological replay rules.
- [x] Nash: pgo_season_availability.py and focused tests. Capture dated reports/inactives for supplied game and roster identities; return explicit coverage and QB gates; preserve raw sources.
- [x] Fermat: pgo_season_view.py and focused tests. Pure render_season(state), current rankings/picks, W/L/T, availability and archived weeks using existing styling.
- [x] Root: pgo_season.py and focused lifecycle tests. Capture/validate final results, reconcile schedule, advance complete weeks, retain pre-lock forecast revisions, archive sources and expose verified current state. Reuse historical grade functions and probability mapping.
- [x] Root: integrate latest season view and imported result grades into the current board/Lab, leaving prior evidence unchanged; add scheduled workflow and focused automation checks.
- [x] Integrate: run focused tests plus full repository checks, independent review, real source refresh and timing/identity checks, then commit/publish and dispatch the workflow. Verify exact public bytes and current Shopify embed, including mobile layout. Record any source-delay status honestly.

The runnable lifecycle tests must use synthetic clocks and source fixtures, never fabricate a pregame timestamp in a production capture. Runtime capture uses the real clock. All publication is already authorized by the user; routine implementation choices do not require another approval.

- [x] Capacity check: preserve existing files and URLs; compress new state/raw captures, retain only availability replay inputs, and link future audit folders directly from the public Git repository. Validate old/new readers, exact replay, and Pages exclusions before the final server run.

Release verification: application code `454535e54cfc85ac49324b55f165d114d0fabd4d`; full server run `34432109741` passed 700 tests (one skipped) and both 14-test research suites. Compact-format updater `34432119786` published `5cc236c9862ba673282598113815099cb1852218` with READY status at 2026-09-10 03:24:14 UTC. All 16 numeric forecasts, the locked opener, and 48 prior archive files were preserved. Public bytes, new-folder Pages exclusions, original archive URLs, mobile layout, live Shopify embed, and automatic visible-page refresh passed. The capture contained no verified final scores; prospective grading and weekly rollover remain conditional on their required source data. Native theme release: `1394c17694729f8d51070d81d1e78540e65a2701`. Detailed receipts are in the ignored `output/season-automation-20260909/` handoff folder.
