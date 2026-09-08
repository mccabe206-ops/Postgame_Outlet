# PGO input and valuation audit

**The concern about New England exposed substantive modeling issues.** Its
saved first-place rank is reproducible, but it is not a sufficiently supported
claim that NE is the strongest NFL team. We found different historical/current
roster eligibility, misleading continuity measures, QB reliability weights
that do not always match the statistic being measured, and a neutral-field
offset inconsistent with the strength-price interpretation. Status: **EXPERIMENTAL /
HOLD**. Issued ratings and forecasts remain preserved.

The reader-facing explanation is: **The September model puts New England first
because it gives substantial weight to recent results and passing performance.
Its lead over the Rams is only 0.287 model units. Those signals overlap, and the
audit found questionable roster and preseason valuations, so we cannot defend
that exact ordering as established team strength.** We will judge repairs by
league-wide forecasting evidence, not whether they produce a more familiar top
five. McCabe's human-set neutral-field prices remain a separate view.

## What the inputs really measure

| Input family | Actual construction | What it cannot establish |
|---|---|---|
| Results history | A margin-updated team rating, with capped game residuals and 0.5 retention at historical season boundaries | Independent roster talent or a probability of winning the Super Bowl |
| Team efficiency | Ten passing/rushing EPA, explosive-play, sack and turnover rates; the issued fit uses a four-game half-life | Fully isolated player ability, comprehensive opponent adjustment, or a balanced multiyear preseason prior |
| QB efficiency | Historical passing/rushing EPA and CPOE, sack avoidance and ball security, shrunk toward a player-population average | Causal QB value separated from teammates, opponents and usage |
| QB metadata | Log passing volume, log experience, inverse square-root draft position | A validated aging curve or a reason that draft status should retain a permanent price |
| Roster composition | Prior snap weights among currently listed players, compared with each player's last recorded team; rookie draft metadata | The fraction of last season's team snaps retained or the value of replacement players |
| Coaching | Whether the coach matches the last processed game's coach, plus log games coached | A coaching-quality grade or a season-long measure of system change |
| Availability | Expected missing historical snap shares and a QB lineup difference under inherited availability probabilities | Complete current injury coverage, medically calibrated return probabilities, or player-specific replacement value |
| New skill quality | Four prior-season receiving/rushing EPA proxies, weighted by prior snap role | Offensive-line or defensive player grades, current rookie development, or fully adjusted individual talent |
| Game context | Neutral/home venue and capped rest-day difference | Weather, travel, all matchup interactions or market information |

