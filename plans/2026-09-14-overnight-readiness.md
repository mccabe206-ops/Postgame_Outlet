# Overnight readiness implementation plan

Approved scope: the five overnight recommendations accepted September 14, 2026.
Starting source: `0f525515a762b4bbf6bf85d957d02137329cec8d`.

Use the existing isolated worktree and Python 3.12 environment. Preserve issued
forecasts, confidence allocations, sportsbook lines, accepted finals, raw source
archives, fitted coefficients and prior sealed studies. The weight deliverable
is a proposed fixed protocol, not a fit or promotion. Publish tested application
repairs through the existing main/Pages workflow; do not simulate a live final.

## 1. Repair the statistics boundary

- [x] Reproduce the unidentified penalty-only row against `build_week` and the
  archive statistics verifier. Retain the 24/119 source capture and a fresh feed.
- [x] Add a shared `partition_player_rows(team_rows, player_rows, games)` helper
  in `pgo_season_model.py`, returning identified rows and dated cohort receipts.
  It may separate one completely unnamed penalty-only row per season/week only
  when the complete known game cohort reconciles team and player penalty counts
  and yards. Reject nonzero other production, missing required exposure, partial
  identity, duplicate records, wrong labels, missing/extra teams and mismatches.
- [x] Use that helper in both `build_week` and
  `pgo_season_rollover.verify_statistics`. Save the receipt in new ranking
  editions and require exact replay of it. Editions without a separated bucket
  retain their previous output shape and strict identity handling.
- [x] Run `python -m unittest tests.test_pgo_season_statistics
  tests.test_pgo_season_model tests.test_pgo_season_rollover`.

## 2. Rehearse rollover

- [x] Exercise refresh, next-edition construction, durable save/load, and
  `rollover.observe` using fixed mocked captures in temporary directories.
  Include complete finals/statistics, delayed data, conflicting data and cutoff
  failures. Require unchanged Week 1 evidence and reconciled Week 2 outputs.
- [x] Use existing workflow/publication and alert tests for failed publishing;
  add coverage only for demonstrated gaps. Real Week 2 remains pending DEN-KC.

## 3. Injury evidence

- [x] Capture current official DEN-KC and SEA/MIN availability and current usage
  feeds into `output/overnight-20260914/injury` in the publication worktree.
- [x] Replay saved pregame absence identities against published playing time,
  recording eligible, matched and missing coverage without injury point weights.

## 4. Provisional Week 1 diagnostic

- [x] Freeze the current saved state. Independently check straight-up, ATS,
  confidence, margin and total arithmetic for all accepted finals.
- [x] Write a readable game-by-game report and standalone HTML under the new
  ignored diagnostic output, with late/unavailable exclusions and DEN-KC pending.

## 5. Weight protocol and release

- [x] Review the coefficient audit and failed existing removal experiments.
  Specify one distinct next test, or justify reuse, with fixed chronological
  comparisons, acceptance rules and explicit reused-history limitations.
- [ ] Independently review the repair, replay captured source evidence, run
  focused regressions and the required full CI, then publish the source repair.
- [ ] Verify actual deployed bytes and preservation of issued records; retain
  logs, source clocks, the diagnostic, proposed protocol and hashed manifests.

Current output root:
`D:/CodexWorktrees/Postgame_Outlet-publication-20260909/output/overnight-20260914`.
