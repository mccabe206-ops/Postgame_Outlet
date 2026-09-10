# PGO penalty-history candidate: model card

**FAIL: adding penalty history did not improve average forecast error. The candidate is not promoted and does not replace the main PGO model.** It remains **EXPERIMENTAL / HOLD**, retained only for a separate, fixed-weight prospective comparison. Six seasons improved slightly, but the combined result was slightly worse and the uncertainty interval includes zero.

## Identity and intended use

Owner: **Postgame Outlet / Alex**. Version: `pgo-penalty-candidate-2026-09-10`; prospective series: `pgo-penalty-shadow-2026`. Card date: September 10, 2026. The [locked charter](charter.md) defines the experiment and review rules.

The audience is PGO's owner and readers comparing dated forecasts. The output is an NFL regular-season game's estimated **home score minus away score**, including overtime. One row is one game. A positive margin favors the home team; zero means no directional pick. Margin error includes games that end tied.

Prospective records must be durably saved before the real kickoff-minus-60-minute deadline. Each candidate margin is paired with a frozen postseason control margin computed from the same saved team, quarterback, venue and rest inputs. This test does not change main rankings or issued picks, and does not produce new probabilities, confidence allocations, score totals, injury weights, or profit claims. The already-final NE-Seattle opener is excluded from new candidate issuance.

## Data and feature definition

The baseline is the frozen [September 9 postseason experiment](../pgo_postseason_candidate/run-20260909-attempt01/manifest.json), specifically its `candidate` prediction column. Its **3,407 regular-season feature rows from 2013-2025** were copied with every original field preserved. Historical construction uses **3,562 completed REG/WC/DIV/CON/SB games and 7,124 team-game observations**. Playoffs update prior history; only regular-season games are fitting and evaluation targets.

The added feature, `prior_penalty_yards_per_game`, is the home team's prior exponentially weighted penalty yards per game minus the away team's. With decay `0.5 ** (1 / 4)`, each completed game updates numerator to `decay * old numerator + penalty yards` and denominator to `decay * old denominator + 1`. The rate is numerator divided by denominator. This is a **four-game half-life**, not an average of only four games and not a deduction per flag. Penalty counts are audited but are not a second feature.

Features are read before updating any game in the same kickoff batch. History carries through playoffs and across seasons. Missing history remains missing; real zero-yard observations stay zero. Sources require exact game, team, opponent, season, week and season-type identities, unique observations, and nonnegative integer penalty counts and yards. The pinned schedule and 13 yearly team-stat files are recorded with hashes in the [run receipt](run-20260910-attempt01/run-receipt.json). Required penalty coverage was complete, including 24 genuine zero-yard observations.

**Historical source vintage: REVIEW REQUIRED.** These are provider snapshots with unresolved historical revision/publication timing. Prior-game chronology is checked, but the data do not recreate what a historical T-60 feed actually contained.

## Fitting and validation

The experiment adds one feature and refits **all coefficients**, using the existing symmetric-perspective Huber ridge procedure: alpha 200, Huber delta 1, training-fold-only imputation and scaling. It uses eight expanding earlier-season training folds to evaluate 2018-2025, followed by one final fit on all 3,407 regular-season rows. There were nine fits, with no hyperparameter search.

The final penalty coefficient is **-0.0059123683 points per additional yard/game in the home-minus-away prior-rate difference**. A 10-yard larger difference changes the fitted margin by about **-0.059 points**, holding the other inputs fixed. This is an association inside the fitted formula, not a causal cost of committing penalties. Because all weights were refitted, this coefficient alone does not explain the full candidate-versus-baseline change.

All models below are compared on the same **2,127 evaluation games**. MAE is average absolute margin error; RMSE gives larger misses more weight. Lower is better for both. Bias is predicted margin minus actual margin.

| Model | MAE, points | RMSE, points | Bias, points |
|---|---:|---:|---:|
| Postseason baseline | 10.1021019568 | 13.044643 | +0.150197 |
| Penalty candidate | 10.1022524340 | 13.047519 | +0.151525 |
| Saved September 8 corrected model | 10.0994558676 | 13.044989 | +0.152719 |
| Saved PGO v0 | 10.2661502345 | 13.229772 | +0.972907 |
| Saved constant reference | 11.0579581552 | 14.326250 | +0.424107 |

The candidate's MAE improvement, defined as baseline minus candidate, was **-0.0001504772 points**. The paired season-block bootstrap used 10,000 draws, seed 20260910, and eight season blocks. Its 95% improvement interval was **[-0.0044405108, +0.0032710250] points**.

The predeclared further-study screen required at least 0.05 points lower pooled MAE, improvement in at least five of eight seasons, and an interval lower bound above zero. Only the season-count condition passed. The complete result is **FAIL**.

