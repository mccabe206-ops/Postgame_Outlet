# WR reception bonus

User request: add a receiver PPR bonus to PGO Fantasy league settings. Interpret receiver as WR; the existing general reception score and TE premium remain separate.

Use subagent-driven development for this bounded implementation, followed by independent review and browser verification. Reuse existing scoring, profile validation, and published-panel migration paths. No dependencies or model/source/receipt changes.

- [x] Add optional `wr_reception_bonus`, default 0, with the same supported range as TE reception bonus. It adds to normal PPR only for WR receptions. Presets and custom scoring behave consistently with TE premium.
- [x] Saved profiles created before this field default to zero. Preserve other settings; validate finite/range constraints and persist the new value through normal apply/save/reload.
- [x] Add an accessible field labeled `Extra points per WR reception` beside TE premium. Update the scoring summary so readers can see the effective WR reception value. General PPR continues to apply to all eligible positions.
- [x] Update the real public-board refresh path, using existing migration helpers, so already-published Fantasy panels acquire the new field and script. Preserve forecast source cells, player identities, scoring receipt bytes, publication states, McCabe-first order, and unrelated panels.
- [x] Extend existing focused JS/Python checks: WR-only point delta; RB/TE unaffected; old profile zero default; save/reload; invalid inputs; HTML upgrade idempotence. Test the real `python pgo_comparison.py --refresh-mccabe` output and record protected hashes.
- [x] Commit only owned files and this plan; report tests/commit. Parent reviews and performs desktop/mobile browser QA before publication.

Owned paths: `fantasy_league.js`, `fantasy_league_ui.js`, `pgo_comparison.py`, existing related tests, `docs/index.html`, and this plan. Do not change the frozen fantasy scoring receipt, projections, injury annotations, locks, raw captures, or Shopify files.
