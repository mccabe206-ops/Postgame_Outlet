# Why are New England and Jacksonville so high?

PGO's preserved July 21, 2026 snapshot ranks New England first and Jacksonville fourth. The separate September 7 active-roster snapshot ranks them first (+7.219) and fifth (+5.392). **Both remain experimental; the new snapshot is HOLD.**

McCabe's ratings are human-set neutral-field point estimates: QB + non-QB offense + defense. PGO is independently fitted to game margins, then centered across 32 teams. Its intended point interpretation is still experimental; subtracting its output from McCabe's number is not an established point-price disagreement.

## Why the July ratings are high

The saved rating file contains two contribution groups. We put both on the same league-average baseline before displaying them. The original groups had large, canceling offsets; those offsets were not evidence of a terrible roster or a dominant individual feature.

| Team | PGO output | Performance group | Roster/coaching group |
|---|---:|---:|---:|
| New England | +7.000 | +6.417 | +0.583 |
| Jacksonville | +6.281 | +6.018 | +0.263 |

New England is third in the performance group and ninth in roster/coaching. Jacksonville is fourth and fourteenth. New England's modest roster advantage moves it above the Rams and Seahawks, which have higher performance contributions. These are contributions to the model output, not separate offense, defense, or QB grades.

The performance group includes the earlier results-based PGO rating and recent team efficiency statistics. The selected team-stat half-life is four games, so recent games matter heavily. Correlated inputs mean these groups do not establish independent evidence for a ranking.

The public fit has now been reconstructed using the original code, all 67 hash-verified frozen sources, and the recorded parameters. It reproduces **all 32 rows and every serialized CSV cell**, including the complete CSV text after newline normalization. This recovers the predictor behind the published output; it does not establish that the original coefficient-file bytes were found or that the model is accurate.

The recovered feature contributions explain the arithmetic more precisely. New England's earlier results-based PGO input contributes +3.864 and passing efficiency +2.084; Jacksonville's contribute +4.134 and +1.128. These are centered, correlated fitted associations, not causal player values. The prospective archive's different fitted vector was not used to explain the July ratings.

## What changed in September

Replaying the exact public-generation source constructor against all 67 verified frozen source files confirmed that it selected **Nick Mullens for Jacksonville** and **Drake Maye for New England**. It chooses the roster quarterback with the highest shrunk historical passing efficiency, rather than an authoritative projected-starter depth chart. In this snapshot the full-strength and lineup QB selections were the same.

The new snapshot keeps the recovered fit and historical performance through 2025 fixed, but uses freshly captured 2026 rosters and the September 7, 13:13 UTC depth chart. It includes only administratively active (`ACT`) players and selects the active QB1 by depth order. This is a separate inference policy, not a rewrite of the July ratings or the July/August prospective experiment.

**Jacksonville's change is not solely a depth-chart correction.** Nick Mullens is `DEV/P07` in the fresh roster and is excluded by the active-only policy. Even the old efficiency selector already chooses Trevor Lawrence from that eligible roster. Jacksonville's isolated fresh QB-policy effect is therefore zero. New England also retains Drake Maye. Fresh roster inputs and centering across the changed league matter to the resulting ratings; a team's centered rating change is not its isolated QB effect.

Depth selection does change eight other teams' fresh QB choices: Seattle (Milroe → Darnold), the Giants (Winston → Dart), Miami (McCord → Willis), Indianapolis (Leonard → Jones), Carolina (King → Young), Arizona (Beck → Brissett), Tennessee (Trubisky → Ward), and the Jets (Klubnik → Smith). These differences demonstrate why starter selection matters, without proving better forecasts.

The [Forecast Lab](forecast-lab.html) presents the new 32-team snapshot, Week 1, and all 272 regular-season game scores and spreads. Each game uses the same preseason roster assumptions. Scores combine the model margin with a simple total based on both teams' 2025 scoring and points allowed. Active status is not proof of health or game-day availability. Week 1 matchups and kickoffs were independently checked against NFL.com; later provider-listed kickoffs may change, and Week 18 times are provisional.

The weekly record is separate from that preseason baseline. Each matchup's scores, spread, and total lock together **60 minutes before kickoff**. Week 1 starts with the September 7 projections as drafts. Any reviewed revision must be saved before that game's cutoff, and all earlier revisions remain available. No automatic injury refresh or inherited validation is implied. Later weeks' fixed preseason forecasts remain available even when no weekly edition has been recorded.

## What we cannot yet claim

Exact reproduction resolves the missing-fit obstacle to attribution. It supplies no new historical validation, and the September roster/depth policy and score baseline do not inherit the old model's evaluation. The displayed spreads remain experimental model estimates, not calibrated betting prices.

The existing 2018–2025 rolling historical test reports margin MAE of 10.205 for the challenger versus 10.266 for the earlier PGO model over 2,127 games. The improvement interval, −0.024 to +0.145 points, crosses zero. The model also did worse in 2018 and 2025, and slightly worse in weeks 1–4 overall. That is why the historical status remains **HOLD**.

Historical injury-source revision timing also remains a limitation: the saved audit cannot verify the publication vintage of the 2025 injury rows. Chronological code and frozen file hashes do not remove that uncertainty.

The September candidate needs its own evaluation while the entire earlier prospective record remains preserved. Neither agreement with McCabe nor disagreement with consensus is a reason to move a team manually.

## Evidence

- [Recovered public fit and preprocessing](evidence/forecast-lab-2026/september-07/fit.json)
- [September snapshot, contributions, QB comparisons, and all 272 forecasts](evidence/forecast-lab-2026/september-07/snapshot.json)
- [Original ratings and contribution groups](https://github.com/walshja9/Postgame_Outlet/blob/d9947df0e8de6b7a75bf91b1b5d9b9754ef12685/research/pgo_v1/ratings_2026_preseason.csv)
- [Original historical test receipt](https://github.com/walshja9/Postgame_Outlet/blob/d9947df0e8de6b7a75bf91b1b5d9b9754ef12685/research/pgo_v1/backtest.json)
- [Original model and QB selection source](https://github.com/walshja9/Postgame_Outlet/blob/d9947df0e8de6b7a75bf91b1b5d9b9754ef12685/pgo_challenger.py)
- [Historical source audit](https://github.com/walshja9/Postgame_Outlet/blob/d9947df0e8de6b7a75bf91b1b5d9b9754ef12685/research/pgo_v1/source_audit.json)

This audit distinguishes the reproduced July predictor from the separately identified September inference snapshot. Neither recovery nor publication changes the historical HOLD decision.
