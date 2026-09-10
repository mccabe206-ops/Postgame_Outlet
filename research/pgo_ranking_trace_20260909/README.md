# PGO ranking disagreements: frozen input trace

The trace found two concrete roster-to-snap identity failures, unpriced availability, and large ranking effects from crude age/draft descriptors. This explains the saved board's construction; it does not establish player value or validate that ordering.

**EXPERIMENTAL / HOLD.** Historical margin MAE remains **10.133540 candidate versus 10.099456 corrected**, over the same 2,127 games. Only 3 of 8 seasons improve; all three fixed criteria failed. The paired improvement interval is [-0.102307, +0.044823]. Nothing in this post-hoc audit changes that result.

Inputs remain **September 8, 2026, 15:01:38 UTC (11:01:38 EDT)**. This is a saved-input trace, not a current health update. No coefficient fitting, feature-preparation rerun, source refresh, forecast change, model adoption or publication occurred.

## What the ranking movements actually contain

For each feature, apply its saved coefficient and scale, then subtract its average contribution across the same 32 teams. Sum these centered terms to recover each rating. Compare candidate and corrected terms using the identical original base feature cells. Separate the ten added descriptors from changes to existing coefficients/preprocessing in the joint refit. This is an exact additive accounting convention, not a causal attribution or a removal/replacement experiment.

All numbers below are centered model-rating units. The four component columns sum to the total change, allowing rounding. The five largest absolute rating moves are PIT, MIN, NYG, KC and DET; DEN and the LAR/NE comparison address the other specific disagreements raised.

| Team | Corrected to candidate rank | Total change | New QB-age terms | New offense descriptors | New defense descriptors | Existing-feature reweighting |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PIT | 16 to 8 | +2.057 | +0.876 | +0.213 | +0.619 | +0.350 |
| MIN | 15 to 18 | -1.266 | -0.191 | -0.189 | -0.403 | -0.483 |
| NYG | 24 to 19 | +1.007 | +0.616 | -0.020 | +0.579 | -0.168 |
| KC | 20 to 22 | -0.796 | -0.294 | -0.054 | -0.659 | +0.211 |
| DET | 12 to 10 | +0.776 | -0.315 | +0.121 | +1.016 | -0.046 |
| DEN | 10 to 13 | -0.337 | +0.074 | -0.236 | +0.244 | -0.419 |
| LAR | 2 to 1 | +0.368 | +0.104 | -0.067 | +0.289 | +0.041 |
| NE | 1 to 2 | -0.356 | +0.478 | -0.117 | -0.598 | -0.119 |

**Pittsburgh:** +0.876 comes from Aaron Rodgers' age terms, +0.619 from defense descriptors, +0.213 from offense descriptors and +0.350 from reweighting the original features. The frozen DOB makes Rodgers 42.769 years old. His squared-age term contributes +2.496 and linear-age term -1.621. The defensive draft feature gets its largest numerator components from Jalen Ramsey (pick 5), Patrick Queen (28) and Joey Porter Jr. (32). This is no direct measurement of those players' present football value.

**Minnesota:** -0.483 is existing-feature reweighting and -0.403 is the new defense block. Its defensive draft term alone contributes -0.680. Blank draft records for positive-role players such as Eric Wilson, James Pierre and Jalen Redmond encode zero in the numerator while retaining their roles in the denominator. The selected QB is Kyler Murray, inherited from the frozen expected-QB package; this adapter did not choose him or replace J.J. McCarthy.

**Giants:** Jaxson Dart's age terms add +0.616 and defense descriptors add +0.579. The draft feature is led by Abdul Carter (pick 3), Kayvon Thibodeaux (5) and Tremaine Edmunds (16). A separate Jon Runyan snap-identity failure is documented below. No corrected-input counterfactual was computed, so that failure is not assigned a rating delta.

**Kansas City:** the new defense block contributes -0.659 and Mahomes' age terms -0.294; reweighting existing features offsets +0.211. Defensive draft prior contributes -0.379 and defensive rookie capital -0.260. The rookie field is largely Mansoor Delane, Peter Woods and R Mason Thomas, none with prior role history; it is draft-record arithmetic, not evidence they will play poorly. KC was already #20 in the corrected board. Existing team sack-avoidance and passing-efficiency terms are negative contributions, while Mahomes' QB EPA term is +0.830. The low ranking is not explained by the model overlooking his identity.

