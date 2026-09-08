# September 7 PGO snapshot refresh: modeling charter

Requested by Alex on September 7, 2026: review the published model audit and
Forecast Lab, then take a new snapshot with current team ratings, Week 1 and
full-season forecasts, projected scores, and projected spreads.

## Question and decision

What do independently generated PGO ratings and game projections say before
the 2026 regular season, using inputs actually captured before prediction?
This is a new experimental candidate, not a replacement of the old record or
a claim that a new snapshot proves predictive quality.

- Population: all 32 NFL teams and all 272 scheduled 2026 regular-season games.
- Grain: one team per rating; one unique NFL game per forecast.
- Decision time: actual UTC generation time, after source capture and before
  every included kickoff. Capture time, provider time, generation time, and
  public attestation time remain distinct.
- Horizon: the entire season under today's fixed information. Week 1 is a
  filtered view of the same freeze. Later weekly updates require new dated
  records; none may overwrite this preseason edition.
- Targets: final home score minus away score (margin), their sum (total), and
  each final score, including overtime. Actual ties remain zero-margin games.
- A team rating is a centered model output under declared roster assumptions.
  It is not a separately validated neutral-field price or McCabe's human rating.

## Minimum method and review sequence

1. Recover the July public fit using the exact historical source revision,
   verified 67-file source inventory, and already selected parameters
   (half-life 4 games, Huber ridge alpha 100, delta 1). Do not retune or repeat
   model selection. Require reproduction of all 32 saved ratings before
   using this fit for attribution. Preserve the recovered preprocessor and
   coefficients, and disclose whether exact reproduction succeeded.
2. Capture fresh schedule, 2026 roster, and QB depth source bytes, with URLs,
   SHA-256, byte counts, actual acquisition timestamps, and available provider
   metadata. Verify all 32 teams, unique identities, depth order, and all 272
   games. Independently check the Week 1 schedule against the official NFL
   listing. Capture failures and conflicting identities block the new freeze.
3. Build a separately named starter-aware inference candidate. Expected QB
   depth order must not be inferred from highest historical passing EPA or
   manufactured injury probabilities. Keep existing training and fitted
   weights fixed; this changes inference policy and has not inherited the
   old model's historical validation. Save exact team features, selected
   QB identities, feature contributions, and the old-selector sensitivity.
   Through-2025 performance remains through-2025 performance; a September
   timestamp does not imply new regular-season observations.
   The candidate is an **active-roster preseason scenario**: retain only
   source status ACT; exclude RES, DEV, CUT, RET, and EXE. Require QB1 to
   match an ACT QB by team and GSIS identity. ACT is administrative roster
   status, not evidence of health or game-day availability. No comprehensive
   practice, injury, or game-day inactive adjustment is claimed. Freeze
   today's roster assumption for all weeks. Report excluded-status counts.
4. Compute matchup margins directly from matchup features and the saved fit,
   including venue and rest. Do not infer margins by subtracting displayed,
   rounded team ratings. Build a simple separate total-points baseline from
   completed prior-season team scoring/allowing rates; lock its exact formula
   before producing any new predictions. Combine total and margin into
   expected scores, clearly identifying presentation rounding.
   The total formula is fixed before output inspection:
   `T = (home_2025_PF_per_game + home_2025_PA_per_game +
   away_2025_PF_per_game + away_2025_PA_per_game) / 2`, using all completed
   2025 regular-season games and no postseason or preseason games.
   Expected home points are `(T + M) / 2`, away points `(T - M) / 2`, where
   `M` is the unrounded matchup margin. Scores displayed as whole numbers
   use nearest-integer half-up rounding; model spread and evaluation retain
   unrounded expectations. Reject nonfinite or negative expected scores.
   This is a simple scoring baseline, not a newly validated scoring model.
5. Preserve the original July/August locks, CSVs, attestation, historical
   receipts, and published rating file byte for byte. The fresh edition has
   its own identity and artifact paths. Add it to Forecast Lab with Week 1
   first, full-season access, downloads, and explicit experimental status.

## Evidence, baselines, and evaluation

- Primary metric: margin MAE, lower is better, on the exact same finalized
  games for every compared candidate. Missing outcomes remain ungraded.
- Margin baselines: zero margin; fixed home advantage +2.5 (neutral 0);
  saved PGO v0; original archived forecast, with exact game identity checks.
- Total baseline: prior-season NFL mean total; score baseline: half that
  total per team, with the fixed venue margin. The candidate total method
  must be written before its predictions are inspected.
- Secondary: margin RMSE/bias, total MAE, per-team score MAE, winner accuracy
  with actual ties and predicted ties reported separately. No probabilities,
  confidence percentages, ATS claims, or invented market baselines.
- Historical 2018-2025 results are development evidence already inspected;
  they are not an untouched test for this new inference policy or scoring
  method. Historical source publication-vintage limits remain disclosed.
- Prospective 2026 results arrive after this freeze. A successful capture
  requires complete provenance, finite reproducible output, exact identities,
  and an independent review. This is an engineering qualification only.
- Model acceptance: remain EXPERIMENTAL / HOLD. No automatic promotion from
  a Week 1 record or from refreshing sources. Promotion requires a separately
  reviewed evaluation charter and adequate prospective evidence.
- Cancellations, postponed or revised kickoffs, conflicting results, and
  late source revisions must remain visible and cannot silently change the
  evaluation denominator or rewrite a forecast. Schedule claims describe
  the captured schedule, including any explicit TBD timing.

## Required output and stopping rules

Save a review, source manifest, exact fit artifact, team/QB/features and
contributions, 32-team ratings, 272 game forecasts, a model-method note, and
verification receipt. Never present missing source evidence as current or a
local timestamp as external proof of a pregame publication.

Block a dependent output if its required sources, identity, chronology,
numerics, or reproducibility cannot be established. Preserve the failed
attempt and explain its concrete limitation. Do not tune a team toward McCabe
or consensus. Do not change fantasy projections, McCabe's numbers, Shopify
theme styling, or the old historical/scientific gates during this refresh.

## Weekly cutoff requested during implementation

Alex subsequently requested that weekly predictions lock one hour before
each team's game. The grain is one matchup, so both teams' projected scores,
the spread, and the total share one cutoff: scheduled kickoff minus 60 minutes.
The September preseason artifact stays frozen under its original contract.

Weekly forecasts are a separate append-only series of reviewed revisions.
Each revision records its actual registration time and the verified source
snapshot. A revision must be registered strictly before that game's cutoff;
at the cutoff, the latest eligible saved revision is the locked forecast.
This rule does not depend on a scheduled job starting at an exact minute.
There is no caller-supplied backdating option or later replacement of history.
An earlier game's deadline must not close updates for later games.
Registration is not proof of public availability: predeadline publication
claims require the corresponding external repository/deployment evidence.

Start Week 1 with the verified September projections, labeled with their
actual input date. These are drafts until each game's cutoff. Later revisions
require a separately reviewed source snapshot; this change adds no unattended
roster or injury refresh. Future weeks remain available as preseason forecasts
until a weekly edition is recorded. Missing weekly forecasts remain missing.
The current source verifier accepts the reviewed September edition; a later
in-season inference format needs its own review before this recorder accepts
it. The cutoff recorder does not qualify a new source format by itself.
The UI displays each game's cutoff and distinguishes draft, locked, and
preseason records. Results and accuracy are recorded separately for each series.
Schedule changes cannot silently extend a previously recorded cutoff; hold the
affected game for explicit schedule adjudication while preserving its history.
