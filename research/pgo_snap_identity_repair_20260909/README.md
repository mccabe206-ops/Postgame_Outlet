# PGO snap identity repair

**Code repair and player-value definitions complete locally. Source qualification
remains STOP because the admitted files contain conflicting identities.
EXPERIMENTAL / HOLD is unchanged.**

Working branch: `codex/pgo-snap-identity-repair-20260909`, based on `275289e`.
The completed study checkout at `Postgame_Outlet-league-profiles` is preserved.
Changes are reviewable in the separate `Postgame_Outlet-snap-identity-repair`
worktree; no merge, publication or frozen forecast rebuild occurred.

## Repair

The shared resolver uses roster-provided full, first/last and football/last names,
with case/whitespace normalization and trailing generational suffix removal.
It resolves **NE Mike/Michael Onwenu** and **NYG Jon Runyan/Jon Runyan Jr.** without
inventing nickname mappings. Matching stays within one season/week/team.

Ambiguous names remain unresolved. Conflicting nonempty PFR/name identities,
duplicate PFR owners and duplicate resolved snap assignments raise errors.
History construction, coverage reporting and the candidate's postgame audit use
the same resolver.

Unresolved identity or an absent unit feed no longer creates zero role targets
or history observations. Explicit observed zero is retained, as is the existing
known-PFR absence convention on an observed unit feed. Missing observations do
not enter the four-observation history. This does not repair stale-role estimates.

## Final-code source evidence

The [conflict inventory](source-conflict-inventory.json) completes all 13 seasons
(2013-2025), 416 team-seasons and 310,475 regular-season snap rows. It only joins
the pinned raw files; it never rebuilds feature histories or fits a model.

- All eight documented Onwenu/Runyan examples resolve to their expected IDs and
  original snap counts under the final code.
- 2,244 additional rows resolve, covering 81,088 offense-plus-defense snaps.
- 16 former matches become explicitly ambiguous: Cincinnati's Michael Thomas,
  covering 109 snaps across 2021-2022. No prior match changes to another player.
- 115 rows have conflicting PFR/name identities, covering 2,195 snaps across
  seven identities. They are a separate conflict category, not production
  missing/zero observations. No duplicate assignments were found.
- Matched volume changes from 9,635,404 to 9,714,193 of 9,957,627 total snaps.
  This is diagnostic coverage, not permission to use the conflicting source set.

The ordinary final-code audit stops on New Orleans' Jonah Williams: its 2025 W1
roster supplies `WillJo10`, while the snap row supplies `WillJo16`. The diagnostic
inventory catches and records this specific exception type to count all cases;
it does not relax production resolution. **Source qualification stays STOP.**
The [source notes](notes.md) list all seven identities and preserve both earlier
STOP receipts. Resolving these contradictions with documented source evidence is
required before a future reconstruction can proceed.

## Verification and preservation

- Full repository suite: **565 tests, one skipped, OK**, before the final
  conflicting-ID guard was added.
- Final code: **114 focused tests passed**, including the regression that failed
  before that guard; **15 candidate/temporal/verifier tests passed**.
- Independent code review closed the conflicting-ID finding; definitions review
  found no material issue. The full suite was not repeated after the narrow guard.
- All 26 pinned raw source files plus the frozen receipt/context retain their
  before/after hashes. All ten copied ranking-trace artifacts are byte-identical.
- Across 215 protected tracked files, 170 match the old checkout byte-for-byte;
  45 differ only by checkout line endings. None has a content change or Git diff.
  The original checkout itself retains no tracked changes.

See [validation receipt](validation.json) for commands, file hashes and scope.
Neither these checks nor improved joins establish predictive improvement.

## Player-value definitions

The [definitions](../../docs/superpowers/specs/2026-09-09-pgo-player-value-definitions.md)
define next-game neutral-field points, shared reference centering, unit versus
player value, average versus replacement, complete lineup scenarios, and the
separate roles of quality, opportunity and availability. Interactions remain
visible rather than being counted twice. Individual OL and defender point values
remain unavailable with today's admitted inputs. No numerical player values or
new component model were fitted.