**Detroit:** its +1.016 defense-descriptor contribution is the main driver. Aidan Hutchinson and Devin White lead the defensive draft numerator. A low share of defensive role mass under age 26 also raises the score because that feature has a negative fitted coefficient.

**Denver:** the added block is slightly positive overall (+0.082). The decline is primarily reweighting the original features (-0.419). Within the new block, low defensive young-role share contributes +0.527, while defensive draft prior contributes -0.400. Alex Singleton, Malcolm Roach, Ja'Quan McMillian and Dondrea Tillman have blank draft entries encoded as zero. Do not describe Denver's -0.836 QB sack-avoidance contribution as evidence of poor sack avoidance: its input is above the current 32-QB mean, but its conditional coefficient is negative. This illustrates why reading correlated coefficients as standalone football judgments is unsafe.

## Why LAR passed NE

The corrected LAR-minus-NE gap was -0.693714. The candidate gap is +0.030121, a +0.723835 change:

| Component of gap change | LAR relative to NE |
| --- | ---: |
| New QB-age terms | -0.374218 |
| New offense descriptors | +0.050100 |
| New defense descriptors | +0.887700 |
| Existing-feature reweighting | +0.160254 |

The defensive draft feature alone accounts for +0.675603 of that gap change. The frozen Rams roster lists Myles Garrett, whose pick-1 record and prior role contribute 0.072486 of LAR's 0.149323 defensive draft feature. NE's corresponding feature is 0.089337, with nine blank draft records; seven have positive prior role, including Robert Spillane, Christian Elliss and Cory Durden. This statement reports the saved roster input, not independently verified current roster news.

The new age block actually favors Maye over Stafford by 0.374218 in this comparison. LAR taking first is therefore not principally an age-based endorsement of Stafford, and no numerical injury adjustment caused the flip. A 0.030121 lead is not a rank-confidence statement.

## Concrete input defects and limitations

1. **Failed identities become false zero usage.** The inherited snap resolver tries roster PFR ID, then exact normalized name (case/whitespace only). NE Mike Onwenu has no roster PFR ID, while snap files say Michael Onwenu / OnweMi00. NYG Jon Runyan similarly mismatches Jon Runyan Jr. / RunyJo00. Both saved offense histories are [0,0,0,0]. Raw 2025 snaps show Onwenu playing 52/74/58/59 offensive snaps in his last four ACT regular-season games; Runyan 55/68/64/75. These are verified identity failures, not injuries or nonparticipation. They contribute zero role mass to the candidate's offense descriptors. The original corrected board does not use these new non-QB descriptors; this finding alone does not prove its current numerical ratings are affected.
2. **Availability is annotation-only for these non-QB terms.** All 32 teams have offense_availability = defense_availability = qb_current_minus_full = 0. Thirty teams are UNKNOWN; NE and SEA have dated, unadjusted reports. NE Ben Brown remains ACT with prior role 0.540541 despite a saved Out designation. Henderson's DNP is a practice observation, not an Out designation. A verified unavailable expected QB would instead block issuance of its matchup; no such QB block occurred in this snapshot. This is the locked modeling contract, not a newly introduced implementation bug.
3. **Old roles survive absences and transfers.** NE Alijah Vera-Tucker carries [1,1,1,1] from his last four 2024 Jets ACT games because all 17 regular-season 2025 roster rows are RES. NYG Odell Beckham Jr. carries 2024 Miami usage across no 2025 observations. These histories have no new-role or elapsed-time adjustment. The frozen summary stores values without per-entry dates; the examples were dated by tracing raw historical sources.
4. **Finite team features mask partial player coverage.** Of 717 offensive and 795 defensive ACT players, only 593 and 663 have prior role history. Known-role counts include zero histories. Across all ACT positions, 347 draft entries are blank; their zero encoding does not prove undrafted status or zero talent. The source has complete current DOB/experience and resolved current IDs, which does not fix historical roster-to-snap matching.
5. **The descriptors are not non-QB player-performance estimates.** They use age, a hard under-26 cutoff, draft records and prior participation. They do not measure individual blocking, coverage, pass-rush effectiveness or injury point value. Team/QB historical performance remains the principal separate performance input.

Named player tables, exact histories, unit denominators and source hashes are in [player-input-notes.md](player-input-notes.md). Status and source-clock evidence are in [availability-notes.md](availability-notes.md).

## Coefficient shape and limits

The saved final QB-age component before league centering is:

`-0.1222616227 * (age - 27) + 0.0112142892 * (age - 27)^2`

