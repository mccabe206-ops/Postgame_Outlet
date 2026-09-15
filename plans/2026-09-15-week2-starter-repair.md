# Pending-week starter admission implementation plan

> Use test-driven development and an independent whole-diff review. The user approved resolving the Atlanta starter input and the circular starter-admission defect on September 15, 2026.

**Goal:** Make verified official starter evidence usable for the immediate pending week before ranking rollover, without guessing Atlanta's starter.

**Base:** `11aae466cdc8a3bfcf55ed4103d7be11fc068260`, existing isolated worktree `D:/CodexWorktrees/Postgame_Outlet-sunday-release-20260913`, branch `codex/pgo-week2-starter-20260915`.

**Architecture:** Reuse official-article replay, active roster identity, strict default-depth selection, complete league-wide calculation, exclusive receipts and T-60 durable-write checks. Resolve applicable reviewed starter authority before validating defaults for the remaining teams. Preserve fresh captured roster references on a failed weekly build so the supported capture/review/activation path has auditable current inputs.

**Boundaries:** No new dependency, fitted model, weights, manual player status, manual forecast, old archive rewrite, or carried-forward Week 1 announcement. No new scheduler. Missing or conflicting Week 2 authority remains blocked.

## Implementation

- [x] Reproduce with focused regressions before changing source: pending Week 2 is rejected by capture context; inactive default QB prevents a valid active official replacement from being considered; failed rollover drops current roster provenance.
- [x] In `pgo_starter_capture.py`, permit the current scheduled week and only the immediate pending week supported by verified completion of the current week. Capture, review and activation must all use that rule, current verified roster evidence and existing clock/identity checks. Reject unrelated future weeks, ambiguous schedules, incomplete current-week results and late activation.
- [x] In `pgo_expected_starters.py` / `pgo_season.py`, use one shared resolution path for initial issuance and pre-lock revisions: validate applicable official evidence first; select default depth only for unoverridden teams; require unique complete requested-team coverage and active roster identities. Preserve unrelated default conflicts as failures.
- [x] Make initial `build_next` retain game-specific announcement annotations and their source references. Already locked games must retain their archived starter authority through league-wide revisions; their numerical forecasts and confidence allocations remain immutable.
- [x] Retain actual captured build inputs in a blocked state's source references with their real timestamps and hashes. Do not install new rankings or partial forecasts on failure. Reuse existing capture/archive storage, avoiding a separate new provenance store.
- [x] Add a real integration regression with a complete prior-week fixture, inactive default Atlanta QB, a valid game-specific active replacement, initial next-week build, save/load/replay, and unchanged Week 1 evidence. Include wrong-week/late/tampered/conflicting evidence rejection. Mock network and clocks only; no fitting.
- [x] Update `docs/pgo-starter-updates.md` for pending-week eligibility and verified evidence use. Keep external starter status separate from software readiness.

## Verification

Run focused modules first:

```text
python -B -m unittest tests.test_pgo_expected_starters tests.test_pgo_starter_capture tests.test_pgo_starter_revision tests.test_pgo_availability_scope tests.test_pgo_season tests.test_pgo_season_boundaries tests.test_pgo_season_statistics tests.test_pgo_season_rollover
```

Then run the exact `.github/workflows/update-season.yml` test list and the full board CI commands from `.github/workflows/update-board.yml`. Expected: all required tests pass; any known skip must be reported separately. Preserve red/green and complete validation logs under ignored `output/week2-starter-20260915/`.

Independent review must cover every caller of default and official starter selection, next-week admission, archived clocks/hashes, failed-build provenance, immutable prior records and no invented starter. Resolve findings and rerun affected checks before considering release.

## Live Atlanta evidence

Recheck official club news and current provider roster/depth. Activate only a current game-specific supported announcement for Carolina at Atlanta (`2026_02_CAR_ATL`, September 20, 17:00 UTC) with a uniquely matching current active QB. If no such evidence exists, retain the truthful input hold and report the exact unresolved requirement. The software repair does not authorize treating the old Pittsburgh announcement as Week 2 evidence.

