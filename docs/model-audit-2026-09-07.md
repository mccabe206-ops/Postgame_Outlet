# Why are New England and Jacksonville so high?

PGO's July 21, 2026 snapshot ranks New England first and Jacksonville fourth. We audited those outputs without changing the rankings. **The model remains experimental.**

McCabe's ratings are human-set neutral-field point estimates: QB + non-QB offense + defense. PGO is independently fitted to game margins, then centered across 32 teams. Its intended point interpretation is still experimental; subtracting its output from McCabe's number is not an established point-price disagreement.

## What the saved model actually explains

The saved rating file contains two contribution groups. We put both on the same league-average baseline before displaying them. The original groups had large, canceling offsets; those offsets were not evidence of a terrible roster or a dominant individual feature.

| Team | PGO output | Performance group | Roster/coaching group |
|---|---:|---:|---:|
| New England | +7.000 | +6.417 | +0.583 |
| Jacksonville | +6.281 | +6.018 | +0.263 |

New England is third in the performance group and ninth in roster/coaching. Jacksonville is fourth and fourteenth. New England's modest roster advantage moves it above the Rams and Seahawks, which have higher performance contributions. These are contributions to the model output, not separate offense, defense, or QB grades.

The performance group includes the earlier results-based PGO rating and recent team efficiency statistics. The selected team-stat half-life is four games, so recent games matter heavily. Correlated inputs mean these groups do not establish independent evidence for a ranking.

## A quarterback assumption needs review

Replaying the exact public-generation source constructor against all 67 verified frozen source files confirmed that it selected **Nick Mullens for Jacksonville** and **Drake Maye for New England**. It chooses the roster quarterback with the highest shrunk historical passing efficiency, rather than an authoritative projected-starter depth chart. In this snapshot the full-strength and lineup QB selections were the same.

That rule needs a separately tested correction if the intended input is the expected starter. We have not isolated its point effect on the published rating. Changing a frozen ranking now would erase the distinction between the original experiment and a corrected candidate.

## What we cannot yet claim

The prospective forecast archive contains a different fitted vector and feature set from this public ratings snapshot. It cannot supply the missing feature-by-feature explanation for these ratings. We need the exact original fitted artifact before showing detailed point contributions or claiming that one variable caused the result.

The existing 2018–2025 rolling historical test reports margin MAE of 10.205 for the challenger versus 10.266 for the earlier PGO model over 2,127 games. The improvement interval, −0.024 to +0.145 points, crosses zero. The model also did worse in 2018 and 2025, and slightly worse in weeks 1–4 overall. That is why the historical status remains **HOLD**.

Historical injury-source revision timing also remains a limitation: the saved audit cannot verify the publication vintage of the 2025 injury rows. Chronological code and frozen file hashes do not remove that uncertainty.

The next steps are to recover the exact fitted artifact, test the starting-QB assumption in a new candidate, and retain the entire prospective record. Neither agreement with McCabe nor disagreement with consensus is a reason to move a team manually.

## Evidence

- [Original ratings and contribution groups](https://github.com/walshja9/Postgame_Outlet/blob/d9947df0e8de6b7a75bf91b1b5d9b9754ef12685/research/pgo_v1/ratings_2026_preseason.csv)
- [Original historical test receipt](https://github.com/walshja9/Postgame_Outlet/blob/d9947df0e8de6b7a75bf91b1b5d9b9754ef12685/research/pgo_v1/backtest.json)
- [Original model and QB selection source](https://github.com/walshja9/Postgame_Outlet/blob/d9947df0e8de6b7a75bf91b1b5d9b9754ef12685/pgo_challenger.py)
- [Historical source audit](https://github.com/walshja9/Postgame_Outlet/blob/d9947df0e8de6b7a75bf91b1b5d9b9754ef12685/research/pgo_v1/source_audit.json)

This September 7 audit is an interpretation of preserved artifacts, not a new model fit, validation result, or ranking edition.
