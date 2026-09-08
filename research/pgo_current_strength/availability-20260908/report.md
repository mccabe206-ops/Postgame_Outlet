# Current roster strength and availability evidence — 2026-09-08

Status: research inputs only. No model fit, forecast replacement, lock, or publication.

## Non-QB skill efficiency candidate

`pgo_roster_strength.py` implements four chartered efficiency proxies: WR receiving, TE receiving, RB/FB receiving, and RB/FB rushing. It uses only the three completed seasons before each prediction season, weighted 1, 0.5, and 0.25. Fixed shrinkage priors are 50 WR/TE targets, 30 RB targets, and 75 RB carries. Historical and current aggregation both use the incumbent prior-game median-last-four offense snap-share proxy. Missing histories receive the position prior; no positive role weight yields missing rather than zero. Availability is separate.

Among the frozen ACT roster, 2023–2025 opportunity history covers 146/182 WRs (80.2%), 95/121 TEs (78.5%), and 99/112 RB/FBs (88.4%). Offensive-line player quality is unavailable because the admitted sources contain no blocking-quality measure and all 302 current ACT OL rows lack PFR IDs. Defensive player quality is unavailable because the admitted weekly source contains counting stats but no player-level defensive EPA or coverage grade.

Charter SHA-256: `edf1328d2dc1a7d047f75d40cffa6ba3eb1d4e0a2b5858e8de5ef0b74aafa157`.

## Official availability capture

NFL.com was captured at `2026-09-08T02:24:19.275711+00:00`. Exact HTML SHA-256: `8036332159db6056c9fd24355603cd2e21172e4200d0844f537d9dbb265f6797` (328,956 bytes).

The page contained 11 formal practice-report rows for NE and SEA. Every row resolved uniquely to the frozen ACT roster and produced a validated overlay. The other 30 teams are recorded as `no_formal_report`; “No Injuries Reported” at capture time is not proof of health or final game availability.

Existing prior snap metadata makes this dated overlay usable without a new role model. NE has an offense unavailable share of 0.295294 and defense share of 0. SEA has an offense unavailable share of 0.099275 and defense share of 0.280476. These belong to a separate current-availability candidate. The frozen September full-strength scenario remains unchanged. A future overlay containing an unavailable QB must use the reviewed depth-aware QB policy and fail closed otherwise.
