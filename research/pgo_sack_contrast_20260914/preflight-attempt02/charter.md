# One fixed QB/team sack-avoidance contrast experiment

Status: **DESIGN ONLY / NOT RUN**. Proposed experiment ID: `pgo-qb-team-sack-contrast4-v1-20260914`.

This document fixes one proposed candidate before any candidate fitting or prediction. The present task prepares the design and checks existing evidence only. It does not execute an experiment, issue a forecast, alter production, or promote a model. A later implementation must bind this exact charter, executable bytes, inputs and environment before its first fit. Any substantive design change requires a separately identified charter; preserve this proposal.

## Question and boundary

Does stronger shrinkage of the difference between the QB and team sack-avoidance coefficients improve regular-season margin prediction while avoiding greater year-to-year coefficient drift? The motivation is the saved-fold audit's overlapping QB/team sack inputs, not Week 1 results, betting returns, or New England's rank. This is a test of conditional coefficient allocation; it does not estimate the causal effect of sacks or player quality.

Target: final home points minus away points, including overtime. Grain: one original NFL REG game. Ties remain in margin errors. Operational decision time is T = kickoff minus 60 minutes, with actual future capture and durable issuance strictly before T. Historical rows retain their existing reconstructed pregame meaning; this design does not certify historical source availability at T.

Use exactly the 3,407 saved original feature rows in `research/pgo_postseason_candidate/run-20260909-attempt01/historical-features.json`. Do not rebuild histories, repair inherited historical identities/availability, update raw inputs, change decay, or add 2026 outcomes. Preserve all 24 raw feature keys, values, missingness, targets, game IDs, order and subgroup flags. The manifest is `a58aeff835471182a555e4b926beafd0db01c7c5e3fe19827ddf56bd03f2514a`; feature-file SHA-256 is `5b0aa4ac3d06ff37314c71984003651434f0df1cb2f17c6a74e7b26c44f20365`.

## Exactly one candidate

Candidate name: `sack_contrast4`. The sole change is a fixed transformation of the two standardized VALUE columns for `qb_sack_avoidance` (q) and `sack_avoidance_rate` (t):

```text
common   = (z_q + z_t) / sqrt(2)
contrast = (z_q - z_t) / (2 * sqrt(2))
```

Replace the q value-column slot with common and the t value-column slot with contrast. Resolve slots by exact feature name, not hardcoded position. All other standardized value columns and all existing missing-indicator columns remain unchanged and in their original order. Preserve the original preprocessor metadata and store the named transformation separately.

Use the existing symmetric Huber-ridge routine unchanged: alpha 200, delta 1, maximum 50 iterations, coefficient tolerance 1e-8, existing residual-scale/IRLS logic, and unpenalized intercept. Do not implement a new optimizer, constrain coefficient signs, tune the contrast factor, or test another pair. Planned count is eight candidate evaluation fits plus one final historical fit, once each. The saved control is replayed, not refitted.

This retains both dimensions. For standardized original coefficients b_q and b_t, its ridge quadratic on this pair is:

```text
alpha * ((b_q + b_t)^2 / 2 + 4 * (b_q - b_t)^2 / 2)
```

Thus the disagreement direction has four times the original penalty; the common direction has the original penalty. The fixed factor four is a design choice, not an estimated optimum. A rotation with equal penalties would be algebraically redundant and is not this candidate. Do not re-standardize common/contrast after this transform: that would change the declared penalty. Do not add the transformed columns alongside the old pair.

## Missingness, scale and symmetry

Use each matching baseline fold's serialized, training-only preprocessor. Before candidate fitting, independently reconstruct that preprocessor from exactly its mirrored training rows with the existing helper; require the same feature/missing-flag inventory and medians/scales within absolute 1e-12. The final fit uses its corresponding final preprocessor. Never compute medians, scales, correlations or rotations on evaluation rows to set this transformation.

For an observed value, z = (value - saved median) / saved scale. For missing data, use the existing median imputation, so its value term is zero; retain its original missing-indicator term. A measured zero remains observed. One missing member does not make the other missing; both original missing flags remain available. The transformed coordinates are arithmetic features, not imputed observations of two healthy/full-strength units. Preserve the existing zero-variance scale fallback of one. Entirely unobserved training features, malformed numbers, Boolean values, nonfinite inputs or invalid saved scales stop the attempt.

Mirror training exactly as the baseline: negate every finite matchup value, signed venue, rest and target; keep missing values missing. Each original and its reversed perspective remain in the same training fold. Evaluate the original perspective once. Require neutral self-match zero and reversal symmetry, including one/both missing pair values, within absolute 1e-8.

## Locked historical folds

Use the exact ordered training/validation ID lists in `fold-fits.json`, not a newly selected subset. All training seasons precede the test season. Require maximum training kickoff earlier than minimum test kickoff. The baseline history already uses earlier completed games; no new embargo can retroactively prove historical publication timing, so source vintage remains REVIEW REQUIRED.

| Test season | Training seasons | Original training games | Mirrored rows | Test games |
| --- | --- | ---: | ---: | ---: |
| 2018 | 2013-2017 | 1,280 | 2,560 | 256 |
| 2019 | 2013-2018 | 1,536 | 3,072 | 256 |
| 2020 | 2013-2019 | 1,792 | 3,584 | 256 |
| 2021 | 2013-2020 | 2,048 | 4,096 | 272 |
| 2022 | 2013-2021 | 2,320 | 4,640 | 271 |
| 2023 | 2013-2022 | 2,591 | 5,182 | 272 |
| 2024 | 2013-2023 | 2,863 | 5,726 | 272 |
| 2025 | 2013-2024 | 3,135 | 6,270 | 272 |
| Final, not evaluation | 2013-2025 | 3,407 | 6,814 | 0 |