It is U-shaped, with a minimum near age 32.45, holding other inputs fixed. Thus both Rodgers and Dart receive positive centered age contributions. This is the fitted arithmetic, not a physiological aging curve. Age and experience are strongly correlated, and older surviving NFL starters are a selected population; this trace does not identify the statistical cause of the fitted shape.

| Mirrored final-training features | Complete original games | Correlation |
| --- | ---: | ---: |
| qb_age_centered / qb_age_squared | 3310 | +0.805 |
| qb_age_centered / qb_experience_prior | 3308 | +0.900 |
| defense_role_weighted_age / defense_young_role_share | 3391 | -0.793 |

These are pairwise checks, not a claim that all multivariate dependence is resolved. Coefficients are conditional on the other correlated inputs. Below, coefficients are converted to raw feature units by dividing by each saved fold's scale. No fold was refitted.

| Saved fit | Linear QB age | Squared QB age | Defensive draft prior | Defensive young-role share |
| --- | ---: | ---: | ---: | ---: |
| fold_2018 | -0.02919 | +0.02525 | +14.60269 | -2.32459 |
| fold_2019 | -0.04590 | +0.02298 | +14.22178 | -1.23286 |
| fold_2020 | -0.10922 | +0.02234 | +13.02195 | -0.68551 |
| fold_2021 | -0.09882 | +0.02342 | +15.46887 | -1.22618 |
| fold_2022 | -0.09574 | +0.01911 | +14.15598 | -1.35680 |
| fold_2023 | -0.09787 | +0.01374 | +13.85065 | -2.30198 |
| fold_2024 | -0.07336 | +0.01148 | +14.77640 | -2.17302 |
| fold_2025 | -0.07619 | +0.00877 | +12.36456 | -2.04007 |
| final_2013_2025 | -0.12226 | +0.01121 | +11.26277 | -2.44636 |

These four coefficient signs persist across all eight evaluation fits and the final fit, while magnitudes change. Sign persistence does not establish useful prediction, causality or cleanliness of historical source timing.

## Historical context remains unfavorable

Target: final home-minus-away points including overtime; one row per regular-season game. Eight expanding-season evaluations use 2013 through S-1 to evaluate S=2018 through 2025. The final diagnostic fit uses 2013-2025. Earlier same-season games may update features only after their kickoff batch, without refitting that fold.

**Leakage status: REVIEW REQUIRED.** Historical publication/revision vintage and whether recorded starters were known at the intended pregame decision time remain unresolved. Prior temporal perturbation and arithmetic checks do not establish those source properties. These repeatedly inspected years are diagnostic folds, not a fresh untouched test. Consequently this report stops at descriptive source and arithmetic explanation; it makes no validated player-value or causal claim.

| Slice | Games | Corrected MAE | Candidate MAE |
| --- | ---: | ---: | ---: |
| All games | 2127 | 10.099456 | 10.133540 |
| Week 1 | 128 | 9.891116 | 10.035390 |
| Weeks 1-4 | 509 | 9.786012 | 9.891345 |
| Weeks 5-18 | 1618 | 10.198061 | 10.209732 |
| Neutral site | 37 | 8.383516 | 8.541823 |

Only 2018, 2020 and 2025 improve at the season level. The full unfavorable season/team slices remain in the [original metrics](../pgo_corrected_roster_candidate/run-20260908/metrics.json). There is no probability output here, so calibration/probability-tail claims are not applicable.

Largest absolute candidate margin misses below are selected across every evaluated game, not from a favorable team. Positive margins favor the listed home team. Both models suffer large blowout misses; this list does not establish a recurring cause or justify a new model variant. Season, week and home/away context are retained in the game IDs and full JSON.

| Game ID | Actual home margin | Corrected prediction | Candidate prediction | Candidate absolute error |
| --- | ---: | ---: | ---: | ---: |
| 2020_13_NE_LAC | -45 | +2.872 | +3.325 | 48.325 |
| 2019_01_BAL_MIA | -49 | -5.050 | -4.313 | 44.687 |
| 2023_03_DEN_MIA | +50 | +6.236 | +6.309 | 43.691 |
| 2023_15_LAC_LV | +42 | +0.250 | -1.296 | 43.296 |
| 2024_06_DET_DAL | -38 | +2.403 | +4.045 | 42.045 |
| 2018_10_BUF_NYJ | -31 | +5.959 | +9.883 | 40.883 |
| 2018_01_NYJ_DET | -31 | +11.235 | +9.567 | 40.567 |
| 2023_01_DAL_NYG | -40 | +0.024 | +0.512 | 40.512 |
| 2021_10_ATL_DAL | +40 | +3.070 | -0.402 | 40.402 |
| 2021_01_GB_NO | +35 | -3.466 | -5.006 | 40.006 |

