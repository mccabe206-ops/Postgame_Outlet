# Current-strength research charter - 2026-09-07

Written before candidate fitting. Status: EXPERIMENTAL / HOLD. Preserve issued
forecasts, source locks, the September snapshot, and production inference code.
The user approved all five workstreams: QB selection, QB recency, roster quality
and availability, component ablation, and honest board sensitivity/freshness.

## Fixed question and data

Predict next-game home-minus-away final points. One row per completed NFL
regular-season game, 2013-2025; expanding-season evaluation 2018-2025, each fit
using earlier seasons only. Reuse the 66 historical files from the existing
67-file source lock; exclude current_roster:2026 from historical fitting. All
arms must have identical games and targets. Refit preprocessing on each training
fold. Existing settings remain team half-life 4 games, Huber delta 1, ridge 100.
No hyperparameter search. These seasons were already inspected, so this is
exploratory research with no untouched holdout.

## Four arms

1. raw: unchanged historical construction and frozen September inference.
2. starter: replace best-EPA QB selection with the frozen schedule's recorded
   starter GSIS ID. These are actual starter reconstructions, NOT verified
   pregame expected starters or T-60 observations. Missing/ambiguous roster
   match leaves all eight QB features and current-minus-full unavailable;
   preserve the game and report coverage. Never inject a postgame roster player
   or fall back to highest EPA. Live inference uses the frozen verified QB1 ID.
3. starter_recency: additionally decay every player and pooled QB numerator,
   denominator, and dropback total by 2^(-elapsed_days/365.25), once per kickoff
   batch before its observations. At September inference, decay from the last
   processed kickoff to the snapshot generated_at. Keep the 200 effective-
   dropback prior, log1p(effective dropbacks), experience and draft formulas.
   This models recency/staleness, not biological age. Do not fit an age curve.
4. starter_recency_roster: additionally add four prior-season skill-player
   efficiency proxies: WR receiving EPA/target, TE receiving EPA/target,
   RB/FB receiving EPA/target, RB/FB rushing EPA/carry. Use the preceding three
   completed seasons, weights 1, 0.5, 0.25, with position-population priors from
   the same window. Prior opportunities: WR/TE receiving 50, RB receiving 30,
   RB rushing 75. Aggregate using the existing prior-game median-last-four
   offensive snap share, identically historically and currently. Unobserved
   players receive the population prior with explicit observed-weight coverage;
   absent role weights or population data remain missing. No current-season
   outcomes enter a season's player profiles. These are efficiency proxies,
   not comprehensive player grades or causal talent estimates. OL/defensive
   quality remains unavailable without a defensible source.

At 2026 inference the three candidate arms apply the existing results-rating
offseason retention 0.5 exactly once. Raw retains the frozen snapshot for exact
reproduction. Show raw with retention as a descriptive control if needed. Do
not combine the previous HOLD opponent adjustment into these candidate arms.

## Availability

Reuse official-injury normalization, source coverage and availability helpers.
Capture into a new directory; never overwrite frozen captures. Formal reports
may adjust a separate current scenario through existing role-share machinery.
No formal report is unknown, not healthy. Record report/capture times and hashes.
Do not double-penalize player efficiency and existing availability features.
Current injury coverage is descriptive and is not retrospectively injected.

## Ablations and evaluation

For the full starter_recency_roster arm, refit one-group-out variants for:
results history (pgo_v0); team passing (passing EPA for); other nine team
performance inputs; all QB inputs including current-minus-full; four existing
roster-continuity inputs; two coaching inputs; four new skill-quality inputs;
two offense/defense availability inputs. Keep venue/rest controls. Remove
associated missingness flags through fold-local preprocessing, not by zeroing
coefficients. Report every variant; do not select a new combination after
seeing results and call it confirmed.

Baselines: each training fold's constant mean margin, frozen PGO v0, matched raw.
Primary metric pooled margin MAE; secondary RMSE and winner accuracy with actual
and predicted ties reported. Report each season, weeks 1-4 and weeks 5-18.
Paired season-block bootstrap: 10,000 draws, seed 20260908, improvement defined
as baseline absolute error minus candidate absolute error. Report versus raw,
v0, and the preceding arm; ablations also versus the full arm. Only eight season
blocks, reused evaluation data and actual-starter reconstruction limit inference.

A candidate merits further prospective study only if pooled MAE improves,
the 95% season-block interval is above zero, at least five of eight seasons
improve, and early-week MAE does not worsen against raw. This never constitutes
promotion. All arms retain HOLD pending source-vintage review and prospective
evidence. Ablation improvements nominate simplifications for a future frozen
test; they do not trigger retrospective tuning in this run.

## Public explanation and receipts

Add one collapsed sensitivity panel to the existing Forecast Lab, linking from
the board; retain McCabe-first ordering. Use verified all-32-team research files
and distinguish July board, September baseline, and research dates. Rank/score
spans across variants are model sensitivity, NOT confidence intervals. State
calibrated uncertainty unavailable. Explain rank gaps and source freshness.

Write a new immutable run directory with pre-fit charter hash/start receipt,
source/code hashes, matched predictions, per-fold parameters, metrics, coverage,
all-team candidate features/contributions, and a final manifest. Verify raw
reproduces the frozen fit and ratings before interpreting candidates. Recheck
protected sources, snapshots and inference code after the run. Historical
publication vintage remains REVIEW REQUIRED. No probability calibration claims,
new game-total model, automatic forecast replacement, or live model promotion.
