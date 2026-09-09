# Final model-presentation and publication-integration review

**PASS. No Critical or Important findings remain.**

Reviewed frozen theme commit `c859c508fff53ab599990d9ad798170b8176057b` and publication merge `436487b` against reviewed parent `438878b` and upstream `951ec61`. The theme worktree is clean. None of the five theme paths differs between the publication merge and the theme commit's base, so the reviewed theme applies without an independently changed version of those files. Exact checked hashes and test counts are in `final-presentation-release-review.json`; merge-data checks are in `publication-merge-review.json`.

## Presentation

The current corrected table and September 7 ranking table reuse one team-marker and signed-bar renderer. Rank/team/rating remain the mobile essentials; native, labeled checkboxes reveal additional columns within horizontal table containers. The shared dark theme keeps the July archive's existing structure and disclosure intact. Existing links, team IDs, source clocks, model limitations and EXPERIMENTAL / HOLD remain unchanged.

An initial review found that the proposed -8/+8 bar range clipped actual September 7 values down to -12.325 without context. That issue is resolved: the final shared -14/+14 scale covers both issued snapshots, retains their numeric values and marks any future clipped value in the accessible label. Positive, negative, zero, issued ranges and out-of-range behavior are tested.

Independently rendered all 32 actual corrected rows and all 32 September 7 rows in memory. They retain source ranking order, exact `data-value` numbers, existing display precision (three decimals for current corrected; one decimal for September 7), selected QB identities and source links. All 50 forecast-evidence files remained byte-identical. The July archive roundtrip and Fantasy compatibility tests pass. No model equation, trained parameter, forecast or grade changed in the theme diff.

`python -B -m unittest tests.test_pgo_current_board tests.test_pgo_forecast_lab -v`: **44 passed** independently after the final range correction.

## Publication reconciliation

Independently checked merge `436487b`:

- All 32 approved numerical component grades and quarterback names match the original editorial-import receipt; San Francisco offense remains exactly `0.2`.
- Exactly 20 rating rows changed only their notes versus `438878b`, and each adopted note equals upstream `951ec61`.
- All 32 reviewed writeups are byte-identical to `438878b`, preserving the dated sourced BUF/LAR/NE/SF corrections. Rich writeups take precedence over the older shorthand rating notes in the published drawers.
- `data/snapshots.json` and issued `docs/evidence` are unchanged versus `438878b`.
- The upstream KC-only historical injury marker is retained in `generate_site.py`; the upstream `injury_recovery.csv` is preserved exactly and has no Python/JS consumer in this checkout. It is not applied to model values or player availability.
- Final config has all three columns and nine unique complete rows. Its latest capture clock is **15:57:22.915277 UTC / 11:57 AM ET**, distinct from the earlier player-note clocks. All four fresh official source files reproduce their receipt byte counts and hashes. The final config SHA-256 is `97807f8c07f49cb7f47368d5e1b0e2497ce0306be57558d8afa27fe353e661eb`.
- `python -B -m unittest tests.test_mccabe_opening_night tests.test_pgo_current_injury_notes -v`: **8 passed** independently in the publication checkout.

The intermediate local config writer failure is not present in the reviewed merge. The preserved application receipt records its repair; this review makes no claim to have independently audited remote publication history beyond the final Git/artifact state.

Final integration checked: publication commit `0f42ba08c064c89fc5eefa2530e7adcb6df94e75` contains theme Git blobs identical to `c859c50`; its data and issued evidence remain identical to merge `436487b`.

Root owns the final combined render, responsive browser verification and publication workflow. Source/integration approval here does not alter the separate model-readiness conclusion: operationally reproducible conditional output, predictive utility unproved, EXPERIMENTAL / HOLD.
