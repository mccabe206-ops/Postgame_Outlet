# PGO automatic season updates implementation plan

Approved flow: [design](../specs/2026-09-09-pgo-season-automation-design.md). Existing isolated publication worktree, starting at ef7c175. Reuse standard-library capture, the frozen model and current renderer.

- [x] Halley: pgo_season_model.py, focused tests, and a verified compact historical accumulator seed. Expose prepare_seed and build_week, with no fitting; verify the seed reproduces issued feature values and chronological replay rules.
- [x] Nash: pgo_season_availability.py and focused tests. Capture dated reports/inactives for supplied game and roster identities; return explicit coverage and QB gates; preserve raw sources.
- [x] Fermat: pgo_season_view.py and focused tests. Pure render_season(state), current rankings/picks, W/L/T, availability and archived weeks using existing styling.
- [x] Root: pgo_season.py and focused lifecycle tests. Capture/validate final results, reconcile schedule, advance complete weeks, retain pre-lock forecast revisions, archive sources and expose verified current state. Reuse historical grade functions and probability mapping.
- [x] Root: integrate latest season view and imported result grades into the current board/Lab, leaving prior evidence unchanged; add scheduled workflow and focused automation checks.
- [ ] Integrate: run focused tests plus full repository checks, independent review, real source refresh and timing/identity checks, then commit/publish and dispatch the workflow. Verify exact public bytes and current Shopify embed, including mobile layout. Record any source-delay status honestly.

The runnable lifecycle tests must use synthetic clocks and source fixtures, never fabricate a pregame timestamp in a production capture. Runtime capture uses the real clock. All publication is already authorized by the user; routine implementation choices do not require another approval.
