# Frozen availability and expected-QB trace

Read-only audit at HEAD `275289e71ae4d8950b621f86447fff673f84840d`.
Status remains **EXPERIMENTAL / HOLD**. This note does not run feature preparation, fitting, source capture, forecast issuance, or publication.

## Finding

Availability does not numerically explain candidate-versus-corrected rating changes. In `research/pgo_corrected_roster_candidate/current-preflight-20260908/current-features.json`, all 32 teams have exactly zero `offense_availability`, `defense_availability`, and `qb_current_minus_full`. This is prescribed by `pgo_forecast_corrected.py:125-147`, inherited by `research/pgo_corrected_roster_candidate/adapter.py:184-223`. The adapter adds ACT roster age/role/draft descriptors with availability weight one; it does not read an injury probability overlay.

ACT is administrative eligibility, not confirmed health or game-day participation. Excluding RES/EXE players changes which players may enter roster descriptors, but there is no separate priced penalty for the excluded player's lost talent. An unavailable ACT non-QB can remain in the descriptors.

## Selected QBs and coverage

All five selected QBs are unique ACT roster matches and depth rank 1 in the frozen source qualification. None changed from the September 7 selected starter. The same identities appear in the issued corrected snapshot and candidate diagnostic.

| Team | Expected QB | GSIS ID | ACT rows | Frozen injury coverage |
| --- | --- | --- | ---: | --- |
| PIT | Aaron Rodgers | 00-0023459 | 53 | UNKNOWN / no formal report |
| DEN | Bo Nix | 00-0039732 | 53 | UNKNOWN / no formal report |
| KC | Patrick Mahomes | 00-0033873 | 53 | UNKNOWN / no formal report |
| LAR | Matthew Stafford | 00-0026498 | 52 | UNKNOWN / no formal report |
| NE | Drake Maye | 00-0039851 | 53 | DATED_REPORT_UNADJUSTED |

Evidence: `docs/evidence/forecast-lab-2026/september-08-corrected/source-qualification.json:174` (chosen QBs); its coverage entries begin DEN:518, KC:596, LAR:622, NE:674, PIT:789. Derived team coverage statuses are in `snapshot.json` under `teams[].coverage`, rather than the separate top-level raw `coverage` object.

All 32 teams are explicitly covered as reporting states: two formal reports (NE/SEA), thirty unknown; eleven observations; one known unavailable player; zero expected-QB blocks. None of the observed injuries is a selected QB. `pgo_forecast_corrected.py:151-162` would mark a confirmed unavailable selected QB `BLOCKED_EXPECTED_QB_UNAVAILABLE`; lines 293-306 omit its matchup instead of silently substituting or continuing issuance. This conditional gate is not triggered in this frozen package.

## Concrete ACT versus unavailable example

The saved Monday September 7 Patriots report, captured September 8, contains:

| Player | Status in raw roster | Saved report | Prior median role used in candidate |
| --- | --- | --- | ---: |
| Ben Brown (OL; 00-0037413) | ACT | Out; knee; Did Not Participate | offense 0.5405405405 |
| TreVeyon Henderson (RB; 00-0040734) | ACT | No game designation; ankle; Did Not Participate | offense 0.4437744459 |
| Christian Barmore (DL; 00-0036981) | ACT | No game designation; knee; Full Participation | defense 0.7489010989 |

Ben Brown is explicitly `known_unavailable_unpriced`; the other observations are `unadjusted`. His saved offense history is `[0.0, 0.08108108108108109, 1.0, 1.0]`. Because he is ACT, that nonzero median contributes to the candidate's aggregate roster descriptors despite Out. This establishes a modeling limitation, not an unimplemented deviation from the locked charter. DNP alone is not an Out designation.

Evidence: source qualification lines 674-734, `roster.csv.gz` rows keyed by these GSIS IDs, and `research/pgo_corrected_roster_candidate/preflight-20260908-revised/historical-context.json` under `snap_history` for each ID. That history stores four role entries without per-entry dates.

## Source clocks and history limits

