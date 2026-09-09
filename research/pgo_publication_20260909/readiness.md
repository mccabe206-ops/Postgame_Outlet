# Corrected PGO model readiness audit ? September 9, 2026

**Operational artifact readiness: PASS for publishing the existing dated, conditional experimental output. Demonstrated predictive utility: NOT ESTABLISHED; EXPERIMENTAL / HOLD remains required. Final game-day availability review: still pending. No blocking code bug was found in this bounded audit.**

Audited checkout HEAD `438878b0689e3738a60905c676306dac74e4c609`. Applied the sports-modeling doctrine to the existing pre-fit contract in `research/pgo_week1_corrected/charter.md`; no new charter, fit, feature selection, historical walk, spent-study retry or forecast rewrite was performed. Exact commands, exit codes, output, current source hashes and before/after forecast hashes are in `readiness-receipt.json`. Live workflow inspection is in `readiness-automation.json`.

## Active model and inputs

`pgo_forecast_lab._load_corrected` (`pgo_forecast_lab.py:849`) selects the latest registered corrected source, and `pgo_current_board.add_current_board` uses the same verified corrected snapshot. The current source is `docs/evidence/forecast-lab-2026/september-08-corrected`; the failed corrected-plus-v2 candidate is not selected.

The active snapshot was generated September 8 at 15:18:05.595213 UTC, from inputs captured through 15:01:38.802823 UTC; its depth snapshot is 11:56:57 UTC. All 32 expected quarterbacks resolve on the qualified ACT roster. NE is conditional on Drake Maye (`00-0039851`), SEA on Sam Darnold (`00-0034869`). No expected quarterback appears among the September 9 annotation ledger's reported player rows; that absence is not a new healthy/inactive confirmation.

The model package contains Monday NE/SEA practice evidence and unknown formal coverage for the other 30 teams. The newer September 9 10:42?10:46 Eastern injury review is a separate reader-annotation package, with four formal/practice teams and 28 unknown teams. It does not change the model fit, source package or forecast values. The active fit explicitly leaves non-QB availability unadjusted, and assumes its selected quarterback plays (`pgo_forecast_corrected.py:125-161`). An unavailable expected QB blocks an affected newly built matchup until a supported replacement is selected. ACT membership is an eligibility rule, not a measure of lost injured-reserve talent.

## Runtime and preservation evidence

- `python -B pgo_forecast_corrected.py --verify docs/evidence/forecast-lab-2026/september-08-corrected`: exit 0; 32 teams and 16 games verified, HOLD. The loader verifies pinned manifests/source qualifications, replays the saved fit against current-package features, checks symmetry and contributions, and checks exact saved CSV consistency (`pgo_forecast_corrected.py:322-383`).
- `python -B pgo_forecast_weekly.py --verify`: exit 0; two immutable revisions and 16 latest game forecasts verified.
- `python -B -m unittest tests.test_pgo_forecast_corrected tests.test_pgo_forecast_weekly -v`: **32 passed**. Coverage includes unavailable-QB blocking, source tampering, finite numeric replay, symmetry, changed schedule identities, pre-cutoff acceptance, exact/late-cutoff rejection and a durable write crossing cutoff. Synthetic tests write only temporary fixtures.
- Independently hashed all manifest members: 25 active snapshot files, eight corrected research files and six failed-candidate research files; zero mismatches. All 50 files beneath `docs/evidence/forecast-lab-2026` retained identical before/after bytes.
- Active snapshot manifest: `85fe35069145505410567709261663be0939b3ae2fbe05ad147da1d17fc54d83`; final fit: `f6e6deda6665ded3ea0764a486fc68bc4667abd4a49f17afe5e3c39284a8806f`; latest weekly revision: `34de3020267227a4c97ceb20e3ae3ca117623e98fb5b1f4ad2d267103d81efcb`.

## Tonight's cutoff works without a scheduled job

