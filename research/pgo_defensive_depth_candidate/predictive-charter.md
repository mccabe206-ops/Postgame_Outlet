# Fixed defensive production and experience diagnostic

Locked September 9, 2026 before feature construction or fitting. This is one
separate corrected-plus-defense candidate. It is not combined with the separate
postseason-inclusive team/QB/results candidate, and it does not change issued
forecasts. Scientific status remains EXPERIMENTAL / HOLD for every result.

Target, population, baseline and split: final home margin, the same 2,127
regular-season games in the corrected 2018-2025 expanding season folds. Training
history begins in 2013; 2013 has no admitted previous-season player history and
receives explicit missing values. Use the corrected fixed Huber fit, scaling,
missingness and signed symmetry, with no parameter search. Corrected saved
predictions are the primary paired control. All historical seasons have already
been inspected and are diagnostic, with source-publication vintage REVIEW
REQUIRED. No drop of difficult teams, seasons, rookies or missing-history games.

Exactly four added team fields, constructed identically from historical ACT
rosters and the captured current ACT roster. Defensive positions use the shared
defense group plus explicit safety aliases. For target season s, only season
s-1 player production and defensive snap history is used, including REG and POST.
History follows stable identity across teams. Current official depth order is
not used by these fitted fields and no actual backup-quality claim is made.

1. Prior QB-hit activity: 100 times total QB hits divided by total defensive
   snaps on exact matched player/team/week records with a finite observed hit
   field. Excluded snap exposure and unmatched production are reported.
2. Prior pass-defense activity: the same ratio for passes defended, with its
   own observed-field exposure. Interceptions are not added again.
3. Effective experienced-defender count: (sum q)^2 / sum(q^2), where q is a
   player's median of their last four positive observed prior-season defensive
   game snap shares. The game denominator is the largest observed team defender
   snap count, matching the existing role proxy. This measures breadth of prior
   contributors; it does not identify current true backups or grade talent.
4. Observed-history coverage: ACT defenders with at least one resolved positive
   prior-season defensive snap divided by all ACT defenders. It is a coverage
   descriptor, not an automatic low-quality value for rookies.

An empty denominator is null, never zero ability. Duplicate/conflicting IDs,
future source rows, negative/nonfinite counts or unsafe game joins stop the
affected construction. The existing conflict-rejecting PFR/name resolver is
reused and its exact unique-name fallback counts are disclosed. Unresolved
records remain excluded and visible; no invented identities or probabilities.
All preprocessing is fit only on each training fold; home/away differences and
their missingness use the same corrected symmetric construction.

Primary metric: lower paired margin MAE. Secondary: RMSE, per-season MAE/RMSE,
Week 1, Weeks 1-4 and later weeks, large-error rates, identity/exposure coverage.
Paired 10,000 resamples of the eight season blocks, seed 20260909, 95% interval
for baseline MAE minus candidate MAE. Fixed screen: lower pooled MAE, positive
improvement in at least five of eight seasons, and interval lower bound above
zero. Passing is a diagnostic screen only; rank movement or New England's rank
is not acceptance. Record any failed result without tuning or replacing it.

Root must review preparation checks and source/identity coverage before the
single fit. Save new construction, all matched predictions/fits, source and
code hashes, coverage, metrics, and one immutable receipt. The descriptive
current-depth panel is independently publishable and never claims that its
official depth ranks were included in this model.
