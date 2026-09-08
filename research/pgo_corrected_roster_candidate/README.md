# Corrected PGO plus v2 roster descriptors: prepared, not fitted

**Status: EXPERIMENTAL / HOLD. Zero candidate coefficient fits.**

The fixed ten-feature block is implemented and the historical/current feature
preparation checks pass. This is readiness evidence, not a model result: there
are no combined-candidate predictions, error metrics, rankings, or adoption
claim. The issued corrected model, old v2 experiment, source packages, weekly
revisions and T-60 locks remain unchanged.

The first actual Fable review requested revisions. Those revisions and 14
focused tests are complete. The requested actual Fable re-review encountered
HTTP 429, with the provider indicating a reset at **15:40 EDT on September 8,
2026**. Parent explicitly retained the no-fit gate; independent local checks do
not substitute for that review. Resume only after the actual re-review and an
explicit parent fit go-ahead. The user authorized evaluation, not promotion.

## Completed evidence

| Artifact | SHA-256 |
| --- | --- |
| [Revised charter](charter.md) | `a33f4d400dcbfe4a466ac332400067bae4c136592113b8368d4603800edf2b6b` |
| [Implementation chronology/status](implementation-status.json) | `9e7eb1e8fdf01e0dce489f80283da2a000dbb795d4ba8747d2d8c4699cbc63f6` |
| [Historical preparation manifest](preflight-20260908-revised/manifest.json) | `de0dcf0a80eb7daec12bd7c606a4d0f714496b782dd09d321296c9494d425a69` |
| [Separate current diagnostic manifest](current-preflight-20260908/manifest.json) | `0e35d51dc0bcdeb739a17b10e693d47d55e0f8b4810d59da4271dc85b6cf2200` |
| [Independent arithmetic verification](independent-verification.json) | `44ca349b045177ef8d4d1e469cd4c0c17adf5a7e989a83ba6df9105f89b6d934` |

Historical preparation retains all 3,407 games and 6,814 team-game coverage
records. Every original corrected feature matches its saved reference within
1e-12, with identical missingness; each new descriptor varies in every fold's
training data. The preparation took 386.39 seconds and fitted no coefficients.
The [coverage receipt](preflight-20260908-revised/coverage.json) distinguishes
raw ACT rows, collapsed rows, resolved identities, prior role/age coverage and
postgame-only snap-resolution counters. All historical raw ACT rows have a
GSIS or PFR identifier. All pinned old sources/code/evidence were rehashed before
and after the operation.

The separately manifested current diagnostic covers 32 teams with 22 unchanged
corrected fields plus ten descriptors, with no missing current cells. It uses
the issued snapshot's saved input clock, **2026-09-08T15:01:38.802823Z**, not the
diagnostic's execution time. All original current feature cells replay; no
current rating or game forecast has been generated for this candidate.

Independent read-only review by the parallel artifact reviewer also passed:
the six historical manifest members, 3,407 unique rows, 2,127 evaluation rows,
6,814 unique team-games, 80 fold/descriptor variation checks, 67 raw-file hashes
and 23 code hashes reconciled. All 80,387 finite and 1,381 missing original
historical cells match exactly (maximum difference zero). The four current
manifest members reconcile; all 704 original current cells match exactly and
all 1,024 combined current cells are finite. The reviewer independently reran
the 14 passing tests and independently recomputed all 320 new current descriptor
cells exactly. The additive verification receipt linked above records these
checks; it does not clear the external Fable gate.

The interrupted `preflight-20260908` directory preserves the first no-fit start
receipt. It has no completed manifest and must never be treated as qualified
input. The chronology receipt explains why that attempt was stopped and how the
subsequent preparation was corrected. The original charter was written before
implementation; implementation then began during review with parent approval.

## Limits that remain part of the experiment

- Blank draft records are zero-encoded draft-record proxies, not proof a player
  was undrafted or had no talent. In 2016, 18,586 of 29,399 raw ACT rows have blank
  draft numbers; per-team counts are retained. Unknown experience makes unit
  rookie capital missing: 172 offense and 156 defense team-games in 2016.
- Inherited role history includes fallback zero when an ACT player's completed
  game has no resolved snap record; it can also use the base's unique normalized
  name fallback. These are disclosed and counted, never relabeled as observed
  zero participation. The new metadata join uses IDs only.
- Historical recorded starters/rosters are not verified T-60 expectations. The
  2018-2025 evaluation seasons have already been inspected. Age, prior usage and
  draft record do not add OL talent, blocking grades or a calibrated injury model.
- The future study screen has exactly three requirements: lower pooled MAE than
  corrected, wins in at least five of eight seasons, and a positive lower paired
  season-block interval. Weeks 1-4 remain descriptive. Even a screen pass leaves
  scientific status HOLD and does not authorize issuance or adoption.

## Review and resume commands

From the repository root, the focused no-fit tests are:

```powershell
python -B -m unittest research.pgo_corrected_roster_candidate.test_candidate research.pgo_corrected_roster_candidate.test_temporal
```

Result: **14 passed**. These include hand-calculated descriptors, strict DOB and
UTC-boundary handling, missing versus zero data, selected QB/current collision
guards, same-stack corrected-base parity, future-input and kickoff-batch checks,
exception restoration, symmetric missing-pattern replay, and the three-part
screen. Preprocessing fixtures fit no model coefficients.

The following is the **pending, gated** one-candidate command. Do not execute
until parent records the actual Fable re-review and explicit fit go-ahead:

```powershell
python -B -m research.pgo_corrected_roster_candidate.train --fit --prepared research/pgo_corrected_roster_candidate/preflight-20260908-revised --prepared-manifest de0dcf0a80eb7daec12bd7c606a4d0f714496b782dd09d321296c9494d425a69 --output research/pgo_corrected_roster_candidate/run-20260908
```

That command uses the already prepared bytes, eight expanding-season fits and
one final fit, with fixed symmetric Huber ridge settings. It does not rerun the
historical walk or refit old baselines. The reviewed prepared-manifest digest is
bound before fitting and checked again before completion. Output creation is
exclusive; preserve incomplete attempts and never reuse an existing directory.
If review changes construction, revise the contract and prepare separately;
never silently repin or rewrite this evidence.

The separate current diagnostic has already completed; do not repeat it merely
to advance its timestamp. After a future authorized fit, independent saved-fit,
metric/bootstrap, source-preservation and symmetry verification are still
required. Prospective use would be a separate decision.
