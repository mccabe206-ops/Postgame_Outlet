# Separate season-frozen strength diagnostic

EXPLORATORY / HOLD. No model was fitted. Retrospective Week-1 roster/starter oracle; not verified T-60.
All32 strengths freeze before any season observation; full-strength Week-1 QB remains fixed all season.
Saved recency fits train only on earlier seasons. Per-game venue/rest remain inherited controls.
The frozen v0 comparator retains its existing2.5home-field/no-rest formula and one0.5offseason retention.

| Arm | Games | MAE | RMSE | Home-minus-away bias |
|---|---:|---:|---:|---:|
| rolling_recency | 2127 | 10.1198 | 13.0695 | +0.3074 |
| frozen_recency | 2127 | 10.9191 | 14.0399 | +0.2305 |
| rolling_v0 | 2127 | 10.2662 | 13.2298 | +0.9729 |
| frozen_v0 | 2127 | 10.7404 | 13.8235 | +0.8792 |

This diagnostic checks the fixed-season strength policy separately from next-game updating.
It does not validate exact scores, playoff probabilities, prediction intervals, or source-vintage availability.
All seasons and early/late slices are retained in metrics.json; no arm is promoted.
