# Full Week 1 confidence slate

User instruction: include NE vs SEA in the full slate. This authorizes a new full-slate calculation and public display, with honest timing labels. Preserve the original 16 score forecasts, the saved 15-game confidence allocation and its validation code unchanged.

Reuse the exact saved calibration and original preseason/postseason model margins; no refit, current outcome or live-score input. Create a new immutable package containing all 16 games, confidence points 1 through 16 sorted by selected-team unconditional win probability, each confidence * probability contribution and their sum. Existing game win probabilities and picks remain unchanged. NE-SEA's probability is derived from its original saved margin using that same curve.

Record the actual creation and durable-write times. Mark each row added_after_lock when its original deadline has elapsed; currently this applies to NE-SEA. The full-slate point total and eventual earned points include this late-added row and are explicitly full-slate tracking, not an entirely pregame pool submission or prospective validation. Probability accuracy metrics exclude after-lock rows. The original 15-game allocation stays available unchanged for its separate prospective tracking; never mix the two confidence allocations.

Display the new full slate on the PGO model board and Forecast Lab. Mark NE-SEA inline as added after lock; explain once that its original score prediction was saved before lock but the confidence calculation was added afterward. Show the previous 15-game edition in a collapsed comparison with unique anchors. Keep plain-language calculation and source links.

Implementation: add the smallest new capture/loader module that reuses the pinned existing module, a new exclusive evidence directory, focused tests, and shared-renderer support for the second edition. Reject changed calibration/source identity, duplicate or missing games, invalid probabilities, missing/wrong timing flags, attempted overwrite, mutation of old evidence, or presentation that treats the late row as prospective probability evidence. No model promotion; status remains EXPERIMENTAL / HOLD.

Verification: arithmetic, ordering, timing, no refit and old-byte invariance; both page renders, 16 full-slate rows and 15 archived rows, original score-row preservation, unique links, pending/tie/correct-result grades; live public-byte and Shopify embed verification after publication.
