# PGO current-strength work: all five workstreams

**QB identity consistency helped. Additional complexity did not consistently help.**
All five approved workstreams are implemented and evaluated as research. Issued
forecasts and promoted ratings remain unchanged. Status: **EXPERIMENTAL / HOLD**.

The [pre-fit charter](charter.md) fixes the inputs, priors, folds, metrics and
decision rules. The [complete run](run-20260908/) contains matched predictions,
fold fits, all-team features/contributions, coverage, and byte-hash receipts.
See the [implementation and independent verification](verification.md).
Its manifest SHA-256 is
`6682197b16fcc0974fef19e6c704ef238d4d2a30ba0db066e3e86a6bad35ee4a`.
The run began 2026-09-08 02:32:52 UTC and finished 02:34:18 UTC
(September 7, 10:32-10:34 PM EDT).

## What was tested

| Workstream | Implementation and finding |
|---|---|
| Consistent QB identity | Historical games use the recorded starter GSIS ID, with the same identity resolution used for the frozen live QB1. This replaces historical highest-EPA selection. All 6,814 historical team-games matched, including all 4,254 evaluation team-games. |
| Current QB ability | Every QB and population accumulator has a fixed 365.25-day half-life and a 200-effective-dropback prior. Experience and draft inputs remain separate. This reduces stale career-volume influence; it is not a fitted aging curve. |
| Non-QB quality and injuries | Four position-shrunk receiving/rushing efficiency proxies use only the prior three seasons and consistent prior-snap role weights. Current official injury coverage is captured separately. OL and defensive player grades remain unavailable. |
| Component testing | Eight whole-group ablations refit preprocessing and coefficients. Removing old roster-continuity inputs produced the strongest simplification signal; removing QB inputs hurt. |
| Honest board presentation | The existing Lab exposes rank gaps, source dates, experimental results and sensitivity. McCabe remains first. Model variation is explicitly distinguished from calibrated uncertainty, which remains unavailable. |

Historical starter IDs are **recorded actual starters**, not verified pregame
expected starters. An earlier discovery probe reported 240 missing starters;
that was a team-alias join error. Normalizing both frozen sources gives complete
coverage. The adapter still fails closed on a missing or ambiguous roster match.

## Matched future-game results

Each evaluation season, 2018-2025, is predicted using a model fitted on earlier
seasons only. All rows are the same 2,127 games. The fixed raw arm exactly
reproduces the frozen full fit and September ratings.

| Arm | Margin MAE, lower is better | RMSE | Winner accuracy |
|---|---:|---:|---:|
| Training-fold constant | 11.0580 | 14.3262 | 54.03% |
| PGO v0 | 10.2662 | 13.2298 | 63.05% |
| Matched raw | 10.1937 | 13.1594 | 63.95% |
| Recorded starter | 10.1193 | 13.0881 | 64.98% |
| Starter + recency | 10.1198 | 13.0695 | 65.60% |
| Starter + recency + skill quality | 10.1318 | 13.0836 | 65.83% |

Winner accuracy excludes eight actual ties, leaving 2,119 decisions; this run
has no exact-zero predicted ties. MAE and RMSE retain all 2,127 games.

Starter selection improves MAE by **0.0744 points** versus matched raw; the
paired season-block 95% interval is **+0.0173 to +0.1387**. Six of eight seasons
improve, and early weeks do not worsen. This merits prospective study. The
absolute gain is modest: about 0.73% of raw MAE.

Recency adds essentially no MAE improvement over starter selection alone
(-0.0005 points; interval -0.0550 to +0.0585). Skill quality worsens MAE by
0.0121 points versus recency (improvement interval -0.0360 to +0.0128).
Better winner accuracy does not override the predeclared primary MAE metric.

All three candidates pass the screen against raw, but this does **not** establish
that each added layer helps. These are reused historical seasons, with only
eight bootstrap blocks and incomplete historical publication receipts.

## What the model can probably lose

Removing old roster continuity improves the full candidate's MAE from 10.1318
to **10.1082**; paired improvement **+0.0236**, interval **+0.0059 to +0.0447**.
Removing coaching improves pooled MAE by 0.0111, but its interval crosses zero.
Removing the new skill-quality inputs restores the recency-only result.
Removing all QB inputs worsens MAE by 0.0866, with an interval entirely below
zero for improvement. All eight results are in [the report](run-20260908/report.md).

These results nominate a simpler model for a future frozen comparison. We did
not search combinations after observing outcomes or relabel the best ablation
as an independently validated model.

## What happens to NE, JAX and PIT

| Team | Frozen September | Starter candidate | Starter + recency | + Skill quality |
|---|---:|---:|---:|---:|
| NE | 1 / +7.219 | 2 / +4.473 | 1 / +4.861 | 1 / +4.817 |
| JAX | 5 / +5.392 | 5 / +3.287 | 5 / +3.206 | 6 / +3.247 |
| PIT | 11 / +3.303 | 4 / +3.627 | 13 / +1.722 | 12 / +1.790 |

Values are rank / centered model output, not calibrated neutral-field prices.
Candidate columns also apply the existing 50% offseason results-rating
retention once; comparison with the frozen column therefore combines policy
and fit changes. The previous [opponent experiment](../pgo_opponent_adjustment/)
isolates retention separately.

Recency reduces Rodgers' 6,467 observed 2013-2025 dropbacks to 553 effective dropbacks;
his shrunk passing EPA moves from +0.1318 to +0.0423. Maye's 911 become 407,
and his shrunk passing EPA moves from +0.1315 to +0.1506. Lawrence's 2,747
become 566, with passing EPA moving from +0.0254 to +0.0465. Recent play can
raise or lower an estimate; this is not an automatic young-QB bonus.

NE remains high because the full research fit assigns it +2.248 from the QB
group, +1.597 from results history, +0.560 from team passing and +0.459 from
other team performance. Roster continuity adds +0.620, coaching subtracts
0.657, and skill quality contributes about -0.011. These reconcile to +4.817;
they are conditional contributions, not independent grades or causal effects.

## Current availability and limits

The new official NFL capture, 2026-09-08 02:24:19 UTC, has 11 formal player rows
for NE and SEA. The other 30 teams are `no_formal_report`, not healthy.
The [separate availability scenario](availability-20260908/) uses the fixed
research fit; it does not backdate those observations into the September
snapshot or replace any weekly forecast. Exact original HTML is retained
locally; the research package contains factual normalized rows and source hashes.

EPA efficiency reflects role, teammates, opponent and usage as well as talent.
The prior-season-only skill profiles omit current-season development, and
snap-role weights can lag rookies or depth changes. Historical actual-starter
selection and final/backfilled source releases still need vintage review.
The current snapshot has 127 of 128 quality values available; Detroit's TE
group is missing because its active players have no positive prior role weight.
Neither this study nor the earlier opponent study supplies calibrated rank
intervals, validated win probabilities, or a new game-total model.

To reproduce in the existing verified cache, use a new output directory:

```powershell
python pgo_strength_evaluation.py --output output/pgo-current-strength-reproduction
```

The runner refuses an existing directory, checks pinned inputs, writes a start
receipt before fitting, and writes its manifest only after preservation checks.
For an independent arithmetic check without fitting, run
`python research/pgo_current_strength/verify_metrics.py`. It recomputes all 14
metric arms and 33 paired bootstrap comparisons from saved predictions;
[1,430 numeric checks passed](metric-verification.json) at absolute tolerance 1e-10.
