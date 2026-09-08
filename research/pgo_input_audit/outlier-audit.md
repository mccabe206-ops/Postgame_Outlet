# Independent PGO input and valuation audit — 2026-09-08

**Verdict: the arithmetic reproduces; NE's exact #1 position is not ready for a predictive endorsement.** The strongest concerns are the meaning and preseason distribution of roster/coaching inputs, correlated passing signals with counterintuitive conditional coefficients, and historical/current eligibility differences. None justifies adjusting NE by hand.

Audit anchor: checkout `d35ca9948746ec05e701f2e7b6c4df184f5418a4`; completed research manifest `6682197b16fcc0974fef19e6c704ef238d4d2a30ba0db066e3e86a6bad35ee4a`. No fitting, source capture, production edit, or frozen-artifact write occurred. New diagnostics are confined to this directory.

## Scope and reproducibility

Target is next-game home-minus-away final margin, one row per completed regular-season game. The existing expanding-season evaluation predicts 2018–2025 from earlier seasons. Historical recorded starters are retrospective reconstructions, not verified expected starters at T-60. Historical source publication vintage remains **REVIEW REQUIRED**. The diagnostics below explain fixed arithmetic and unresolved methodology; they do not upgrade the leakage or promotion verdict.

Verified all eight manifested run files. Reconstructed the full candidate's 3,407 historical matchup rows and 6,814 team states from the existing hash-verified cache, using the unchanged adapter and roster hook. Applying each of the eight saved fold preprocessors/coefficient vectors reproduced all 2,127 saved full-candidate predictions with **maximum error exactly 0.0**. No fit was performed. Earlier independent checks also established exact raw-fit and all-32 raw-rating reproduction and zero non-QB feature changes between raw/starter/recency arms.

Raw has 30 numeric inputs plus 25 missingness indicators. The full candidate adds four skill-efficiency inputs and their four indicators: 34 numeric inputs, 29 indicators, plus an intercept. Team matchup features are home-minus-away; neutral current team scores are centered across 32 teams. Consequently a centered contribution is neither a stand-alone football grade nor the effect of a causal intervention.

Global matched MAE is 10.1937 raw, 10.1193 recorded starter, 10.1198 starter plus recency, and 10.1318 with skill quality. The PGO v0 baseline is 10.2662. The starter improvement is modest and useful; recency and skill quality do not add primary-metric improvement over the preceding arm. This qualification precedes the NE-specific story.

## 1. Roster continuity largely measures a transition that disappears after one game

`pgo_challenger.py:2107` and `:2656` compute the returning share among currently eligible players using their historical snap weights and last recorded team. It is not the fraction of last season's team snaps that returned. `pgo_challenger.py:2331` sets `last_team` for every roster player after each game. New arrivals therefore generally become “returning” players at the next game, even though offseason roster change has not been undone.

The coaching analogue compares the scheduled coach with the previous processed game's coach (`pgo_challenger.py:2122`), then updates that coach after the game (`:2336`). The continuity indicator is mostly a first-game-after-change flag. Tenure is a separate accumulated-games input.

Excluding the initial 2013 cold-start season, the actual reconstructed distributions are:

| Input / statistic | Week 1, 382 team states | Week 2+, 5,920 team states | September, 32 teams |
|---|---:|---:|---:|
| Returning offense, mean | 0.799992 | 0.997398 | 0.824799 |
| Returning offense, SD | 0.114310 | 0.011801 | 0.113204 |
| Returning defense, mean | 0.777816 | 0.996447 | 0.744982 |
| Incoming prior snap share, mean | 0.212840 | 0.003146 | 0.216557 |
| Coach continuity = 0 | 82 / 382 | 19 / 5,920 | 7 / 32 |

Returning-offense variance is 0.013067 in historical Week 1 versus 0.000139 later; September variance is 0.012815. The current values look like preseason values, while most fitted rows are ordinary in-season states. This is a pooled-domain/valuation concern, **not evidence that September values are outside the historical preseason support**.

NE's returning-offense input, 0.664032, is -5.734 SD against all 2014–2025 team states but only -1.189 SD against historical Week 1. Its difference from LAR's 1.000 is 8.655 training **matchup** SDs. In the full candidate that single term contributes **+1.477442 to NE relative to LAR**, against NE's final total lead of only **+0.269450**. Other terms offset much of it. In the recency-only candidate, the corresponding relative term is +1.337797 against a total lead of +0.346450. These are exact contribution comparisons, not ablation/refit results.

