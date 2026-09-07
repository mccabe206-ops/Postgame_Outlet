# Fantasy League Profiles Implementation Plan

> **For agentic workers:** Use subagent-driven-development for the independent scoring basis and pure league engine; the parent owns board integration, validation, and release. Run continuous execution within the user's approved scope.

**Goal:** Publish usable manual league profiles, supported scoring adjustments, and league-value rankings on the existing PGO board.

**Architecture:** Preserve the frozen half-PPR artifact and add a deterministic, separately qualified scoring adjustment. Embed a small vanilla JavaScript engine and profile form into the existing self-contained board. Use browser storage and the existing Python/Node tooling.

**Tech Stack:** Python standard library plus existing NumPy where required by the source builder; vanilla browser JavaScript, native forms/localStorage, Node assert, existing unittest and Playwright.

## Global constraints

- Implement the approved spec `docs/superpowers/specs/2026-09-07-fantasy-league-profiles-design.md`.
- Preserve all frozen challenger source, inputs, outputs, locks, receipts, eligibility, original half-PPR projections/ranks, and injury notes. No old model is refit, rerun, or promoted.
- Only the new scoring adjustment is evaluated. Lock its stated acceptance rules before the run; record failures honestly without tuning them away.
- No new service, package, accounts, platform import, synthetic stat reconstruction, arbitrary QB penalty, or change to Shopify commerce.
- Profile data is untrusted. Reject nonfinite/out-of-range weights and slot counts, duplicate player identities, unknown fields, malformed storage, and unsupported schema versions. Render names with textContent.
- All search and view filters operate after full-pool replacement calculation. Missing replacement evidence never becomes an invented zero.
- Half-PPR preserves original values exactly. Noncanonical scoring needs complete matching qualified component data; otherwise provide a specific unavailable message.

## Tasks

- [x] Inspect current main, frozen source data and scalar model, live board, and existing refresh boundary. Create `D:/CodexWorktrees/Postgame_Outlet-league-profiles` from `dc3d398f82c6f1fe88aa384dd3aa7d0cc05ef69d`. Baseline comparison tests: 32 passed.
- [x] Implement and test `pgo_fantasy_scoring.py` and `tests/test_pgo_fantasy_scoring.py`. Reuse the existing population/strong-baseline functions, preserve source hashes, reconstruct components, evaluate against held-out predictions, and write a new bound artifact/receipt under `output/league-profiles/`. Public component rows contain `gsis_id`, `game_id`, `position`, `half_ppr_prediction`, and `components` with the 13 canonical field names. Top-level metadata includes schema/model/status, base preview hash, input hashes, evaluation acceptance, and rows. No public mutation by this worker.
- [x] Implement `fantasy_league.js` with pure `PGOLeague` functions and `tests/test_fantasy_league.js`. Export for Node without a dependency. Interfaces: `DEFAULT_PROFILE`, `HALF_PPR`, `PRESETS`, `validateProfile(profile)`, `scorePlayer(player, profile)`, and `rankLeague(players, profile)`. A player is `{id, position, points, components?, inactive?}`. Profiles are `{version:1,name,teams,slots:{QB,RB,WR,TE,FLEX,SUPERFLEX},scoring:{13 canonical weights,te_reception_bonus}}`. Return derived rows plus positional baselines and a clear unavailable reason. Tests must cover exact canonical preservation, PPR/TD/TE calculations, invalid data, full-pool replacement, flex/superflex uniqueness, ties, and exhaustion.
- [x] Parent: integrate controls, embedded components/engine, rank/value display, profile persistence and safe fallback into `pgo_comparison.py`; upgrade the existing `docs/index.html` without regenerating protected models. Add a real refresh regression and run the Node checks through existing Python test discovery. Save multiple named profiles, handle disabled/corrupt storage, keep keyboard/focus accessible, and preserve source data on every UI change.
- [x] Review scoring evaluation against the locked charter. Publish the sanitized new scoring receipt with immutable filename under `docs/evidence/`; embed only qualified complete components. Do not present custom scenario weights as separately evaluated presets.
- [x] Independently review the complete diff and run relevant regression/browser checks: 1QB versus superflex, scoring presets/custom weights, source annotations, canonical return, filters, empty results, profile reload/delete/reset, blocked/corrupt storage, mobile overflow, and real CI refresh preservation.
- [ ] Publish reviewed changes to the existing board, verify Pages and update-board workflows, verify actual embedded PGO site behavior, and save exact release hashes and remaining limitations.

## Verification commands

Pure engine: `node tests/test_fantasy_league.js` (assertions must fail before implementation, then pass).

Scoring: `python -B -m unittest tests.test_pgo_fantasy_scoring -v`; include manufactured histories proving weekly update timing, invalid-source rejection, canonical equality, and component/scalar linearity.

Integration: `python -B -m unittest tests.test_pgo_comparison -v`; assert an actual refresh preserves league assets/components and rejects missing/duplicate/orphan inputs.

Final: `python -B -m unittest discover -s tests`, `git diff --check`, and native Playwright desktop/mobile interaction. Re-run only checks affected by later fixes. Record evidence in `output/league-profiles/`.
