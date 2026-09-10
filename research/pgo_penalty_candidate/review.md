# Independent penalty candidate review — September 10, 2026

The saved experiment is internally reproducible and fails its locked improvement screen. The penalty candidate's margin MAE is **10.102252433999**, versus **10.102101956754** for the postseason baseline: an increase in error of **0.000150477245 points per game**. Six of eight seasons improve, but neither the required pooled improvement nor the positive confidence-bound criterion passes. Scientific status remains **EXPERIMENTAL / HOLD**. These results do not support promotion or a claim of improved predictive accuracy.

Independent review completed at approximately 2026-09-10 09:32 UTC. The reviewer performed zero fits and changed no sources, feature tables, coefficients, forecasts, or issued evidence. The only new artifact is this report.

## Bound artifacts and audit contract

- Locked charter SHA-256: `073a491cbe704b19934d7c9ab313bdd51eb32e2685124a53131a6d3f49ec3730`.
- Reviewed candidate implementation SHA-256: `8620710473bb967248756b45819bbdbd5288a0a8ca16d7fe15c8f78bf1a12be4`.
- Preparation: [prepared-20260910-attempt01/manifest.json](prepared-20260910-attempt01/manifest.json), SHA-256 `c253ee17a6a446d5e77410a07b6658696f3d25b83416840b59fb16e614eb09a6`.
- Fixed run: [run-20260910-attempt01/manifest.json](run-20260910-attempt01/manifest.json), SHA-256 `15291ce6b302a64733b53e3616bc37c43a3f00825b889d14ab19f0b0b916d5dc`.
- Postseason baseline manifest SHA-256: `a58aeff835471182a555e4b926beafd0db01c7c5e3fe19827ddf56bd03f2514a`.

The target is final home-minus-away NFL scoring margin, including overtime. One evaluation row is one regular-season game. Operational decision time is kickoff minus 60 minutes. The added feature is the difference between the teams' prior exponentially weighted penalty yards per game, with a four-game half-life and history carried through the postseason and across seasons. No penalty-count feature, arbitrary point deduction, sign constraint, or hyperparameter search is included.

The baseline comparison uses the original postseason run's `candidate` predictions, copied into the new CSV's `postseason` column. It does not substitute the September 8 corrected model. All four comparator columns and their identities, targets, teams, dates, and neutral-site flags match the original saved CSV exactly.

## Source, temporal, and split checks

**Temporal construction: CLEAN within the declared historical-data construction.** Direct reconstruction from the 14 pinned raw files matched every added feature and every final team accumulator exactly. The inventory contains 3,562 completed games, 7,124 team observations, 44,594 penalties, and 375,967 penalty yards. All 32 team accumulators are present. Twenty-four actual zero-yard observations remain zero; the 16 games without an initial pair of team histories remain missing.

Raw team observations bind to game ID, canonical team, opponent, season, week, and REG/POST membership. Duplicate or missing required identities and negative, fractional, nonfinite, or empty penalty values fail closed. The provider defines `penalty_yards` as yardage lost through penalties; the feature's units and direction agree with that meaning. [Official nflfastR variable dictionary](https://raw.githubusercontent.com/nflverse/nflfastR/master/data-raw/nfl_stats_variables.json).

Pregame values precede the game's own history update. All games sharing a kickoff are formed before their batch updates. The independent reconstruction also confirmed each team's preceding observation had a strictly earlier kickoff. Current/future perturbation, kickoff-order invariance, postseason/offseason carry, zero/missing handling, and seeded replay are covered by the seven focused tests. Those tests passed again during this review: **7 tests, 0.284 seconds, no failures**.

All 3,407 original regular-season rows retain every original field and all 24 original features exactly; the candidate appends one feature. Expanding evaluation folds contain **256, 256, 256, 272, 271, 272, 272, 272** games for 2018–2025. Training IDs and validation IDs match each saved fit receipt exactly, and the latest training kickoff precedes the earliest evaluation kickoff in each fold. Only training rows are mirrored; each original evaluation game is scored once.

The reviewer independently reconstructed every saved median, scale, and missing-feature indicator from each fold's mirrored training rows, including the final fit. Scales matched exactly, with maximum absolute difference **0**. All nine receipts retain ridge alpha **200**, Huber delta **1**, and the prescribed half-life. There is no evidence of evaluation rows entering these transformations.

