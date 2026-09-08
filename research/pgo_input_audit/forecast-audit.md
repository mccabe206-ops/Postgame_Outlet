# PGO historical-to-2026 input audit

Audit basis: repository `d35ca9948746ec05e701f2e7b6c4df184f5418a4`, frozen current-strength run `6682197b16fcc0974fef19e6c704ef238d4d2a30ba0db066e3e86a6bad35ee4a`. This was a read-only trace; no model was fit and no forecast or protected evidence changed.

## Confirmed correctness and validation issues

### 1. Historical roster eligibility does not match 2026 inference

`pgo_challenger._read_inputs` admits every `weekly_rosters` row without inspecting `status` (`pgo_challenger.py:2478-2509`), and `_players_for_team` then turns every admitted row into a model player (`pgo_challenger.py:2149-2192`). The September inference path instead filters the current roster to `ACT` (`pgo_forecast_snapshot.py:322-325`; `pgo_current_strength.py:207-220`).

This is not a small coverage difference. The locked 2025 historical roster source has 27,377 `ACT` rows alongside 8,783 `DEV`, 5,763 `RES`, 3,593 `INA`, 951 `CUT`, and other statuses. New England's 2025 Week 1 historical model roster contains 102 rows, of which only 48 are `ACT`; the remainder include 22 `CUT`, 14 `DEV`, 10 `RES`, 7 `INA`, and 1 `RET`.

Those extra players can affect raw QB selection, returning and incoming snap shares, rookie draft capital, availability, and the new role-weighted skill-quality features. The 2018-2025 results therefore do not validate the current `ACT`-only construction. Treat the current-strength screening result as nonportable until an eligibility-matched replay is run.

### 2. Rolling validation does not validate a season-static 272-game forecast

Historical rows are generated immediately before each game, then team performance, QB history, snap roles, coaches, and the results rating update after every kickoff batch (`pgo_challenger.py:2019-2083`, `2269-2351`). The September snapshot computes one team state and applies it unchanged to every 2026 game (`pgo_forecast_snapshot.py:377-395`).

Thus the overall 2,127-game MAE and the weeks 5-18 slice test a weekly refreshed model, while the displayed later-week forecasts are preseason-static. Even weeks 2-4 in the historical slice have already consumed current-season games. This is a use-case validation gap, not evidence that any particular team's rank is wrong. Validate preseason-only snapshots separately, or build and prospectively record reviewed weekly feature snapshots.

### 3. QB rushing shrinkage uses passing volume as its reliability weight

`_qb_features` defines `sample` as dropbacks (`pgo_challenger.py:2231-2234`) and passes that same value when shrinking rushing EPA per carry (`2245-2247`). `_shrunk` then computes the player weight as `dropbacks / (dropbacks + 200)` even though the player rate denominator is carries (`2256-2266`). A high-dropback quarterback with very few carries can therefore receive an almost unshrunk rushing rate. The implementation is deterministic and chartered, but the feature's claimed reliability is not aligned with its measurement denominator. A corrected candidate should use metric-specific exposure, with the existing version retained as the frozen reference.

## Known limitations confirmed, not newly discovered bugs

- **T-60 timing:** historical injuries select the latest revision at or before kickoff, not kickoff minus 60 minutes (`pgo_challenger.py:2170-2176`). In the timestamped 2013-2024 sources, this audit found no selected revision in the final 60 minutes and no resulting probability difference. All 5,783 matched 2025 injury identities lack `date_modified`, so their decision-time vintage remains unverifiable. The run already labels leakage `REVIEW REQUIRED` and the public audit discloses the 2025 limitation.
- **Recorded starters:** `pgo_current_strength._recorded_starters` uses final schedule `home_qb_id`/`away_qb_id` (`pgo_current_strength.py:68-85`). This is an actual-starter oracle, not a historical T-60 expected-starter policy. The report discloses this, so its small MAE gain supports research only.
- **Offseason v0 convention:** the historical walker applies 0.5 at season changes (`pgo_challenger.py:2022-2026`); candidate 2026 inference applies the same decay while frozen raw reproduction preserves the prior public convention (`pgo_current_strength.py:274-276`). This is a known candidate-versus-frozen confound, not evidence that the decay itself is wrong.
- **Coaching:** all 6,814 historical team-game coach fields are populated. There is no missing-coach bug in the frozen run. However, removing the two coaching features improves MAE slightly (10.1318 to 10.1207), and the fitted negative continuity relationship produces large counterintuitive contributions. Treat coach terms as unvalidated associations, not coach valuations.
- **Roster quality:** players with no prior role weight are omitted; players with a role but no history receive the position mean (`pgo_roster_strength.py:170-200`). This is the predeclared rule, but it makes rookie and changed-role preseason quality deliberately incomplete. OL and defensive player quality remain unavailable (`233-236`).
- **Scores and totals:** the margin model is evaluated only on margin. Every 2026 total is the mean of the two teams' 2025 points-for and points-allowed rates, and scores are the arithmetic split of that total by model margin (`pgo_forecast_snapshot.py:384-390`). No historical score/total experiment in the current-strength run validates this static heuristic. It should remain separately labeled experimental and compared prospectively against league-mean/venue and other locked score baselines.

## Minimal next tests

1. Replay the four-game reference with historical `weekly_rosters` filtered to `ACT` before identity construction; keep all games and missing starters, and report source-status coverage.
2. Compare the active-only arm after removing roster-continuity and coach fields, because those fields are most directly affected by the eligibility mismatch and the coaching ablation already improves MAE.
3. Add an eight-game team-history sensitivity and a compact QB feature arm with metric-specific audit output; do not promote from the same reused eight seasons.
4. Separately evaluate preseason-static margins and the score/total heuristic. Do not treat rolling weekly MAE as validation of all 272 frozen forecasts.
