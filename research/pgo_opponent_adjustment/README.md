# Opponent adjustment and offseason consistency: results

**Neither opponent-adjusted candidate earned promotion.** The full adjustment
changes New England's September rank, but improves historical margin error by
only **0.00177 points per game**, with uncertainty spanning improvement and
regression. The published ratings and frozen forecasts remain unchanged.

The experiment ran September 7, 2026, 9:39–9:40 p.m. EDT. The
[pre-fit charter](charter.md) fixed the construction, parameters, folds, and
screening rules before fitting. This is exploratory retrospective research;
historical source-publication status remains **REVIEW REQUIRED**.

## What changed in the test

Three arms used the same 2,127 evaluation games from 2018–2025. Each season's
model trained on 2013 through the preceding season. Half-life 4, ridge alpha
100, and Huber delta 1 were held fixed. Each arm fitted its own preprocessing
and coefficients using only its training seasons.

The team-only arm adjusted four passing/rushing EPA inputs. The full arm also
adjusted QB passing/rushing EPA and its derived availability difference. For
offense, the correction credits performance against an above-average defense;
for defense, it credits prevention against an above-average offense. Opponent
strengths came from raw histories available before the current NFL week and
were centered on a play-weighted league reference. Corrections stayed frozen
throughout the week. No end-of-season opponent records entered these features.

The same raw QB selection and availability probabilities were used in every
historical arm. September comparisons kept the exact frozen expected QB1 for
each team. Other feature definitions were unchanged. Because coefficients were
refitted, their contribution changes are not isolated causal schedule penalties.

## Historical accuracy

Lower margin MAE and RMSE are better; values below are NFL points. Winner
accuracy excludes eight actual ties. There were no exact-zero predicted ties.

| Model | Margin MAE | Margin RMSE | Winner accuracy |
|---|---:|---:|---:|
| Training-fold constant mean margin | 11.057958 | 14.326250 | 54.03% |
| Existing PGO v0 | 10.266150 | 13.229772 | 63.05% |
| Raw EPA, fixed parameters | 10.193699 | 13.159375 | 63.95% |
| Team EPA adjusted | 10.197064 | 13.164440 | 64.51% |
| Team + QB EPA adjusted | 10.191932 | 13.160442 | 64.23% |

The comparison is against a matched fixed-parameter raw arm. Its 10.193699 MAE
differs from the previously published 10.205173 rolling result, which used a
different parameter-selection procedure. They are not interchangeable baselines.

| Candidate versus raw | MAE improvement | Season-block 95% interval | Seasons improved |
|---|---:|---:|---:|
| Team EPA | -0.003365 | [-0.021533, +0.013219] | 3/8 |
| Team + QB EPA | +0.001767 | [-0.022997, +0.021415] | 4/8 |

Both candidates fail the predeclared screen. Slightly better winner accuracy
does not override the primary margin-error result. Neither candidate's
season-block improvement interval against v0 excludes zero either. These
intervals use just eight season blocks and should not be treated as precise
population guarantees.

| Evaluation season | PGO v0 MAE | Raw MAE | Team EPA MAE | Team + QB EPA MAE |
|---|---:|---:|---:|---:|
| 2018 | 10.118525 | 10.210385 | 10.209983 | 10.212184 |
| 2019 | 10.621300 | 10.639276 | 10.646085 | 10.639693 |
| 2020 | 10.163501 | 10.045695 | 10.009362 | 10.004625 |
| 2021 | 11.309144 | 11.241510 | 11.218956 | 11.209018 |
| 2022 | 8.989205 | 8.863814 | 8.868337 | 8.849940 |
| 2023 | 10.467374 | 10.377650 | 10.383655 | 10.382255 |
| 2024 | 10.182203 | 9.886669 | 9.896637 | 9.877745 |
| 2025 | 10.279424 | 10.298187 | 10.354744 | 10.371573 |

For weeks 1–4, MAE changes from 10.046919 raw to 10.045926 team-only and
10.043244 full. For later weeks it changes from 10.239874 to 10.244610 and
10.238707, respectively. In 2025, the full candidate is worse than raw by
0.073386 points per game. No unfavorable season was removed.

## New England and Jacksonville

These are centered **model scores**, not calibrated neutral-field prices or
McCabe points. Each inference comparison uses all 32 teams; each arm's final
fit uses all 3,407 completed 2013–2025 games.

