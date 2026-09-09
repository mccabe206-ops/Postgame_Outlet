# Independent replacement pre-fit review

**Verdict: READY FOR SINGLE FIXED RESEARCH FIT. No blocking defect found in the reviewed fixed candidate or prepared inputs.**

Reviewer: independent Codex agent `/root/replacement_prefit_review`; this reviewer did not implement the candidate. This is not an actual Fable review and does not claim Fable concurrence. Recorded 2026-09-09T00:21:44.341400+00:00. Checkout: `119c5ee37b8b6e7520848b4dbae6534685fcd104`.

This verdict addresses the one existing research fit only. Parent custody verification and an explicit parent fit-go-ahead receipt remain required by `reviewer-substitution-20260909T001653Z.md`. No fit, historical preparation, current preparation, capture, forecast, or publication was performed by this reviewer. Only this new review and its receipt were written. Earlier incomplete and completed evidence remains immutable.

## Contract reviewed

The target is final home-minus-away margin including overtime, one regular-season game per row. Historical feature time is that game's kickoff, with age computed on its UTC date. Recorded starters and frozen weekly rosters are accepted retrospective identity inputs; they are not verified pregame T-60 expectations. The optional current diagnostic is frozen at `2026-09-08T15:01:38.802823+00:00`, regardless of this review's date.

The ten added fields are the selected QB's age minus 27 and its square, plus offense/defense role-weighted age, under-26 role share, role-weighted inverse-square-root draft number, and unit rookie draft capital. The squared team value is differenced before signed augmentation. No eleventh field, feature selection, NE-specific exception, old v2 coefficients, or older v2 runner enters the candidate. The original corrected fields stay fixed.

## Findings

- **PASS - Definitions and missingness.** `adapter.py:59-107` reproduces the fixed v2 unit formulas and aliases. Prior role is the median of up to four existing ACT observations. Age-weighted terms use known-role/known-age mass; draft weighting uses known-role mass; rookie capital divides by the whole selected unit. Unseen roles, zero denominators and missing selected-QB age remain missing. Blank or numeric-zero draft is the declared zero encoding; missing experience makes the unit rookie term missing. Invalid integral metadata, malformed DOB, out-of-range age, nonfinite roles and roles outside [0,1] fail. The raw metadata join uses resolved IDs, not names. The all-ACT weight-one policy is applied equally to full/current views while preserving the inherited corrected fields.
- **PASS - Temporal data flow.** `pgo_current_strength.build_rows` removes current_roster:2026 before historical loading. `RosterHook` reads only its season/week/team raw rows and existing snap deques. The real walker prepares every equal-kickoff game before any postgame update. Same-game snap rows accessed in the hook affect coverage counters only. Future performance and metadata cannot update earlier predictive accumulators through this hook. The existing real-walker perturbation checks pass and prove nonvacuous later age, QB-performance and role-state changes. Current-age arithmetic uses the saved source clock; the issued constructor copies context, applies its single QB clock advancement and 0.5 offseason results retention, and all saved original current cells match.
- **PASS - Identity and coverage.** Raw historical ID-less ACT counts are zero; ACT filtering precedes duplicate collapse. Conflicting or unresolved duplicate roster identities stop construction. The prepared context has zero historical colliding GSIS IDs. Current-period GSIS reuse across teams or multiple nonblank smart IDs stops independently of that historical set. Team-game coverage distinguishes pre-collapse ACT rows, resolved rows, known-role and known-age mass, missing metadata, inherited snap-name fallback and postgame fallback-zero usage. The 2016 blank-draft counts are present for all 32 teams; no season or game is dropped to address that vintage shift.
- **PASS - Fixed base and cohort.** Independently checked all 3,407 unique historical rows, their ordering, target and kickoff identity. All 80,387 finite and 1,381 missing original corrected feature cells match exactly, maximum difference zero. The ten new descriptors have finite nonzero variation in each of eight training folds: 80 checks. There are 6,814 unique team-game coverage rows and exactly 2,127 evaluation rows. Training counts are 1,280/1,536/1,792/2,048/2,320/2,591/2,863/3,135; validation counts are 256/256/256/272/271/272/272/272. Each training prefix ends before its validation season starts.
- **PASS - Symmetric fitting and decision rule.** `train.run` invokes eight fixed expanding-season fits and one final 2013-2025 fit using saved prepared rows. `corrected.fit_combined` routes to signed row/target augmentation and train-only medians, scales and missing inventory with Huber delta 1 and alpha 200. Validation rows are scored once, and saved controls are read rather than refitted. The runner and independent verifier apply exactly three criteria: lower pooled MAE than corrected, at least five season wins, and a positive lower 95% paired season-block bootstrap endpoint versus corrected. The helper defaults to 10,000 draws, and the runner fixes seed 20260908. Gain sign is control absolute error minus candidate absolute error. Early weeks and secondary controls cannot change the screen. No candidate result is asserted before fitting.
- **PASS - Current arithmetic and custody checks performed here.** Independently recomputed all 320 new current descriptor cells from the frozen roster and saved snap context using separate standard-library arithmetic: exact agreement, maximum difference zero. All 704 original current cells also agree exactly; all 1,024 combined current cells are finite. The 1,693 ACT players cover 32 teams. Both preparation manifest hashes, all ten manifest members, and all 23 protected code/reference hashes match their recorded pins. The receipt records every additional reviewed input hash. Parent performs the separate full raw-source custody audit.

