# PGO next improvements implementation plan

User-approved scope: repair the availability blocker, explain ranking changes,
automate completed-week reviews, run the fixed weight experiment, and audit
subsequent statistical corrections. Starting commit:
`44411fad35508f15644b1e0f84f39b714566dce7`.

Architecture: extend the existing season updater, pure views, archive readers
and canonical publisher. Keep research isolated. Python 3.12 and existing
dependencies only. Root retains the existing isolated worktree; independent
agents use sibling worktrees so the urgent availability repair can ship first.

## Boundaries

- Preserve every issued forecast, fixed confidence allocation, locked quote,
  accepted grade, prior edition, original source capture and frozen study.
- Resolve identities against dated sources; never turn inactive into healthy,
  substitute a quarterback silently, or lower source checks to clear an error.
- The new weight experiment is authorized to run under its frozen charter.
  Fitting is isolated research; promotion into public predictions is not part
  of this task. Existing model coefficients remain unchanged.
- New display explanations must reconcile numerically and use plain language.
  Missing comparisons remain unavailable, not zero.

## 1. Availability isolation and source diagnosis — root

- [ ] Capture current failing roster/depth bytes and identify the exact conflict.
  Reproduce the caller path with Atlanta's unrelated QB mismatch and valid
  Denver/Kansas City identities before modifying `pgo_season.py`.
- [ ] Add focused regressions in the existing season/availability tests. An
  unrelated roster conflict must not prevent an unchanged eligible matchup's
  availability refresh. A conflict for a participating team must still fail
  closed. Complete ranking editions still require all 32 valid team inputs.
- [ ] Repair the shared selector/callers with explicit scope and useful team
  identity errors. Preserve reviewed starter handling, dated depth checks,
  source receipts, forecast revision rules and durable T-60 guards.
- [ ] Run season boundaries, availability, starters, storage, ATS and publication
  regressions; independently review. Publish this repair through full CI first.

## 2. Explain ranking movement — isolated agent

- [ ] Extend new ranking editions with a comparison to the exact previous
  ranking edition: prior rating, QB identity and contribution values or deltas.
- [ ] Show rating change, largest positive/negative contribution changes, and
  explain that peers' movement can alter rank. Add one bounded edition summary
  for newly included completed weeks and changed QB assumptions.
- [ ] Reconcile contribution deltas to rating change, test peer-only rank moves,
  missing legacy comparisons and tampering. Do not alter model arithmetic.

## 3. Automatic completed-week review — isolated agent

- [ ] Reuse `pgo_season_accuracy`, `pgo_market_benchmark` and archived season
  state to render a dated final weekly report only after all scheduled games
  have accepted finals. Keep eligibility separate for winners, ATS, margin,
  totals and probability scores, including the late NE–SEA pool entry.
- [ ] Preserve the September 14 provisional report. Produce immutable final
  reports with source state/manifest references and plain labels using the
  existing theme. Repeated rendering must be deterministic and idempotent;
  existing reports must not be silently replaced.
- [ ] Integrate generation and staging with the canonical publishers. Extend
  tested-source admission only as needed for verified generated reports.
  Test incomplete weeks, complete weeks, byes, late/missing lines, and archive
  preservation. Review desktop/mobile rendered output.

## 4. Fixed QB/team weight experiment — isolated research agent

- [ ] Read and hash-check the complete sealed charter at
  `D:/CodexWorktrees/Postgame_Outlet-publication-20260909/output/overnight-20260914/weight-plan/proposed-charter.md`.
- [ ] Bind executable bytes, pinned historical inputs and environment before
  fitting. Implement exactly `sack_contrast4` with the existing optimizer,
  preprocessing and eight chronological folds; write algebra/source checks.
- [ ] Root reviews the executable preflight. Run the declared eight evaluation
  fits and one final historical fit once; retain failed attempts if any.
- [ ] Evaluate all locked acceptance rules, including paired error/stability
  and uncertainty checks. Report PASS/FAIL/UNAVAILABLE honestly. Reused seasons
  remain diagnostic. Publish findings without promoting the candidate.

## 5. Later-statistics review — root after availability repair

- [ ] Add a separate review of a saved ranking edition's captured team/player
  statistics against later captures for the same completed game cohort.
  Reuse archive hashes, identity checks and the repaired penalty partitioner.
- [ ] Keep this monitor independent of forecast issuance and model weights.
  Record source clocks, changed model-input fields and coverage/conflicts.
  Unknown/missing/duplicate rows cannot be reported as unchanged or zero.
- [ ] Recheck on a bounded six-hour cadence once a completed-week edition
  exists. Save findings through the existing state/archive workflow. Display
  changes as a review notice; never rewrite earlier forecasts or grades.
- [ ] Test unchanged, revised, missing, duplicate and future-game sources,
  cadence and preservation, then review the public explanation.

## 6. Integration and release

- [ ] Review each agent's diff and independent checks before integrating.
- [ ] Run focused integration checks and all required canonical CI commands.
- [ ] Publish source and generated assets to main via the existing workflow.
- [ ] Verify actual Pages/Shopify bytes, archive preservation, live availability
  status and clean worktree; retain a final hashed report in the new output
  directory. No edits to the sealed overnight output.
