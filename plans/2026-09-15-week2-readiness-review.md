# PGO Week 2 readiness review â€” September 15, 2026

> Follow-up: Week 2 advanced at 12:51 UTC during the repair. See the [implementation and verification record](2026-09-15-week2-starter-repair.md) for the current status and remaining Atlanta starter uncertainty.

## Verdict

**Week 1 verified. Automation healthy. Week 2 not yet ready.**

The old Denverâ€“Kansas City statistics gap is resolved upstream. Atlanta's expected quarterback still fails the active-roster/depth consistency check. A separate code gap prevents the existing official-starter workflow from resolving a next-week starter while rollover is blocked.

Read-only source and operational review; only this report was added. No forecast, source archive, model, configuration, publication, workflow, or issue was changed.

## Evidence identity

- Reviewed source: `D:/CodexWorktrees/Postgame_Outlet-sunday-release-20260913`, branch `codex/pgo-next-20260914`, HEAD `a72d1cf0b4485e8240e8f4e11b99fd86555768be`.
- Verified live main/deployment: `a7355279434ed3c61108447413bde032ecf135f5`. The 25 intervening commits changed season evidence and generated HTML only; reviewed source and workflows match.
- Public state checked at `2026-09-15T11:43:09.667455+00:00`, archive `runs-v2/20260915T114309667455Z`.
- Manifest SHA-256: `540331c785c7febc4ca368d3612cf435b944caaffa663985f51844a5f8edfcf5`.
- Compressed state SHA-256: `088feaffbbb9300d18d6f8ac23ea0872a957f605ab0b1b06e8a74ce9dfb328df`.
- Pointer, manifest, compressed state hash and byte length verified. Public pointer, board and Forecast Lab matched immutable deployed-commit bytes at 11:55â€“11:57 UTC.
- [Public pointer](https://walshja9.github.io/Postgame_Outlet/evidence/season-2026/current.json); [full refresh](https://github.com/walshja9/Postgame_Outlet/actions/runs/34964629804); [Pages deployment](https://github.com/walshja9/Postgame_Outlet/actions/runs/34965119502).

## Verified Week 1

Independent arithmetic over all 16 saved games and accepted finals reproduced:

| Measure | Result |
|---|---|
| Winner picks | 10â€“6 |
| ATS suggestions | 6â€“9 |
| Winner picks covering the saved sportsbook line | 7â€“8 |
| Confidence points | 86/136 |
| Grading discrepancies | 0 |
| Missing saved sportsbook line | New England at Seattle |

All 16 locked forecasts, confidence allocations, saved sportsbook choices and accepted results were preserved between the local 03:48 archive and the verified live state using `pgo_season_rollover.check_preserved`.

The [final report](https://walshja9.github.io/Postgame_Outlet/analysis/weekly/2026-week1-final.html) matches its published receipt: 8,370 bytes, SHA-256 `153c98ff1f01086e2baee130ba4102a33ce70ed7db53ec7bdd70ac529cd29569`. This is evidence preservation and grading validation, not proof of predictive quality.

## Current input readiness

Fresh GET-only checks at 11:55â€“11:58 UTC:

- [Team statistics](https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_2026.csv.gz): 32 rows, all 16 Week 1 games; provider Last-Modified 10:22:09 UTC.
- [Player statistics](https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv.gz): 1,118 rows, all 16 games; provider Last-Modified 10:22:06 UTC.
- Pure `partition_player_rows` accepted 1,117 identified rows and one reconciled penalty-only cohort (28 penalties, 138 yards). `_validate_production` passed all 16 games / 32 team periods. No model build or next-week forecasts were produced.
- Fresh ESPN explicit finals, the schedule feed and saved finals agreed for all 16 games, including Denverâ€“Kansas City.
- [Roster](https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_2026.csv.gz): Atlanta lists Michael Penix Jr. and Tua Tagovailoa as `INA`, Cooper Rush as `ACT`.
- [Depth feed](https://github.com/nflverse/nflverse-data/releases/download/depth_charts/depth_charts_2026.csv.gz), latest September 14 at 13:53:31 UTC: Penix rank 1, Tua rank 2, Rush rank 3. Atlanta alone fails active-roster membership among the 32 unique first-ranked QBs.
- The Falcons' [September 14 official update](https://www.atlantafalcons.com/news/dashawn-hand-out-for-year-chris-lindstrom-tua-tagovailoa-michael-penix) supplied no Tua/Penix return-status update entering Week 2. No newer official resolution was found. An undated depth page is not new Week 2 confirmation.

The current saved reason is `Waiting to publish the next week: ATL: Expected QB is ambiguous or not on the active roster`. That error occurs before statistics validation; the independent feed check above establishes that the previous statistics coverage gap has cleared.

## Vetted code finding

| Priority | Finding | Category | Impact | Effort | Fix risk | Confidence |
|---|---|---|---|---|---|---|
| P1 | Let the verified starter workflow resolve the pending next week before rollover | Correctness / coverage | Official starter confirmation cannot unblock the pending slate when the provider's default QB remains inactive or inconsistent | M | MED: future QB assumptions and confidence issuance; preserve all source and lock controls | HIGH |

Evidence:

1. `pgo_starter_capture.py:89â€“99`: `_context` admits only a game whose week equals `state.current_week`. Capture, review and activation all call it. With Week 1 still current, actual scheduled game `2026_02_CAR_ATL` is rejected as `Starter game is not uniquely current`. Independently reproduced in memory.
2. `pgo_starter_capture.py:95â€“98`: the supported workflow also requires a roster capture linked from current state. Failed rollover captures are not installed as edition sources by `pgo_season.py:870â€“880`; this must be handled explicitly in any repair, without inventing capture clocks or rewriting archives.
3. `pgo_season.py:479â€“501`: initial next-week construction calls strict `select_roster` and never applies reviewed starter announcements.
4. `pgo_season.py:645â€“651` and `:662â€“663`: within 24 hours of kickoff, default roster selection still runs before the official announcement override. If the default QB is inactive, selection throws before the override can run. A read-only in-memory reproduction confirmed the override was never called.
5. `pgo_expected_starters.py:35â€“86`: existing reviewed-source validation already checks matchup, week, publication/capture/review clocks, exact official statement, and an active roster identity. Reuse these checks.

Recommended repair scope: admit only the immediate pending scheduled week through the existing reviewed-starter process; supply verified current roster evidence; resolve valid game-specific official authority before requiring a complete default selection; use the same resolution in initial issuance and later unlocked revisions. Missing or conflicting authority must still block. Retain the 32-team model contract, T-60 durable-write check, archived announcements, fixed confidence allocations and all locked Week 1 evidence. Do not choose Rush, Penix or Tua without current supported evidence.

An official Week 2 announcement does not currently exist in the reviewed configuration (it contains only `2026_01_ATL_PIT`). The code repair would make confirmed evidence usable; it would not resolve today's unknown starter by itself. Consistent provider inputs are the other existing route to normal rollover.

## Automation and secondary statuses

- `Update PGO season` is enabled. Full run `34964629804` passed 415 workflow tests and capture, render, publish, rollover observation and alert stages. Extra idle ticks deliberately skip those stages and are not counted as fresh captures.
- The rollover observation remains `WAITING`: 16 finals, 16 locked games preserved, ranking inputs still through completed Week 0.
- [Existing owner issue #22](https://github.com/walshja9/Postgame_Outlet/issues/22) is open. Its overdue threshold is strictly six hours after the last accepted final: after September 15 at 09:27:21.111113 UTC. Notification creation/delivery was not triggered by this review.
- ATS, totals and weight comparisons are held because main state is not READY. Offensive inventory also reports an identity source older than 24 hours. These do not invalidate saved Week 1 grades; they must be rechecked after the next edition exists.

## Completion gates for Week 2

1. Obtain consistent current Atlanta starter evidence; repair the circular starter-admission path if using official authority while provider feeds lag.
2. Observe the real scheduled transition and its `VERIFIED` rollover receipt, with all 32 teams and all 16 Week 2 fixtures, preserved Week 1 records, and appropriate QB/availability/market status.
3. Verify deployed bytes and the Week 2 board before the first lock: **Detroit at Buffalo, Thursday September 17 at 7:15 PM Eastern** (kickoff 8:15 PM). If no pick exists by its cutoff, it must remain unissued; never backdate it.

## Verification and limits

Root verification command, exit 0, **63 tests passed**:

```text
python -B -m unittest tests.test_pgo_weekly_review tests.test_pgo_season_rollover tests.test_pgo_season_statistics tests.test_pgo_statistics_review tests.test_pgo_publication_guard tests.test_pgo_alerts
```

Separate starter-focused regressions and in-memory reproductions also passed. The 415-test workflow run is a separate CI invocation, not a locally rerun full repository suite.

Not audited: whole-repository security/dependency posture, Shopify visual layout, Fantasy release readiness, new model qualification, fitting or predictive improvement. No code repair, official starter activation or Week 2 publication was performed by this review.
