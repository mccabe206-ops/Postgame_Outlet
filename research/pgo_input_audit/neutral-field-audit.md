# Neutral-field symmetry audit

The issued September fit has a **structural inconsistency with an orientation-free neutral-strength interpretation**, not a numerical implementation error. Its saved matchup regression assigns an equal-strength neutral matchup a nonzero designated-home margin. The published ratings and forecasts remain preserved.

## Exact frozen arithmetic

For a complete raw matchup vector `d`, the saved predictor is

`f(d) = b0 + sum_j beta_j * (d_j - median_j) / scale_j`.

For neutral venue and equal rest, let

`c = b0 - sum_j beta_j * median_j / scale_j`.

All 32 issued team states have complete inputs. Their centered rating difference cancels the common affine offset, so **`neutral_margin(A,B) = rating(A) - rating(B) + c`**.

| Quantity | Saved value |
|---|---:|
| Raw fitted intercept | +1.7869733439567297 |
| Effective neutral constant `c` | -0.8011250871186808 |
| Nonneutral venue slope, `beta_home_field / scale_home_field` | +2.5383602237165808 |
| NE rating minus LAR rating | +0.2873200553423345 |
| NE versus LAR, neutral/equal rest | -0.513805031776347 |
| LAR versus NE, neutral/equal rest | -1.088445142461015 |
| NE versus NE, neutral/equal rest | -0.801125087118681 |

The reverse pair sums to `2c`, rather than zero. With missing inputs, imputation and the symmetric missing-indicator terms can add further orientation-invariant offsets; merely subtracting the raw fitted intercept would not repair the general case.

Reproduce with `python research/pgo_input_audit/check_neutral.py`. The check pins the issued manifest, verifies the snapshot/fit hashes and sizes, independently implements the scalar fitted transform, then asserts agreement with production `_margin` and detection of both invariant violations. It performs no fit or artifact write.

## Source and caller trace

- [`Preprocessor.transform`](../../pgo_challenger.py) fills missing values with training medians, centers/scales finite values, and adds missing flags. `fit_huber_ridge` estimates an unrestricted intercept; `_ridge_solution` penalizes other coefficients using an unnormalized weighted sum of squared residuals.
- The same file's `_difference` and `_matchup_features` build home-minus-away inputs, zero `home_field` for neutral games, and use signed rest differences. `_neutral_feature_row` sets venue/rest to zero. `build_ratings` centers individual team scores, canceling their common offset.
- [`pgo_forecast_snapshot._margin`](../../pgo_forecast_snapshot.py) calls `_score` on those matchup features. Snapshot generation and `validate_snapshot` use that same path for saved margins and the old-selector comparison. Thus the verifier reproduces the inconsistency faithfully.
- [`pgo_prospective`](../../pgo_prospective.py) also predicts directly from transformed matchup differences. The weekly track inherits saved forecasts; the Lab displays the saved values. Research ratings in [`pgo_strength_evaluation._ratings`](../../pgo_strength_evaluation.py) and the opponent evaluator use centered individual states, so their constants also disappear from rank comparisons.

The September [design](../../docs/superpowers/specs/2026-09-07-pgo-snapshot-refresh-design.md) explicitly requires direct saved-fit matchup prediction and says team outputs are not separately validated neutral-field prices. No inspected definition documents the residual neutral constant as an intended designated-home advantage. A nominal-home effect is statistically possible, but that interpretation is **unvalidated**, not an established explanation for this offset.

## The issue persists in research fits

The final fits saved in `research/pgo_current_strength/run-20260908/fold-fits.json` have these complete-data neutral constants:

| Arm | Effective neutral constant |
|---|---:|
| Raw | -0.801125087119 |
| Recorded starter | -0.542551398264 |
| Starter plus recency | -0.558205319609 |
| Starter plus recency plus roster | -0.593537974496 |

The older opponent-adjusted team and team-plus-QB fits have constants -0.782660449601 and -0.811003479210. Neither experiment imposed symmetry.

The locked schedule (`schedule_results`, SHA-256 `cfb9c79a28ac1187a44be0bcfa0d8ff2f5a7ca201c5183a1dbf1e6d227d72f39`) contains **37 neutral games among the 2,127 evaluation games**: 2018: 3; 2019: 5; 2020: 3; 2021: 3; 2022: 6; 2023: 5; 2024: 5; 2025: 7. This small subgroup limits predictive conclusions independently of the algebra.

## Repair options and charter review

The minimal diagnostic proposed during review was a **postprocessing** arm:

`f_odd(A,B,r) = [f(A,B,neutral,r) - f(B,A,neutral,-r)] / 2`.

It uses the same fit, cancels even offsets, and could initially leave nonneutral games unchanged. For this NE/LAR pair it gives +0.287320055342 and its exact opposite. This diagnostic has not replaced any issued prediction.

The accepted [seventh-arm charter](charter-v3-symmetry.md) instead specifies a **broader refit**. Its mathematics is coherent: mirror every finite training feature and target; keep missing values missing; reverse venue from +1 to -1 for the same physical home stadium, and reverse rest. Fit preprocessing on the augmented training fold only. Finite-feature medians become zero; missing indicators remain even. A symmetric Huber/ridge solution should have negligible intercept and missing-indicator coefficients and an odd prediction function.

Using **alpha 200 rather than 100** correctly compensates for doubling observations in this solver's summed weighted-residual objective. This preserves regularization relative to original-game count; it does not make the new fit equivalent to the old one. Symmetric preprocessing/scales and the robust residual-scale estimate also change.

Apply the charter's absolute **1e-8** identity and reversal checks to every chronological fold and the final fit. Test finite and missing-input cases directly, including equal states and actual missingness patterns; coefficient checks alone are insufficient. Evaluate each original game once, with original venue/rest, and report original versus augmented training counts. Compare the refit against its declared controls on identical games, with pooled and neutral-subgroup MAE/RMSE/bias, season slices and paired season-block intervals. The symmetry guarantee is structural; it does not prove better forecasts, calibrated prices, or a CLEAN historical source vintage.

No fit, publication, or frozen-artifact change was performed for this audit.
