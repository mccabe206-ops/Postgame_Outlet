# PGO verified quarterback reconciliation

Approved by the user on October 11 against `origin/main` at `2265a755`; implementation and publication are in progress.

## Verified defect

The comparison in `pgo_season_view._rank_comparison()` reads the weekly `state.rankings` snapshot from October 6. It never reads the separately verified current projections. The current roster/depth refresh continues to select ordinary depth-chart QB1 unless an official, game-specific starter rule has been reviewed and activated.

| Team | Weekly PGO assumption | Verified replacement | Evidence |
| --- | --- | --- | --- |
| CHI | Caleb Williams | Tyson Bagent, `00-0038416` | Bears article, October 7: https://www.chicagobears.com/news/tyson-bagent-looking-forward-to-facing-rival-packers |
| BAL | Lamar Jackson | Tyler Huntley, `00-0035993` | Ravens injury update, October 9: https://www.baltimoreravens.com/news/lamar-jackson-trey-hendrickson-injury-report-marlon-humphrey-zay-flowers-ronnie-stanley-ravens-falcons |
| TB | Baker Mayfield | Jalon Daniels, `00-0041251` | Existing admitted current projection for `2026_05_TB_DAL`, issued October 9 at 03:14:35 UTC; official source: https://www.buccaneers.com/news/bucs-cowboys-inactives-rueben-bain-jr-ko-kieft-return-action |

All three replacements resolve uniquely to ACT quarterbacks on their respective teams in the latest saved roster, captured October 11 at 14:14:51 UTC. PGO already calculated Tampa Bay at rank 29 with Daniels in its separate current projection, while the comparison still displays rank 22 with Mayfield. Chicago's saved report marks Williams QUESTIONABLE; Baltimore's marks Jackson OUT. A questionable designation alone does not identify a replacement starter.

## Recommended approach

Use the existing official starter capture, review and activation machinery for missing game-specific authority. Respect real source, capture, review, activation and T-60 clocks. Chicago is already past T-60 and must use the separate current calculation; its saved original forecast cannot be revised. Baltimore uses verified current authority in the separate lineup calculation while its original weekly forecast remains preserved. Reuse Tampa Bay's admitted source and saved calculation; do not capture or backdate a replacement for its completed game.

Produce one separately dated current-lineup ranking snapshot with all 32 teams, using the existing frozen coefficients and completed-week feature construction. Resolve each changed quarterback to its verified GSIS identity before recalculating; never just replace displayed names or copy McCabe's quarterback grades. Carry applicable admitted replacement authority consistently into the calculation, including the already completed Tampa Bay matchup, without applying expired game-specific evidence to another matchup or week.

Use this same complete snapshot for the current ranking table, rating explanations, and McCabe comparison. Preserve the original weekly ranking snapshot, issued forecasts, issue clocks, confidence allocations, grades, and archives. Current calculations cannot enter locked-record or ATS/confidence grading. Keep the existing experimental status.

The approved implementation updates the default current ranking table and its comparison from the same complete calculation.

## Scope and validation

Implementation reaches the existing current projection/starter resolver, season-state save/load validation, ranking selection in the shared renderer, their callers, and focused tests. No dependency, refit, human ratings edit, non-QB fitted adjustment, or historical forecast rewrite is needed.

Reproduce the stale comparison first. Verify that all three changed QB identities reach the numerical model inputs and displayed explanations; all 32 ratings, ranks and contribution totals reconcile; missing, ambiguous, expired or conflicting evidence blocks the current update; full source/clock replay survives save/load; and original weekly records remain byte-identical. Render both the board and Forecast Lab from the same verified state. Verify public deployment and Shopify embedding separately from local source checks if publication is authorized.

## Current state

The user approved current rankings and publication with "proceed". See the linked implementation plan for scope and validation; historical forecasts and grades remain preserved.
