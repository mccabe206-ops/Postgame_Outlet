# Non-QB availability sensitivity

This adds a separate, dated **EXPERIMENTAL / HOLD** view beside the unchanged
corrected PGO board and issued forecasts. It reuses the existing corrected fit;
it does not refit, adopt a failed candidate, copy McCabe's grades, or issue an
injury-adjusted league ranking.

The fit assigns about 0.238443 model points per lost offensive role-share unit
and 0.118991 per defensive unit. The inputs sum once per player. OUT, IR and PUP
form one scenario; a second adds all questionable/doubtful players as absent.
Those endpoints are assumptions, not participation probabilities or confidence
bounds. Unknown roles and coverage stay unknown. Partial rows display only the
contributions that can be calculated, with no complete adjusted rating/margin.

Official reports, team reserve pages and the fresh roster/depth sources were
captured September 9 at approximately **1:14–1:16 PM Eastern**. All 32 expected
QBs still match the existing conditional base. The ledger contains 21 verified
non-QB identities: five formal game-status rows, 14 reserve supplements and two
separately sourced official-news absences. Two teams have formal game reports,
two practice-only coverage, and 28 unknown coverage. Final inactives are pending.
Conflicting reserve/roster identities and an unsupported alias remain excluded
and visible; exclusions are not treated as healthy.

Fourteen players have positive observed 2025 unit usage; seven do not. The role
proxy is the median of the last four positive regular-season observations, with
fewer observations disclosed. This explicitly differs from the older historical
role convention and is unvalidated. Source witnesses retain exact raw rows,
identities, team denominators and per-game shares. Corrected historical identity
sources are separately qualified; original sources and model fit stay unchanged.

Usage is not player quality. These weights do not distinguish stars from
backups with equal usage, value a named replacement, or estimate nonlinear unit
injury effects. Ben Brown's prior median is 100%, while his fresh depth listing
is C2: his row explicitly warns that prior usage can overstate a backup's current
lost playing time. Old performance can already reflect long-term absences.

## Evaluation

The [saved-fold diagnostic](diagnostic-20260909/README.md) replays 2,127 existing
2018–2025 predictions within 4.44e-16. Keeping the saved availability terms gives
MAE 10.099455868, versus 10.097429512 with the two observed terms set to zero.
The gain is -0.002026355, with season-block 95% interval
[-0.008629912, +0.003355498]; 4/8 seasons improve. There is no demonstrated lift.

This post-hoc diagnostic includes historical QB losses and heuristic status
probabilities. It does not validate the new non-QB role/status policy. No tuning
followed the result. Future claims require before-cutoff prospective comparisons
against the preserved base on the same final game margins, including bad results.

## Reproduce

`prepare_roles.py` reads the explicitly qualified 2025 identity sources and
builds role witnesses. `build_release.py --evidence CAPTURE_LEDGER --output NEW_DIR`
normalizes the reviewed source ledger, verifies fresh QB assumptions, and writes
an exclusive package. The first integration attempt stopped before creating a
package on the official T/G versus roster OL label; the shared unit resolver was
fixed. Attempt 02 was preserved as a local draft. Review added display-name and
depth-source binding, exact latest-four verification, and an unknown display for
entirely unpriced teams before the final package was prepared.

`python -B pgo_nonqb_availability.py --verify PACKAGE_DIR` checks every captured
byte, current roster/name/depth witnesses, qualified historical raw rows, exact
last-four observations and all arithmetic. The preserved base and fit are pinned.
Writes check actual UTC before and after durable output; an elapsed T-60 cutoff
cannot be backdated. No existing weekly record is rewritten.

The public addition is rendered by `pgo_availability_view.py` in the PGO Model
tab and Forecast Lab. Source refresh and scenario issuance remain explicit
operations. Rendering is local-file-only and does not fetch injury reports.

## Release verification

Final canonical discovery: **599 tests, OK, one skipped**. The 14 required
corrected-roster research tests also pass. A regression check covers Fantasy
injection with the availability view; the accessible div wrapper preserves the
existing comparison-section boundary. Desktop and 375px mobile review passed,
with wide tables contained in focusable horizontal scrolling regions.

Independent staged-byte review preserved all 51 earlier evidence files, all
32 McCabe grades, 32 current PGO rows, 32 archived comparison rows and 447
fantasy rows. All 33 new package files match their reviewed raw bytes under
cached Git attributes. The package manifest SHA-256 is
`4cc93e8ff89b81e435140bff9b38196e243915c8b0bf323b341f1cbe8dfc8659`.

An additional official NE/SEA report check at **1:56 PM Eastern** found no
material game-status changes. Final inactives remain pending; this check does
not change the saved scenario's 1:16 PM source clock or issue a new forecast.
