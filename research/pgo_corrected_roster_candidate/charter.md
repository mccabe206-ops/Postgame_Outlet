# Corrected PGO plus the v2 roster feature block

Status: REVIEW-READY DESIGN / EXPERIMENTAL HOLD. Written September 8, 2026,
before candidate feature construction or fitting. The user authorized evaluation
of a combined candidate, not adoption. Parent and independent Fable review must
resolve implementation readiness before the single run starts.

Revision note, September 8, 2026: the preceding chronology describes this
document's creation. Adapter/test implementation and an explicitly no-fit
preparation began during the first Fable review, with parent authorization.
That preparation was interrupted and remains incomplete; no candidate fit has
run. The implementation-status receipt records the sequence and review fixes.
This revised charter and prepared evidence require parent and Fable re-review
before fitting. Historical preparation is independent of the optional current
diagnostic, so a current-input failure cannot discard completed history evidence.

## Question, scope, and immutable references

Does adding the fixed ten-feature age/role/draft block from the older v2
experiment improve next-game home-minus-away margin predictions over the issued
corrected construction on exactly the same historical games? One row is one NFL
regular-season game; target is final home-minus-away points including overtime.
This is a joint refit, not an average of ratings or a splice of old coefficients.
There is no NE rank target, team exception, feature selection, parameter search,
or additional candidate arm. The combined candidate has its own identity:
`pgo-corrected-roster-candidate-2026-09-08`.

Keep the corrected edition, all older experiments, sources, receipts, current
board, weekly revisions and T-60 locks unchanged. This charter authorizes no
forecast issuance, new source capture, promotion, or production integration.
Research-only current ratings may use the already verified September 8 input
package; they are a construction diagnostic, never a replacement forecast.

References to rehash before and after execution:

| Reference | SHA-256 |
| --- | --- |
| `research/pgo_week1_corrected/run-20260908/manifest.json` | `7530b3199f8a17ffec34f9e5351919ea67cb45df66e16befd655ab4e746f7a4c` |
| Corrected `final-fit.json` | `f6e6deda6665ded3ea0764a486fc68bc4667abd4a49f17afe5e3c39284a8806f` |
| `research/pgo_v1/sources.lock.json` | `3a7673ac4617d57954cb56954f2216226a358c7b187b1e3ce62994a6f2b3fd29` |
| `docs/evidence/forecast-lab-2026/september-08-corrected/manifest.json` | `85fe35069145505410567709261663be0939b3ae2fbe05ad147da1d17fc54d83` |
| Older v2 worktree `pgo_challenger.py` | `70ab4a09f793bc61accae02490e9dba2bb308ebc95e58a324db0e69ddabfd3af` |
| Older v2 worktree `pgo_roster_challenger.py` | `2b37f2e2fb182d9e42692ab9c05ad731dd7b76271bccbe3c45294b64096fb3d1` |
| Older v2 `research/pgo_v2/backtest.json` | `cb199b67c582b09e8e67e05b8d6e9f236ef69107a3daa3251733b0fc4b5412c3` |

The older worktree is `D:/CodexWorktrees/Postgame_Outlet-pgo-v2-roster`.
Its backtest remains HOLD: its MAE gain over its own v1 baseline was about
0.000355, with interval [-0.051825, 0.053304]. That is neither evidence for this
combined candidate nor permission to reuse its preprocessing or coefficients.

## Fixed corrected base and fitting contract

Reuse the construction in `research/pgo_week1_corrected/train.py`: ACT rows
before duplicate collapse, recorded historical QB selection, four-game team
efficiency decay, 365.25-day QB decay, metric-specific exposure shrinkage, and
the same six removed continuity/coach/global-rookie fields. Do not restore those
six fields accidentally by importing the older v2 core. The two unit-specific
rookie fields below are distinct from the removed global rookie field.

The unmodified corrected historical feature cells, game IDs, order, targets,
kickoffs and fold membership must match saved `historical-features.json` before
any fit. Compare finite cells within 1e-12 and missingness exactly. Preserve the
corrected historical availability fields as recorded; the new block below does
not add availability probabilities. Retain all 3,407 training-history games
(2013-2025) and all 2,127 evaluation games (2018-2025), including missing starters.

Use eight expanding-season folds: train 2013 through S-1, evaluate S for
S=2018,...,2025. Earlier games within an evaluation season may update rolling
inputs only after their kickoff batch has been prepared; they never refit that
season's coefficients or preprocessing. Fit the final research model once on
2013-2025. Thus there are nine candidate fits and no baseline refits: use the
verified saved corrected and comparator predictions.

