# PGO validation results

Checked September 12, 2026, Eastern time (September 13 UTC).

**Collection and preservation checks passed. Numerical injury adjustments and score ranges remain unqualified.** The pass found a substantial player-ID coverage gap that must be repaired before the offensive playing-time study can cover the line.

The audited checkout is `466b36569872318a5cb11ed9d55237da351a2086`. Its [saved archive](../../docs/evidence/season-2026/runs-v2/20260912T235505865661Z/manifest.json) was checked at 23:55:05 UTC and durably saved at 23:55:11 UTC. This report describes that exact edition; scheduled updates continue independently.

| Area | Result | Evidence and remaining requirement |
|---|---|---|
| Offensive playing-time collection | Limited; awaiting games | 1,108 identified players across 32 teams, but 506 lack the PFR ID needed to link to the snap source. This includes all 438 offensive linemen. Among the 966 players on the 28 teams with upcoming games, 443 lack that link. Missing IDs stay unknown. |
| Numerical non-QB injury effects | Source admission incomplete | All 5,477 offensive/defensive non-QB injury rows from 2025 lack update clocks. Earlier files still lack proof of the exact source version available before each game and of complete team reports. Those gaps prevent the isolated numerical experiment. |
| Numerical score ranges | Insufficient evidence | Fourteen actual pregame observations have verified saved receipts, but none has a completed outcome. There are zero complete calibration seasons. The declared two-season/500-game calibration requirement and separate later evaluation remain unmet. |

## What passed

There were 104 fresh focused tests: 68 shared defender, storage, cutoff, integration, rollover and health checks; 19 offensive checks; and 17 score-range checks. The historical source auditor's separate self-check also passed. These are software and data-integrity results, not evidence that injury deductions improve picks.

The canonical [fresh source audit](report02/source-admission.json) verified all 63 pinned inputs and reproduced the prior result exactly. Root verification independently rechecked all 63 hashes and all four report members. The old 2,127-game availability diagnostic still shows no demonstrated improvement: margin error is 10.099456 with its availability terms and 10.097430 with those terms removed. It includes quarterback losses and heuristic participation assumptions, so it cannot qualify the proposed isolated non-QB calculation.

The saved historical score-range calculations also reconcile: 1,313 of 1,615 margin outcomes and 1,326 of 1,615 combined totals fell within the saved ranges. However, all 2,127 historical input rows lack required prospective timing evidence. Recalculating those old metrics does not create new validation games or qualify public ranges.

Actual current offensive and defensive inventories reproduce from their saved sources. Both usage collectors correctly retain the two completed openers as excluded, wait for the 14 upcoming games, and make no source request or production write during this replay. All 16 issued forecasts, all 32 complete ranking records, 136 allocated confidence points, both accepted results and locked ATS records were preserved.

## Remaining source gaps

- The current offensive inventory retains NYJ rookie RB Al-Jay Henderson as unresolved because its provider record has no stable player ID. Seven additional offensive depth-name matches remain unresolved. A bounded check of the pinned 2025 roster supplied no PFR links for the 506 current missing-ID players; no replacement mapping was invented.
- Across the 1,199 saved defenders, 371 have no prior playing-time history and 14 have unresolved depth-name matches. Unknown reports and reserve-list context remain distinct from an injury diagnosis. These counts cover all 32 teams, not just the upcoming-game cohort.
- For historical non-QB injuries, another 25 records are too late and 16 lack a matching completed game. Missing reports cannot stand for healthy players or zero absence burden. The provider defines `date_modified` as the record's update time; it is not proof of an archived pregame source version. [Injury data dictionary](https://nflreadr.nflverse.com/articles/dictionary_injuries.html).
- Snap counts record playing time separately for offense, defense and special teams. They do not measure player quality or the point cost of an injury. [Snap-count data dictionary](https://nflreadr.nflverse.com/articles/dictionary_snap_counts.html).

The next useful repair is a verified player-ID crosswalk for future captures, especially offensive linemen. Preserve existing captures and qualify the new source before using it. Numerical injury fitting also needs the declared dated injury-report and role inputs. Score errors can start accumulating after the 14 eligible games finish; cross-season lifecycle support and an explicit recipe-compatibility policy are still needed for the longer range-validation protocol. Waiting alone does not implement those capabilities.

## Audit custody

The [new audit receipt](report02/receipt.json) and [manifest](report02/manifest.json) preserve source/code/charter hashes. The legacy auditor writes a static example command naming `report01`; the actual invocation for this pass was `python -B research/pgo_nonqb_validation_20260912/audit_sources.py --output research/pgo_nonqb_validation_20260912/report02`. That legacy metadata limitation does not change the input verification or admission result.

Detailed scripts, reports, logs, failed harness attempts, ID-gap rows and independent receipts are retained under `output/validation-pass-20260913/`. No model was fitted, no injury weights or score bounds were enabled, and no production code, source authority, forecast, grading rule or old research artifact was changed. This validation adds a fresh audit and this report only.