- Candidate diagnostic recorded at `2026-09-09T00:25:22.890532+00:00` uses inputs at `2026-09-08T15:01:38.802823+00:00`. It is not a fresh September 9 source capture.
- Depth snapshot: `2026-09-08T11:56:57Z`; provider timestamps: roster `2026-09-08T07:56:45-04:00`, depth `2026-09-08T07:57:03-04:00`, schedule `2026-09-08T10:47:03-04:00`.
- The NFL overview was captured `2026-09-08T15:01:37.997812+00:00`; Patriots report `15:01:38.080270+00:00`; Seahawks report `15:01:38.140411+00:00`. Formal report date is September 7, before later final game designations.
- Team-efficiency and prior role inputs are final-2025-history state, not 2026 live performance. Historical QB state last kickoff is `2026-01-05T01:20:00+00:00`; current QB features decay that state forward to the September 8 input clock with a 365.25-day half-life (`pgo_current_strength.py:50-64`).
- Role histories use the median of last four prior ACT roster observations. They can carry across absences, teams and seasons. The inherited updater appends zero when an ACT player has no resolved snap row (`pgo_challenger.py:2300-2331`). Consequently a saved zero can be an unmatched-row fallback; it is not always observed nonparticipation. The current aggregate context alone cannot date each role entry or distinguish each zero's origin. Historical source publication vintage and historical recorded-starter pregame availability remain REVIEW REQUIRED.

The separate older `research/pgo_current_strength/availability-20260908/scenario-report.md` applied an overlay from a September 8 02:24 UTC capture to another frozen model: NE output delta -0.179842, SEA -0.192687. Those values are not inputs to the corrected roster candidate and cannot be imported as its injury effects.

## Coverage and missingness

Across the current candidate: 1,693 ACT rows, 1,693 resolved identities, zero unmatched identities, zero unmapped positions, zero missing selected-QB ages, and all 1,088 team-feature cells finite. Complete final feature cells do not imply complete role/player or injury coverage.

| Team | Offense players with role history / unit players | Defense players with role history / unit players | Blank offense / defense draft records |
| --- | ---: | ---: | ---: |
| PIT | 16 / 22 | 20 / 24 | 6 / 1 |
| DEN | 20 / 23 | 24 / 25 | 3 / 7 |
| KC | 18 / 23 | 17 / 24 | 5 / 6 |
| LAR | 22 / 24 | 21 / 22 | 5 / 7 |
| NE | 20 / 24 | 18 / 24 | 6 / 9 |
| All teams | 593 / 717 | 663 / 795 | 121 / 152 |

Thus 124 offensive and 132 defensive ACT players lack role history and do not enter role-weighted means. The known-role count includes zero-role histories; it is not a positive expected-snap count. All current ACT DOB and experience fields are present. There are 347 blank draft records among all ACT positions; blank/zero draft encodes zero prior, not proven undrafted status or zero talent. No source identity mismatch was found in this trace.

Evidence: current-preflight `coverage.json` and `current-features.json`, raw current roster, `adapter.py:59-108`, candidate charter's role and missingness definitions. The source qualification lists RES/EXE exclusions without decoding their raw codes into injuries or suspensions; examples include DeShon Elliott (PIT RES/R48), Jonathon Cooper (DEN EXE/E02), Aaron Donald (LAR EXE/E02), and Harold Landry III (NE RES/R04). Those raw codes alone are not medical claims.

## Review priorities and verification

1. Preserve the explicit frozen clock, UNKNOWN/DATED_REPORT_UNADJUSTED state, and conditional expected-QB interpretation anywhere these rankings are explained. This is already implemented in the corrected source and presentation contract; no repair is established by this audit.
2. A later authorized source refresh should resolve game-specific QB and final availability before the relevant cutoff. It must be a new preserved package; this audit does not claim today's availability or authorize a refresh.
3. Any numerical availability model or change to missing/stale role handling needs its own defined evaluation. Do not translate these annotations directly into penalties or modify a failed frozen candidate.

Read-only SHA-256 checks matched all four files in the current-preflight manifest and all 25 files in the corrected-source manifest. No model or source code was executed, and no preexisting artifact was changed by this subtask. The only write is this newly created note.
