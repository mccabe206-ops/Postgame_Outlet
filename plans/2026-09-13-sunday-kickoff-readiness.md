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
- [ ] Independent review and relevant regressions; required Python 3.12 CI checks.
- [ ] Publish tested source through existing workflows; observe final-inactive
  captures and verify deployed state before early prediction lock.
- [ ] Preserve original picks/grades and save an exact operational receipt.

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
raw club articles: 16 complete target lists across 15 distinct teams. Baltimore
still lacks a confirmed full-list source. No expected starting QB discrepancy
has been found. This is source evidence, not a claim of live parser admission.

Python 3.12 full CI attempt 1 failed because the fresh Windows environment lacked
timezone data. The failure is retained. After installing tzdata in the local
venv, attempt 2 runs all three canonical commands against pinned final sources.
No model coefficients, confidence allocation, locked picks or grades are edited.