| September construction | NE rank / score | JAX rank / score |
|---|---:|---:|
| Frozen raw construction | #1 / 7.219 | #5 / 5.392 |
| Raw + existing offseason retention | #1 / 5.287 | #6 / 3.325 |
| Team EPA adjusted | #2 / 6.899 | #4 / 5.177 |
| Team EPA adjusted + retention | #1 / 4.784 | #8 / 2.914 |
| Team + QB EPA adjusted | #3 / 6.711 | #4 / 5.161 |
| Team + QB EPA adjusted + retention | #2 / 4.582 | #8 / 2.883 |

New England's team passing EPA falls from **0.323606 to 0.293520 per dropback**,
but the adjusted value still leads all 32 teams. Its defensive passing
prevention rate falls from 0.102912 to 0.052431, and Maye's shrunk historical
passing EPA falls from 0.131452 to 0.117479. The correction therefore removes
some favorable efficiency, while leaving a strong recent passing profile.

In the full adjusted fit with offseason retention, NE's two largest positive
contributions are results history (+2.128 model units) and team passing EPA
(+1.553). This explains why it remains near the top. It does not establish that
NE is truly the second-best team or that either contribution is an independent
team grade. Counterintuitive conditional coefficients elsewhere in the model
remain a separate reason for caution.

Jacksonville's team passing EPA falls from 0.185539 to 0.140264. Its overall
score falls under opponent adjustment alone, yet its rank rises to fourth
because other teams move too. The separate offseason correction moves it to
eighth. It would be incorrect to summarize this as “schedule adjustment moved
Jacksonville from fifth to eighth.”

## The offseason issue is real but separate

Historical training already halves the results rating at each new season.
The frozen September constructor stopped after the last completed 2025 game
and never crossed the 2026 boundary, so that input retained its end-of-2025
value. The research adapter implements a separate inference copy with the
existing 0.5 retention applied once. Repeated calls cannot compound it.

This consistency correction requires no new fitted parameter. It also creates
no historical MAE improvement: historical training already applied it. No
new offseason decay was imposed on team EPA or individual QB histories.

## Decision, evidence, and reproduction

Keep both opponent candidates on **HOLD**. The hypothesis produced measurable
rank sensitivity, but this experiment did not establish a useful accuracy gain.
Keep the offseason correction explicit in any future separately identified
edition; preserve previously issued forecasts and their original construction.
All evaluated seasons and the chosen parameters had already been inspected, so
this run supplies no untouched holdout or prospective validation claim.

All 67 frozen source files were verified; the historical walkers used the 66
historical inputs and excluded the 2026 roster. Added correction histories
crossed 226 NFL week boundaries. The only missing-opponent fallback was the
first 2013 week: 128 team-feature corrections set to zero. Final raw fit
coefficients, medians, scales, feature names, missing flags, and training count
exactly reproduced the frozen public fit. All 192 team/variant contribution
breakdowns reconcile.

- [All 32 teams across six constructions](run-20260907/ratings.csv)
- [All matched game predictions](run-20260907/matched-predictions.csv)
- [Metrics, both bootstrap comparisons, and screening](run-20260907/metrics.json)
- [Fold fits, preprocessing, and training game IDs](run-20260907/fold-fits.json)
- [Raw features and contributions for all variants](run-20260907/rating-details.json)
- [Run receipt and preserved-file/source hashes](run-20260907/run-receipt.json)
- [Artifact manifest](run-20260907/manifest.json)

From the repository root, with the existing frozen source cache available:

```powershell
python -m unittest tests.test_pgo_challenger tests.test_pgo_opponent_adjustment tests.test_pgo_opponent_evaluation tests.test_pgo_forecast_snapshot -q
python pgo_opponent_evaluation.py --output research/pgo_opponent_adjustment/a-new-run-directory
```

Each run requires a new directory. A start receipt without a manifest marks an
incomplete attempt. No source fetching or public update occurs. The exact
[evaluator used for this run](evaluator-at-run.py.txt) is preserved and matches
its recorded SHA-256. Afterward, the current evaluator received an additional
alternate-cache integrity check; no feature, fitting, metric, or ranking logic
changed, and the experiment was not refitted after that guard-only repair.

Final verification: **109 tests passed**. An independent calculation reproduced
the pooled/per-season MAEs, season-block intervals, all 32 ranks in each variant,
and all 192 contribution sums. All eight manifested files, 67 source files,
and 188 existing tracked files matched their run-receipt hashes. The run
manifest SHA-256 is
`0e2fd095579fdd33a6ab1c728eeeb07c373779cdb32da6c8d14ce48b08de5998`.
At completion this work was local and uncommitted; no publish, push, or deployment occurred.
