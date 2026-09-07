# PGO snapshot refresh implementation

Scope is defined in ../specs/2026-09-07-pgo-snapshot-refresh-design.md.
Use the existing isolated league-profiles worktree; preserve old evidence.

1. Recover the public predictor with recorded parameters and verify every
   published CSV field. Capture and independently qualify current inputs.
   Keep executable recovery/qualification receipts under the dated output
   directory; put portable evidence in the new public edition.
2. Add `pgo_forecast_snapshot.py` to build and verify one explicit edition.
   Reuse existing feature construction, preprocessing, matchup prediction,
   canonical lock validation, and exclusive output writer. Do not modify
   historical challenger or prospective scientific behavior.
   - `load_snapshot(directory)` returns the verified snapshot dictionary.
   - `snapshot['generated_at']` is actual UTC issuance.
   - `snapshot['teams']` contains rank, team, rating, qb_name, qb_gsis_id,
     old_selector_qb_name, old_selector_rating, raw features, and centered
     feature contributions.
   - `snapshot['games']` contains game_id, season, week, kickoff, game_type,
     home, away, location, home_rest, away_rest, margin, total, home_points,
     away_points, pgo_v0_margin, legacy_margin, old_selector_margin.
   - `snapshot['method']` and `snapshot['sources']` explain formula/coverage.
   - `snapshot['lock']` is a separately issued schema-1 canonical margin
     lock. Scores and the candidate identity are separately bound in the
     snapshot manifest; this is not the August attestation.
   Save `snapshot.json`, `forecasts.csv`, `ratings.csv`, `manifest.json`, and
   portable source/fit/recovery evidence to an exclusive new directory.
   First check: changing QB order changes features without altering EPA,
   missing/non-active QB1 fails, scores reconcile with total/margin, and
   reload rejects tampered bytes and algebra/identity violations.
3. Extend `pgo_forecast_lab.py` with the verified September edition as the
   primary view; retain the original archive in a separate labeled section.
   Use native details/week navigation, show Week 1 first, all 18 weeks,
   32 team ratings with QB assumptions, score/spread/total explanations,
   downloads, and independent experimental records. Tests cover sign,
   rounding, chronology, unchanged archive, and score/margin/total metrics.
4. Update the model audit with the successful exact-fit recovery and the
   actual new-snapshot findings. Independently review calculations and
   evidence. Run focused checks, then the full repository gate once.
   Verify desktop/mobile rendering and public files after publication.

No new dependencies, speculative model tuning, probability claims, or
automatic promotion. Fantasy payloads and McCabe inputs are unchanged.