NE at SEA is scheduled for **September 9, 8:20 PM Eastern**; this agrees with both the pinned schedule and the current [official Patriots viewing guide](https://www.patriots.com/news/how-to-watch-listen-patriots-at-seahawks-week1). The model's T-60 boundary is **7:20 PM Eastern / 23:20 UTC**, recorded on the opener's latest weekly row. The already registered forecast is SEA by `0.43982679672328245`, registered September 8 at 15:23:19.158416 UTC. It remains the eligible final forecast unless a new verified revision is appended before the cutoff.

There are two separate mechanisms:

1. **Forecast immutability:** `record_week` checks actual UTC at registration, before exclusive write and after durable write (`pgo_forecast_weekly.py:281-370`). `load_weekly` rejects revisions registered at or after their game cutoff and selects the last eligible revision per game (`pgo_forecast_weekly.py:197-278`). No new write or scheduled freeze event is needed at 7:20 PM.
2. **Visible Draft/Locked badge:** `_forecast_weeks` emits each cutoff; the already-issued HTML contains `updateWeeklyLocks`, which updates the label from browser time and schedules the next cutoff (`pgo_forecast_lab.py:1239-1251`). Extracted the exact issued JS and ran it under Node with a small controlled DOM/clock: before cutoff both games were Draft; exactly at cutoff the opener became Locked while the later game remained Draft; after kickoff the result persisted. This passed in `readiness-lock-check.cjs`. With JavaScript disabled, the static fallback reflects render time; the explicit cutoff remains displayed.

**No new scheduler or lock-toggle fix is needed tonight.** GitHub's live Update board and Publish edition workflows are active but have only push/manual triggers, and the inspected local Windows tasks contained no matching PGO action. `weekly_refresh.py` refreshes team-workspace caches, not the PGO forecast registration pipeline. Neither source refresh, final-inactive review nor result scoring happens automatically. A browser Locked badge means the forecast deadline elapsed, not that final inactives were fetched.

## Predictive utility remains unproved

The existing charter's target is final home-minus-away margin including overtime, one row per regular-season game. Historical evaluation uses earlier-season training against the same 2,127 games in 2018?2025; those seasons were already inspected, so they are diagnostic rather than new confirmation. Primary metric is margin MAE.

The pinned corrected report gives MAE **10.099456**, versus recency reference **10.119775**: a 0.020319-point gain with season-block interval **[-0.030609, +0.074064]**. This does not establish added accuracy. The saved arithmetic verification covers 2,127 predictions and 2,558 metric/bootstrap values; its hashes were verified here, but the historic experiment was not rerun (`research/pgo_week1_corrected/README.md`, `verification.json`).

The separate corrected-plus-v2 candidate worsened MAE to **10.133540**, improved only **3/8 seasons**, and failed all three declared further-study criteria. Its gain interval is **[-0.102307, +0.044823]**. Keep that completed candidate closed and unadopted (`research/pgo_corrected_roster_candidate/README.md`, `saved-fit-verification.json`). A cosmetically preferable ranking is not grounds to replace the active model.

Historical starter-oracle/vintage limits, overlapping fitted terms, uncalibrated availability and the prior-season PF/PA total heuristic remain material. Exact scores, calibrated win probabilities, market edge and a proven team-strength ranking are unsupported. There are no captured prospective final results yet; software QA cannot supply that missing evidence.

## Necessary next actions

- Publish this output only with its actual snapshot date, conditional-QB/non-QB-injury limitations and EXPERIMENTAL / HOLD status intact. Current reader annotations can accompany it without changing saved forecasts.
- Before 7:20 PM Eastern, perform the already documented official roster/QB/final-report review and preserve a new capture if new information is obtained. Final inactives must come from their actual release. If issuing a changed forecast, follow the existing append-only fresh capture ? qualification ? reviewed hash-pair ? new snapshot ? verifier ? weekly registration procedure in `research/pgo_week1_corrected/README.md:96-109`; never overwrite the current package or backdate a revision. If no replacement forecast is issued, the current eligible revision still locks normally.
- A read-only deadline check is `python -B pgo_forecast_weekly.py --verify`. For a static render after the deadline, `python -B pgo_forecast_lab.py --output output/pgo-publication-20260909/forecast-lab-after-cutoff.html` writes only a preview and does not change forecast records; no special mark-locked command is required.
- After final results become available, capture/validate exact game identities and scores, then grade the last eligible revision against the preserved v0 and September incumbent. Keep all errors and version comparisons. New prospective evidence, not another pass over inspected history, is the next route to a predictive-readiness claim.

No implementation change is requested by this audit. Source refresh and later prospective scoring are operational/evidence work still to perform, not hidden consequences of publication.
