# Opponent EPA experiment — 2026-09-07

Status: exploratory retrospective research; no promotion or forecast replacement.
This charter is written before candidate fitting. The run receipt must record its
SHA-256 and start time. Existing public ratings, September/July snapshots,
weekly forecast records, and their inference code remain unchanged.

## Question and target

Does a simple opponent correction improve next-game home-minus-away margin
predictions relative to otherwise identical raw EPA features? Separately, how
does applying the existing offseason results-rating retention at September
inference change all 32 team ratings? Neither question is answered by whether
New England falls to a more familiar rank.

One row is one completed NFL regular-season game, 2013–2025. Evaluation seasons
are 2018–2025, training on 2013 through the preceding season. Target is final
home-minus-away points. Features use the existing historical pregame walk;
added opponent corrections use only raw histories from earlier NFL weeks,
frozen before the first game of each season/week. No same-week results enter
these corrections. This is a historical pregame proxy, not proof of T-60 source
availability: revised statistics, historical roster/injury vintages, and the
incumbent kickoff-order update convention remain limitations.

## Fixed arms and construction

- `raw`: unchanged feature construction.
- `team_epa`: replace only the four team passing/rushing EPA for/against inputs.
- `team_qb_epa`: additionally replace QB passing/rushing EPA, including the
  derived current-minus-full QB EPA difference. Keep raw QB selection values,
  identities, eligibility, availability weights, and all other inputs identical.

For each EPA feature, the league reference is sum(raw historical numerators)
divided by sum(raw historical denominators), frozen at the week boundary.
Defensive inputs already mean **negative EPA allowed**. For an offensive
observation, add opposing defense minus league defense; for a defensive
prevention observation, add opposing offense minus league offense. Add this
rate correction times the observation denominator to its numerator. All
correction weights are 1; no grid search or newly tuned prior is allowed.
Missing opponent history or an unavailable league reference means zero
correction, with fallback counts retained; missing own observations stay missing.

Keep raw opponent histories separate; do not recursively feed adjusted rates
back into the correction. Adjusted team histories use the same four-game
half-life. QB passing/rushing observations use the opponent team defense
correction; player and population accumulators receive the same adjustment.
Retain existing QB shrinkage, including its 200-dropback prior. Team rushing
defense is an approximation for QB rushing, not a QB-specific matchup measure.
CPOE, explosive plays, sacks, turnovers, and other inputs remain unadjusted.

All arms use half-life 4, ridge alpha 100, Huber delta 1, and the existing solver.
Each arm/fold fits its own imputation, scaling, and coefficients on earlier
seasons only. These previously selected settings and all evaluation seasons
have already been inspected: there is no untouched historical holdout.

## Comparison and decision

Use identical game IDs/targets in every arm. Baselines: training-fold constant
mean margin and unchanged PGO v0. Primary metric: pooled margin MAE. Secondary:
RMSE and winner accuracy (report ties under the existing metric convention).
Report each season and weeks 1–4 versus later weeks. Report paired MAE
improvement versus raw and v0 with 10,000 paired season-block bootstrap draws
(seed 20260907); existing season-week bootstrap is a sensitivity check. Only
eight season blocks and prior inspection limit inference from these intervals.

An improvement merits further prospective study only if pooled MAE improves,
the season-block 95% interval is above zero, at least five of eight seasons
improve, and weeks 1–4 do not worsen. These are research screening criteria,
not deployment authorization. Report both candidates regardless of outcome;
do not retune or select based on NE/JAX rank movement. Source-vintage review
and a genuinely prospective comparison are still needed before promotion.

## September inference and offseason consistency

Use the exact September 7 roster/QB identities and frozen feature snapshot.
Refit each arm on all 2013–2025 rows for descriptive all-team sensitivities.
Verify the raw final fit reproduces the frozen public fit before interpreting
candidate rankings. Show raw, team-only, and team-plus-QB EPA fits, each with
and without the existing results-rating offseason retention of 0.5.

Historical training already applies retention once at each season boundary.
The frozen September snapshot does not cross a completed 2026 game, so its
results input retains the end-of-2025 value. Apply 0.5 ** season_gap once to
that input in a separate candidate inference copy. No new regression rate,
team/QB offseason shrinkage, altered training folds, or historical MAE claim
is attached to this inference correction. Record both ratings and ranks for
every team and inspect NE/JAX contributions without manual rank adjustments.

## Checks and deliverables

Reuse the current feature/fit/metric helpers in a separate research module;
do not edit pinned production modules. Runnable checks must cover adjustment
sign, cold starts/missing observations, prior-week freezing, future-result
perturbation, unchanged QB selection, fold boundaries, and one-time offseason
application. Preserve source and protected-file hashes before/after the run.
Write complete matched predictions, fold fits/metrics, 32-team comparisons,
and a reproducible report. A failed or unfavorable experiment stays visible.

Leakage verdict remains REVIEW REQUIRED for historical publication vintage,
even when chronological construction checks pass. No calibrated probabilities,
betting claims, new forecast locks, publication, or promotion are part of this run.