## Verified implementation checkpoint

All source, regression and operator-document changes are complete. Independent whole-diff review found no actionable correctness or scope findings. The regression first failed because a blocked rollover discarded the current roster reference; the repaired integration now captures, reviews and activates synthetic official evidence in a temporary root, creates the next edition through frozen coefficients, verifies all 32 teams and 16 fixtures, and preserves all 16 prior predictions and every prior archive byte. Separate RED/GREEN checks cover an inactive default, later locked-context replay, stale roster evidence and T-60 crossings. No model was fitted or live starter override activated.

Python 3.12 validation (native exit 0 for every command):

| Gate | Result |
|---|---|
| Eight focused starter/season modules | 68 passed |
| Pending-week end-to-end regression | 1 passed |
| Exact scheduled season workflow command | 419 passed |
| Full repository discovery | 1,104 passed; 1 expected skip |
| Corrected-roster research regression modules | 14 passed |
| Defensive-depth research regression modules | 14 passed |

The skip is `test_frozen_artifact_checks_are_complete_when_present`: the optional separate Fantasy scoring qualification under ignored `output/league-profiles/scoring-20260907-qualification` is absent. It is not a starter-repair failure or evidence of scoring qualification. Windows-only timezone data was installed in the isolated test environment; repository requirements were unchanged.

Logs, native exit receipts and source hashes are under ignored `output/week2-starter-20260915/`. Scheduled log SHA-256: `57265c8789f6cd719c660ab635107816179385e3973a05e19dedceff94594f0b`; full-suite log: `23aecda4a3049aeb69542a161013f340ff7040e2f06a78ea0cca3c030bcafe66`. After all tests, all 8,881 protected data, evidence, weekly-review and research files still matched their original raw hashes. The nine changed source/test/workflow/operator-document files also matched the tested snapshot. `git diff --check` passed.

## Live transition during verification

The existing scheduled updater advanced Week 2 before this repair was merged. [Run 34971205424](https://github.com/walshja9/Postgame_Outlet/actions/runs/34971205424) published the 12:51:38 UTC edition; its [rollover artifact](https://github.com/walshja9/Postgame_Outlet/actions/runs/34971205424/artifacts/10396789008) verified statistics, 16 finals, 32 rankings, 16 Week 2 fixtures and 16 preserved locked forecasts. Independent replay against the saved 12:32 state preserved every accepted result and ATS record. Public pointer, board and Forecast Lab matched commit `61889fd` at 13:04 UTC and successor `566602a` at 13:05 UTC.

Fresh provider GETs at 13:00:49 UTC selected unique eligible default QBs for the other 31 teams and now pass all 32: the roster updated at 12:40:52 UTC to mark every Atlanta QB ACT, while depth observed at 12:39:14 UTC ranks Michael Penix Jr. first. Across the league, 184 players changed INA to ACT; the file moved mainly to Week 2 rows. This looks like weekly roster rollover, not evidence of medical recovery. [ACT denotes active-roster membership](https://nflreadr.nflverse.com/articles/dictionary_roster_status.html), and [depth observations are timestamped rather than week-specific](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html).

Atlanta's starter remains provisional. The undated [official depth page](https://www.atlantafalcons.com/team/depth-chart) still follows its dated Week 1 Tua/Rush/Strand/Penix ordering. The [Monday injury update](https://www.atlantafalcons.com/news/dashawn-hand-out-for-year-chris-lindstrom-tua-tagovailoa-michael-penix) provides no Tua/Penix return update, and no affirmative Carolina-at-Atlanta starter announcement was verified through 13:03:41 UTC. The live model's Penix selection has no official-announcement annotation. Do not describe it as confirmed return or starting assignment. Normal pre-lock updates remain enabled; reviewed game-specific evidence can revise unlocked forecasts through the repaired path.

Updated top five: Seattle (2 to 1), Buffalo (3 to 2), Jacksonville (7 to 3), Los Angeles Rams (1 to 4), Chicago (9 to 5). Atlanta moves 27 to 25 under the provisional Penix input. Week 1 remains 10-6; the 16 pending games are Week 2.
