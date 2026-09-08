# Verification - 2026-09-08 UTC

- Full regression suite: `python -m unittest discover -s tests` - **520 passed**,
  508.826 seconds. Final presentation follow-up: all 30 Forecast Lab tests passed.
- Independent saved-prediction arithmetic: all 14 metric arms, 33 bootstrap
  comparisons and 1,430 numeric checks passed at absolute tolerance 1e-10.
- Actual-source feature isolation: 3,407 matching games; zero non-QB feature
  changes from raw to starter or starter to recency. Experience/draft inputs
  remain unchanged under recency. No new fits were used for this audit.
- Raw final fit matches all frozen parameters, preprocessing and coefficients
  exactly; all 32 raw current ratings reproduce with zero error.
- Eight research artifacts, nine inference/research code files, 51 protected
  files and all 67 cached source hashes verified. The September verifier still
  reports 32 teams and 272 games. Issued weekly forecasts remain unchanged.
- Availability: nine original member artifacts verified; NE/SEA have model-scale
  deltas, 30 teams remain unknown. Three checks cover formal roles, unknown
  reports and failure on missing reduced-player roles or an unsupported QB case.
  The original manifest is restored exactly; the metadata-only generator receipt
  revision and CLI reproduction evidence are preserved in
  [manifest history](availability-manifest-history/README.md).
- Browser QA: desktop 1280px, mobile 375px and 319px; McCabe opens first,
  sensitivity starts collapsed, its fragment link expands it, and the document
  has no horizontal overflow. The four-arm summary fits the mobile viewport;
  the wider 32-team table scrolls inside its container. Screenshots are retained
  locally under `output/playwright/current-strength-*`. The only observed console
  resource error was the pre-existing local `/favicon.ico` 404.
- Final local HTML SHA-256: index
  `9ea1cc67c1cc3d5041e6f1a7c2c41438a885dda6519860f4de9e5a59dd301809`;
  Lab `a47cd12cd20c2365365315ee405d1287d24cfdeb7c6b5cadf92353b7304be2b0`.
  Lab regeneration is byte-identical. The fantasy panel, embedded data and
  existing comparison cells remain unchanged.

These are implementation, arithmetic, source-preservation and UI checks.
They do not establish calibrated probabilities or prospective predictive
validity. Historical source vintage remains REVIEW REQUIRED; promotion is HOLD.
