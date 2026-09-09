# Sitewide McCabe theme and plain-language forecasts

**Goal:** Apply the already approved slate/cobalt design throughout the current
Shopify storefront and explain forecasts without misleading rounded ties.

**Architecture:** Keep the existing Shopify theme and independent ratings app.
Use the fresh live theme as the native styling baseline, edit its shared CSS and
native color/font settings, and upload only reviewed changed files. Reuse the
Forecast Lab's shared display helpers; saved model inputs and forecasts stay exact.

**Authorization:** The user's request extends the already approved McCabe theme
sitewide and asks for simpler forecast language. Publication remains authorized
in this session; no additional design approval is needed.

- [x] Capture the active Shopify theme and preserve its current settings/content.
- [x] Restyle native navigation, content, cards, products and cart consistently;
      review an unpublished preview on desktop and mobile before scoped upload.
- [x] Display decimal expected points and a plain-language team edge. Confirm
      BAL/IND's saved 25.2236/24.7764 estimates no longer look like a 25-25 tie.
- [x] Put technical lineage and detailed calculations in existing disclosures;
      retain understandable experimental and incomplete-injury explanations.
- [x] Run affected regression and theme checks, preserve all issued evidence,
      and regenerate the app.
- [x] Publish the app and verify the final live embedded release.

**Native worktree:** `D:/CodexWorktrees/Postgame_Outlet-sitewide-mccabe-20260909`.
The model/app changes remain in the existing publication worktree. No model
refit, new injury issuance, forecast rewrite, or promotion is part of this change.

Native release: branch `codex/pgo-sitewide-mccabe-20260909`, commit `a714a71`.
The live theme remains `159107678440`. Desktop and mobile review passed;
14 native contracts passed and Theme Check introduced no findings relative to
the fresh live baseline. Exactly three reviewed files changed on Shopify;
373 other files were byte-identical on live readback. Release receipts and the
rollback capture are under the native worktree's
`output/sitewide-mccabe-20260909/` directory.

Application validation: 601 tests ran successfully (one skipped), plus 14
corrected-roster research tests. Independent review confirmed unchanged McCabe,
current and archived PGO, fantasy, and saved forecast payloads. The complete
84-file issued evidence set remains byte-identical to `0dd1339`.

Published application release: `b0fe9a9`. Pages deployment `34390770257`
succeeded. Both public HTML files matched that commit's Git blobs exactly;
the live Shopify iframe now uses `?release=b0fe9a9`. The cache update is
recorded in native theme commit `f96b849` and matched Shopify readback exactly.
Live browser checks confirmed the new injury wording and BAL 25.2 / IND 24.8,
with Baltimore favored by 0.4 points. No saved forecast was rewritten.

## Follow-up: readable score estimates

The user found Patriots 23.1 / Seattle 23.5 too similar to the original apparent
tie. Show independently rounded whole-point estimates in the score cell, with
the decimal model averages in a native disclosure. If both scores round equal,
say "About 25 points each" rather than presenting a tied final score. The
favored-team column continues to use the unrounded margin, so no winner or
larger edge is invented. Apply the same display policy to weekly and archived
score estimates; preserve every issued forecast and grading calculation.

The user's additional request is a plain-language explanation of what goes
into each prediction. Add a native "Why this forecast?" disclosure: saved team
strength gap, venue and rest adjustments, expected quarterbacks, 2025 scoring
averages, and the split from combined points into each team's estimate. Bind
the detailed corrected-model explanation to the exact source manifest and
saved game; older or mismatched sources receive only their saved score
arithmetic. Link the existing team explanations and separate injury scenarios.
Reconcile every displayed component before showing it. These explanations
describe the formula without changing forecasts or asserting improved accuracy.

Follow-up validation: all 38 Forecast Lab tests passed in 15.734 seconds.
Independent review reconciled all 16 current explanations and verified that
the 272 archived rows do not borrow corrected-model drivers. All 288 score
summaries, favorites, totals, comparison values, grades, and 84 issued evidence
files preserve their saved values. Desktop review and a 375-pixel viewport
check confirmed readable wrapping; the rating link opens its team disclosure
with keyboard activation. Scores stay at the top of an expanded explanation.
Receipts are under `output/rounded-scores-20260909/`.

## Follow-up: matchup layout and defensive-depth coverage

The user's screenshot showed the expanded explanation stretching one narrow
table column. Keep each matchup's score row compact and put its native
explanation disclosure in a separate full-width row. Four short blocks explain
the edge, team/QB inputs, combined points, and injuries; equations and saved
edition metadata stay in a second collapsed disclosure. Native CSS provides
two columns on desktop and one on mobile.

The user also challenged New England's rank because of EDGE/LB depth. The new
input audit traces the saved rating, checks current official roster sources,
and documents that current defensive starter/replacement quality is absent.
Make this limitation explicit on the current board, the matchup explanations,
and New England's team explanation. Publish `docs/model-depth-audit-2026-09-09.md`
with source links and the useful next research test. The failed age/draft
candidate is not adopted; all issued model and forecast evidence stays exact.

Validation before publication: 48 Forecast Lab/current-board tests passed in
44.081 seconds. Desktop inspection showed a 66.8-pixel score row and two
474-pixel explanation columns. At a 375-pixel viewport the explanation uses
one 296-pixel column within the 314-pixel table container, without page or
card overflow. Exact equations remain accessible in the nested disclosure.
Audit and visual receipts are under `output/ne-defense-depth-audit-20260909/`
and `output/ne-depth-layout-20260909/`.
