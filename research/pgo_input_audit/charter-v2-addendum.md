# Sixth arm: metric-specific QB exposure

This additive amendment is written before any follow-up fitting. The implementer
confirmed no fit had started; no results from the new five arms were inspected.
The original charter remains unchanged at SHA-256
4be3031146e6f7f58347a7139a8c249b5bbb40a69876b86547ddaca4b45f52fd.
All of its data, evaluation, timing, preservation and decision rules apply.

The input audit found that every QB rate's shrinkage reliability uses passing
dropbacks, including rushing EPA per carry. Passing experience does not supply
the missing rushing observations. Add exactly one arm to test this issue:

**active4_exposure** is active4_clean with metric-specific reliability weights.
Use passing_epa_plays/(passing_epa_plays+200) for passing EPA;
cpoe_plays/(cpoe_plays+200) for CPOE;
sack_dropbacks/(sack_dropbacks+200) for sack avoidance;
security_dropbacks/(security_dropbacks+200) for ball security;
carries/(carries+50) for rushing EPA. Each mixes the player's rate with the
same time-decayed population rate. Missing/no player observations use the same
population/missing-data policy. Log dropbacks, draft and experience features
remain unchanged. Apply identically to historical and current construction.

The 50-carry prior is a fixed exploratory assumption, not empirically calibrated
uncertainty. The CPOE source is still a weekly aggregate weighted by attempts,
not a reconstructed play-level count of eligible CPOE observations. This arm
does not cure that source granularity or certify a causal player valuation.

Compare against active4_clean and reference4 with the same games, season-block
bootstrap, primary MAE screen, slices and no-promotion decision. No seventh arm,
prior-size search, or retrospective selection of favorable team ranks is allowed.
