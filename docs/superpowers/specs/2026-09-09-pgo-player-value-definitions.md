# PGO player and unit value definitions

Status: **DEFINITIONS ONLY. No player point estimates, replacement model, fits,
adoption or publication. Existing scientific status remains EXPERIMENTAL / HOLD.**

The user requested the snap identity repair followed by player-value definitions.
This document defines the quantities a future roster model would have to estimate.
It does not rename the existing age/draft/usage descriptors as player values.
McCabe's human QB/offense/defense judgments remain a separate comparison product.

## The quantity PGO should explain

**Team strength** is the expected next-game scoring-margin advantage, in points,
on a neutral field against the edition's frozen league-average reference, under
a stated roster and availability scenario and a common opportunity/context
distribution. Positive means stronger. It is not season wins, fantasy points,
an EPA rate, a subjective talent grade, or an established betting-price edge.

The future accounting identity is:

`Team = QB + supporting offense + defense + unallocated context`

The fourth term is deliberate. Interactions, coaching/system, special teams and
unallocated team information must not be silently credited to individual players.
A three-part display is justified only if an independently reviewed allocation
can reconcile those terms without hiding a material residual. Renaming the
current fitted feature groups would not supply that allocation.

| Quantity | Definition | What it does not mean |
| --- | --- | --- |
| QB unit | Expected margin contribution of the designated QB role, relative to the reference average QB unit, with common opportunities and reference supporting cast/opponents. Includes QB passing and rushing under one declared sack/turnover allocation. | The sum of every QB-related regression coefficient; credit for all team passing production. |
| Supporting offense | Expected contribution of RB/FB, WR/TE and offensive line together, relative to the average supporting offense at the same opportunities, reference QB and opponent distribution. Includes blocking and receiving/rushing work. | Receiver or team EPA added on top of the same plays already credited entirely to the QB. |
| Defense | Expected contribution through preventing opponent scoring, relative to the average defense facing common reference offenses and opportunities. Better prevention is positive. | Individual defender quality inferred from draft position or participation alone. |
| Unallocated context | The centered remainder needed to reconcile the independently estimated team result with the three units under the chosen allocation. | A disguised player grade, free adjustment to reach a preferred team rank, or a fitted catch-all claimed to be identified football skill. |

These are prospective model estimands. They are not currently identified causal
effects. A claim about what would actually happen if a player were traded or
removed would need stronger assumptions and evidence than a good margin forecast.

## Average, replacement and absence are different references

For player `p`, define its role `r`, opportunity budget `n`, roster scenario,
comparison context and reference pool before any value can be reported.

1. **Value above role average:** the expected point difference between the player
   and the reference average player filling the same role/opportunity allocation.
2. **Value above replacement:** the expected difference from a separately frozen,
   feasible replacement pool and its selection rule, specified by role and date.
   The average starter is not replacement level. A team's current backup is not
   automatically the generic replacement standard.
3. **Team-specific absence effect:** the predicted difference between complete
   feasible lineups with and without the player, including named substitutes and
   redistributed work. It is a lineup scenario result, not necessarily the
   player's context-independent value above replacement.

Never sum uncentered player values above replacement and call the result a unit's
value above average. Individual replacement contrasts can overlap through shared
plays and interactions. They need an explicit additive allocation; otherwise
retain the interaction in the unallocated term and show scenarios separately.

The minimal future numerical path is unit-level estimation with a visible
residual. Full individual-player allocation requires additional evidence. No
standalone numerical estimate for either path is implemented by this document.

## Frozen reference and time

Each edition fixes all 32 team identities, roster vintage, reference unit
distributions, opportunity budgets and centering constants at its edition clock.
Equal team weights define the average; a missing team must not silently shrink
the reference population. Unit means and the residual mean are zero in the
complete reference full-healthy scenario.

For an individual game, the decision cutoff is **scheduled kickoff minus 60
minutes**. Use only evidence available by that cutoff. Earlier previews are
marked previews and carry their own earlier clock. One evaluation row is one NFL
regular-season game; the target is final home-minus-away points including overtime.
Paired team views remain the same event, never separate train/test observations.