**Historical source vintage: REVIEW REQUIRED.** The pinned tables do not establish when every historical statistic or revision became available. Event chronology is verified; availability of each historical input at its original T-60 decision time is not reconstructed. This limitation also applies to the inherited baseline inputs, which were preserved rather than recertified. There is no detected same-game, future-history, join, split, or preprocessing contamination in the added feature. The unresolved publication/revision history prevents an unqualified overall CLEAN leakage verdict.

## Independent numerical reconciliation

The reviewer recalculated all reported metric views directly from the paired CSV: overall, Week 1, Weeks 1–4, Weeks 5–18, neutral-site games, model-specific large predicted margins, eight seasons, and all 32 team perspectives. All reported values agree within `1e-12`. The large-margin slice is selected separately for each model and is descriptive, rather than a common-cohort primary comparison.

| Model | Games | Margin MAE | RMSE | Bias, predicted minus actual | Correct winners / non-ties |
|---|---:|---:|---:|---:|---:|
| Postseason baseline | 2,127 | 10.102101956754 | 13.044643073814 | 0.150196864412 | 1,383 / 2,119 |
| Penalty candidate | 2,127 | 10.102252433999 | 13.047519172968 | 0.151525230872 | 1,385 / 2,119 |
| September 8 corrected | 2,127 | 10.099455867556 | 13.044988969614 | 0.152719457277 | 1,392 / 2,119 |
| PGO v0 | 2,127 | 10.266150234489 | 13.229771660094 | 0.972907406031 | 1,336 / 2,119 |
| Constant reference | 2,127 | 11.057958155158 | 14.326249822307 | 0.424106962107 | 1,145 / 2,119 |

Eight actual ties remain in the margin-error metrics and are excluded from winner accuracy. No model in this paired sample predicts an exact tie. Week 1 MAE also increases slightly, from **9.898632381158** to **9.899277114782**, on the same 128 games. The two additional correct winners overall do not overturn the locked primary metric.

All four paired season-block bootstrap comparisons were independently recalculated with **10,000 draws**, seed **20260910**, and eight resampled season blocks. For candidate improvement over postseason, defined as baseline absolute error minus candidate absolute error, the pooled mean is **-0.000150477245** and the 95% interval is **[-0.004440510760, 0.003271025029]**.

| Locked screen condition | Result |
|---|---|
| At least 0.05 points lower pooled MAE | FAIL: error increases by 0.000150477245 |
| Improvement in at least five of eight seasons | PASS: six seasons |
| Positive lower 95% paired improvement bound | FAIL: lower bound -0.004440510760 |
| Overall screen | **FAIL / EXPERIMENTAL / HOLD** |

Manual serialized coefficient arithmetic reproduces all 2,127 candidate evaluation predictions and agrees with the replay path for all 3,407 final-fit training probes. Maximum absolute replay discrepancy is **3.552713678800501e-15**. Team-perspective reversal, including missing features, has maximum prediction-sum error **1.7763568394002505e-15**. The final fit's fields exactly match the ninth saved fit receipt; this is replay, not a repeat fit.

The final penalty coefficient is **-0.00591236827755157 margin points per additional yard of home-minus-away prior penalty rate**, after reversing the saved feature standardization. Holding the other candidate inputs fixed, a ten-yard larger difference contributes about **-0.0591 points**. All coefficients were refitted together, so this single contribution does not equal the whole change from the postseason model. It is an association in the fitted model, not a causal cost per penalty yard or a current-game penalty adjustment.

## Integrity and disposition

All preparation, run, and baseline manifest members pass independent byte-length and SHA-256 checks. Preparation and run start/end receipts bind the same code and raw-source inventory. The reviewer independently checked the **366 pre-existing issued files**, **10 protected code files**, and **14 raw sources** against those pins, including a final check after numerical replay; all remain unchanged. The preparation receipt records zero fits, and the run records the prescribed eight evaluation fits plus one final fit, for nine total. The review invokes no fitting routine; the numerical replay explicitly blocks fitting entry points.

Overall leakage verdict: **REVIEW REQUIRED for historical publication/revision vintages; temporal construction and saved numerical evidence pass**. No repair to the saved experiment is required by this review. Its non-improvement is a result, not a reason to tune or replace the spent run.

These reused 2018–2025 folds are not a fresh holdout. Any authorized prospective monitoring must retain separate candidate/control snapshots on the same inputs and games, enforce the real T-60 durable-write cutoff, exclude the already-final NE–SEA opener, and preserve frozen weights and issued picks. The charter's later fresh-cohort review requires at least 150 paired games across at least 12 eligible weeks after the 2026 regular season. There is no automatic promotion, no candidate probability or confidence claim, and no evidence here for changing the main model's penalty or injury weights.
