# PGO primary board implementation plan

**Goal:** Lead the public PGO presentation with the approved September 9 edition.

**Architecture:** Reorder the existing verified renderers and put the earlier
board in a native disclosure. Keep frozen model packages and forecast ledgers
unchanged. Update the Shopify wrapper after the generated app is published.

**Tech stack:** Existing Python, HTML/CSS, native details, GitHub Pages, Shopify.

## Tasks

- [x] Reuse `pgo_current_board.py`, `pgo_model_updates.py` and
  `pgo_forecast_lab.py` to lead with September 9 and preserve earlier links and
  grades under `Compare previous models`; adjust `pgo_comparison.py` only where
  required by its existing composition and page boundaries.
- [x] Update the existing affected UI checks for primary order, hidden archive,
  experimental/injury copy, optional-evidence fallback and deep-link access.
- [x] Update `docs/model-update-2026-09-09.md` to distinguish the historical test
  outcome from the newly approved display order.
- [x] Regenerate with `python -B pgo_comparison.py --refresh-mccabe` and
  `python -B pgo_forecast_lab.py`; independently verify preserved source/forecast
  bytes and primary rank identities (SEA 2, NE 6).
- [ ] Check desktop and narrow-screen views, publish the app and verify live
  page bytes; update `shopify-theme/templates/page.power-ratings.json` in the
  native-theme worktree with matching explanatory copy and the new app release.
- [ ] Verify live Shopify readback and automated build status; save publication
  evidence under ignored `output/pgo-primary-board-20260909`.

User approval and publication authority are already recorded in the conversation.
No model fitting, evidence rewriting or new numeric injury adjustment is part of
this change. Existing renderer tests are reused; no new testing framework.
