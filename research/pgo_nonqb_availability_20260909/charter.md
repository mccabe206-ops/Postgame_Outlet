# Non-QB availability scenarios — September 9, 2026

User approved the proposed separate experimental availability adjustment and
evaluation: “let's get this done ASAP.” Continue in the clean publication
worktree at d89afc4. Existing publication authorization covers this separately
labeled addition, not promotion or replacement of issued forecasts.

Question: how does the saved corrected PGO margin change under newly verified
non-QB absences? NFL 2026 regular-season team/game scenarios; points in the
existing model's scale; information must be captured before kickoff minus
60 minutes. Existing base ratings and issued forecasts remain unchanged.

Reuse the exact September 8 corrected fit and its two availability predictors.
Subtract summed lost offensive/defensive role shares from their current zero
baseline and replay the same coefficients/preprocessor. Do not import McCabe's
grades, old candidate coefficients, heuristic status probabilities, or recovery
durations. No new fit, parameter search, model selection, or historical rebuild.

Roles use independently resolved prior regular-season snap observations, with
raw source hashes and per-player rows. Use the median of the last four observed
positive unit snap shares through 2025 as an explicit playing-role proxy; this
avoids turning injured weeks into healthy zero-role assumptions. Require stable
GSIS/team identity, report any changed team, and expose sample size/last date.
No history, unresolved identity or unsupported role means unknown, never zero.
This differs from the older historical role convention and is unvalidated.
The fitted unit weight represents an aggregate conditional association, not an
individual player valuation or a measured replacement-quality estimate.

Official OUT/IR/PUP absences contribute to the known-out scenario. Questionable
and doubtful players contribute only to a separate all-uncertain-out scenario;
no percentage or midpoint is a forecast. Practice participation alone supplies
no absence. Current reports and reserve supplements remain explicitly scoped.
Missing team reports/roles prevent a complete adjusted rating. Known-player
subtotals may be shown only as partial, with excluded players and reasons.
Do not rank partially covered teams as an injury-adjusted league table.

No extra team-level penalties or separate injury-quality deductions: each
player contributes once within its unit, with QB and special teams excluded.
Historical team performance can already reflect absences; residual overlap and
replacement quality remain limitations. A returning or transferred player's
old usage is a proxy, not a fresh depth-chart claim.

Evaluate saved season-fold predictions with versus without the two availability
terms on identical games; preserve missingness, compare MAE, RMSE, season and
early/late slices, with paired season-block intervals. This is a post-hoc
diagnostic on previously inspected 2018–2025 seasons, not a new experiment or
evidence that the new role/status policy improves accuracy. No tuning follows.
Record all outcomes. New prospective comparisons use issued before-cutoff
scenarios and the unchanged base, then final margin including overtime.

Operational acceptance: exact pinned fit/base and source-byte verification,
unique identities, finite shares in [0,1], no mutation of baseline inputs,
signed matchup arithmetic, monotonic loss scenarios, explicit unknowns,
exclusive writes, before-cutoff issuance, saved-output replay, preservation of
all old evidence, focused tests, full suite and independent review.
Scientific status remains EXPERIMENTAL / HOLD. No calibrated probabilities,
confidence intervals for scenario ranges, exact-score changes, or promotion.

Implementation: one small scenario module and tests; dated source/role ledger
and manifested output; shared HTML section for current board and Forecast Lab;
existing theme, generators and deploy workflow. Publish only after verification.
