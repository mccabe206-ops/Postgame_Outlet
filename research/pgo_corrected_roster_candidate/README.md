# Corrected PGO plus v2 roster descriptors: completed, screen failed

**Status: EXPERIMENTAL / HOLD. One candidate invocation completed; nine coefficient fits. No adoption or publication.**

Adding the fixed v2 age/role/draft block did not improve the declared primary
measure. On the same 2,127 historical games, average absolute margin error rose
from **10.099456 to 10.133540 points**. The candidate improved only **three of
eight seasons**. All three further-study criteria failed. This candidate is
closed under this charter: no feature variant, tuning run or baseline refit
follows this result. Keep the issued corrected model unchanged.

The result does not establish that the candidate must be worse in future games:
the uncertainty interval spans both improvement and deterioration. It supplies
no evidence sufficient to replace the corrected model. These repeatedly used
historical seasons remain diagnostic evidence, not fresh prospective validation.

## Fixed comparison results

Primary target: final home-minus-away game margin, including overtime. One row
per regular-season game. Eight expanding-season evaluations cover 2018-2025;
coefficients and preprocessing use prior seasons only. The final research fit
uses all 3,407 history games. No baseline was refitted.

| Measure | Corrected | Corrected + v2 |
| --- | ---: | ---: |
| Average absolute margin error, 2,127 games | 10.099456 | 10.133540 |
| Root mean squared error | 13.044989 | 13.107834 |
| Predicted-minus-actual margin bias | +0.152719 | -0.001915 |
| Winner accuracy, excluding 8 actual ties | 65.691% (1,392/2,119) | 66.116% (1,401/2,119) |
| Week 1 average absolute margin error, 128 games | 9.891116 | 10.035390 |
| Weeks 1-4 average absolute margin error, 509 games | 9.786012 | 9.891345 |
| Weeks 5-18 average absolute margin error, 1,618 games | 10.198061 | 10.209732 |

Winner accuracy and average bias improve slightly, while the primary margin
error and early-season error worsen. Those secondary measures cannot replace
the predeclared primary criterion. Neither model predicts a tie in this table.

| Required criterion | Observed | Result |
| --- | --- | --- |
| Lower pooled margin error than corrected | Error increases by 0.034085 points | FAIL |
| Lower error in at least 5 of 8 seasons | 3 of 8 | FAIL |
| Positive lower 95% paired interval for improvement | -0.102307 | FAIL |

The mean paired gain is **-0.034085 points**, with 95% paired season-block
interval **[-0.102307, +0.044823]**. Positive means improvement. The calculation
uses 10,000 draws, seed 20260908, resampling eight whole seasons and pooling all
games in the sampled seasons. No new sampling scheme or favorable subgroup is
used to change the decision.

| Season | Games | Corrected error | Combined error | Combined improves |
| --- | ---: | ---: | ---: | --- |
| 2018 | 256 | 10.081265 | 10.045470 | Yes |
| 2019 | 256 | 10.417260 | 10.533580 | No |
| 2020 | 256 | 10.174956 | 9.991297 | Yes |
| 2021 | 272 | 11.059011 | 11.184666 | No |
| 2022 | 271 | 8.821680 | 8.926900 | No |
| 2023 | 272 | 10.326789 | 10.334170 | No |
| 2024 | 272 | 9.778289 | 9.937492 | No |
| 2025 | 272 | 10.153763 | 10.120296 | Yes |

[Full metrics](run-20260908/metrics.json) retain every team, season, early-week,
neutral-game and large-predicted-margin slice plus all six saved controls and
paired intervals. The [matched predictions](run-20260908/matched-predictions.csv)
retain all original control values and game identities.

## Frozen September 8 ranking diagnostic

The separate [32-team arithmetic diagnostic](current-ratings-diagnostic-20260909.json)
applies the saved final fit to the already prepared September 8 features. Its
input clock remains **2026-09-08T15:01:38.802823+00:00**. It is not a fresh source
capture, issued forecast, rank-confidence interval or adoption criterion.

| Combined rank | Team | Combined model rating | Corrected rank |
| ---: | --- | ---: | ---: |
| 1 | LAR | +4.874160 | 2 |
| 2 | NE | +4.844039 | 1 |
| 3 | SEA | +4.202398 | 3 |
| 4 | JAX | +3.645649 | 5 |
| 5 | HOU | +3.531991 | 6 |

LAR leads NE by just 0.030121 model units. NE moving to second does not establish
a better ranking or rescue the failed forecasting screen. Current rank was
never a selection target. All 32 neutral team scores were independently checked
with scalar arithmetic; all 1,024 ordered pair differences match the centered
rating differences within 2.7e-14. The actual public ordering is unchanged.

## Review, execution and verification