Append the ten raw matchup features below, then mirror training rows and targets
only. Negate every finite home-minus-away field, signed venue and rest; retain
missing values. Use the existing Huber ridge fit, delta 1, alpha 200 on doubled
training rows (same penalty per original observation as alpha 100 before row
doubling). Learn medians, scales and missing-flag inventory on each augmented
training fold only. Mirror after forming the differences: in particular,
`(home_age-27)^2 - (away_age-27)^2` is a signed feature; it is not the square of
the age difference. Evaluate each original game exactly once.

## Exact ten-feature adapter

Use the existing `pgo_current_strength.build_rows(..., 'starter_recency',
roster_hook=...)` inside `audit_model.construction_scope` with ACT, half-life 4,
and exposure repair. The small new adapter belongs under this research
directory. Port the old pure `_age_years`, position mapping and unit aggregation
definitions with provenance; do not import or run the old v2 training runner.

The hook receives corrected `metadata['roster']` and `metadata['starter']`.
Join additional raw fields from `inputs['rosters'][(season, week, team)]` through
the existing collision-aware `_roster_player_id` identity (GSIS, smart-ID where
required, existing PFR fallback). Require one resolved metadata row per roster
player; never guess by name or use a later roster to repair an earlier one.
Read birth date, experience and draft number from those raw rows, not the base
player dictionary whose experience parser currently defaults blanks to zero.

For this block only, every ACT player has availability weight one in historical
and current construction. Populate the same values in full/current team views.
This intentionally differs from the older v2 probability-weighted current view:
it matches the corrected current product's unadjusted non-QB contract without
claiming calibrated availability. Preserve the base fields independently.

For a player, age `a` is `(feature_date - birth_date).days / 365.2425`. Historical
feature date is the UTC date of that game's kickoff; current date is the UTC
date of the verified source `inputs_as_of`, never wall-clock rendering time.
An absent birth date yields missing age; malformed dates or ages outside
[18, 50] fail preflight. Selected QB means the corrected recorded starter in
history and the verified expected QB in the current snapshot. If unresolved,
both age terms are missing; do not substitute the historically best EPA QB.

For unit U, `s_i` is the corrected context's median of the player's existing
last-four prior ACT roster game role entries. Use only history available before
the game; do not estimate an unseen player's role from that game's snaps.
No prior role history is missing, never replaced with zero by this adapter.
The inherited base updater does append zero when an ACT player has no resolved
snap row in a completed game. Thus existing zeros can be fallback zeros, not
observed nonparticipation. Preserve that base policy and count its use separately.
The base snap resolver first uses PFR and then unique normalized name within
season/week/team; that inherited name fallback remains disclosed and counted.
The new raw DOB/draft/experience join itself uses IDs only.
The ACT-filtered context can skip inactive observations and carry old role
history across absences, teams and seasons; preserve and disclose that behavior.
Do not introduce a new role model or time decay in this experiment.

Position mapping exactly follows v2: first slash-separated position, upper case;
HB=RB, OT=T, OG=G, MLB=LB, FS/SS/SAF=S. Offense is RB/FB/WR/TE/C/G/T/OL;
defense is DE/DT/DL/NT/LB/ILB/OLB/EDGE/CB/S/DB. Exclude QB and K/P/LS from
non-QB units. Unmapped positions are excluded and counted, not guessed.

Let `d_i=1/sqrt(draft_number)` for a recorded positive integral draft number.
A blank or numeric zero uses zero to retain v2's draft encoding; it means
**no recorded draft value**, not confirmed undrafted or zero talent. Negative,
nonfinite or fractional values fail. Experience must be a nonnegative integral
number when present. Missing experience is unknown, never a rookie; invalid
nonblank experience fails. If any selected unit member has missing experience,
that unit's rookie-capital feature is missing rather than silently counting
unknown players as veterans. This explicit missingness repair is fixed before
fitting and distinguishes this adapter from a byte-for-byte old v2 replay.

