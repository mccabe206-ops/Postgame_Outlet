# What PGO's New England ranking includes and misses

**The #1 ranking is reproducible, but it is not a complete assessment of New
England's current roster.** The September 8 model relies on past results and
quarterback performance. It includes past team defense results, but does not
separately grade today's edge rushers, linebackers, or the quality of their
backups. A thin position group can therefore escape direct measurement.

Audit dated September 9, 2026. Model inputs remain the saved September 8 edition;
the current-source observations below were checked September 9 around 4:50 PM
Eastern. Status remains **EXPERIMENTAL / HOLD**. No ranking, forecast, fit, or
grade was changed by this audit.

## Why New England is high

The saved +5.200 rating can be accounted for as follows. These are contributions
relative to the same 32-team average, rounded to two decimals. They are
conditional formula terms, not separate football grades or causal player values.

| Saved input group | Contribution to NE rating |
|---|---:|
| Quarterback history, including passing and rushing | +2.29 |
| Past game results | +1.75 |
| Past team offense performance | +0.51 |
| Past team defense performance | +0.65 |
| Current non-QB injury adjustment in this saved rating | 0.00 |
| Total | +5.20 |

Results and passing describe some of the same games. They are not independent
confirmations that New England is the best team. Of the defensive contribution,
about +0.496 comes from preventing big plays. Sack creation contributes about
-0.004: the model is not rewarding New England for an exceptional pass rush.
The current rating carries forward historical team results rather than
rebuilding the defense player by player.

The complete inputs and contributions are in the
[saved corrected snapshot](evidence/forecast-lab-2026/september-08-corrected/snapshot.json).
The [current constructor](https://github.com/walshja9/Postgame_Outlet/blob/0d2babac470042cd1eed7d969a07f89d51906503/pgo_forecast_corrected.py) uses fresh depth order
to choose the expected starting quarterback. It has no corresponding current
EDGE/LB starter-versus-backup quality input.

## The depth concern is not resolved by the injury report

The [official Patriots roster](https://www.patriots.com/team/players-roster/)
lists Harold Landry III on reserve/PUP and Khalil Jacobs on injured reserve.
It lists Gabe Jacas, Quintayvious Hutchins, and Erick Hunter as rookies.
Those facts support a concern about available experience; they do not establish
how well their replacements will play.

The [club-hosted depth chart](https://www.patriots.com/team/depth-chart) is
explicitly the writers' unofficial chart. Its outside-linebacker rows list
Dre'Mont Jones with Jacas, and Elijah Ponder with Hutchins and Hunter. Its
rows labeled LB list Robert Spillane with Darius Muasau, and Christian
Elliss without a second name. An empty chart slot is not proof that no other
player can fill the role: rookie LB Namdi Obiazor also appears on the active
roster. Position labels alone do not fully separate edge-rushing and off-ball
assignments.

The latest [Week 1 formal injury report](https://www.patriots.com/news/week-1-injury-report-patriots-at-seahawks),
published September 8, has no New England EDGE/LB questionable, doubtful, or out
designation. That does not erase reserve-list absences or establish adequate
depth. Christian Barmore is listed as a full participant without a game
designation; he should not be counted as ruled out.

The separate [injury scenarios](forecast-lab.html#nonqb-availability) use prior
playing share and a broad offense/defense coefficient. They do not compare the
missing player with his replacement, and incomplete coverage prevents a full
adjusted prediction. Missing information is not zero injury impact.

## What would be useful to add

Pinned historical player files already contain defensive sacks, QB hits,
tackles for loss, passes defended, interceptions, and tackles. Historical snap
files provide defensive playing time. These can support a test of prior player
production and experienced-backup coverage, with stable player identities,
dated roles, and explicit missingness.

They do not provide a clean pass-rush-opportunity denominator, complete pressure
or missed-tackle data, or coverage-assignment grades. Sacks or hits per total
defensive snap would be a rough activity measure, not a pass-rush talent grade.
Rookies need an explicit unknown/prior treatment, not an automatic zero-quality
penalty. Players changing teams require their history to follow their identity.

The next useful experiment is a small, league-wide defensive production and
replacement-depth block, built only from information available before each
game. First audit historical depth timing and role coverage. Then compare it
with the corrected baseline on identical chronological folds, reporting margin
error overall, Week 1, early season, and each season. Reused historical seasons
are diagnostic; newly captured prospective forecasts are needed to test live
decision-time behavior. New England's rank is not a success criterion.

We already tested a broader age/draft/roster package. It moved New England to
second but **worsened** historical margin error: 10.134 versus 10.099 over 2,127
games, and passed none of its acceptance criteria. That result does not justify
adopting it. See the [saved candidate audit](https://github.com/walshja9/Postgame_Outlet/blob/0d2babac470042cd1eed7d969a07f89d51906503/research/pgo_ranking_trace_20260909/README.md).
Adding inputs can help only if their coverage and subsequent forecasting
evidence support the change.
