# PGO model update: playoffs and defensive depth

September 9, 2026. All model versions remain **EXPERIMENTAL / HOLD**. Earlier
saved forecasts and their grades are preserved.

## Why we tested this

Seattle beat New England 29-13 in the neutral-site Super Bowl on February 8,
2026. The September 8 PGO model used regular-season history, so it did not
include that game or any other playoff game in team results, team performance,
quarterback history or scoring averages. The result was present in the source;
the historical filter excluded it. [Official Seahawks recap](https://www.seahawks.com/news/2025-the-seahawks-are-super-bowl-lx-champions).

We tested playoff history and defensive roster information separately across
the league. Neither test sets a desired New England rank, applies a special
rematch penalty or imports McCabe's player grades.

## What including the playoffs changes

The new postseason edition includes 155 playoff games in its 2013-2025
history. Before changing that membership, we reproduced all 3,407 original
regular-season input rows exactly. It still trains and evaluates on regular-
season games; playoff results update the history used for later predictions.

For the September 9 candidate, New England moves from #1 to **#6**, and Seattle
from #3 to **#2**. The neutral-field estimate changes from New England by 1.2
to **Seattle by 1.7**. Adding the fitted home advantage gives **Seattle by 3.3**,
with model-average scores of New England 20.97 and Seattle 24.27, displayed as
**New England 21, Seattle 24**. These are a separate saved edition, not edits to
the September 8 record.

New England's recent passing-efficiency input falls sharply when its playoff
games enter the history. Seattle's recent team passing and results-history
inputs improve. New England's earlier playoff wins still count: the model does
not simply subtract the Super Bowl's 16-point margin. Each team receives the
same history policy, and the whole model is refitted.

Scoring averages also now include the playoffs. New England's scoring average
falls from 28.82 to 26.52 points per game over 21 games; Seattle's rises from
28.41 to 29.20 over 20 games. The combined-points estimate becomes 45.24 rather
than 46.62. This remains a simple scoring-history estimate, not a separately
validated exact-score model.

**The postseason candidate did not pass the historical acceptance rule.** Its
average margin error is 10.102 points versus 10.099 for the baseline, improving
in four of eight seasons. The paired error-reduction interval is -0.0196 to
+0.0145 points. The difference is very small and does not establish an accuracy
gain. Week 1 error is 9.899 versus 9.891. The candidate is published for open
comparison and separate prospective grading. The September 9 edition is now
the primary public display, titled **PGO Power Rankings — Experimental**, because
it includes both regular-season and playoff history. This display choice does
not establish an accuracy improvement or change its EXPERIMENTAL / HOLD status.
The September 8 board remains available under **Compare previous models**, with
its original forecasts and grades preserved. Non-QB injuries are shown as dated
context and are not included in either edition's saved forecast numbers.
The primary board's team links explain each September 9 rating using that
edition's saved contributions, including both upward and downward factors.
Its matchup list and grades use the September 9 records already issued before
their cutoff; selecting the display does not recalculate a locked prediction.
[Saved candidate forecasts](evidence/forecast-lab-2026/september-09-postseason/forecasts.csv),
[complete inputs and outputs](evidence/forecast-lab-2026/september-09-postseason/snapshot.json),
[historical test](../research/pgo_postseason_candidate/run-20260909-attempt01/metrics.json).

The historical replay deliberately retains the original baseline's recorded-
starter and role-history limitations so that this test isolates playoff history.
Its historical data was obtained after those games; exact historical source
publication timing remains unresolved. Prospective comparisons are needed.

## Defensive production and experience

The fixed test added four inputs: prior QB-hit activity, prior pass-defense
activity, the number and distribution of experienced defensive contributors,
and the share of current active defenders with recorded prior defensive snaps.
These are historical production and experience measures. They do not establish
the talent of a rookie, the quality of a replacement or the coach's intended
depth order.

The comparison used the same 2,127 regular-season games from 2018-2025, training
each season's model only on earlier seasons. All previously saved baseline
input cells were preserved. These years have already been studied, so this is
a diagnostic comparison rather than fresh proof of future accuracy.

| Measure | September 8 construction | Added defensive inputs |
|---|---:|---:|
| Average margin error, all games | 10.099 points | 10.084 points |
| Average margin error, Week 1 | 9.891 points | 9.985 points |
| Average margin error, Weeks 1-4 | 9.786 points | 9.817 points |
| Seasons with lower error than the baseline | — | 4 of 8 |

**The defensive candidate did not pass the acceptance rule.** Its average
improvement was about 0.015 points, with a season-based comparison interval
from -0.034 to +0.064 points. That interval includes no improvement, and the
early-season results were worse. It is not adopted into the main forecast.

On the same fresh current inputs, refitting with these fields moved New
England from #1 to #2. That is a result of the complete fitted model, not a
standalone injury penalty. A more agreeable rank is not evidence of greater
forecast accuracy. [Fixed test and saved results](../research/pgo_defensive_depth_candidate/run-20260909-attempt01/metrics.json).

## What the current depth information shows

The captured provider roster and depth listings cover all 32 teams. New England
has 24 active-roster defenders in that capture: 18 have observed prior-season
defensive snaps and six have no matched prior-season defensive snap history.
Of its 12 defenders listed below first in provider depth slots, six have prior
defensive snaps and six do not. No history means unknown, not poor ability.

Provider depth labels can differ from the Patriots' club-hosted unofficial
chart. They are not verified coaching assignments. A generic linebacker label
does not necessarily mean edge rusher, and a team can have more than 11 players
listed first across different formation slots. The public table preserves
these labels and includes player-level evidence.

Harold Landry III's reserve/PUP status and Khalil Jacobs's injured-reserve
status are material roster context. Being absent from the weekly game-status
list does not erase a reserve-list absence. [Patriots roster](https://www.patriots.com/team/players-roster/),
[club-hosted unofficial depth chart](https://www.patriots.com/team/depth-chart).

The current defensive production test matches 97.0% of selected prior snap
exposure to observed statistic rows; New England's matched share is 97.6%.
Unmatched snaps stay visible and are excluded from each statistic's denominator.
The rates describe that matched subset, not every defensive snap or every
pass-rush opportunity. Identity coverage is weaker in 2013-2015. Missing
historical publication timestamps and recorded-starter timing remain limits.

**Roster update checked at 6:48 PM Eastern, September 9:** Seattle's official
announcement says AJ Finley joined the 53-man roster, Rodney Thomas II and
Velus Jones Jr. were elevated from the practice squad, and Bryce Cabeldue was
waived. The provider roster retrieved at 5:16 PM still labels the first three
DEV (practice squad) and Cabeldue ACT. Temporary elevations do not necessarily
change the provider's permanent roster label, but the captured list does not
fully describe tonight's available personnel. These announcements are shown
as context; saved forecasts and model inputs are unchanged.
[Official Seattle roster moves](https://www.seahawks.com/news/seahawks-make-roster-moves-ahead-of-season-opener-vs-patriots),
[dated source check and captured pages](../research/pgo_defensive_depth_candidate/source-review-20260909/review.md).

## Injury reports and grades

**Patriots clarification verified at 7:15 PM Eastern:** Behren Morton is
inactive as the emergency quarterback. The club's analysis identifies Ben
Brown (knee), Karon Prunty, Erick Hunter, Morton, TreVeyon Henderson (ankle),
Walter Rouse and Efton Chism III as its seven inactives. Both the current club
roster and official stories spell the linebacker Erick Hunter. Our earlier
check used the plain inactive list, which omitted Morton's emergency-QB detail;
the separate analysis now supplies that qualification. This updates reader
annotations only; earlier source captures and all forecast inputs are preserved.
[Official Patriots analysis](https://www.patriots.com/news/inactives-analysis-patriots-elevate-rb-lan-larison-from-practice-squad-with-treveyon-henderson-inactive-for-season-opener-vs-seahawks),
[dated clarification and captures](../research/pgo_defensive_depth_candidate/source-review-20260909/patriots-correction-20260909T231518Z/review.md).

**Final inactives verified at 6:52 PM Eastern:** Seattle's Nick Emmanwori and
Tory Horton, previously questionable, are inactive. Seattle also lists Ty
Okada, Nick Kallerup, Beau Stephens, Mike Morris and Jalen Milroe (emergency
third quarterback). New England lists Karon Prunty, TreVeyon Henderson, Erick
Hunter, Walter Rouse, Ben Brown, Efton Chism and Behren Morton inactive. Hunter's
absence is additional gameday depth context despite his ACT roster label.
An inactive designation alone does not identify an injury or its severity.
The forecast editions and their 5:16 PM input snapshot remain unchanged.
[Official Patriots list](https://www.patriots.com/news/week-1-inactives-patriots-at-seahawks),
[official Seahawks list](https://www.seahawks.com/news/nick-emmanwori-tory-horton-inactive-for-seahawks-opener-vs-patriots),
[dated capture receipt](../research/pgo_defensive_depth_candidate/source-review-20260909/inactives-20260909T225151Z/review.json).

The fresh source package was captured at 5:16 PM Eastern on September 9. All 32
expected quarterbacks and all 16 Week 1 game identities passed the source
checks. The official NFL page contained 21 team reports; the other 11 teams
remain unknown. Active-roster status is not a claim that a player is healthy
or will play. Later inactive announcements may change available personnel.

The captured New England report lists Ben Brown and TreVeyon Henderson out.
Seattle lists Ty Okada out and Nick Emmanwori and Tory Horton questionable.
These are dated observations, not probabilities. [Patriots report](https://www.patriots.com/news/week-1-injury-report-patriots-at-seahawks),
[Seahawks report](https://www.seahawks.com/news/2026-week-1-injury-report-seahawks-vs-patriots).

An official-report recheck at 6:44-6:48 PM Eastern found those game injury
designations unchanged. That later read-only check does not refresh the saved
5:16 PM model inputs. Final inactive lists were not present in the team news
pages checked at 6:48 PM; the later 6:52 PM verification above supersedes that
earlier availability check.
[Dated check and source captures](../research/pgo_defensive_depth_candidate/source-review-20260909/review.md).

New editions receive separate before-cutoff records. The same verified final
scores can grade each edition, including its misses. A score such as 23.1 is a
model average; whole-score displays do not add precision, and equal rounded
scores do not create a predicted tie.