| Feature | Team-level value before home-minus-away subtraction |
| --- | --- |
| `qb_age_centered` | selected QB age minus 27 |
| `qb_age_squared` | square of selected QB age minus 27 |
| `offense_role_weighted_age` | sum(s_i * a_i) / sum(s_i), over offense with known role and age |
| `offense_young_role_share` | sum(s_i * 1[a_i < 26]) / sum(s_i), same known-age denominator |
| `offense_role_weighted_draft_prior` | sum(s_i * d_i) / sum(s_i), over offense with known role |
| `offense_rookie_draft_capital` | sum(d_i for experience=0) / number of selected offense players |
| `defense_role_weighted_age` | defense version of role-weighted age |
| `defense_young_role_share` | defense version of young-role share |
| `defense_role_weighted_draft_prior` | defense version of role-weighted draft prior |
| `defense_rookie_draft_capital` | defense version of rookie capital |

Zero denominators produce missing, never zero or NaN. Rookie capital includes
rookies without prior roles and divides by the entire unit count, not the count
of rookies or expected snaps. If either team's value is missing, its matchup
difference is missing; use fold-fitted missing flags. No eleventh feature is
authorized. Age, draft record and prior usage are crude descriptors: they do not
measure OL protection, blocking talent, defensive assignment quality, player
development, or the point value of injured players.

Under signed training augmentation the finite difference medians are zero and
the missing indicators repeat unchanged for each opposite-target pair. Their
fitted intercept/missing-flag weights should therefore be zero within numerical
tolerance. A missing difference contributes zero on the centered scale, rather
than a freely learned directional missingness penalty. Test this structure and
retain missingness coverage; do not describe missing inputs as learned injury
or talent estimates.

## Source qualification and timing limitations

Use the same 66 historical files, excluding current_roster:2026 from historical
construction, from the corrected inventory backed by the 67-file source lock.
Existing raw weekly rosters already contain the required columns; no extra
historical fetch is required. Other required inputs are the already locked
schedules/recorded starters, player/team statistics and snap shares. Rehash raw
bytes through the prior inventory; inherited source publication-vintage gaps
remain REVIEW REQUIRED. A recorded game's QB and roster are not a verified
T-60 expectation. Outcome availability does not prove pregame identity availability.

A read-only raw-row inventory found 2016 ACT rows with 432 absent birth dates,
773 absent experience values and 18,586/29,399 blank draft numbers. Other
seasons' blank draft rates are roughly 25-31%. Counts include all raw ACT weeks,
not just the final REG cohort and not deduplicated players. Existing September 8
current ACT rows total 1,693, with complete birth dates/experience and 347 blank
draft numbers. These are schema observations, not a completed feature-coverage
qualification or proof of undrafted status.

Before fitting, save by-season/unit and team-game coverage for: raw and resolved
ACT rows, duplicate/collision cases, unmapped positions, known-role player count
and role mass, known-age role mass, missing DOB/experience/draft, missing selected
QB age, and the final ten feature missing rates. Denominators must include all
eligible rows and unmatched identities, not only successful joins. Report both
known-role and known-age denominators; never label a known-subset percentage
as whole-roster coverage. Require all mapped known-role shares finite in [0,1],
all 3,407 rows retained, no unresolved duplicate identities, and each new feature
to have finite observations and nonzero finite variation in every fold's
training data. Missing rows alone do not justify dropping games or searching a
replacement policy. Any failed guard stops for documented review before fitting.

Include 2016 blank-draft coverage by team, rather than only a league aggregate.
Count raw ID-less ACT rows before attempting collapse/resolution; absence of both
GSIS and a PFR fallback is an explicit stop. Current ACT identities must also be
checked independently of historical collision membership: fail if a current
GSIS appears on multiple teams or has multiple smart IDs. Do not silently attach
historical role history to a newly colliding current identity.

For the optional current 32-team research diagnostic, use the verified September
8 roster and expected QB, and reproduce all original corrected base feature
cells at its saved input clock before appending new fields. The old portable
context lacks snap history: export the new walk's collision-aware prior snap
deques in a new, bound candidate context; never modify the old context. Apply
0.5 offseason results retention exactly once and the existing QB capture-clock
decay exactly once. Carry all source/coverage labels and conditional-QB caveats.
No model-scale injury delta, availability probability, score/total change, new
weekly revision or fresh capture is part of this task.

## Required pre-fit checks and independent verification

1. Synthetic hand-calculated fixtures cover all ten terms, unit mapping, zero
   versus missing role, missing age/experience/draft, rookie denominator, missing
   starter, GSIS collision, invalid metadata, and birthday/capture-clock behavior.
