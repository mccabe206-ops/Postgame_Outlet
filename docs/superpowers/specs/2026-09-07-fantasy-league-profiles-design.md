# Fantasy league profiles and scoring

Approved direction: the user accepted saved manual league profiles, scoring presets/custom weights, lineup slots, and league-adjusted weekly values with "proceed" after the scoring-data limitation was explained. This implements the actual public board; the existing permission to update the PGO website remains in scope.

## Product

The fantasy board defaults to a 12-team, one-QB, half-PPR profile with QB=1, RB=2, WR=2, TE=1, FLEX=1, SUPERFLEX=0. Its League view ranks weekly points above an estimated replacement player. Position, FLEX, and all-position raw-point views remain available and clearly labeled. A compact native details/form editor supports league name, league size, lineup slots, and scoring. Profiles persist in this browser; storage failure preserves working session behavior and displays an honest unsaved message. No account, backend, platform import, or new dependency is needed.

Scoring includes the 13 existing PGO scoring components and an additive TE reception premium. Presets are standard, half-PPR, PPR; passing-TD points and other admitted weights are editable. Threshold bonuses, first downs, kicker, defense, and unsupported stat categories are not offered.

## Scoring contract

The current challenger provides a scalar half-PPR prediction C. It cannot be decomposed into projected stats. Build a separate 13-component, eight-game exponentially weighted baseline using the existing `pgo_fantasy.strong_baseline` formula and chronological position priors. A scoring-adjusted forecast is:

`league_points = C + sum((league_weight - half_ppr_weight) * projected_component)`.

For TE, the reception-weight difference also includes the selected TE premium. Half-PPR with no premium returns C exactly, independent of component rounding. Verified INACTIVE players remain zero; practice annotations never zero a player. Identify noncanonical scoring as an experimental scoring adjustment with its own receipt. It does not inherit the challenger qualification or change its status.

Use only the already-frozen 2020-2025 nflverse source lock/cache and existing 2022-2025 held-out challenger predictions. Preserve roster-authoritative positions and the audited population; missing raw stat rows become zero only when the existing population builder admits that outcome. Reject duplicate identities, bad joins, nonfinite values, missing sources, hash changes, and mismatched reconstructed half-PPR targets.

## Evaluation charter (locked before running)

Question: does this deterministic adjustment provide usable weekly forecasts under supported scoring while preserving canonical half-PPR exactly? Grain: one ACT-roster-qualified player-game. Outcomes enter histories/position priors only after the entire season-week has been predicted. Use unchanged 2022-2025 folds and the existing primary-pool membership, with all-eligible and position/cold-start slices as secondary evidence.

Compare the anchored adjustment, the independent component baseline, and score-specific training-position means on identical rows. Presets to check: standard, half-PPR, PPR, half-PPR with six-point passing TDs, and half-PPR with a 0.5-point TE reception premium. Primary metric: pooled primary-pool MAE. Bias and season/position MAE must also be reported.

Acceptance for enabling noncanonical scoring: exact input/target/population checks, exact canonical projection preservation, component linearity within 1e-9, anchored MAE no worse than the component baseline pooled for each checked preset, at least three of four folds no worse for each preset, and no position-season primary slice with at least 30 rows more than 25% worse than the component baseline. No tuning after results. A failure is reported and the affected scoring support remains unavailable; do not repair or replace prior evidence. Custom weights outside checked presets are explicitly custom scenarios, not separately validated models. Source publication-vintage limitations and HOLD remain visible in the receipt.

## League value

Fill required position slots across the entire league from the full eligible player pool, then FLEX from remaining RB/WR/TE, then SUPERFLEX from all remaining positions, always by selected-scoring points. No player can fill two slots. The best remaining player at each relevant position is the estimated replacement baseline; league value is points minus that baseline. Compute before search/team/position filters. Explain that this is a starting-lineup estimate, not a claim about actual waivers or benches. If the pool cannot fill slots or provide a required replacement, do not fabricate a zero baseline; clearly fall back to raw-point rankings.

## Integrity and release

All 447 eligible identities and original point/rank fields, the 55 exclusions, injury annotations, source links, PREVIEW/HOLD, and existing frozen artifacts remain preserved. New model/scoring evidence has separate paths and identity. The PGO team panel and McCabe refresh behavior remain intact. The self-contained HTML embeds the scoring basis and engine; refresh validates and preserves them exactly. Reject incomplete, duplicated, or orphaned league assets.

Verify pure scoring/value behavior, real refresh preservation, full Python regressions, and desktop/mobile/browser-storage/profile interactions before publishing. Keep the old public artifact and immutable challenger evidence for comparison. No Shopify commerce or Klaviyo change is part of this feature.