The negative returning-offense coefficient occurs in every evaluation fold and final fit in all four arms. In the full arm its standardized coefficient moves from -0.61635 in the 2018 fold to -0.17071 in the final fit. Coach continuity is also negative in every fold: -0.79948 initially, -0.44101 finally. Stable sign does not establish that turnover or coach changes help teams; these inputs combine rare transition states, correlated roster changes, and other model controls.

The already completed whole-group ablation is stronger evidence than an intuitive sign objection: removing old roster-continuity inputs improves MAE by 0.0236, paired interval +0.0059 to +0.0447. Removing coaching improves pooled MAE by 0.0111, but its interval includes zero. Roster removal is therefore the best-supported simplification; coaching removal remains a reasonable separately declared hypothesis.

## 2. Results, team passing and QB passing are correlated evidence

On reconstructed full-candidate home-minus-away inputs, pairwise complete-case correlations are:

| Pair | Correlation | Games |
|---|---:|---:|
| Team passing EPA / QB passing EPA | 0.795729 | 3,390 |
| Results rating / team passing EPA | 0.695309 | 3,391 |
| Results rating / QB passing EPA | 0.641088 | 3,405 |
| QB passing EPA / QB CPOE | 0.705074 | 3,405 |
| Returning defense / incoming snap share | -0.813218 | 3,391 |
| Returning offense / incoming snap share | -0.725194 | 3,391 |

These are overlapping signals, not literal duplicate columns. Ridge regularization can distribute credit among correlated columns, so “results + passing + QB all agree” is not three independent confirmations. The raw final team-passing standardized coefficient is 1.26523; it becomes 0.37517 in recency-only and 0.33989 in the full candidate. QB passing rises from 0.86935 raw to 1.78479 / 1.79571. This redistribution is a reason to avoid treating individual contribution changes as newly measured football value.

Two more sign findings matter:

- **QB sack avoidance has a negative coefficient in all eight full-candidate evaluation folds and the final fit** (fold coefficients -0.1036 to -0.7906; final -0.4984). NE gets +0.388194 from having a lower-than-current-average sack-avoidance input. Do not describe that contribution as the model rewarding protection or avoiding sacks.
- QB CPOE changes sign across folds. New WR and TE skill-quality coefficients are negative in all eight evaluation folds, then positive only in the final fit. Current positive coefficients are not evidence of stable positive player valuation. The skill-quality group's lack of incremental MAE improvement reinforces this concern.

NE's recency passing EPA is 0.150619, within historical Week-1 support; its team passing input is 0.323606, +2.205 Week-1 SDs and below the historical Week-1 maximum 0.388435. NE CPOE is 6.070900, above the historical Week-1 maximum 5.049626 (+3.230 SD), but its full-candidate contribution is only +0.130624. Thus the most visibly unusual raw input is not the biggest valuation issue.

## 3. NE's historical errors do not show persistent overrating

Positive bias below means the model predicted a better NE margin than occurred; negative means it underpredicted NE. These are exploratory slices of already inspected evaluation seasons, with small team-specific samples.

| Arm | NE games | NE MAE | NE bias | Weeks 1–4 MAE, 32 games | Weeks 1–4 bias |
|---|---:|---:|---:|---:|---:|
| Raw | 133 | 11.4236 | -0.8843 | 11.0589 | +0.7863 |
| Starter | 133 | 11.3611 | -1.2543 | 10.6850 | +0.5589 |
| Starter + recency | 133 | 11.2536 | -1.1873 | 10.7771 | +0.6584 |
| Full candidate | 133 | 11.2532 | -1.2929 | 10.7620 | +0.6375 |
| PGO v0 | 133 | 11.4340 | -0.9239 | 11.4700 | +0.2068 |

Full-candidate home/away NE MAE is 11.3480 / 11.1569; home/away bias is -0.9252 / -1.6662. These do not reveal a simple location-specific NE premium.

| Season | NE full-candidate MAE | NE bias | Weeks 1–4 bias |
|---|---:|---:|---:|
| 2018 | 10.7615 | -0.5278 | +4.3602 |
| 2019 | 10.5109 | -2.8223 | -12.9095 |
| 2020 | 12.2597 | +2.4681 | +0.2652 |
| 2021 | 14.0768 | -7.8466 | -0.8959 |
| 2022 | 11.0288 | +0.4358 | +6.0160 |
| 2023 | 9.9572 | +5.0738 | +10.5883 |
| 2024 | 10.6867 | +1.7526 | +4.9022 |
| 2025 | 10.7305 | -8.7007 | -7.2265 |

Exact values are in `diagnostics.json`; the table is rounded. The direction changes sharply by season. In particular, 2025 NE results were substantially better than predicted, so “the model always overrates NE” is unsupported. Conversely, underpredicting its 2025 results does not establish a correct 2026 #1 rank.