2. A small meaningful chronological fixture changes future performance, future
   roster DOB/draft/position/experience, future snaps and current-2026 roster
   metadata. Earlier feature cells and the eligible training prefix must remain
   identical. Mutating one game's observed snaps must affect only later roles,
   not its own or another game in the same kickoff batch. Perturbations must
   actually change the later eligible features, avoiding vacuous assertions.
3. Validate equal-kickoff batching, ACT filtering before duplicate collapse,
   unique game/team-week identities and scoped-hook restoration on exceptions.
   Reject duplicates rather than silently dropping rows. Test the adapter leaves
   every corrected base field unchanged. A validation-only extreme value must
   not change fitted training medians/scales/missing-flag selection.
4. After the single run, independently replay saved fold fits and all 2,127
   original predictions; recompute metrics/intervals from matched predictions.
   Check neutral identical teams give zero and reversed teams/venue/rest negate
   within 1e-8, including individual and combined missing patterns. Check that
   centering current ratings does not create a nominal-home ranking offset.
5. Rehash all old members, source bytes and implementation files before/after;
   save charter/code/source pins, feature coverage, 3,407 feature rows, nine fits,
   2,127 matched predictions, current context/rating diagnostics if generated,
   readable metrics, limitations, start/finish receipts and a manifest written
   last in a new exclusive run directory. Preserve incomplete attempts; do not
   retry a spent fit or overwrite evidence without an explicit correction record
   and parent coordination.

## Metrics and decision rule

Primary metric is pooled margin MAE versus saved `corrected` predictions on all
2,127 games. The corrected reference MAE is 10.099455867555735. Also retain saved
reference4, exposure, symmetric, v0 and constant predictions from the corrected
matched table. Do not substitute each older model's preferred cohort. Report
RMSE, predicted-minus-actual bias, winner accuracy (exclude eight actual ties
with counts; disclose predicted ties), every season, Weeks 1-4 versus later
weeks, neutral games, and all team slices. Team slices are descriptive; no team
slice or current rank can decide adoption.

Use 10,000 paired season-block bootstrap draws, seed 20260908, resampling eight
seasons with replacement and pooling all their games. Positive gain means
mean(abs(control-actual) - abs(candidate-actual)). Primary control is corrected;
v0/constant and other saved-control intervals are secondary. Save exact draw
count, seed, sign convention and 2.5/97.5 percentile endpoints. No probability,
calibration, exact-score or spread-price claim is authorized by margin results.

The fixed further-study screen requires: lower pooled MAE than corrected, lower
MAE in at least five of eight seasons, and a positive lower endpoint of the
95% paired interval versus corrected. If any criterion fails, report screen
FAIL without trying another feature variant or favorable subgroup. Passing is
only permission to propose prospective research; status remains HOLD. The
2018-2025 outcomes were inspected repeatedly in earlier studies: they are reused
diagnostic folds, not fresh confirmation or counterfactual clean test seasons.
The perturbation checks test information flow, not historical source availability.
Future 2026 T-60 revisions and grading would require a separate adoption decision
and comparison against existing corrected/v0/incumbent forecasts on the same
eligible games, preserving every lock and unfavorable result.

## Implementation readiness and expected cost

Minimal work is one research adapter/runner using the existing roster hook,
audited construction scope, symmetric fit and receipt helpers, plus focused
fixtures and an independent saved-artifact verifier. Do not edit pinned model
modules, old runners or the production corrected source verifier. Required
readiness gates are implemented missingness/identity policies, full coverage
receipt, exact corrected-base parity, perturbation tests, and parent plus Fable
review before fitting. Raw schemas are present; no source-fetch blocker is known.

The previous corrected one-walk/nine-fit run took 377.2 seconds on this machine
(15:01:29.854 to 15:07:47.059 UTC). Allow approximately 7-12 minutes for the
larger fixed-block run and several minutes for replay/metrics verification; this
is an estimate, not a benchmark of the unbuilt adapter. Implementation, coverage
inspection and independent review are additional work. There is no grid search
or repeated full-season simulation budget. Stop on correctness/source failures
rather than spending a new candidate to diagnose them.

The fit command requires an explicitly reviewed prepared-manifest digest. Bind
that digest in its start receipt before any fit and reverify the same preparation
at completion. Every reference pin in the table is enforced before/after, along
with the current corrected constructor used by the optional diagnostic. The
three-part further-study screen above is authoritative; early-week metrics are
descriptive, not an additional gate.
