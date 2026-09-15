# Sack-avoidance weight test: retain the published model

The fixed experiment did not improve historical margin predictions. Average
margin error rose from **10.10210 to 10.10520 NFL points**. Its two overlapping
sack-avoidance weights became more stable across fitted seasons, but that did
not produce better predictions. The candidate is **not adopted**.

Both models were evaluated on the same 2,127 regular-season games from
2018–2025. Each evaluation model used only earlier seasons for fitting. These
seasons have been inspected before, so this is a diagnostic comparison rather
than a new test on untouched games. Historical source timing and expected-QB
limitations remain **REVIEW REQUIRED**.

## What changed

The QB and team sack-avoidance measurements partly describe the same plays.
The experiment kept both inputs and all other inputs, but made it harder for
their fitted weights to diverge. It used the exact saved inputs, preprocessing,
folds and optimizer. It did not add defensive depth, new injury weights,
probabilities, ATS choices, confidence points, or 2026 results.

Eight evaluation fits and one separate final historical fit completed once.
The final fit is archived; it was not used to issue forecasts or rankings.

## Locked decision rules

| Requirement fixed before fitting | Result | Screen |
| --- | --- | --- |
| Reduce average margin error by at least 0.05 NFL points | Error increased by 0.003097 | FAIL |
| Improve at least 5 of 8 seasons | Improved 3 of 8 | FAIL |
| Paired 95% season-block interval entirely above zero improvement | −0.013892 to +0.010246 | FAIL |
| Do not increase coefficient drift | 0.157450 → 0.085437 | PASS |
| Source, fold, preprocessing, symmetry and replay checks | Passed | PASS |

The overall further-study screen is **FAIL**. Stable coefficients alone are
insufficient under the written rules. No factor change, alternate pair,
outcome-based retry or live adoption followed this result.

The interval uses 10,000 draws of eight whole seasons with replacement, seed
20260914, and pooled game-weighted error. Positive improvement would favor the
candidate. Reused seasons and prior experiments limit inference. Drift is the
mean absolute change across seven adjacent folds in the effective raw QB/team
coefficient contrast per percentage-point unit; it is not a football grade or
a causal effect.

## Margin error by season and timing

Average absolute margin error, in NFL points; lower is better.

| Slice | Games | Saved postseason control | Candidate |
| --- | ---: | ---: | ---: |
| All evaluation games | 2,127 | 10.10210 | 10.10520 |
| 2018 | 256 | 10.09726 | 10.11558 |
| 2019 | 256 | 10.46005 | 10.48500 |
| 2020 | 256 | 10.20243 | 10.16280 |
| 2021 | 272 | 11.04565 | 11.04380 |
| 2022 | 271 | 8.82518 | 8.83745 |
| 2023 | 272 | 10.32592 | 10.32964 |
| 2024 | 272 | 9.73272 | 9.73032 |
| 2025 | 272 | 10.14957 | 10.15869 |
| Week 1 | 128 | 9.89863 | 9.92873 |
| Weeks 1–4 | 509 | 9.79644 | 9.81457 |
| Weeks 5–18 | 1,618 | 10.19826 | 10.19663 |

Week 1 is contained in Weeks 1–4; these slices are not independent samples.

## Secondary results and contextual references

The control picked 1,383 of 2,119 non-tied winners correctly (65.27%); the
candidate picked 1,377 (64.98%). Eight actual ties remain in margin errors and
are excluded from winner accuracy. Neither model predicted a tie.

Control/candidate RMSE was 13.04464/13.04577 NFL points. Mean predicted-minus-
actual margin bias was +0.15020/+0.14985 points. Winner accuracy and coefficient
signs were not the primary acceptance rule.

On the identical 2,127 games, the saved regular-season corrected reference had
10.09946 margin MAE, PGO v0 had 10.26615 and the training-fold constant had
11.05796. These predeclared references are context; the saved postseason
control remains the designated comparison.

Complete per-team, season, timing, winner, RMSE and bias results are in
[metrics.json](run-attempt01/metrics.json). Every effective raw coefficient,
missing-indicator term, pair sign, contribution summary and sample size is
retained in [coefficient-report.json](run-attempt01/coefficient-report.json).
Final-fit values are separately labeled and excluded from fold stability.

## Verification and artifacts

- 135 protected source pins match before and after the run.
- Independent training-preprocessor reconstruction matched exactly.
- Ten no-fit algebra and boundary tests passed.
- The separate verifier imports no model and performs no fitting. It checked
  all 2,127 predictions using the original raw-feature basis, all 230 metric
  views, coefficient conversion, drift, bootstrap, locked gates and manifests.
- Maximum independent prediction difference was 3.55e-15 NFL points.
- All 3,407 final-training predictions were finite in independent replay.

Run manifest SHA-256:
`b402573ba466c571fd826d77c67a27fae548c6231cf0fb46c4be0ea6437f6786`.
The [independent verification receipt](independent-verification.json),
[original sealed charter](preflight-attempt02/charter.md), and
[root preflight review](root-preflight-review.md) preserve the evidence.
The failed first preflight and successful second preflight both remain intact;
the first failed before any candidate fitting due to a path-key assumption.

Prospective collection for this candidate is **NOT STARTED**. Existing public
picks, rankings and model weights remain unchanged by this experiment.