Source event time, publication/revision time, capture time and the calculation
time must remain distinct. Historical recorded starters and revised stat files
are not proof of what was knowable at a past cutoff. The existing historical
publication-vintage gap remains REVIEW REQUIRED after the identity repair.

Keep the **same full-healthy reference constants** when calculating an available
scenario. Recentring the available scenario separately would erase league-wide
availability losses. Its league mean can therefore differ from zero.

McCabe's inspected displayed totals average +1.475 while the statistical board is
centered at zero. A common translation preserves matchup gaps but does not prove
that the two scales are calibrated alike. Keep the two products attributed and
independent; do not train toward McCabe's points or rank ordering.

## Quality, role and availability

Keep three estimates separate:

- **Quality:** the player's context-adjusted performance distribution at a
  specified role and opportunity exposure. Report source/window and uncertainty.
- **Role:** the expected allocation of relevant opportunities conditional on a
  feasible lineup. Current usage is not automatically the last four observed
  ACT snap entries, particularly after a transfer or long absence.
- **Availability:** participation probabilities or explicit conditional facts
  known at the prediction cutoff. Unknown coverage is not healthy.

When supported, `expected opportunity = participation probability * opportunity
conditional on participation`. An injury label does not by itself supply either
the calibrated probability or an effectiveness adjustment.

Each complete scenario must allocate its full role/opportunity budget. QB
occupancy has one QB-role budget. Receiver targets, carries, blocking snaps and
defensive tasks have their own denominators. Participant snap shares are not
probabilities and need not sum to one. Never renormalize only the successfully
matched players to make incomplete coverage appear complete: preserve an
explicit unresolved opportunity bucket, and withhold point outputs if it cannot
be valued under a declared prior.

An unavailable player's work goes to named substitutes or an explicit unresolved
replacement bucket. Simply multiplying that player's points by availability
omits the substitute's contribution. Apply a substitution once: do not also
retain an overlapping unavailable-snap penalty or an injury discount already
included in quality. Likewise, QB EPA, receiver EPA and team passing EPA cannot
be independently credited for the same production without an allocation rule.

## Scenario names

| Scenario | Exact meaning |
| --- | --- |
| Full-healthy roster | The explicitly declared roster/depth chart known at the edition clock, under a stated hypothetical absence of medical restrictions. Departed players are not restored; nonmedical eligibility restrictions remain. The roster must state whether and how retained injured/reserve players are included in that hypothetical. Unknown RES/EXE codes are not silently decoded as injuries. |
| Expected-available | An expectation over complete feasible next-game lineups, using supported joint availability and role assumptions known by the decision cutoff. Correlated absences/role competition cannot be treated as independent by accident. |
| Conditional lineup | A named feasible lineup assumption where probabilities are not supported. It may be useful for sensitivity analysis but must not be labeled an expected-available estimate. |
| Existing ACT-roster/QB-conditioned diagnostic | The actual current construction: ACT membership, the saved expected QB, carried descriptors and unadjusted non-QB availability. It is not relabeled full-healthy or expected-available. |

Confirmed Out/inactive can establish zero participation for the applicable game;
it cannot establish the backup's quality or a point cost. DNP/limited practice is
not automatically Out, and does not automatically create a performance discount.
If the selected QB's identity is unsupported or contradictory, block its output
rather than silently selecting another QB. Cross-product comparisons disclose
different starters, as in the inspected ATL McCabe/candidate comparison.

## Missing and stale evidence

Record separate states: observed positive usage; observed zero; no history;
unresolved identity; known-ID absence on an observed unit feed; stale history;
uncertain role; unknown injury coverage; and unavailable value estimate. Source
identity method and observation dates belong with the records.

The repaired updater preserves explicit observed zero and its existing
known-PFR-absence convention on a present unit feed. Unknown identity or an absent
unit feed supplies a missing target, not a zero label. Missing observations do
not enter its four-observation deque. Consequently old valid observations may
remain: this code repair does not solve stale-role estimation.