The weekly EPA source defines passing EPA over pass attempts and sacks, with a
special treatment of receiver fumbles. CPOE is a completion-percentage measure.
These are performance statistics, not scouting grades. See the provider's
[player-stat dictionary](https://nflreadr.nflverse.com/articles/dictionary_player_stats.html).

## Findings that change our confidence

**Neutral-field margins do not consistently follow the ratings.** With equal
rest, the issued fit predicts NE to lose by 0.801 points against an identical
NE team. It predicts NE versus LAR at -0.514, but reversing the teams gives
-1.088 instead of +0.514. The fitted regression leaves a common -0.801 neutral
offset, while subtraction of individual ratings cancels it. This faithfully
reproduces the code; it is a model-specification and interpretation problem,
not a rounding error. **That common offset changes no team rank and is not a
cause of NE being first.** There is no validated nominal-home neutral effect that
justifies the offset. A separately declared symmetric training arm tests a
zero-for-identical-teams, opposite-for-reversed-teams construction as a structural
modeling constraint; this consistency rule is not itself predictive validation.
See the [independent neutral-field audit](neutral-field-audit.md).

**Historical and current rosters differ.** The historical reader accepts all
weekly roster statuses, while the September constructor admits only ACT. For
example, NE's 2025 Week 1 historical roster contains 102 listed players, only
48 ACT. Non-ACT players can affect selection, availability, continuity and skill
weights. That mismatch prevents treating the previous historical screen as
validation of the active-only current construction. Filtering to ACT is still
historical reconstruction: a final weekly status is not proof of its publication
time before a game's T-60 cutoff. The provider describes these as
[week-level rosters](https://nflreadr.nflverse.com/reference/load_rosters_weekly.html).

Active-only history also changes which players receive snap-history and
last-team updates. An excluded non-ACT week no longer appends a zero-snap
observation, so prior role memory can persist through that absence. The active
arm tests the full matched historical construction, not just a one-time filter
on today's roster; its result cannot be attributed to eligibility alone.

**Continuity is largely a short transition flag.** Once a new player appears in
a processed game roster, the code updates that player's last team. The next
game can call them returning even though the offseason change remains relevant.
Across 2014-2025, average returning-offense share is about 0.800 in Week 1 and
0.997 in later weeks. The September mean is 0.825. NE's 0.664 is unusual relative
to all-season rows but within historical preseason experience. Coaching
continuity has a similar first-game concentration. Applying coefficients learned
mostly from in-season states can make these preseason differences influential.

**The exact NE/LAR ordering depends on those valuations.** In the prior full
research candidate, returning-offense share alone gives NE a +1.477 relative
contribution over LAR, while its overall lead is only +0.269. This is a
conditional arithmetic comparison, not a refitted removal test. The previously
completed whole-group removal test improved MAE; that justified a new, separately
declared simplification test. Stable negative coefficients do not establish
that roster turnover improves football teams.

**Several apparent confirmations overlap.** Historical matchup team-passing
and QB-passing inputs correlate at 0.796; results history and team passing at
0.695. They are not duplicate columns, but they reflect related games. QB sack
avoidance has a negative coefficient in every prior full-candidate evaluation
fold. That model gives NE a positive contribution for lower sack avoidance;
describing it as a good pass-protection grade would reverse its actual meaning.

**Rushing reliability uses the wrong exposure concept.** The inherited QB
shrinker uses passing dropbacks even for rushing EPA per carry. A large passing
sample does not supply rushing observations. The new fixed exposure arm tests
per-statistic denominators, with an explicitly uncalibrated 50-carry prior.

**NE does not show a consistent historical overrating pattern.** The prior full
candidate overpredicted NE margins by 5.07 points on average in 2023 and
underpredicted them by 8.70 in 2025. This rejects a simple permanent NE bonus
story; it does not validate a 2026 first-place rank. All seasons, home/away
slices and largest misses are in the [independent outlier audit](outlier-audit.md)
and [diagnostic data](diagnostics.json). Applying all eight saved fold models
reproduced all 2,127 saved predictions exactly, without fitting.

## Fixed follow-up experiments

The [charter](charter.md), [pre-fit exposure addendum](charter-v2-addendum.md), and
[pre-fit symmetry amendment](charter-v3-symmetry.md) declare seven arms: the existing recency reference; active-only rosters; active-only
without roster/coaching transitions; that clean construction with an eight-game
team window; a compact QB feature set; metric-specific QB exposure weights; and
a symmetric neutral-field fit using the clean four-game inputs.
Every arm retains all games and reports missing starters. No current rank is a
selection criterion. Historical source vintage and actual-starter reconstruction
remain limitations even if accuracy improves.

The [first eligibility attempt](run-20260908-eligibility/) stopped before any
fitting because the runner retained unused full historical contexts across
arms. Its start receipt, interrupted code and correction receipts are preserved.
The [second attempt](run-20260908-eligibility-attempt02/) releases each unused
context after retaining the required feature rows. Independent review confirmed
that the memory correction changes no inputs, model mathematics or declared
comparison. It is a retry of the same experiment, not another candidate search.

## Completed results: NE stays high, but no candidate clears the screen

All seven arms evaluated the same **2,127 games in 2018-2025**. These are rolling
next-game margin errors; lower MAE is better. Current ranks use each arm's own
historical construction and the frozen September identities. They are separate
from the issued September ratings and are not calibrated point prices.

| Construction | Margin MAE | NE rank | JAX rank |
|---|---:|---:|---:|
| Recency reference, historical all-status rosters | 10.1198 | 1 | 5 |
| Active-only historical rosters | 10.1362 | 4 | 7 |
| Active-only, remove roster/coaching transitions | 10.1107 | 1 | 5 |
| Same clean inputs, eight-game team half-life | 10.1107 | 2 | 5 |
| Clean four-game inputs, compact QB predictors | 10.1577 | 1 | 5 |
| Clean four-game inputs, metric-specific QB exposure | 10.1117 | 1 | 5 |
| Clean four-game inputs, symmetric fit | 10.0982 | 1 | 5 |

**None of the six new candidates passes the declared screen.** Every improvement
interval against the reference includes zero, and candidates improve only three
or four of eight seasons rather than the required five. The symmetric arm has
the lowest observed MAE: a **0.0216-point** improvement, with a paired season-block
interval **[-0.0299, +0.0762]** and four season wins. Its correction of the
neutral-field invariant is independently verified, but that does not establish
superior predictive performance. All candidates remain **EXPERIMENTAL / HOLD**.

**The new evidence rules out an overly simple NE explanation.** Removing the
questionable transition fields does not remove NE from first place: the clean
four-game model has NE at +5.210 versus LAR +4.588. The symmetric version also
keeps NE first. The eight-game version puts LAR first and NE second, but its
MAE differs from clean four-game by just 0.0000063 points. The active-only arm
that places NE fourth actually worsens overall MAE. We should not choose either
construction because its ranking looks more comfortable.

Across the seven specified constructions NE is first five times and ranges
from first to fourth; JAX ranges from fifth to seventh. This is sensitivity to
these particular modeling choices, not a rank-confidence interval or seven
independent votes. NE's high output persists beyond the old roster bonus, while
the exact ordering and its meaning as future football strength remain unproven.
The compact QB arm also leaves NE first and worsens MAE; counterintuitive QB
coefficients alone are not a sufficient explanation for its position.

In the symmetric research fit, NE's largest positive contributions relative to
the league average include results history **+1.752**, QB passing EPA **+1.498**,
team passing EPA **+0.684**, and explosive-play prevention **+0.505**. However,
results history actually favors LAR by **0.339** in their direct comparison.
The exact NE-over-LAR ordering includes opposing sack-related differences:
team sack avoidance **-1.243** and QB sack avoidance **+1.170**, plus explosive-play
prevention **+0.976**. These are conditional fitted contributions, not independent
pass-protection or defensive grades. The remaining counterintuitive valuations
are reasons to investigate generalization, not a license to delete whichever
term changes NE's rank. The saved all-team terms make those concerns inspectable.

Active-only construction matches 6,715 of 6,814 historical team-game starter
identities; 99 are unavailable in the eligible roster, including 14 in the
evaluation seasons. They remain explicitly missing. No game was dropped or
backfilled with an excluded player. The reference matches all 6,814. This
coverage change is reported alongside the metrics, not concealed by changing
the evaluation cohort.

The [independent verifier](verify_run.py) reproduced **4,710 metric/bootstrap
values**, all **224 current ratings and contribution tables**, every reference
fit and the source hashes. It tested every symmetric fold and final fit across
all 32-by-32 team pairs and missing-input patterns; the largest reversal residual
was 6.87e-18, below the declared 1e-8 tolerance. See the
[verification receipt](verification.json), [all metrics and failed screens](run-20260908-eligibility-attempt02/metrics.json),
[all current rankings](run-20260908-eligibility-attempt02/ratings.csv), and
[saved contributions](run-20260908-eligibility-attempt02/rating-details.json).
Run manifest SHA-256:
`440734823c333f3f47229ba3edc2e43d50d84be62aa318c4c59395744d15899c`.

## Game totals need their own evidence

The existing projected total averages the two teams' prior-season points-for
and points-allowed rates. We applied that same rule to all 2,127 games from
2018-2025 using only each game's preceding season. It has total MAE **11.0417**
versus **11.0800** for the prior-season league-mean total. Improvement is only
**0.0383 points**, with a paired season-block interval **[-0.0609, +0.1246]**.
That is not convincing evidence of useful improvement over the simple baseline.

[Corrected results](totals-20260908-corrected/metrics.json) and
[all predictions](totals-20260908-corrected/predictions.csv) were independently
recomputed from the locked raw schedule: all predictions, all 12 metric views,
and all 10,000 bootstrap draws match. Future-outcome perturbations leave earlier
predictions unchanged, and duplicate games are rejected. See the
[verification receipt](totals-independent-verification.json).

The initial [totals attempt](totals-20260908/) is retained for provenance. Its
forecasts and error metrics were correct, but the bootstrap arguments were
reversed and used the helper's default seed. The corrected run uses
control-minus-candidate improvement and the charter's 20260908 seed; a direct
MAE-difference assertion now checks the direction. The initial interval is
superseded, not additional evidence.

A total-only check does not validate exact scores, margins, playoff odds or
the fixed 272-game season forecast. Rolling next-game validation and a forecast
frozen before the season are different use cases; even historical weeks 2-4
already consume current-season games in the rolling evaluation.

## Freezing strength for an entire season performs worse

We also replayed the saved recency model with all 32 team states frozen before
the first kickoff of each evaluation season. No current-season game had entered
the state. Each team's recorded Week 1 QB and full-strength roster stayed fixed
for all later games; these are retrospective identity assumptions, not verified
pregame knowledge. Each saved fit trained only on earlier seasons. Venue/rest
controls were kept consistent with the rolling comparison.

| Forecast policy | Margin MAE |
|---|---:|
| Recency model updated before each game | 10.1198 |
| Same model with preseason strength frozen all season | 10.9191 |
| Simple v0 rating frozen before each season | 10.7404 |

The frozen recency policy loses to the updating policy in all eight seasons and
to frozen v0 in five. Its late-season MAE is 11.1497 versus 10.1705 for updating.
This does not prove which new input arm will forecast 2026 best; it does show why
the old next-game result cannot endorse a fixed-season forecast. **We have no
positive evidence that the issued fixed-strength forecast beats frozen v0 in
that use case; the tested recency replay loses.** This replay is not an exact
historical backtest of every issued inference convention. See the
[corrected season diagnostic](preseason-20260908-corrected/report.md), all
[season and early/late metrics](preseason-20260908-corrected/metrics.json), and
[individual predictions](preseason-20260908-corrected/predictions.csv).

An [independent reconstruction](preseason-independent-verification.json)
reproduced all 2,127 fixed-strength predictions, all original v0 predictions and
256 frozen v0 states, and all 192 reported metric values. Of the 256 retrospective
team-season identities, 240 come from Week 1 games later than the common freeze
boundary, by as much as 98 hours. This is therefore a conditional diagnostic
with future-known identities, not a certified as-of preseason replay.

The first season diagnostic used the embedded challenger's shorter history for
the frozen v0 control. The corrected control uses the original v0 history and
exactly matches its rolling Week 1 predictions. Frozen recency predictions are
unchanged. The original directory and original script remain preserved; the
corrected run is the comparator to cite.

Independent review also caught a wording error in that run's report/receipt:
the original v0 accumulator warms up from **1999**, using the parser's default.
The year 2002 is the baseline parameter-selection/evaluation start, not its
history start. The corrected code uses the matching 1999 warm-up and its
predictions are unchanged; the manifested report's "from2002" wording is
superseded by this clarification.

## Independent review and remaining limits

The [construction audit](forecast-audit.md) and [outlier audit](outlier-audit.md)
were performed independently before follow-up fitting. Fable initially returned
HTTP 429 with no review; that [quota receipt](fable-review-status.json) is
preserved. A later request through the installed persona and actual `fable`
alias returned a review from **claude-fable-5-1**, with no blocking adapter,
symmetry or evaluation defect found. The [verbatim review](fable-review.md) and
[service receipt](fable-review-receipt.json) distinguish that review from the
separate independent arithmetic verification.

Fable observed attempt02 while it still had only its start receipt. Its comments
about pending results describe that observation, not the now-completed run.
We accepted its clarifications that the neutral offset cannot change ranks,
active-only construction also changes role-history updates, and the fixed-season
product lacks positive evidence against its simple control. The board's wording
now describes model output rather than neutral-field point strength. Fable did
not review the final seven-arm results: those were independently recomputed
afterward. In particular, the completed clean models show that removing roster
transitions does not by itself remove NE from first place.

Two low-level review notes do not change results: active4's immediate control is
the reference itself, so its two named bootstrap comparisons share one saved
key; exact reference-fit equality is intentionally strict for this same-stack
reproduction, and a different numerical stack must not silently replace it.
Fable's approximate neutral-offset standard error and broad rolling-model
significance statement were not independently established for a matching
comparison here and are not used as audit conclusions. No additional arm,
parameter search or evidence rewrite followed the review.

Historical injury rows in 2025 lack verified modification timestamps. Earlier
timestamped rows showed no selected update inside the final 60 minutes, but
that does not establish the missing 2025 vintage. Provider
[availability documentation](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html)
also identifies an injury-source discontinuity after 2024. Current official
injury observations remain separate, dated scenarios. No report means unknown,
not healthy. OL/defensive player quality, reliable rookie role estimates,
calibrated rank uncertainty, and prospective performance remain missing.

The site now identifies each edition, puts an explanation and a material concern
before technical contributions, and explains the review/save/T-60-lock/results
process. Publication of this audit does not promote a research candidate or
rewrite any issued forecast.

## Checks and reproduction

The full repository suite passed **530 tests**. After the final explanation
changes, **87 focused comparison, Lab and input-audit tests** passed. Browser
checks covered 375px and 1280px layouts, NE/JAX links, glossary/process
disclosures and the archived-board drawer. The saved September snapshot still
verifies as 32 teams and 272 games; its issued values are unchanged.

From the repository root, with the locked source cache available:

```sh
python -m unittest tests.test_pgo_input_audit
python research/pgo_input_audit/verify_run.py --output output/pgo-input-audit-verification.json
```

The verification output must not already exist. A deliberately fresh replay can
use `python -m research.pgo_input_audit.audit_model --output research/pgo_input_audit/run-local-review`.
That output directory must also be new. The evaluator verifies charter, source
and code identities and preserves the published attempt02; do not overwrite a
saved run or interpret a start receipt as completion.
