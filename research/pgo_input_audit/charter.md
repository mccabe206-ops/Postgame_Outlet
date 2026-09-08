# Input and valuation audit: fixed follow-up charter

Written September 8, 2026 UTC before this follow-up's candidate fitting. The
user authorized a thorough input/valuation review and the explanation cleanup.
The prior research nominated simplification; this is a new exploratory test,
not a new untouched holdout and not an attempt to select New England's rank.

## Question, data, time and preservation

Predict next-game home-minus-away final points. One row per completed NFL
regular-season game, 2013-2025. Evaluate the same 2,127 games in 2018-2025 with
expanding-season fits using only earlier seasons. Use the existing 67-file
source lock, excluding current_roster:2026 from historical construction, and
the frozen September 7 snapshot for 2026 identity and current roster inputs.
No fresh performance data, external ratings, or outcomes are admitted.

The operational decision time is kickoff minus 60 minutes. Historical roster
statuses, actual starter identities and injury publication vintages are not
fully proven to have been observable then. This is conditional historical
reconstruction, not a certified T-60 replay. Preserve every game with explicit
missing features when an actual starter is unavailable in an eligible roster.
Report the count and identities; never substitute an outcome-selected player.
Historical injuries still use the inherited reconstruction policy and are a
limitation, not certified availability. No CLEAN leakage or promotion claim.

Do not change any production inference module, issued snapshot, existing run,
source lock, or forecast revision. A new research adapter may reuse existing
construction with sequential, restored hooks. Emit a new exclusive run directory
with pre-fit charter hash, code hashes, source identities, start receipt and
final manifest. Preserve failed runs and all evaluated candidates.

## Five fixed model arms

All arms use the established recorded-starter reconstruction, 365.25-day QB
history half-life, 200-effective-dropback shrinkage, ridge alpha 100 and Huber
delta 1. No parameter tuning. The reference has no new skill-quality fields.

1. **reference4**: reproduce the prior starter_recency historical predictions,
   final fit and current ratings, with the existing all-status weekly rosters
   and four-game team-efficiency half-life.
2. **active4**: same settings, but historical weekly roster source rows must be
   ACT before duplicate-status collapse or feature construction. Preserve
   missing/ambiguous recorded starters as missing, never backfill from excluded
   players. This tests eligibility consistency, not historical status vintage.
3. **active4_clean**: remove the four roster composition fields
   (returning_offense_snap_share, returning_defense_snap_share,
   incoming_prior_snap_share, rookie_draft_capital) and both coach fields from
   active4. Refit preprocessing and coefficients without their missingness flags.
   These fields are excluded because their definitions and preseason use are
   questionable, not because of the rank they assign any one team.
4. **active8_clean**: same as active4_clean with an eight-game team-efficiency
   half-life. This one fixed contrast checks dependence on the latest few games;
   no 4/8/16 grid search and no selecting a window after inspecting current ranks.
5. **active4_compact**: same as active4_clean, retain QB passing EPA and rushing
   EPA plus the existing QB lineup difference, but remove QB CPOE, sack avoidance,
   ball security, log dropbacks, experience and draft-prior predictor fields.
   Their internal shrinkage remains unchanged. This tests whether correlated
   secondary QB predictors and metadata improve forecasts beyond the two EPA
   summaries. Team performance, results history, availability, venue/rest remain.

Current inference must use each arm's own reconstructed historical context,
including its team-efficiency half-life and ACT-derived snap/identity history.
Recompute affected current roster inputs from the frozen ACT roster; do not
reuse four-game/all-status team or role features in another arm. Use the frozen
expected QB1 and its own static metadata. Apply the existing 0.5 results-rating
offseason retention exactly once in every current arm, including reference4.
The reference therefore matches the prior research recency rating, not the
issued September raw rating. No availability scenario is backdated into ratings.

## Evaluation and decision rule

Primary metric: pooled next-game margin MAE. Baselines on identical rows: prior
matched raw, prior starter-only, reference4, PGO v0, and training-fold constant.
Secondary: margin RMSE, mean predicted-minus-actual bias, winner accuracy
(exclude actual ties only for accuracy, retain all games for error metrics).
Report every season, weeks 1-4 and weeks 5-18, Week 1 alone, large predicted
margins, and each team's errors with sample sizes. Keep all unfavorable slices.

Paired season-block bootstrap: 10,000 draws, seed 20260908; improvement is
baseline absolute error minus candidate absolute error. Report all four new
arms against reference4 and their immediate construction control: active4 vs
reference4; clean vs active4; eight-game and compact vs active4_clean. Eight
season blocks and reused evaluation data limit these intervals.

A candidate merits a future prospective comparison only if pooled MAE improves,
its interval versus reference4 is above zero, at least five of eight seasons
improve, and weeks 1-4 do not worsen versus reference4. This is a research screen,
never promotion. Construction repairs may be scientifically necessary even if
they worsen apparent historical fit; report that outcome honestly. Do not pick
the best combination after results or hide failed arms.

## Separate season and score diagnostics

The current full-season forecast uses fixed preseason assumptions; next-game
validation does not validate that product. Independently evaluate the existing
prior-season PF/PA total formula against prior-season league-mean totals over
2018-2025, using only completed earlier-season scoring history. Report total
MAE/RMSE/bias and early-season slices without fitting or revising issued scores.
State that this total check alone does not validate exact scores, playoff odds,
or the fixed-season strength forecast. Any season-frozen strength replay must
freeze all teams before the first kickoff of the season, avoid week-one updates,
and be reported separately from the primary next-game results.

## Required checks and reporting

Prove reference reconstruction against saved predictions and current all-32
ratings; identical targets/game IDs; training/test chronology; finite values;
ACT filter before status collapse; explicit starter coverage; eight-game current
features from eight-game state; contributions sum to scores; scoped hooks restore
on success/error; protected hashes unchanged. Independently recompute new metrics
from saved predictions. Report model versions, data cutoffs, source/vintage
limitations, all attempted arms and the Fable service result. No claim of a
Fable verdict unless that service actually returns one.
