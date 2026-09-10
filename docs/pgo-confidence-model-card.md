# PGO model confidence picks, Week 1 remaining games

**EXPERIMENTAL / HOLD.** Owner: Postgame Outlet. Prepared and code-reviewed by the assistant; independent scientific qualification has not been established. This is a new probability and confidence-pool output layer for the September 9 postseason margin model, authorized by the user's clarification to incorporate expected points into model-based picks. It is not a promotion of that model or a rewrite of its issued scores.

## Use and timing

For PGO readers comparing the model's remaining Week 1 picks, one row represents one saved game. The selected team has the higher model-estimated unconditional win probability. Confidence points are unique integers 1 through the eligible slate size, with higher probabilities receiving more points. Expected pool points are confidence points multiplied by selected-team win probability, summed over games. Wrong picks and actual ties earn zero. These are pool points, not NFL scoring predictions; this objective does not maximize the chance of beating other entries.

The new snapshot's real UTC creation time, per-game deadlines and exact values are saved in its [evidence package](evidence/confidence-pool-2026/week1-remaining/picks.json). It was created at September 9, 2026, 8:28:38 PM EDT and includes only games still before their existing kickoff-minus-60-minute deadline at capture and durable completion. NE–SEA was already locked and is excluded. Its original forecast remains intact. This is a new 15-game partial slate, not a backdated full-week entry. Values do not change as games lock or results arrive. The saved expectation is 77.0017158371 pool points out of 120 available.

## Data and method

Reuse the [pinned historical diagnostic](confidence-pool-study.md): 2,127 out-of-fold game margins and outcomes from the 2018–2025 seasons. No 2026 outcomes or live score enter the fit. The fixed method fits a nonnegative symmetric logistic slope, with no intercept and the same ridge penalty used in the diagnostic. The empirical tie estimate with the fixed smoothing rule reserves probability mass for ties; remaining mass is split between home and away wins. Current inputs are the exact saved September 9 postseason margins. A positive scalar mapping preserves favorite choices and absolute-margin ordering; it cannot independently improve that ordering.

The snapshot also freezes corrected-model and training-frequency constant probabilities for comparison. All future probability grades use the same finalized games. Primary metric: three-outcome log loss. Current secondary metrics: three-outcome Brier score and actual confidence points. Selected-team reliability needs a later review with more prospective games; it is not a live grade from this 15-game slate. Pending games are excluded from grades. The existing reviewed official final-result feed supplies results; this feature does not fetch or infer them.

## Evidence and limits

The prior fixed walk-forward diagnostic evaluated 1,615 games in 2020–2025 after two warmup seasons. Each calibrator saw only preceding seasons. Postseason log loss was 0.647142 versus 0.648094 for corrected and 0.711287 for constant; Brier was 0.440351 versus 0.441205 and 0.501591. Postseason improved log loss in five of six seasons. This is a small improvement on previously examined history. Season, early-season and fixed-bin reliability counts are available in the linked diagnostic, but prospective calibration and uncertainty for the new slate are not established.

Historical source publication vintage and recorded-starter assumptions remain unresolved limits. A constant tie rate ignores matchup-specific tie risk. Applying a curve trained on older model forecasts to a new season may not transfer well. Non-QB injuries and replacement-player quality are not fitted into the saved margins or these probabilities; the listed quarterback is assumed to play. Missing source or identity data must never silently become average ability or a 50% win probability.

## Maintenance and reproducibility

Review the frozen slate after all included results are final and before creating another slate. Fifteen games cannot establish reliable calibration or trigger promotion. Any source/hash mismatch, identity drift, invalid probability sum, deadline violation or reconciliation failure blocks rendering/publication. A new model, changed calibration rule or newly admitted injury feature requires a separate dated experiment and evidence package; do not edit this capture or tune it against current outcomes.

The [manifest](evidence/confidence-pool-2026/week1-remaining/manifest.json) pins the snapshot, capture code, historical method/source and source forecast identity. The implementation uses Python's standard library and existing PGO snapshot verification. Run `python -m unittest tests.test_pgo_confidence_picks tests.test_pgo_confidence_view` to verify arithmetic, source integrity, timing and presentation. Capture is explicit and refuses to overwrite an existing package; page rendering only reads the verified frozen output.