There are exactly 2,127 unique held-out games. Final-fit coefficients are reported separately, never counted as a ninth evaluation fold. Planned final fitting does not authorize current-board inference or publication.

## Comparators, metrics and fixed decision

Primary control: the saved postseason `candidate` column in its original matched-predictions file, replayed from the matching saved fold fit. Require finite serialized control replay within 1e-10 before any new fit. Also report saved `corrected`, `pgo_v0` and training-fold `constant` on the same game IDs; these are contextual references, not alternative controls to choose afterward.

Primary metric is pooled, equally weighted game-level margin MAE. Define improvement I = mean(abs(actual - control) - abs(actual - candidate)); positive is better. Do not average season MAEs equally for the primary. Missing or nonfinite predictions stop the attempt; do not drop games or replace them with a favorable baseline.

Retain the earlier weights study's practical further-study thresholds: I >= 0.05 points, strictly lower candidate MAE in at least five of eight seasons, and a strictly positive lower endpoint of the paired 95% season-block bootstrap improvement interval. Use the existing pinned bootstrap helper, 10,000 draws, seed 20260914, sampling eight whole seasons with replacement and recomputing pooled game-weighted improvement. This is a descriptive screen on reused data, not a multiplicity-adjusted discovery or promotion rule.

Secondary output: RMSE, mean predicted-minus-actual bias, every season, Week 1, Weeks 1-4, later weeks, each team with counts, and winner records with actual/predicted ties separate. Report all slices without selecting a new candidate or rule from them. No probabilities, calibration, totals, score ranges, ATS choice, confidence allocation, or 2026 rank comparison is part of this experiment.

Predeclared stability check: convert fitted transformed coefficients back to the original standardized basis:

```text
b_q = (theta_common + theta_contrast / 2) / sqrt(2)
b_t = (theta_common - theta_contrast / 2) / sqrt(2)
a_q = b_q / saved_scale_q
a_t = b_t / saved_scale_t
d_f = 0.01 * (a_q - a_t)
D = sum(abs(d_f - d_(f-1)) for the seven adjacent 2018-2025 folds) / 7
```

Here a is the effective raw coefficient; d is an algebraic coefficient contrast per one-percentage-point input unit, not a causal football intervention. The stability check passes only if candidate D <= control D + 1e-12. Report d, D, both raw coefficients, common/contrast contributions, signs and sample sizes for every fold; report all other effective raw coefficients and missing-indicator terms as well. Overlapping expanding folds make these descriptive, not independent coefficient draws. More attractive signs are not an acceptance criterion.

An overall further-study recommendation requires all integrity checks, all three primary MAE conditions, and the non-worsening stability check. Report primary-screen and stability-screen outcomes separately even when their conclusions differ. Failure remains a result; no second factor, new pair, sign flip, extra feature drop or outcome-driven retry is permitted.

## Reused history versus future evidence

All 2018-2025 seasons, prior ablations and Week 1 2026 results have already been inspected. No historical holdout is untouched. Historical actual-starter, roster identity and source-publication limitations are inherited and remain REVIEW REQUIRED; this design does not qualify numerical non-QB availability. Existing issued weights-monitor pairs belong to their original models and cannot be reused as prospective evidence for this candidate.

A possible later prospective phase is predeclared for 2026 REG Weeks 2-18, only if the exact final fit, unchanged feature recipe, capture protocol and executable manifest are frozen before the first Week 2 T-60 deadline. If that start is missed, this phase is NOT STARTED; choosing a later start requires a separately dated prospective protocol, not backfilling. This document does not activate a collector or issue those predictions.

Each future pair must use the same verified current input vector and source/QB identities, keep candidate/control coefficients frozen, and record actual capture, issuance and durable-write clocks strictly before its game's T. Later results update histories by the unchanged operational recipe; they do not refit weights. Keep the first issued pair immutable, including its matched control, and label later primary revisions separately. Grade only verified finals. Maintain an exclusion ledger for unavailable/late captures; never call the retained control the latest primary pick after it changes.

The only prospective formal review is after all scheduled 2026 REG games are final, with at least 150 eligible pairs across at least 12 weeks. Otherwise report INSUFFICIENT. Prespecify the same pooled MAE improvement >= 0.05 and a positive lower paired 95% week-block interval, using 10,000 draws and seed 20260914; report every week and source-coverage counts. Interim W/L and MAE are descriptive, with no sequential acceptance tests. Any result remains experimental pending independent source/computational review; no automatic promotion, publication or rewrite of primary picks follows.

## Preflight, preservation and allowed failures

Before later execution, verify every member of the original postseason package, earlier ablation package and saved coefficient audit against their manifests. Freeze exact charter/code/environment/input bytes, training/testing IDs, preprocessor inventory and transformation matrix in a new exclusive attempt. No live input fetch is required for the historical phase.

Required meaningful checks: independent transform/inverse and penalty algebra; factor-one rotation as a pure algebraic sanity check only, not a fitted second arm; observed zero versus one/both missing; feature-order permutation rejection; no post-transform rescaling; unchanged unrelated columns; future-row perturbation cannot alter a training transform; matching folds and original IDs; mirrored symmetry; and portable serialized prediction replay within 1e-10. Recompute metrics independently from saved predictions. Verify all protected inputs before/after and retain the full first attempt, including failure receipts.

Construction or integrity failures stop that attempt. Repairs require a distinct numbered attempt and a recorded reason; an unfavorable numerical result does not authorize a rerun. Nothing in this proposal changes existing charters, source-admission gates, sealed artifacts, probability/totals studies, production code, rankings or forecasts.
