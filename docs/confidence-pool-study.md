# Confidence-pool probability study

September 9, 2026. **EXPERIMENTAL / HOLD. No current probabilities were issued and no saved forecasts were changed.**

The fixed chronological diagnostic evaluated 1,615 games from 2020-2025 after 2018-2019 warmup. Each calibration used only earlier out-of-fold seasons.

| Construction | Three-outcome log loss | Three-outcome Brier | Realized pool points | Expected pool points |
|---|---:|---:|---:|---:|
| Corrected | 0.648094 | 0.441205 | 9106 | 9094.73 |
| Postseason | 0.647142 | 0.440351 | 9146 | 9091.83 |
| Constant | 0.711287 | 0.501591 | 6821 | 7034.07 |

The predefined diagnostic screen **PASSED**: postseason log loss improved over corrected in 5 of six seasons. This does not lift HOLD or establish future probability reliability.

Across 107 available-game weekly slates, favorite choices and confidence ordering were unchanged from each margin model's absolute-margin ordering: **True**. A positive monotonic scalar calibration cannot improve that ordering; differences between corrected and postseason pool points come from their original margin forecasts.

Confidence values are the unique integers 1 through the available slate size, assigned in ascending selected-team unconditional win probability. Wrong picks and ties earn zero. This maximizes expected total points under the supplied probabilities, not the chance of winning a pool.

The scalar logistic fit minimizes summed non-tie negative log likelihood plus 0.5 times slope squared, with nonnegative slope and no intercept. The training-only tie estimate is (ties+1)/(games+2); remaining mass is split between home and away. The constant comparator adds one pseudocount to each of the three outcome counts. Brier is the sum over all three classes; log loss uses a 1e-15 floor.

Limits: these historical seasons were already inspected; underlying forecast source timing and recorded-starter limitations remain. Training predictions came from changing past-season models, so calibration transfer is not guaranteed. A constant tie rate does not capture margin-specific tie risk; the small number of ties makes this uncertain. Fixed ten-bin selected-team reliability, season, Week 1 and Weeks 1-4 results are saved with bin counts. Sparse and empty bins cannot demonstrate reliability. No probability percentages from this study are attached to current locked forecasts.

Weekly results are retrospective slates of matched available games, not actual entries or proof of any particular pool rules. Missing or canceled games, including the unplayed 2022 Buffalo-Cincinnati game, are absent rather than adjudicated under a real contest policy. Predictions must also share a valid contest lock time before prospective weekly-pool use. Game dependence does not alter the expectation of a sum but does affect pool-winning chances.

[Charter](../research/pgo_confidence_pool_20260909/CHARTER.md), [metrics and reliability bins](../research/pgo_confidence_pool_20260909/attempt01/metrics.json), [row predictions](../research/pgo_confidence_pool_20260909/attempt01/predictions.csv), [weekly points](../research/pgo_confidence_pool_20260909/attempt01/weekly-points.json), [source and code hashes](../research/pgo_confidence_pool_20260909/attempt01/manifest.json).