## Original Fable corrections

The two blocking findings are closed: the revised charter plus implementation-status receipt explicitly preserve the interrupted no-fit chronology, and historical preparation is now independent of the separately manifested current diagnostic; the issued comparison helper receives its required label. Important corrections are also present: all seven reference pins are enforced; current collisions and raw ID-less rows are checked; raw versus collapsed and 2016 team draft counts are saved; inherited snap-name resolution and fallback zeros are disclosed; missing indicators under symmetry have no directional effect; the three-part screen is explicit and independently checked. UTC-boundary and strict-DOB tests pass. The linear age centering cancels under team differencing, as the formula requires.

The raw inventory does not have a standalone invalid-DOB counter; the completed eligible-row construction and strict parser provide the relevant stop guard for these already prepared bytes. This minor reporting omission does not justify revising or re-preparing the frozen candidate.

## Verification and limits

Independently reran `python -B -m unittest research.pgo_corrected_roster_candidate.test_candidate research.pgo_corrected_roster_candidate.test_temporal research.pgo_corrected_roster_candidate.test_verify`: **15 passed in 0.379 seconds**, exit 0. These tests fit no model coefficients. Additional read-only checks validated saved parity, folds, coverage, all current descriptor arithmetic, and hashes. The prior independent-verification receipt was supporting evidence, not a substitute for these checks.

**Leakage-audit status remains REVIEW REQUIRED for historical source publication/revision vintage and recorded-starter availability.** The retrospective data-flow checks do not establish what was available at a historical T-60 decision. Evaluated outcomes were reused in prior studies; a positive result is a diagnostic further-study screen, not fresh confirmation. Inherited ACT role history can carry across teams/seasons and include unresolved-snap fallback zeros. Blank draft is not evidence of undrafted status or talent. These fixed limits remain accepted for this bounded research fit; scientific status remains **EXPERIMENTAL / HOLD**, including after a screen pass.

After the one fit, saved coefficient/prediction replay, independent metrics/bootstrap/symmetry checks and custody preservation must still complete before reporting its result. This review authorizes no issuance, adoption, production integration or public change.

## Exact primary input hashes

| Input | SHA-256 |
| --- | --- |
| charter.md | `a33f4d400dcbfe4a466ac332400067bae4c136592113b8368d4603800edf2b6b` |
| adapter.py | `b287c33ce08995821f3aaf1dbab5d46e431ad624c72bac775b6ead5c16143bb2` |
| train.py | `182b2a303bf20e128bd67da712c79bcb80960ef761ca934465b1e940616cdfe0` |
| Historical preparation manifest | `de0dcf0a80eb7daec12bd7c606a4d0f714496b782dd09d321296c9494d425a69` |
| Historical prepared feature bytes | `39be871ad7797084d8ce594efe83ab241b6587b1ecb4b0f8a253d11e8c248eae` |
| Current preparation manifest | `0e35d51dc0bcdeb739a17b10e693d47d55e0f8b4810d59da4271dc85b6cf2200` |

The companion receipt contains the complete reviewed input hash map and scope limitations.
