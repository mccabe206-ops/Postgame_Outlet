**Verdict:** I found no blocking correctness defect in the seven-arm adapter, its symmetry construction, or its evaluation. The attempt02 directory contains only a start receipt, so no arm has a result yet and nothing from it can be cited. New England first is a reproducible output of a HOLD model, not a supported claim about team strength, and the newest evidence leans against using this model class as a fixed preseason rating at all.

## Adapter checks that pass

- **ACT filter reaches the right layer.** The scope replaces the reader at `research/pgo_input_audit/audit_model.py:127-131`, and the walker resolves the input loader at call time at `pgo_challenger.py:1993`, so the fresh loader at audit_model.py:133-142 bypasses the memoized cache. Filtering happens before the status-collapse at pgo_challenger.py:2478-2501, and the post-build assertion at audit_model.py:235-239 would abort on any leak.
- **Exposure fix is applied consistently.** All three QB feature call sites resolve `ch._qb_features` dynamically: pgo_challenger.py:2183, pgo_current_strength.py:113, and pgo_current_strength.py:259. The current-feature reconstruction runs inside the scope at audit_model.py:230-246, so historical and 2026 construction match.
- **Symmetric augmentation is mathematically sound.** The augmented training set is closed under negation, so finite-feature medians are exactly zero, missing flags are even, and the normal equations decouple. Intercept and flag coefficients are therefore near machine zero at every IRLS step, and the alpha-200 objective on doubled rows equals exactly twice the alpha-100 objective on original rows with intercept and flags removed. Scales and the Huber MAD do change, which neutral-field-audit.md:65 already discloses.
- **Evaluation direction is right.** Improvement is baseline error minus candidate error at pgo_opponent_evaluation.py:172, and the totals check asserts that direction at check_totals.py:108. Each original game is evaluated once with original venue and rest.
- **Retry claim holds.** The interrupted evaluator differs from the current one only by holding every arm's context in a dictionary and by its output path. No input, fit, or comparison changed.

## Findings

1. **Medium, interpretation.** The -0.801 neutral offset changes no rank. Centering at pgo_strength_evaluation.py:95 and pgo_challenger.py:1261 cancels it, so it affects only neutral-site game margins. It is also a poorly identified quantity: home_field has median one, so the constant is pinned by 37 neutral games with a standard error near two points. The README leads its confidence section with this finding, which has no bearing on the NE question. Add one sentence saying so, and describe the symmetric arm as a specification prior rather than a data-validated repair.
2. **Medium, evidence framing.** The frozen-season replay is the closest evidence to the issued product, and it is negative. Frozen recency loses to frozen v0 even with oracle Week 1 identities that favor the recency model. The README says this does not decide the new arms, which is true, but it should say plainly that the issued fixed-strength forecast has no positive evidence against the simple v0 baseline in its own use case.
3. **Low, arm scope.** The active-only arm changes more than eligibility. Snap history and last-team updates at pgo_challenger.py:2325-2331 now skip non-ACT weeks, so role memory persists rather than decaying to zero. Disclose this in the active4 description so a result is not attributed to eligibility alone.
4. **Low, receipt.** For active4 the immediate control is also reference4, so the two bootstrap keys at audit_model.py:567-572 collapse into one. Harmless, but the receipt loses its explicit control label.
5. **Low, fragility.** The reproduction gates at audit_model.py:554 and 547-552 require bitwise float equality with the prior run. A BLAS or numpy difference would abort the run as a false alarm, not a defect. Do not edit any protected file while attempt02 may be running, because the final hash check at audit_model.py:601 would fail the run.
6. **Low, site wording.** `pgo_comparison.py:857-862` still calls the output a neutral-field point strength. Given this audit, the rating difference is the antisymmetric part of the model, and the model's own neutral prediction differs from it by the offset. The New England explanation at pgo_forecast_lab.py:653-657 is accurate.

No new temporal, identity, denominator, or scaling error surfaced beyond the declared limitations: final weekly statuses, recorded starters, and 2025 injury vintages are not T-60 knowledge. The scheduled 2026 coach comes from the frozen September 7 schedule, which is safe. The rushing exposure fix, the 0.5 offseason retention applied once per arm, and the eight-game current features from eight-game state are all implemented as chartered.

## Is New England first defensible?

| Quantity | Value |
|---|---:|
| Issued NE lead over LAR | 0.287 |
| Rolling MAE, recency vs v0 | 10.12 vs 10.27 |
| Frozen-season MAE, recency vs v0 | 10.92 vs 10.74 |
| Roster-continuity removal MAE gain | 0.024, interval above zero |
| NE 2025 bias, full candidate | underpredicted by 8.70 |

The lead is smaller than the movement any retrained variant produces, the model's edge over a simple Elo is not significant in rolling use, and it loses in frozen use. The lead over the Rams depends on a roster term whose removal improves accuracy. That makes the rank an arithmetic fact about a saved fit, not evidence of the strongest team. Nothing shows NE is wrong either; the 2025 underprediction argues against a permanent NE bonus. The honest public statement is the one the README already makes, plus the two clarifications in findings 1 and 2.