Largest full-candidate NE misses include 2020 Week 13 at LAC (predicted -1.287, actual +45), 2021 Week 10 versus CLE (-0.226, +38), 2023 Week 5 versus NO (+3.406, -34), and 2023 Week 4 at DAL (-4.922, -35). Both unexpectedly large wins and losses matter; do not explain only the convenient blowout. All 12 largest misses are saved with signed NE-perspective margins.

## 4. Remaining train/inference and input-quality mismatches

- Historical `_read_inputs` admits weekly roster rows of all statuses, whereas the September constructor and adapter's `_snapshot_metadata` admit ACT only. Even identical formulas can therefore see different eligible populations and denominators. Historical recorded starters are known retrospectively; matching their IDs does not prove they were knowable from a pregame report. A like-for-like ACT reconstruction must retain every game and explicitly report any newly unavailable starter/features.
- `pgo_challenger.py:2325` defaults unmatched roster/snap identities to `(0.0, 0.0)` before adding history. Actual nonparticipation and unmatched snap records can therefore share the same representation. This is a verified code behavior; the present audit has not established how many missing joins are affected. Investigate provenance/coverage before changing zero to missing across the model.
- Four-game half-life team efficiency carries prior-season ratios unchanged through the calendar offseason; it is a game-history memory, not a calendar-fresh measure. In a steady opportunity stream, the last four games carry approximately half the weight and the last eight approximately three quarters; variable play denominators change exact EPA weights. The candidate does apply the existing 0.5 results-rating offseason retention once, and QB accumulators decay by calendar time. These three memories have intentionally different semantics, but no result here proves their preseason combination is optimal.
- Skill profiles use only completed seasons `target-1`, `target-2`, `target-3` (`pgo_roster_strength.py:102`), with fixed weights 1/.5/.25. No current-season outcome enters those profiles. The four current quality values exist for 127/128 team-feature cells; DET TE is missing because all four eligible TEs have zero positive role weight. OL/defensive talent remains unavailable. EPA also reflects context, usage and opponents, not isolated player ability.
- The previous opponent-adjustment experiment did not establish a clear improvement; opponent-context sensitivity remains a limitation. Do not silently combine it with these candidates or describe the current team/QB EPA as opponent-adjusted talent.

## Smallest justified next comparisons

Freeze these as league-wide research comparisons before fitting or looking at new NE rankings. Keep the current reference arm, games, targets, fold-local preprocessing, ridge/Huber settings, source hashes, and current snapshot identity fixed.

1. **Eligibility isolation:** reference starter-plus-recency using historical all-status rosters versus the same model using historical ACT eligibility. Use the same expected-ID resolution rule, retain all games, and report missing starter/role rates and all altered feature columns. This resolves a concrete inference-policy mismatch before interpreting valuation changes.
2. **Simplification isolation:** ACT candidate versus the same candidate with old roster-continuity and coaching columns (and their missingness flags) removed. Existing separate ablations identify the strongest support for roster removal and weaker support for coaching removal; report that distinction. Do not claim a combined removal has already been validated.
3. **Memory and QB valuation:** compare the fixed clean ACT candidate at four versus eight game half-life, and separately a compact passing/rushing-EPA QB representation versus the full QB block. Eight games is a single predeclared stability contrast, not an optimized value. Retain the 200-effective-dropback shrinkage internally even if dropping the log-sample predictor; explicitly preserve the availability policy. Current eight-game inputs must be reconstructed from the same frozen raw history, not obtained by rescaling saved four-game features.

The eight-game and compact-QB ideas are **hypotheses**, not repairs already proven necessary. Use identical expanding seasons, paired error differences, per-season and first-game/early-week slices, and full missingness/domain receipts. Save every arm. Do not optimize against NE's rank, select a pleasing ranking, impose hand-chosen signs merely for a nicer narrative, or call reused-history gains prospective confirmation.

## Reader-facing conclusion

NE's inputs contain strong recent passing evidence, and NE remains near the top under the related candidate fits. The exact ordering also depends on transition-state roster variables and conditional coefficients that should not be sold as football grades. The appropriate response is a small, frozen, league-wide eligibility/valuation test with clear preseason diagnostics—not a cosmetic explanation that turns #1 into an endorsement.

Reproduction companion: `diagnose_saved_run.py` reads frozen artifacts, reconstructs features, and evaluates already saved coefficients only. It writes `diagnostics.json` exclusively and refuses to overwrite it. That file contains full distributions, all current-team z diagnostics, coefficient histories, error slices, correlations, and exact prediction-reproduction checks.
