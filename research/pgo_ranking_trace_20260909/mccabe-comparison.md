# McCabe comparison: addendum after the supplied Rams explanation

The user supplied McCabe's Rams explanation and methodology during the completed ranking trace. The local current `data/ratings.csv` and `data/writeups/LAR.md` match the supplied +7.3 total, +5.5 QB, +0.9 supporting offense and +0.9 defense. The injury rationale is McCabe's saved assessment, not a newly verified injury report or an empirically established 0.2-point effect.

## What this changes in the interpretation

McCabe explicitly assigns expected player/unit value in neutral-field points. Stafford receives +5.5; the named offensive and defensive personnel support two +0.9 unit judgments. His rationale applies a discretionary -0.1 to each unit for the two named recovery concerns.

The combined statistical PGO candidate instead fits historical game margins using team/QB performance, the results-based rating, and ten added age/role/draft descriptors. It has no corresponding estimated non-QB player point values. Calling a centered QB feature contribution a Stafford grade comparable to +5.5, or describing its defensive draft term as a measured Garrett injury-adjusted value, would misrepresent the construction. Summing its features into three headings would not create those estimates.

| Question | McCabe's supplied method | Saved PGO candidate |
| --- | --- | --- |
| What supports the number? | Explicit QB and non-QB unit judgments | Fitted historical performance and roster descriptors |
| How is player movement represented? | Assessed expected effect on each unit | Current membership plus carried usage, age and draft records in the added block; separate team/QB history |
| How is the Rams injury trim represented? | Explicit -0.1 offense / -0.1 defense in the writeup | No corresponding numerical availability adjustment |
| Does an explanation establish prediction quality? | No; the assessments still need outcome evaluation | No; this candidate failed its historical screen |

This is why agreement on LAR #1 cannot establish that PGO arrived there through the same football assessment. Its narrow lead over NE primarily comes from defensive draft descriptors, not McCabe's explicit Stafford/unit valuation or injury trim. See the [completed trace](README.md).

## Direct comparison of the main teams

Ranks below use the repository's existing McCabe parser and current row order. Equal totals can have successive display positions; they are not resolved strength differences. In particular NE and KC both have +4.0.

| Team | McCabe display rank | McCabe QB | McCabe offense | McCabe defense | McCabe total | Candidate rank / rating |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LAR | 1 | +5.5 | +0.9 | +0.9 | +7.3 | 1 / +4.874 |
| NE | 7 | +3.0 | +0.5 | +0.5 | +4.0 | 2 / +4.844 |
| PIT | 22 | -1.0 | +0.0 | +1.0 | +0.0 | 8 / +2.632 |
| KC | 8 | +4.5 | +0.0 | -0.5 | +4.0 | 22 / -0.766 |
| DEN | 17 | -0.5 | +0.0 | +2.0 | +1.5 | 13 / +1.665 |
| MIN | 20 | -0.5 | +1.0 | +0.5 | +1.0 | 18 / -0.307 |
| NYG | 26 | -1.0 | -0.5 | +0.5 | -1.0 | 19 / -0.483 |
| DET | 13 | +2.0 | +1.0 | +0.0 | +3.0 | 10 / +2.424 |

PIT and KC have the largest absolute differences in displayed position (14 places each). McCabe assigns Rodgers -1.0 and Mahomes +4.5. The candidate's Pittsburgh move includes +0.876 from the fitted QB-age terms and +0.619 from defense descriptors. Kansas City's candidate is pulled down by the new defense descriptors and conditional team-performance terms despite a positive Mahomes QB-EPA contribution. Neither discrepancy is resolved by a measured availability correction.

## The zero-point reference needs clarification

The current 32 McCabe displayed totals average **+1.475**, not zero. Mean unrounded component sums are +1.4765625 (QB +1.21875, supporting offense +0.1671875, defense +0.090625); normal display rounding explains the small difference. The claim that zero is a league-average team may refer to a conceptual reference, but the current board is not arithmetically centered on its own 32 teams.

