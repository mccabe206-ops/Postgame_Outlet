# Independent ranking-trace review

Scope: saved-artifact arithmetic and descriptive interpretation at HEAD `275289e71ae4d8950b621f86447fff673f84840d`. No fit, feature preparation, source capture, forecast issuance, model change, or adoption was performed. This note is the reviewer's only write.

**PASS for accounting and preservation within the checked scope. EXPERIMENTAL / HOLD remains.** No numerical defect was found in `analyze.py` or its saved `analysis.json`.

## Checks performed

- Executed `analyze()` with `python -B`, without redirecting output or writing its result. Its returned object exactly equals saved `analysis.json`.
- All 46 pinned manifests, manifest members, and diagnostic files matched their expected SHA-256 values before and after execution. This establishes preservation of those inputs, not a whole-repository or all-external-source audit.
- All 32 teams reconcile to both saved boards. Old centered feature contributions agree with the issued corrected snapshot. Maximum reconciliation error across contributions, ratings, and changes is `2.2426505097428162e-14`.
- Independently calculated each candidate term as `effective_coefficient * (team_input - mean_of_32_team_inputs)`, with neutral venue and equal rest. Maximum difference from the trace is `1.0512424264419451e-14`. Effective coefficients are saved coefficients divided by the corresponding saved scale.
- Existing current feature values are identical between corrected and candidate inputs. The candidate adds ten descriptors; the four change groups sum to the complete rating change for every team. Neutral venue, equal rest, intercept, and zero current missingness contribute no centered differences here.
- Independently recalculated overall MAE and RMSE from all 2,127 unique matched historical games. Candidate MAE `10.1335404432`, RMSE `13.1078338083`; corrected MAE `10.0994558676`, RMSE `13.0449889696`. The candidate's further-study screen remains FAIL, with only 3/8 season MAE wins. Week 1 MAE is `10.0353903545` versus corrected `9.8911161532`; weeks 1-4 MAE is `9.8913446031` versus `9.7860122677`.
- Saved evaluation folds are chronological: each 2018-2025 fold's training maximum is the preceding season. This does not resolve historical source-publication vintage or whether recorded starters were knowable at the decision time. Those remain REVIEW REQUIRED.

## Confirmed interpretation details

The added QB-age component, before subtracting the league mean, is:

`-0.1222616226762747 * (age - 27) + 0.0112142891598133 * (age - 27)^2`.

Its mathematical minimum is at age `32.4511534763`. This is a conditional U-shaped fitted term, not an estimated optimal quarterback age or causal aging curve. Age and experience are correlated and other QB performance inputs remain in the model. The QB-experience effective coefficient changes from `-0.2360525261` in corrected to `+0.0841442973` in candidate; its change belongs to existing-feature reweighting, not the newly added age group.

PIT moves from rank 16 to rank 8, a `+2.0566182039` rating change: new QB age `+0.8755437958`, offense descriptors `+0.2125249755`, defense descriptors `+0.6187975094`, existing-feature reweighting `+0.3497519231`. The squared-age term alone is `+2.4964117955`, offset by linear age `-1.6208679997`. Calling the whole change an age boost would omit the roster and existing-feature components.

LAR's gap over NE moves from `-0.6937140708` to `+0.0301210813`, a change of `+0.7238351521`. The gap change comprises new QB age `-0.3742181736`, offense `+0.0500997784`, defense `+0.8877000359`, and existing-feature reweighting `+0.1602535114`. Defense role-weighted draft prior alone contributes `+0.6756028368` to that gap change. The age terms favor NE relative to LAR in this comparison; they do not explain LAR taking first place.

DEN's QB sack-avoidance input is `0.9543487428`, above the 32-QB mean `0.9320777136`. Its conditional effective coefficient is **negative**, `-37.5585915202`, producing the centered term `-0.8364684872`. This is not evidence of poor observed sack avoidance. Other counterintuitive conditional signs include negative offensive explosive-play rate, negative defensive sack-creation rate, negative offense role-weighted draft prior, and negative defensive young-role share. They must not be narrated as independent football-quality grades.

The three reported mirrored correlations recompute exactly: QB age / squared age `0.8045721250`, QB age / experience `0.8995868313`, defense age / young-role share `-0.7931439034`. These are descriptive correlations of complete-case historical game differences and their sign mirrors, not a full multivariate collinearity diagnosis or causal evidence. Complete-case counts are 3,310, 3,308, and 3,391, respectively, out of 3,407 original historical games. All saved folds have negative linear-age and positive squared-age coefficients; repeated signs alone do not establish predictive value.

## Reporting limits

1. These are exact accounting allocations for two saved fitted outputs. Added-feature terms and existing-feature reweighting are not experimental ablations or independently identified player effects. Centering also makes them relative to this exact frozen 32-team set.
2. Rankings are construction diagnostics, not validated estimates of the true team ordering. The LAR-NE gap of `0.0301210813` has no calibrated rank-confidence interval attached.
3. Current availability terms and QB current-minus-full are zero for every team. As documented in `availability-notes.md`, this means the specified construction does not price those injuries; it does not mean every team is healthy. ACT eligibility and complete aggregate feature cells do not imply complete injury or player-role coverage.
4. The input clock is `2026-09-08T15:01:38.802823+00:00`; a September 9 diagnostic filename or recording timestamp is not a source refresh. Historical source-publication vintage and starter-knowledge limitations remain unresolved. None of this trace removes HOLD or authorizes changing the failed candidate.

## Final report review

Reviewed the completed `README.md`, the source-backed finding sections of `player-input-notes.md`, `availability-notes.md`, and `check_player_inputs.py`. **PASS for the report's supported scope; no material factual error or causal overreach found.** All 32 full-board rows and all nine saved-fit coefficient rows in the README match `analysis.json` at the displayed precision. The neutral-site MAEs and Kansas City term signs also match the saved analysis.

The report distinguishes added descriptors from existing-feature reweighting, identifies defense descriptors rather than QB age or a numerical injury adjustment as the main LAR-NE gap driver, and labels current player-team assignments as frozen source observations. The inherited resolver code supports the documented Onwenu/Runyan failure mechanism: absent roster PFR match, differing normalized names, then default-zero usage. The report assigns neither case a fabricated rating delta and does not infer that the original corrected current board uses the new non-QB descriptors.

Availability facts, zero-priced adjustments, stale roles, and unknown source timing stay separate. The proposed identity repair and later role/availability policy work are recommendations for a separate reviewable change; the report does not claim those repairs were performed or that a more plausible ordering validates this candidate. This final report review did not rerun the decomposition or the player helper; the earlier arithmetic verification above remains its basis, supplemented by direct saved-table comparisons and code/evidence reading.
