# Postseason history candidate - September 9, 2026

Locked before fitting. User authorized implementation, testing, operation and
publication on September 9. This is a new experimental edition; old forecasts,
grades and evidence remain immutable. Scientific status is EXPERIMENTAL / HOLD.

Question: does including all completed postseason games in prior team, results
and quarterback history improve NFL regular-season margin forecasts? One row is
one regular-season game; target is final home minus away points including
overtime. Ties remain in margin errors. Prediction cutoff is kickoff minus 60
minutes. Current issuance must precede each game's existing registered cutoff.

Construction: use the corrected ACT roster/exposure/symmetric construction with
the same fixed four-game team half-life, 365.25-day QB decay, QB shrinkers,
Huber delta 1, ridge alpha 200, and once-per-offseason results retention 0.5.
The sole fitted change is history membership: completed REG, WC, DIV, CON and
SB games update every team's histories in kickoff order after that game's
pregame features have been constructed. PRE and incomplete games are excluded.
Preserve true game types in coverage evidence. Only REG rows train or score the
margin model. No special rematch, New England, Seattle or Super Bowl weight.
Postseason inputs must cover team statistics and QB production consistently;
missing data must be surfaced and cannot masquerade as healthy/zero ability.

Historical evaluation: the same 2,127 REG games in 2018-2025, with expanding
earlier-season training starting in 2013. Fit preprocessing on training rows
only; mirror training perspectives, evaluate each original game once. Games and
their paired perspectives stay together. Earlier completed games can update
later histories; no current-game or future outcomes enter a pregame predictor.
Latest historical source revisions and recorded-starter timing are unresolved
vintage limitations: this is diagnostic evidence, not a recreated T-60 service.

Primary metric is paired game-level margin MAE, lower is better. Comparators
are the saved corrected model, original v0, constant and existing audited
references on identical IDs. Report RMSE, bias, winner accuracy with ties
counted separately, all eight seasons, Weeks 1-4, Week 1 and later weeks, team
slices, plus season-block bootstrap improvement intervals using 10,000 draws
and seed 20260909. No hyperparameter search or result-driven reruns. This
history has already been inspected; there is no fresh historical holdout.
Prospective 2026 forecasts provide the next new evaluation cohort.

The further-study screen is lower pooled MAE than corrected, improvement in
at least five of eight seasons, and a positive lower 95% paired season-block
improvement bound. This screen never establishes scientific promotion. A failed
screen remains visible in the published comparison and cannot silently replace
the existing leading model. Passing the screen permits presenting this as the
latest experimental model, retaining its HOLD label and every old edition.

Operational score heuristic: separately use 2025 completed REG plus postseason
PF/PA, equally weighting games within each team's own denominator. Preserve
the REG-only baseline comparison and disclose postseason sample counts. Total
is half the sum of the two teams' PF/PA averages; split total by the model's
margin. This is not a fitted or validated exact-score model. No probabilities
or betting claims. Show rounded scores without creating a predicted tie.

Current inputs: capture fresh roster, dated depth, schedule and official injury
reports with source URLs, retrieval times, byte counts and hashes. Require 32
unique ACT expected QBs and 16 unique Week 1 games, conflict-check identities,
venues, rest and cutoffs against issued records. Unknown report coverage means
unknown. OUT/IR/PUP expected QB blocks that team's draft. Non-QB status and
defensive depth remain a separate explicitly bounded analysis until their own
declared feature and validation contract is met; no double injury deduction.

Accept operational publication only after source/identity coverage, finite
arithmetic, serialized replay, reversal/neutral symmetry, temporal perturbation,
baseline preservation, focused checks and independent review pass. Record all
attempts in new exclusive directories, bind code/source/charter hashes before
and after each run. A construction failure stops that attempt; preserve it and
document repairs in a distinct attempt. Numerical non-improvement is a result,
not a reason to tune or retry. Publish reproducible artifacts and plain-language
limits, plus separately dated forecasts eligible for append-only future grades.