| Evaluation season | Games | Baseline MAE | Candidate MAE | Improvement |
|---|---:|---:|---:|---:|
| 2018 | 256 | 10.097264 | 10.088862 | +0.008402 |
| 2019 | 256 | 10.460045 | 10.462890 | -0.002845 |
| 2020 | 256 | 10.202435 | 10.200933 | +0.001502 |
| 2021 | 272 | 11.045653 | 11.045167 | +0.000486 |
| 2022 | 271 | 8.825180 | 8.837956 | -0.012776 |
| 2023 | 272 | 10.325922 | 10.324693 | +0.001230 |
| 2024 | 272 | 9.732725 | 9.730770 | +0.001955 |
| 2025 | 272 | 10.149570 | 10.148332 | +0.001238 |

| Fixed slice | Games | Baseline MAE | Candidate MAE |
|---|---:|---:|---:|
| Week 1 | 128 | 9.898632 | 9.899277 |
| Weeks 1-4 | 509 | 9.796440 | 9.796895 |
| Weeks 5-18 | 1618 | 10.198259 | 10.198314 |
| Neutral-site games | 37 | 8.374465 | 8.383184 |

On the 2,119 games with a non-tied final, winner accuracy was 1,383/2,119 (65.27%) for the baseline and 1,385/2,119 (65.36%) for the candidate. Eight actual ties were reported separately. Winner accuracy was secondary and does not overturn the failed margin-error screen. No candidate probability calibration was evaluated.

The [full metrics](run-20260910-attempt01/metrics.json) include all team slices and per-fold coefficients. The large-predicted-margin slice is selected separately by each model (518 baseline games versus 517 candidate games), so its two averages are not an identical-game paired comparison. These historical seasons have been reused in earlier model work: the results are diagnostic, not a fresh holdout or evidence of profitability.

## Prospective monitoring and stop conditions

The existing season updater performs descriptive checks on its scheduled cycle. It updates candidate/control W/L/T, paired MAE, RMSE and bias after verified finals. The existing complete-week and statistics gates determine when a new weekly slate can be prepared. **Weights stay fixed: no game-by-game refits, repeated acceptance tests, or automatic promotion.**

Existing candidate/control pairs remain immutable even when primary picks later change. Their matched control is the baseline saved at candidate issuance, not a newer primary forecast. Source, identity, hash, history-clock or cutoff failures block new candidate issuance and expose a separate reason. Previously saved pairs remain available and can still receive grades from verified finals. A durable-write deadline check prevents a late new pair from becoming the published state; inconsistent or revised accepted finals require review.

The next formal fresh-cohort review is **after the 2026 regular season**, with at least **150 paired games across 12 eligible weeks**. Otherwise report insufficient prospective evidence. Alex/PGO owns any subsequent continuation, retirement or separately chartered revision. Failure or non-improvement does not authorize tuning this version. Every attempt is preserved; never rerun into an existing attempt directory.

## Evidence and verification

- [Preparation manifest](prepared-20260910-attempt01/manifest.json), [run manifest](run-20260910-attempt01/manifest.json), [paired predictions CSV](run-20260910-attempt01/matched-predictions.csv), [full metrics](run-20260910-attempt01/metrics.json), [final fit](run-20260910-attempt01/final-fit.json), and [32-team seed](run-20260910-attempt01/penalty-seed.json).
- Run manifest SHA-256: `15291ce6b302a64733b53e3616bc37c43a3f00825b889d14ab19f0b0b916d5dc`. The [runtime package manifest](../../docs/evidence/penalty-model-2026/manifest.json) is separately pinned as `298b6f9d7624d3589763ab78ecb80583c1b8e43097e5da8adc1f0ba5f2faa628`.
- Frozen baseline replay covers all 2,127 games with maximum numerical difference `3.552713678800501e-15`. Candidate serialized-fit replay has the same maximum difference. Source/code and issued-evidence before/after checks passed in the saved run receipt.
- Focused candidate checks passed for prior-only updates, same-kickoff ordering, future perturbations, zero/missing history, seeded replay, identity failures, baseline-field preservation, symmetric feature reversal, screen thresholds, and raw-yard coefficient scaling. Fitting also checks serialized prediction replay and symmetry invariants.
- Independent read-only reviews checked baseline/source architecture and the final monitor's source timing, same-input control reconciliation, immutable pairs, grading during candidate failure, and durable T-60 protection. The eight monitor/integration tests passed independently. These checks establish implementation properties, not predictive acceptance.

Implementation uses Python, the repository's installed NumPy, and existing fit/metric helpers. Code and source digests are bound in the run receipt. Read-only verification can run `python -m unittest tests.test_pgo_penalty_candidate tests.test_pgo_penalty_monitor tests.test_pgo_penalty_integration`; these tests do not rerun the fixed historical experiment. See [candidate.py](candidate.py) for the exclusive prepare/fit commands and [the season operations guide](../../docs/pgo-season-operations.md) for scheduling. This card documents the failed experiment; it grants no promotion or permission to overwrite an issued forecast.
