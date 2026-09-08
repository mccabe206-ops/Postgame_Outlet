# PGO five-workstream implementation plan

Approved direction: current QB identity/ability, skill-player quality and injury
coverage, component testing, and honest sensitivity on the existing board.
Design and pre-fit rules: [research charter](../../../research/pgo_current_strength/charter.md).

1. Reuse this isolated worktree. Checkpoint the completed opponent experiment.
2. Add a research-only QB adapter with recorded-starter coverage, consistent
   current identity selection and calendar decay. Regression-check missing
   starters, same-kickoff state, shrinkage and snapshot cutoff.
3. Add prior-season player profiles through one roster hook; reuse existing
   injury import/coverage. Check time boundaries, weighting and unknown coverage.
4. Reuse the existing chronological evaluator for four arms and eight refitted
   group ablations. Freeze charter before fitting; verify exact raw reproduction,
   matched games, fold boundaries, source hashes, output exclusivity and metrics.
5. Add one native collapsed Lab sensitivity table and board link/freshness copy.
   Validate all 32 teams and research file hashes; preserve McCabe-first layout.
6. Review the combined diff, run relevant/full checks, verify protected evidence
   and mobile/desktop presentation. Record results and limitations. Keep issued
   forecasts and promoted model unchanged unless separately supported.

Ownership: current-strength adapter and tests (outlier_audit); roster module,
tests and new availability capture (forecast_audit); Lab/comparison renderers,
tests and generated HTML (league_scoring_basis); evaluator, integration and
final verification (root). No dependency or new service is needed.
