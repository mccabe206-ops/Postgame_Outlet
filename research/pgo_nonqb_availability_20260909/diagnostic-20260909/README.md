# Saved availability-term diagnostic

**EXPERIMENTAL / HOLD.**

All 2,127 saved games replay within 4.44e-16 points. With availability MAE is 10.099455868; zeroing the two observed terms gives 10.097429512. Availability MAE gain is -0.002026355, with paired season-block 95% interval [-0.008629912, +0.003355498]; 4/8 seasons improve.

- Post-hoc diagnostic on already inspected 2018-2025 history; not new validation.
- Historical availability includes QB lost snaps and heuristic status probabilities; this is not an isolated non-QB injury test.
- Only observed offense/defense availability values are zeroed; nulls and all missingness indicators are preserved.
- The same saved season-fold coefficients and preprocessing are used for both predictions; no refit, tuning, historical rebuild or promotion.
- Historical feature publication vintages and historical starter identities retain their previously documented limitations.
- This does not validate the new last-four-positive-snap role proxy or the new OUT/IR/PUP versus uncertain-out scenario policy.
- Eight season blocks give limited uncertainty information; intervals are diagnostic, not scenario confidence ranges.
- Issued forecasts and the active corrected fit remain unchanged. EXPERIMENTAL / HOLD.
