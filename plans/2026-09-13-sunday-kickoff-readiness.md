# Sunday kickoff readiness

User requests operational readiness before the September 13 games. First kickoff
is 17:00 UTC; the eight early forecasts lock at 16:00 UTC. Starting live source
is 3d612286690c01f11d9000d2f398d987af4497ce, saved check 15:04:13 UTC.
The separate injury experiment remains research-only; no numerical promotion.

- [x] Verify current archive, live deployment, early reports, starter assumptions,
  model/score/probability/confidence arithmetic, ATS source replay and final grades.
- [x] Request a fresh canonical season update (run 34765145076; successful).
- [x] Repair demonstrated inactive-link discovery truncation; retain domain,
  matchup, clock, identity and append-only replay checks and bounded fetching.
- [x] Independently review v3 and run the three required Python 3.12 commands.
- [x] Publish v3 through the normal workflow and verify the deployed bytes.
  Publication completed after the early lock; preserve that timing explicitly.
- [x] Verify all eight early forecasts, both completed results, locked market
  lines, and all 136 confidence points remain unchanged after the lock.
- [x] Add and review versioned admission of NFL's new rendered full-slate lists.
- [ ] Run final release checks, publish the NFL reader, and verify public state.

Evidence lives in output/sunday-ready-20260913. Root owns publication and this
plan; starter_capture_tool owns discovery code/tests; market_stats reviews;
offensive_collection checks fresh official reports and inactive lists.

Initial findings: all 152 market/math checks pass; 87 early injury-report rows
match fresh official source. Rush remains Atlanta's announced starter. DEN-KC
is outside the 24-hour availability window, so its missing current archive is
expected. Four unrelated club inactive links can consume discovery slots before
the current article; fix discovery without altering archived parsing semantics.

The final v3 reader preserves v1/v2 replay and supports the observed Sunday club
formats. An independent review passed 58 focused tests and replayed all 13 saved
raw club articles: 16 complete target lists across 15 distinct teams. NFL's new
full-slate article supplied Baltimore's complete source before noon, but the v3
reader cannot admit its rendered list format. Official lists for all 16 teams
were inspected before the lock; no expected starting QB was listed unavailable.
Source coverage is separate from parser admission and resolved player identity.

Python 3.12 full CI attempt 1 failed because the fresh Windows environment lacked
timezone data. The failure is retained. After installing tzdata in the local
venv, attempt 2 passed all three canonical commands at 16:02:52 UTC: 1,073 tests
passed and one was skipped. All six reviewed source/test/workflow pins match.
No model coefficients, confidence allocation, locked picks or grades are edited.

Source commit `1976083bfbc7291f8887e096e530f550caefbab0` was released from a second
isolated worktree while the original full-suite checkout remained unchanged.
The original audited source is retained locally at `b09975d`.

An older refresh hit the expected non-fast-forward guard after the source update;
its failed push is retained. The replacement run `34767394012` succeeded and
published `47cb3a80074376810993bbe793e326b8dc5fc502`. At 16:10:24 UTC, exact public
bytes matched the deployed board, Forecast Lab, stylesheet, current pointer, and
the actual Shopify iframe URL. Browser visual QA was unavailable; these are
network and byte-verification results, not a visual review.

The public state was checked at 16:05:26 UTC. Its early inactive context was
captured after lock: ten teams verified, five partial due to six unresolved
names, and Baltimore unknown to v3. The Bears' earlier six-name supplement was
updated to seven; the current sources agree on membership, with a James/Jamree
Kromah spelling difference. Missing identities are not guessed or treated as zero.

`lock-baseline.json` records a later audit of the durable 15:55:53 prelock archive;
it is not a newly witnessed prelock capture. `postlock-comparison-47cb3a800743.json`
confirms all ten locked games (eight early and two completed), accepted results,
locked ATS cores and confidence allocations are preserved. Evidence files live
under the original worktree's `output/sunday-ready-20260913` directory.

The v4 addition passed all three local Python 3.12 commands at 16:38:21 UTC:
1,079 tests passed and one was skipped. The new module was then normalized only
from CRLF to LF, with identical Python AST and the expected canonical hash;
all 64 focused checks passed again. Raw retained fixtures use `-text` attributes.
Independent review verified 166 archived metadata sets unchanged, representative
real v1/v2 and both v3 packages replaying, and the current state loading exactly.

A real v4 context capture at 16:19:27 UTC discovered NFL's full-slate article and
replayed exactly. Baltimore's seven names all resolved. Chicago also resolved
through NFL's Jamree Kromah entry. The result was twelve verified teams and four
partial teams (ATL, BUF, HOU, IND) with five unresolved name matches. These are
post-lock context observations, with no new numerical injury adjustment.
The actual source's malformed Buffalo position and missing TB/CIN game links
were rejected locally; valid club lists remained available.

All 54 official injury rows for the remaining ten Sunday teams matched the
saved inputs in a fresh check; no contrary expected-QB announcement was found.
Afternoon final-inactive windows begin about 18:55 UTC, Sunday night's at 22:50.
DEN-KC enters the 24-hour capture window at September 14 00:15 UTC.
