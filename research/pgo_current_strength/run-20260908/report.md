# Current-strength research

EXPERIMENTAL / HOLD. Historical source vintage: REVIEW REQUIRED.
Recorded actual starters are reconstructed, not verified T-60 expectations.

| Arm | Games | Margin MAE | RMSE | Winner accuracy |
|---|---:|---:|---:|---:|
| constant | 2127 | 11.0580 | 14.3262 | 54.03% |
| pgo_v0 | 2127 | 10.2662 | 13.2298 | 63.05% |
| raw | 2127 | 10.1937 | 13.1594 | 63.95% |
| starter | 2127 | 10.1193 | 13.0881 | 64.98% |
| starter_recency | 2127 | 10.1198 | 13.0695 | 65.60% |
| starter_recency_roster | 2127 | 10.1318 | 13.0836 | 65.83% |
| without_results_history | 2127 | 10.1613 | 13.1303 | 64.94% |
| without_team_passing | 2127 | 10.1313 | 13.0789 | 65.64% |
| without_other_team_performance | 2127 | 10.1300 | 13.1033 | 64.51% |
| without_qb | 2127 | 10.2184 | 13.1775 | 64.75% |
| without_roster_continuity | 2127 | 10.1082 | 13.0671 | 65.55% |
| without_coaching | 2127 | 10.1207 | 13.0775 | 65.46% |
| without_skill_quality | 2127 | 10.1198 | 13.0695 | 65.60% |
| without_availability | 2127 | 10.1462 | 13.0969 | 65.46% |

## Predeclared screens against matched raw

- starter: merits further study; 6/8 seasons improve; MAE gain +0.0744, 95% season-block interval [+0.0173, +0.1387]. Promotion: HOLD.
- starter_recency: merits further study; 6/8 seasons improve; MAE gain +0.0739, 95% season-block interval [+0.0158, +0.1270]. Promotion: HOLD.
- starter_recency_roster: merits further study; 6/8 seasons improve; MAE gain +0.0619, 95% season-block interval [+0.0001, +0.1183]. Promotion: HOLD.

All ablations refit preprocessing and coefficients on earlier seasons.
Positive MAE improvement means lower error. Ablation gains are exploratory.
Current ranks are model-scale sensitivities, not calibrated confidence intervals.
Skill-player features are efficiency proxies; OL and defensive player quality are unavailable.
Issued forecasts and promoted ratings remain unchanged.
