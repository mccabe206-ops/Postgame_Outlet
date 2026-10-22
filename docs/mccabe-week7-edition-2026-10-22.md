# McCabe Week 7 edition provenance - October 22, 2026

`Week 7 2026` was appended through `snapshot.py` at its actual creation time,
`2026-10-22T10:35:55-04:00` (`2026-10-22T14:35:55Z`). This is a new reviewed
edition, preserving the supplied rating judgments after Week 6.

- Source: [October 21 reviewed-input commit](https://github.com/walshja9/Postgame_Outlet/commit/2f62c019dc46b6a5fa9055f58b91607975e0dead),
  recorded by GitHub with `mccabe206-ops` as author and committer at
  `2026-10-21T05:07:27Z`. This identifies the supplying account. It does not
  establish who operated that account or that Sean McCabe personally entered
  or approved these edits.
- `data/ratings.csv` exactly matches that commit's blob
  `abb2f5f4350a6b2113b362cbd5a54ae548674ee7` (SHA256
  `e98fcc84dee23432fef3b80b88f8b95e7c5389f5030d9db2dfcd66e785699363`).
- All 32 rows have `needs_review=N`. All 32 differ from the immutable Week 5
  snapshot in quarterback identity or numerical rating components. No supplied
  rating was adjusted during this edition repair.
- The eight earlier snapshots retain all of their original rows, timestamps and
  correction notes. No Week 6 snapshot or forecast was backfilled.
- New England's team rating remains +3.0 with Drake Maye; Chicago's remains
  +3.7 with Caleb Williams.
  The five leading human ratings are Buffalo +6.5, Los Angeles Rams +6.3,
  San Francisco +6.1, Kansas City +6.0 and Baltimore +5.1.
- The separate September 9 injury-review metadata is preserved. The current
  board omits its obsolete banner. This edition repair does not claim a new
  league-wide injury review or final-inactive check.

Preparation checks passed: `tests.test_ratings_release`,
`tests.test_editorial_binding` and `tests.test_mccabe_forecasts` (49 tests,
13.347 seconds). The first sandbox run was blocked by temporary-directory ACLs;
the same tests passed with the configured D: temporary location outside that
sandbox. An unchanged `snapshot.load_prior` ResourceWarning remains.

The preflight at `2026-10-22T14:37:14.985200+00:00` found 14 eligible Week 7 games,
including `2026_07_NE_CHI` with a strict `2026-10-22T23:15:00+00:00` cutoff. It
retained the existing 45 McCabe game identities. This preflight did not write a
season archive or issue a durable forecast. Actual collection must use the
normal season writer and retain its real issue and durable-save times before
the cutoff. Maye/Williams remain the assumed quarterbacks pending final inactives.

The first normal refresh exposed a historical venue discrepancy that the earlier
arithmetic preflight did not exercise against the full saved payload:
`2026_05_PHI_JAX` was captured as `Home`, while the verified schedule now says
`Neutral`. Its accepted provider FINAL has the same teams and kickoff,
`2026-10-11T13:30:00Z`, and source SHA256
`bd7685d8de8f2a192c9d1992dfb4913f0abfcd7c2297318cd0fe23d53800bd4c`.
The old issued row, its `Home` context, line and input bundle remain unchanged.
The published formula already applies team/default HFA at neutral venues, so
its numerical replay also remains unchanged. This discrepancy remains a
historical venue review, exposed in saved collection metadata and workflow
health. It is separate from the existing CHI-GB legacy kickoff review.

A venue-only difference can coexist with current collection only for an earlier
week after its cutoff, with an already accepted matching FINAL observed by the
check time. Missing games, changed teams or kickoffs, unfinished games and
current-week venue differences still block collection. New-capture schedule,
edition, issue-time and durable T-60 checks are unchanged. Old archives without
the new disclosure field remain readable; when present, it must replay exactly
from saved schedule, issued record and accepted FINAL evidence.