Fable's first review requested revisions, which were completed before this run.
Its later re-review attempts returned usage errors and no verdict; the
[latest failed attempt](reviews/fable-rereview-service-failure-20260908T232855Z.json)
remains preserved. After the user said "proceed" to the proposed next steps,
root used a fresh independent Codex replacement review under the additive
[reviewer-substitution record](reviews/reviewer-substitution-20260909T001653Z.md).
There is no claim of Fable concurrence. The pinned original charter and prepared
evidence were not rewritten to change reviewer identity.

The [replacement review](reviews/replacement-prefit-review-20260909.md) found no
blocking defects and independently reproduced historical parity and all 320
added current descriptor cells. A separate readiness review verified 23 code,
67 raw-source and 156 public/data/workflow hashes. Root then recorded the
[one-run go-ahead](reviews/fit-go-ahead-20260909.json) against the exact reviewed
bytes. The exact pre-fit README is preserved in
[prepared-state-README-20260909.md](reviews/prepared-state-README-20260909.md).

The single trainer invocation completed at **2026-09-09T00:23:08Z** (September 8
Eastern), exit 0, in 3.302 seconds. It reused prepared features, so it did not
repeat the earlier six-minute historical feature construction. It performed
exactly eight expanding-season coefficient fits and one final fit; no baseline
refit or fresh capture occurred. The manifest was written last. This invocation
is consumed: **do not rerun the trainer or overwrite its directory**.

[Independent saved-fit verification](saved-fit-verification.json) passed:

- Nine serialized fits and all 2,127 predictions replay; maximum difference 4.45e-16.
- All 2,987 metric/bootstrap numeric values reconcile; maximum difference 3.56e-15.
- Training-only preprocessing, game/fold identities, missing-pattern symmetry,
  neutral equality and signed venue/rest reversal checks pass.
- All 23 pinned code files and 67 raw sources are unchanged. The 156 protected
  public/evidence/data/workflow files remain unchanged.

These are arithmetic and preservation results. Historical source publication
vintage remains **REVIEW REQUIRED**, and scientific status remains **HOLD**.

| Artifact | SHA-256 |
| --- | --- |
| [Completed run manifest](run-20260908/manifest.json) | `6bbd0b987d7a619a7b6ffae10c2dde43268b44a3ccb81c7ccd22afd6f51da759` |
| [Final fit](run-20260908/final-fit.json) | `324b6a01d144daf4f665dac6d2173c6113ac942febad2b3d43237930bee8f3d0` |
| [Saved-fit verification](saved-fit-verification.json) | `966e7473de57f4b1a2fc7cfa319ae97786c2e97584a9c5856de3242a95427f88` |
| [Frozen current diagnostic](current-ratings-diagnostic-20260909.json) | `0a155880cf135721c33a1797b7e54b6fbc80ce7dbdd480abf749f06b6343b290` |
| [Unchanged charter](charter.md) | `a33f4d400dcbfe4a466ac332400067bae4c136592113b8368d4603800edf2b6b` |
| [Historical preparation](preflight-20260908-revised/manifest.json) | `de0dcf0a80eb7daec12bd7c606a4d0f714496b782dd09d321296c9494d425a69` |
| [Current feature preparation](current-preflight-20260908/manifest.json) | `0e35d51dc0bcdeb739a17b10e693d47d55e0f8b4810d59da4271dc85b6cf2200` |

## Remaining limits

- These are reused 2018-2025 diagnostic folds. Recorded historical starters and
  weekly rosters are not verified T-60 expectations; source revision/publication
  vintage is unresolved. Information-flow tests do not resolve that limitation.
- Blank draft entries are zero-encoded record proxies, not proof of undrafted
  status or talent. The 2016 blank-draft shift and missing experience remain in
  the full cohort; no games or seasons were removed.
- Prior ACT role history can carry across absences, teams and seasons. An
  unresolved snap record can append a fallback zero; the inherited unique-name
  snap fallback is disclosed and counted. New metadata joins use IDs only.
- Age, prior usage and draft information do not supply OL/defensive talent
  grades, a calibrated injury model, exact scores or rank uncertainty.
- The study fails the fixed screen. No further candidate or prospective adoption
  is authorized here. Issued corrected forecasts, old experiments, source
  packages, weekly revisions, T-60 locks and the public board are preserved.

## No-fit checks and saved-result replay

The focused suite passes **15 tests** without fitting model coefficients:

```powershell
python -B -m unittest research.pgo_corrected_roster_candidate.test_candidate research.pgo_corrected_roster_candidate.test_temporal research.pgo_corrected_roster_candidate.test_verify
```

The existing `saved-fit-verification.json` is complete and immutable. An
additional read-only arithmetic replay, if needed, requires a new output file:

```powershell
python -B -m research.pgo_corrected_roster_candidate.verify --run research/pgo_corrected_roster_candidate/run-20260908 --output research/pgo_corrected_roster_candidate/saved-fit-verification-review.json
```

Do not rerun feature preparation, the current-feature diagnostic, or the trainer.
The interrupted `preflight-20260908` remains unqualified and preserved. Later
results and public changes require their own decision; this study is closed.
