# Defensive evidence implementation plan

Goal: build an all-team current defensive production/experience panel without
changing a forecast. The descriptive contract is in charter.md.

- [ ] Add focused synthetic tests in test_evidence.py. Confirm they fail before implementation.
- [ ] Implement evidence.py using the existing strict snap resolver and CSV reader.
  Reuse the pinned corrected 2025 identity files and player-stat source; accept a
  hash-checked fresh current capture. Keep all transforms pure and no fitting.
- [ ] Test transfers, postseason, unknown rookies, partial statistic exposure,
  conflicting IDs, future depth timestamps, and unique active backup counts.
- [ ] Build a new output directory, report all32 coverage and current-source
  disagreements. Give the UI agent the artifact and root the exact hashes.
- [ ] Separately report fixed historical candidate formulas/coverage before any
  diagnostic fit. Root owns the predictive charter, model run, and publication.
