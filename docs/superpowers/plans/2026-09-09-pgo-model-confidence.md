# PGO model confidence picks implementation plan

User clarification: incorporate expected pool points into PGO's own model-based picks and publish; the separate manual calculator did not satisfy that request.

## Scientific contract and design

Add a frozen experimental probability and confidence layer to the existing September 9 postseason model. It is an output calculation, not a new input to team ratings or score margins. Reuse the fixed symmetric logistic mapping already tested in research/pgo_confidence_pool_20260909/attempt01. Fit its one nonnegative slope on all 2018-2025 out-of-fold postseason margins; use the fixed training-only tie estimate (ties+1)/(games+2). No 2026 results, live score, new injury assumptions or changed hyperparameters enter this fit. Existing source timing, recorded-starter, constant tie-risk and calibration transfer limitations remain; status stays EXPERIMENTAL / HOLD.

Grain: one saved game forecast. Capture real UTC generation time and source hashes. Include only games whose existing kickoff-minus-60-minute deadline is still ahead at capture. NE-SEA is excluded from the new confidence slate because its deadline has elapsed; its original score and margin remain visible unchanged. The other 15 games form a clearly labeled partial Week 1 slate, not a full-week entry or a backdated prediction.

Pick the higher unconditional home/away win probability. Allocate unique integer confidence points 1 through N in ascending selected-team probability; break equal probabilities by game ID. Freeze selections, probabilities and confidence values; rendering or later game locks never recomputes or reallocates them. Per-game expected pool points = assigned points * selected win probability; weekly expectation is their sum. Incorrect picks and ties earn zero. Display a model-generated table on both the main PGO model board and Forecast Lab, with plain-language explanation and evidence downloads. Retain the manual calculator as an optional tool.

Evidence: prior chronological diagnostic evaluated 1,615 games in 2020-2025, with training restricted to preceding seasons. Postseason log loss 0.647142 versus corrected 0.648094 and constant 0.711287; 5/6 season wins. This small reused-history improvement does not establish trustworthy live percentages or promote the model. Positive scalar mapping preserves each margin model's favorite choices and confidence order. Future probability grading uses frozen rows and official final results: primary three-outcome log loss, secondary Brier, selected-team reliability and actual earned confidence points, compared with frozen constant and corrected probabilities on the same eligible games. No promotion is triggered by these 15 games or by an attractive expected total.

Stop/reject on source hash drift, duplicate games, nonfinite margins/probabilities, invalid probability sums, negative slope, source snapshots captured after generation, missing/invalid timezone, selection after deadline, reconciliation failure or attempted overwrite. No automatic data refresh or new outcome fetch belongs to this publication.

## Implementation and verification

- [x] Add the minimum probability capture/verification module, reusing the pinned fixed diagnostic method and source; preserve a new exclusive evidence package.
- [x] Add meaningful arithmetic, source-integrity, timing, cutoff, determinism and immutability checks before publishing.
- [x] Present the saved output beside PGO model picks on both pages; use shared rendering and existing theme styles. Add actual earned points and probability grades through the existing final-result feed without changing frozen rows.
- [x] Generate both pages; verify 16 issued score rows, all 32 ratings, existing evidence, McCabe and Fantasy content remain unchanged. Check desktop/mobile and valid HTML anchors.
- [ ] Commit, publish and verify exact public bytes; record actual publication time and distinguish the new partial slate from the opener's prior lock.
