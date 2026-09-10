# Confidence-pool diagnostic, September 9, 2026

Written before fitting. EXPERIMENTAL / HOLD; no live probability issuance or changes to saved forecasts.

Question: can existing out-of-fold home-margin predictions support useful win probabilities and confidence ordering? Expected pool points are the sum of assigned points times the selected team's unconditional win probability. Incorrect picks and ties earn zero. One unique integer from 1 through the slate size is assigned to each game. This maximizes expected points, not the chance of winning a pool.

Pinned input: ../pgo_postseason_candidate/run-20260909-attempt01/matched-predictions.csv, SHA-256 3df4dbf26743a3686b6253bb4eb578457d0e2629dde1f0218f215c462feea0cf. Grain: one game. The existing margin predictions are chronological out-of-fold predictions. Previously inspected seasons and incomplete historical publication receipts remain limitations.

Fixed procedure: warm up on 2018-2019; evaluate each season 2020-2025, fitting only preceding seasons. Independently fit corrected and postseason margins with a symmetric, nonnegative one-parameter logistic slope, no intercept, ridge penalty 0.5*a*a. Estimate tie probability from training games as (ties+1)/(games+2); allocate remaining probability between home and away. Constant baseline uses training outcome counts with one pseudocount per outcome. No current-season outcomes enter fitting.

Primary metric: mean three-outcome log loss. Also report three-outcome Brier score, fixed ten-bin selected-team reliability, each season, Week 1, and Weeks 1-4. No tuning or rerunning in response to results. Fixed diagnostic screen: postseason log loss beats corrected and constant overall and beats corrected in at least four of six seasons. Passing never lifts HOLD.

Actual pool points: select the larger home/away probability; ties in selection choose home. Assign points in ascending selected win probability, with game ID as stable tie break, separately for each season/week. Compare realized points and expected points across identical slates. A positive scalar monotonic margin mapping cannot improve confidence ordering over absolute margins; explicitly check and report this. Historical slates use all available matched games and are not evidence of a particular real pool's rules or slate.

Save fit dates, source/code/charter hashes, row predictions, metrics and report in a new exclusive attempt directory. Preserve the original sources. No new percentages are added to tonight's locked predictions. Calculator percentages are user assumptions, initially blank, with validation for missing, nonfinite, out-of-range and duplicate point entries.