The candidate is explicitly centered on its current 32 teams. For comparison only, subtracting 1.475 from every displayed McCabe total puts LAR at **+5.825**, against candidate **+4.874160**. Their centered difference is about **-0.951**, rather than the -2.426 obtained by directly comparing differently anchored totals. This translation preserves McCabe's ordering and every pairwise matchup gap. It is not a recalibration, proof of a common scale, or a proposed change to his ratings.

## Implication for next work

The concrete first repair remains the verified roster-to-snap identity failures and the distinction between unresolved usage and observed zero. Repairing these inputs is warranted on correctness grounds; it does not by itself supply the individual player/unit values that McCabe's framework uses.

If PGO is later intended to estimate that kind of roster value, define and evaluate explicit player/unit contributions and availability scenarios. The tested age/draft add-on does not fulfill that objective, and this audit does not authorize a replacement fit or component-model implementation. McCabe remains a separate human assessment and comparison reference; no blending, retuning to his ranks, or forecast rewrite occurred.

## Full comparison

**Different expected-QB assumption:** ATL is the only team with different named QBs across these two sources: McCabe lists Michael Penix Jr.; the frozen candidate uses Tua Tagovailoa. That comparison therefore mixes an identity assumption with valuation differences. The other 31 selected QB names match.

These are current local McCabe source rows inspected in this turn and the unchanged frozen September 8 candidate. This table does not claim a fresh public-site verification or a match to an older locked McCabe snapshot. The McCabe injury prose is kept attributed to its author.

| Candidate rank | Team | Candidate rating | McCabe display rank | McCabe displayed total |
| ---: | --- | ---: | ---: | ---: |
| 1 | LAR | +4.874 | 1 | +7.3 |
| 2 | NE | +4.844 | 7 | +4.0 |
| 3 | SEA | +4.202 | 3 | +6.0 |
| 4 | JAX | +3.646 | 11 | +3.0 |
| 5 | HOU | +3.532 | 10 | +3.0 |
| 6 | BUF | +3.306 | 2 | +7.0 |
| 7 | CHI | +2.742 | 12 | +3.0 |
| 8 | PIT | +2.632 | 22 | +0.0 |
| 9 | BAL | +2.531 | 4 | +5.5 |
| 10 | DET | +2.424 | 13 | +3.0 |
| 11 | PHI | +2.334 | 14 | +2.5 |
| 12 | SF | +2.147 | 9 | +3.2 |
| 13 | DEN | +1.665 | 17 | +1.5 |
| 14 | CIN | +0.893 | 5 | +5.0 |
| 15 | LAC | +0.866 | 6 | +5.0 |
| 16 | GB | +0.258 | 19 | +1.0 |
| 17 | IND | +0.086 | 23 | -0.5 |
| 18 | MIN | -0.307 | 20 | +1.0 |
| 19 | NYG | -0.483 | 26 | -1.0 |
| 20 | TB | -0.589 | 15 | +2.5 |
| 21 | ATL | -0.712 | 27 | -1.0 |
| 22 | KC | -0.766 | 8 | +4.0 |
| 23 | DAL | -1.077 | 16 | +2.0 |
| 24 | CAR | -1.529 | 21 | +0.5 |
| 25 | WAS | -1.608 | 18 | +1.0 |
| 26 | NO | -2.205 | 25 | -0.8 |
| 27 | MIA | -3.320 | 31 | -4.5 |
| 28 | ARI | -4.856 | 29 | -3.5 |
| 29 | CLE | -4.886 | 28 | -2.5 |
| 30 | TEN | -5.954 | 24 | -0.5 |
| 31 | LV | -7.001 | 30 | -4.0 |
| 32 | NYJ | -7.689 | 32 | -5.5 |

Source hashes and exact comparison rows are preserved in [mccabe-verification.json](mccabe-verification.json). Existing audit artifacts and issued sources remain unchanged.
