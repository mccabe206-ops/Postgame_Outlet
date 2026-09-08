# Opening-week corrected construction — September 8, 2026

Status: EXPERIMENTAL / HOLD. Written before this construction is fitted or new
operational sources are captured. This is a separate experiment; it does not
extend, replace, or reopen the completed seven-arm input audit.

## Question and decision

Can PGO produce internally consistent, reproducible next-game margin drafts
using the audited input repairs and information captured before each game's
kickoff minus 60 minutes? One row is one NFL regular-season game; the target is
final home-minus-away points including overtime. Ties remain in margin metrics
and are excluded, with counts, from binary winner accuracy.

The opening game is NE at SEA, September 9 at 20:20 America/New_York. Its cutoff
is September 9 at 23:20 UTC. Capture and issuance must precede each game's own
cutoff. Registration remains append-only; previously issued forecasts remain
available. A corrected experimental draft is not a validated-model promotion.

## One fixed construction

- Reuse the locked 2013–2025 historical feature sources and recorded-starter
  reconstruction. Accept ACT roster rows before duplicate collapse, both in
  history and current inputs. Preserve all games and explicit missing starters.
- Remove returning offense/defense share, incoming prior share, rookie draft
  capital, coach continuity and coach tenure, including their missing flags.
- Keep four-game team-efficiency half-life and 365.25-day QB history decay.
- Use the declared metric-specific QB shrinker: 200 observations for passing
  EPA, aggregate CPOE, sacks and ball security; 50 effective carries for rushing.
  The 50-carry prior is fixed and uncalibrated; aggregate CPOE exposure remains
  an approximation. Keep other QB predictors; add no new player-quality terms.
- Apply results-rating offseason retention 0.5 exactly once from 2025 to 2026.
- Mirror training rows only: reverse every finite feature and margin, including
  venue and rest; preserve missing values. Fit existing Huber ridge, delta 1,
  alpha 200 on doubled training rows. Evaluate original games once.
- Require identical neutral teams to predict zero and reversed team/venue/rest
  perspectives to negate predictions, including missing patterns, within 1e-8.

No parameter search, additional arm, rank target, NE-specific adjustment or
skill-quality expansion is authorized by this charter. Code corrections before
fitting are recorded; interrupted runs are retained and never overwritten.

## Current input contract

Capture a fresh 2026 Week 1 roster, depth chart and schedule with URL, retrieval
time, raw bytes, SHA-256 and period checks. Require 32 teams, unique resolved
expected QB identities on ACT rosters, and 16 unique Week 1 games. Reject
identity/rest/kickoff conflicts with already registered games instead of silently
rewriting their cutoff. Official team/NFL reports establish dated injury
observations; missing reports mean unknown, never healthy. A source's retrieval
time establishes when this run obtained it, not its original publication time.

The base construction uses the selected expected QB and explicitly unadjusted
non-QB availability features. ACT eligibility is not a complete injury model.
Publish source coverage and every unresolved/confirmed material absence beside
these conditional drafts. Do not convert questionable/doubtful/practice labels
into claimed calibrated probabilities. Do not apply the older model's injury
deltas to this fit. An unavailable expected QB blocks that team's base draft
until a supported replacement identity is recorded. Numerical injury scenarios
require a separately documented, reviewed input policy; they are not part of
this fit. Final reports still pending today require a later pre-cutoff refresh.

Use the existing prior-season PF/PA total only as a visibly labeled score
heuristic, retain its league-mean baseline and unrounded total/margin, and derive
display scores consistently. Do not claim validated exact-score forecasts,
calibrated probabilities, betting edges, or injury-adjusted current strength.

## Evaluation and acceptance

Replay the same 2,127 games in 2018–2025 using expanding earlier-season training
folds and no current roster information in history. These seasons have already
been inspected: all results are diagnostic, not fresh held-out confirmation.
Compare the saved recency reference, exposure arm, symmetric arm, original v0
and constant baseline on the identical game cohort. Primary metric is margin
MAE (lower); also report RMSE, signed bias, winner accuracy, each season,
Weeks 1–4 and later weeks, team slices, and paired season-block intervals with
10,000 draws and seed 20260908. Save all predictions, fits and source/code hashes.
No historical result promotes this combined version or selects its parameters.

Operational acceptance requires source/identity checks, unchanged old evidence,
finite arithmetic, exact saved-fit replay, symmetry, reproducible contributions,
and independent review. Failures stop issuance of affected drafts. Historical
starter oracles, source vintage gaps and uncalibrated availability remain
REVIEW REQUIRED. Scientific status stays HOLD even if every operational check
passes. Prospective 2026 game-level errors against v0 and the September incumbent
will supply new evidence; never delete unfavorable outcomes or revise a locked
forecast. Preserve all model-version comparisons.

## Scope and implementation

Produce one separately manifested research run and one fresh opening-week source
package. Reuse the audited construction and fitting functions. Add a dedicated
corrected-edition verifier; do not relax September's pinned verifier. Extend the
existing weekly recorder to recognize that exact edition and keep its T-60 and
append-only rules. Show the corrected edition and coverage in the Lab, retaining
the September archive, McCabe's separate ratings and incumbent/v0 comparisons.

Do not issue another fixed-strength 272-game season forecast: its distinct use
case lacks positive evidence. Preserve the old season forecast as an archive.
No awards model, probabilities, simulations, new service or dependency is needed.