For the first player-value design, dated usage can be displayed descriptively.
Usage predating the most recently completed season must be marked stale and
cannot alone establish expected current role. A transferred player or returning
long-term absentee needs supported current role/depth evidence or an explicitly
conditional assumption. This is a proposed future estimator policy, not a rewrite
of the failed study or an implementation of dated deques in this repair.

Blank draft entries remain unknown records. A prior can be explicitly labeled
and estimated if admitted in a later charter; it is not observed talent or proof
that a player was undrafted. Missing point estimates stay unavailable, not zero.

## What today's admitted inputs can support

| Current evidence | Supported description | Player-value readiness |
| --- | --- | --- |
| QB performance totals and metric-specific exposure | Dated, shrunk efficiency profiles with team/context caveats | Calibrated standalone QB points not established |
| Existing skill-player receiving/rushing efficiency fields | Partial role-dependent efficiency profiles | Comprehensive supporting-offense points not established |
| Rosters, IDs and snap records | Membership, identity, participation and continuity audits | No blocking, coverage or pass-rush quality from participation alone |
| Team efficiency and results | Team/unit historical performance evidence | Cannot isolate individual OL or defender effects |
| Dated official injury observations | Reporting coverage and conditional participation facts | No calibrated participation probabilities or injury point prices |

`pgo_roster_strength.py` already declares offensive-line and defensive player
quality unavailable. Keep those fields unavailable. The current source inventory
does not admit paid/manual grades or special-teams EPA. No source expansion is
implied by these definitions.

Individual OL and defensive estimates would need longitudinal verified identities,
role/assignment-specific performance and exposure, teammate/opponent context, and
source timestamps. Examples include blocking assignments and opportunities;
pass-rush, coverage and run-defense opportunities. Aggregate outcomes and snaps
alone do not identify those effects. A future provider's grade would still need
provenance, scale documentation and tested conversion to this estimand.

## Evaluation and completion boundaries

The identity repair is evaluated by correct joins, guarded conflicts, explicit
missingness, temporal ordering and preserved prior evidence. It is not accepted
or rejected based on whether LAR stays first or any team's number improves.

Any later numerical candidate needs its own fixed charter and new identity:

- Declare feature/source eligibility at T-60, roster/role/availability policies,
  training windows, a naive baseline and the saved corrected/v0 comparators.
- Use identical eligible games, chronological folds and margin MAE as the primary
  measure. Retain RMSE, bias, season/early-week/team slices, coverage and paired
  uncertainty. Do not choose whichever secondary measure looks favorable.
- Lock numerical acceptance thresholds, minimum coverage, uncertainty treatment
  and stop conditions before any fit. This definition document is not a fit-go
  authorization or a substitute for those concrete thresholds.
- Reused 2018-2025 outcomes are diagnostic. New frozen prospective evidence is
  required for predictive acceptance; even a predictive win does not by itself
  identify causal individual-player values.
- Propagate performance, role and availability uncertainty jointly, including
  covariance. Sensitivity scenarios are not calibrated confidence intervals.

Chosen scope now: the repaired identity layer and these definitions. Alternative
next paths are a smaller unit-level estimator with an explicit residual, or a
larger individual-player estimator after its evidence gaps are resolved. The
unit-level path is the recommended first numerical proposal; neither is built
or fitted here. Existing model outputs, forecasts and McCabe's assessments remain
unchanged.

## Evidence anchors

- [Frozen ranking trace](../../../research/pgo_ranking_trace_20260909/README.md)
- [McCabe comparison](../../../research/pgo_ranking_trace_20260909/mccabe-comparison.md)
- [Existing roster-strength coverage](../../../pgo_roster_strength.py)
- [Admitted source schemas](../../../pgo_sources.py)
- [Existing shared-reference rating construction](../../../pgo_challenger.py)
- [Preserved corrected evaluation contract](../../../research/pgo_week1_corrected/charter.md)
