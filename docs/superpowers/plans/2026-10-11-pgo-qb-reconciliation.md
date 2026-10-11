# PGO verified QB reconciliation implementation plan

> Use test-driven implementation with scoped subagents and independent whole-diff review. The parent owns official source admission, season-state integration, commits and publication.

**Goal:** Show numerically recalculated current PGO rankings using verified replacement QBs, while preserving original issued forecasts and grades.

**Architecture:** Reuse the complete 32-team ranking snapshots already stored in current projections. Carry earlier admitted current-week replacement authority into later complete calculations, replaying its actual original evidence clock. The shared renderer selects the newest compatible complete calculation for rankings, explanations, comparison and ranking freshness.

**Tech Stack:** Existing Python standard library, installed model dependencies, GitHub Actions and Pages.

## Global constraints

- No coefficient refit, human QB-grade input, new dependency or fitted non-QB injury adjustment.
- Preserve weekly `state.rankings`, issued games, confidence allocations, grades and historical archives. Current calculations remain excluded from locked-record grading.
- Every displayed ranking comes from one complete league-wide calculation; never splice ranks, ratings or names from different calculations.
- Reuse only game-specific, current-week, admitted starter evidence. Keep actual capture, review, issue and durable-write times. Unverified, ambiguous, stale-week or conflicting inputs fail closed.
- Source refresh, local tests, Git integration and public deployment are separate outcomes; verify each.

## Task 1: Retain admitted current-week starter authority

**Owner/files:** Backend implementer: `pgo_current_projection.py`, `pgo_expected_starters.py`, `tests/test_pgo_current_projection.py`, `tests/test_pgo_current_starters.py`. No Git writes or external source refresh by this implementer.

**Interface:** `refresh(state, root)` and `validate(state, root, durable=None)` remain unchanged. `model_inputs.starter_announcements` may contain a carried annotation with `verified_at` equal to its earlier current projection's `inputs_as_of`. Fresh annotations retain the current representation.

- [ ] Write a regression using the existing real-model fixture: an admitted replacement from an earlier completed current-week game must remain selected in a subsequent current projection's full 32-team calculation. The original current projection and weekly state remain unchanged.
- [ ] Run `python -B -m unittest tests.test_pgo_current_projection` and record the expected red failure.
- [ ] After `apply_current` resolves live applicable authority without completing default depth, carry earlier current projections' own admitted starters for the same completed-week basis and week, excluding teams already resolved by newer live authority. Verify the earlier evidence using its saved clock and resolve the selected player uniquely on the fresh ACT roster. Add source references to the new complete calculation. Mark carried annotations with the earlier actual `inputs_as_of`; never invent a capture or backdate the new issue.
- [ ] Complete default depth only after verified live and retained authority, preserving full-32 validation. A primary QB marked INA must not block its already admitted ACT replacement. Keep the shared resolver's default full-scope contract; only the current-projection caller uses its explicit partial phase. For a game being rebuilt, freshly replay retained own evidence at the actual new clock and use an ordinary annotation, avoiding self-reference to an overwritten earlier map entry.
- [ ] Extend `_replay` to accept carried authority only when the corresponding earlier current projection exists in the state, matches week/game identity and clock, and contains the exact source/identity annotation. Replay the official source at the recorded earlier clock; all other source, roster, feature, coefficient and 32-team reconciliation checks remain intact. Reject self-reference, future clocks, forged earlier clocks, wrong week and absent authority.
- [ ] Preserve exact schedule inventory and core matchup identity for every game. Require full venue/rest identity for completed-week feature games and the projection's own game. Permit later venue/rest corrections only for unrelated same-week games that were not used in its numerical replay, retaining its archived input bytes. Verify unrelated neutral-venue correction succeeds while own venue or core identity tampering fails. This addresses the observed PHI/JAX neutral-venue correction blocking TB replay.
- [ ] Add rejection coverage and verify save/load replay and original archive preservation with the existing tests.
- [ ] Run the focused suite and write `output/pgo-qb-reconciliation-20261011/backend-report.md` with changed files, red/green evidence, test counts and any concerns.

## Task 2: Render one verified current ranking calculation

**Owner/files:** View implementer: `pgo_season_view.py`, `tests/test_pgo_current_rankings_view.py` and affected existing view fixtures if needed. No backend files, Git writes or external refresh.

**Interface:** Input is the existing season state. Eligible current ranking candidates are `state.current_projections[game_id].rankings` whose completed-week basis equals the weekly snapshot, whose game week is that basis plus one, whose generation is newer than the weekly snapshot and no later than `state.checked_at`. Each is a complete 32-team calculation validated on state load.

- [ ] Write tests proving that current ranking rows, explanations, expected QBs, McCabe comparison and ranking freshness select the same newest compatible snapshot without mutating the state. Test old-week, older-generation, malformed ordering and conflicting same-time candidates.
- [ ] Run the new suite and record the expected red failure.
- [ ] Select the newest compatible whole snapshot. Preserve the weekly fallback when no candidate qualifies. Reuse `_rankings` for all numerical/rank/contribution validation; reject equally recent conflicting calculations.
- [ ] Use the selected snapshot for `_rankings` and ranking freshness, and disclose that the dated current-lineup calculation is separate from original weekly forecasts and grades. Do not change saved game rendering or records.
- [ ] Run `python -B -m unittest tests.test_pgo_current_rankings_view tests.test_pgo_current_projection_view tests.test_pgo_season_view` and write `output/pgo-qb-reconciliation-20261011/view-report.md`.

## Task 3: Admit official replacements and release

**Owner/files:** Parent: `data/pgo_current_starter_announcements.json`, new append-only official capture/review/source artifacts and season state; docs and generated public pages.

- [ ] Capture/review/activate Chicago's Bagent authority using the existing current commands and fresh saved ACT roster. Source: `https://www.chicagobears.com/news/tyson-bagent-looking-forward-to-facing-rival-packers`, game `2026_05_CHI_GB`, GSIS `00-0038416`.
- [ ] Capture/review/activate Baltimore's Huntley current authority. Source: `https://www.baltimoreravens.com/news/lamar-jackson-trey-hendrickson-injury-report-marlon-humphrey-zay-flowers-ronnie-stanley-ravens-falcons`, game `2026_05_BAL_ATL`, GSIS `00-0035993`. The separately dated ranking calculation may include verified upcoming starters; it must not revise original locked records.
- [ ] Retain the existing admitted Daniels authority and original TB current projection; no late recapture for the completed TB game.
- [ ] Refresh the supported current projection path with real clocks; verify complete all-32 ranking/model replay and that weekly records remain unchanged. Render both pages with the shared publisher.
- [ ] Run relevant regression suites, then required repository/CI checks. Resolve independent review findings. Inspect scoped source/evidence diff and original record hashes.
- [ ] Integrate by a non-rebasing push after reconciling newer mutable season data through the existing admission rules. Verify required CI, Pages deployment, actual public comparison QBs and Shopify embedding. Save release evidence under `output/pgo-qb-reconciliation-20261011/`.

## Approval and progress

The user approved the linked current-lineup design with "proceed" on October 11. Execute continuously within that scope. Publication is part of completing the current live comparison fix; preserve all historical evidence and original grades.
