# Corrected opening-week experiment

**EXPERIMENTAL / HOLD.** This separately declared version combines the input
audit's construction repairs for a prospective Week 1 draft. It does not promote
one of the seven earlier arms or change an issued forecast. McCabe's human-set
ratings remain the site's lead view.

The fit uses matching ACT history/current eligibility, removes six misleading
roster/coaching transition fields, uses statistic-specific QB exposure, and
enforces symmetric signed matchups. Four-game team history and 365.25-day QB
history remain fixed. Current QB metadata comes from the new roster; results
history receives offseason retention 0.5 exactly once. There is no NE-specific
adjustment, additional feature search, or new season simulation.

## What the replay establishes

All 2,127 games from 2018–2025 remain in the comparison. Each fold trains on
earlier seasons. These seasons have already been examined, and historical
starter identities and source publication vintages remain limitations.

| Construction | Margin MAE |
|---|---:|
| Corrected combination | 10.099456 |
| Previous recency reference | 10.119775 |
| Previous clean exposure arm | 10.111682 |
| Previous clean symmetric arm | 10.098199 |
| Saved v0 control | 10.266150 |
| Saved constant control | 11.057958 |

The corrected combination improves over the recency reference by 0.020319
points, with a paired season-block interval [-0.030609, +0.074064]. Relative to
the previous symmetric arm it is 0.001257 points worse, with an improvement
interval [-0.004082, +0.001545]. These do not establish added predictive accuracy.
No parameter or construction was changed after seeing this result.

[Independent saved-arithmetic verification](verification.json) reproduced all
2,127 predictions, 2,558 metric/bootstrap values, nine signed-symmetry fits and
67 source identities. The maximum prediction difference was 4.44e-16; the maximum
signed reversal residual was 3.47e-18. The fresh input constructor was separately
checked against 704 independently calculated feature values for all 32 teams.
The portable historical state is tied to the pinned ACT/exposure walk; the
verification does not claim a second independent historical reconstruction.

[Independent verification of the actual new source package](source-verification.json)
also reproduced all 32 ratings, 1,440 contribution terms, 16 margins/totals,
32 scores and 96 exact baseline joins. All 1,024 neutral team pairs passed
26 missingness patterns. The source manifest is
`85fe35069145505410567709261663be0939b3ae2fbe05ad147da1d17fc54d83`.

The resulting opening-week output still places NE first (+5.200), LAR second
(+4.507), SEA third (+4.017), BUF fourth (+3.607) and JAX fifth (+3.354). These
are conditional model units, not established neutral-field prices. NE's largest
upward fitted terms are results history (+1.752), QB passing EPA (+1.493) and
team passing EPA (+0.686); they overlap and do not independently confirm its
exact ordering. The results accumulator reacts to beating the model's own
expected margin, without reading public expectations.

All 16 games were appended as revision `20260908T152319158416Z.json`, generated
from the separately verified source. The September 7 revision is unchanged.
The new opener draft favors SEA by 0.440, versus 1.192 in September 7 and 3.865
for the preserved v0 benchmark. Integer score displays are rounded; evaluation
uses the unrounded margin, total and team scores.

The run manifest is
`7530b3199f8a17ffec34f9e5351919ea67cb45df66e16befd655ab4e746f7a4c`.
See [all predictions and fits](run-20260908/manifest.json),
[the pre-fit charter](charter.md), and
[the per-game source refresh clarification](source-refresh-clarification.md).

## Current sources and limits

The fresh capture retrieved September 8 at approximately 15:01 UTC resolves all
32 expected QBs on ACT rosters. The depth snapshot is September 8 at 11:56:57 UTC;
none of the selected QBs differs from September 7. All 16 Week 1 schedule
identities, kickoff times and rest inputs match the previously registered games.

There are dated Monday practice reports for NE and SEA, containing 11 player
observations. The other 30 teams have no formal report in this captured set and
remain unknown. Ben Brown is the one confirmed OUT observation. These reports
are not complete final game-day availability. The source qualification reconciles
report position labels such as C and broad roster labels such as OL using GSIS
identity, team and player name; the first strict-position failure is preserved.

**Non-QB injuries are not priced in these drafts.** ACT is an eligibility rule,
not a valuation of absent talent. All three availability/lineup adjustment
features are explicitly unadjusted; expected-QB selection is separate. Missing
reports do not imply health, and practice labels are not converted into
calibrated availability probabilities. An unavailable listed QB prevents issuing
its affected matchup until a supported replacement is selected.

Scores retain the prior-season points-for/points-allowed total heuristic, whose
separate historical test did not convincingly beat a league-average total.
No calibrated probabilities, validated exact-score claims or new fixed-strength
272-game season forecast are attached to this version.

## Before each game's cutoff

Review the latest official reports, roster and expected starters. Capture a new
source package and qualification without overwriting existing files. Add its
reviewed capture/qualification hash pair to the verifier while retaining every
old pair. Build a new output directory, verify it, then use the existing weekly
recorder to append eligible game revisions. A source package reports skipped
games; the recorder independently rejects an expired cutoff. This workflow
requires source review and is not an automated injury refresh.

NE at SEA locks September 9 at **23:20 UTC / 7:20 PM Eastern**. Later games retain
their own T-60 deadlines. Wednesday's lock cannot freeze the entire week.
Keep every old draft and grade the last eligible revision on the same games
against v0 and the September 7 incumbent, including every loss and large miss.

## Reproduction

`python -m unittest tests.test_pgo_week1_corrected tests.test_pgo_forecast_corrected tests.test_pgo_forecast_weekly`

`python -m research.pgo_week1_corrected.verify --output output/corrected-verification-new.json`

The verification output must be new, and the locked historical source cache must
be present. Do not overwrite or re-fit the published run. The corrected source
package has a separate verifier:

`python pgo_forecast_corrected.py --verify docs/evidence/forecast-lab-2026/september-08-corrected`

## Renderer portability correction

The first publication workflow passed 553 tests (one optional skip), then its
Linux renderer rejected CSV text regenerated from numerical replay because of
floating-point last-digit differences. The verifier now checks exact CSV bytes
against the saved JSON values after the existing independent numerical replay
check at the unchanged 1e-9 tolerance. A regression covers tolerated replay
roundoff and rejects a separately re-manifested CSV mutation. Saved sources,
fits, forecasts, weekly revisions and their manifests are unchanged.