## Full frozen board

All 32 per-feature before/after contributions, exact base-cell parity, the largest additional historical errors and source hashes are saved in [analysis.json](analysis.json).

| Candidate rank | Team | Corrected rank | Candidate rating | Change from corrected |
| ---: | --- | ---: | ---: | ---: |
| 1 | LAR | 2 | +4.874 | +0.368 |
| 2 | NE | 1 | +4.844 | -0.356 |
| 3 | SEA | 3 | +4.202 | +0.185 |
| 4 | JAX | 5 | +3.646 | +0.292 |
| 5 | HOU | 6 | +3.532 | +0.541 |
| 6 | BUF | 4 | +3.306 | -0.301 |
| 7 | CHI | 8 | +2.742 | +0.070 |
| 8 | PIT | 16 | +2.632 | +2.057 |
| 9 | BAL | 9 | +2.531 | +0.235 |
| 10 | DET | 12 | +2.424 | +0.776 |
| 11 | PHI | 7 | +2.334 | -0.650 |
| 12 | SF | 11 | +2.147 | +0.172 |
| 13 | DEN | 10 | +1.665 | -0.337 |
| 14 | CIN | 13 | +0.893 | -0.666 |
| 15 | LAC | 14 | +0.866 | -0.490 |
| 16 | GB | 17 | +0.258 | -0.255 |
| 17 | IND | 18 | +0.086 | -0.140 |
| 18 | MIN | 15 | -0.307 | -1.266 |
| 19 | NYG | 24 | -0.483 | +1.007 |
| 20 | TB | 19 | -0.589 | -0.668 |
| 21 | ATL | 21 | -0.712 | -0.422 |
| 22 | KC | 20 | -0.766 | -0.796 |
| 23 | DAL | 23 | -1.077 | +0.310 |
| 24 | CAR | 26 | -1.529 | +0.629 |
| 25 | WAS | 22 | -1.608 | -0.222 |
| 26 | NO | 25 | -2.205 | -0.419 |
| 27 | MIA | 27 | -3.320 | +0.036 |
| 28 | ARI | 28 | -4.856 | -0.081 |
| 29 | CLE | 29 | -4.886 | +0.352 |
| 30 | TEN | 30 | -5.954 | -0.063 |
| 31 | LV | 31 | -7.001 | +0.223 |
| 32 | NYJ | 32 | -7.689 | -0.120 |

## Recommended next work

First repair roster-to-snap identity resolution and distinguish unresolved usage from an observed zero in a separate, reviewable change. Reuse a verified identifier crosswalk where available; fail or label ambiguity rather than guessing through fuzzy names. The Onwenu and Runyan examples are concrete regression cases. Establish coverage across all teams before considering any replacement feature package.

Treat stale-role policy and numerical availability as separate modeling decisions. A fresh game-specific report can establish an availability fact; it cannot supply a calibrated point penalty by itself. Any future candidate should declare its role/availability policy and prospective evaluation before looking for a more agreeable rank. This failed candidate and issued evidence stay preserved. No corrected-input re-score or new candidate was performed here.

## Reproduction and verification

Run from the repository root:

```powershell
python -B research/pgo_ranking_trace_20260909/analyze.py
python -B research/pgo_ranking_trace_20260909/check_player_inputs.py
```

The scripts only read frozen files and print their results. The accounting script asserts the exact manifest hashes and all 46 referenced file bytes before and after; original base cells match for all 32 teams. Centered contributions reconstruct both boards and every rating change with maximum error 2.25e-14. An independent scalar calculation checked the same accounting. The player trace independently reconstructs all 320 added descriptor cells with zero difference; raw 2025 source hashes and all eight nonzero snap rows behind the two false-zero histories were also checked separately by the parent. Final verification reproduced the saved analysis exactly, reran the player helper successfully, and matched all 67 external raw-source hashes from the pinned current-preflight receipt.

See [trace-review.md](trace-review.md) for the independent review scope. These checks establish arithmetic and source identity, not predictive acceptance or current health. Only the new audit directory was added; frozen models, sources, issued forecasts and public files remain unchanged.
