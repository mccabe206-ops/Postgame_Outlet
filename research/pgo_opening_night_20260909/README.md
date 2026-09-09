# PGO opening-night release candidate - September 9, 2026

McCabe's supplied slate/Cobalt theme, all 32 approved grades and writeups are
implemented in the existing renderer. The board has a signed rating scale,
readable mobile columns, sorting, historical editions, and keyboard drawers.
Dated official injury notes correct stale editorial claims and add current
availability beside affected Fantasy players. The saved Fantasy points and
issued PGO forecasts remain unchanged; PGO remains EXPERIMENTAL / HOLD.

This is a local release candidate. Public generation, push, and Shopify changes
have not been performed. `HANDOFF.md` requires explicit release approval after
review of the private artifact.

## Evidence

- `editorial-import.json` records exact extraction of the 32 supplied rows and
  prose before dated corrections. `mccabe-dashboard-reference.html` preserves
  the supplied file at SHA-256
  `164f9b55a42064ef3107f4e089cb32cd99acec93ac8dd20342d9afd37ca8dae7`.
- `injuries/editorial-application*.json` records the subsequent factual wording
  changes. No injury point penalties were invented and approved grades remain
  exact. `injuries/injury-source.json` is the validated 32-team, 29-player ledger;
  `annotations-reviewed.json` and the dated capture folders retain source bytes,
  IDs, publication clocks and actual observation clocks.
- The official reports were checked September 9, 10:42-10:46 a.m. Eastern:
  NE/SEA final game designations, SF/LAR practice reports, and 28 teams with
  unknown formal coverage in the league overview. Those placeholders do not
  establish health. Final inactive lists are still pending.
- `identity/package-complete-20260909/source-manifest.json` explicitly selects
  the qualified historical correction package. Its reviewed SHA-256 is
  `17f1dec348ad4992dbe32c6e5d54461ef8bd858e7e9d1775e37951385c492f2a`.
  All 219 occurrences of seven evidenced identity conflicts are corrected in
  derived sources, with zero residual conflicts or changed strict assignments
  versus the preserved 115-row diagnostic. The full comparison covers 310,475
  REG snap rows / 416 team-seasons; 8,461 unresolved rows remain unresolved.
  Raw sources and default model source selection remain intact.
- `identity/package-20260909` retains the first STOP attempt and its exact
  builder. Only `package-complete-20260909` passed. No historical feature walk,
  model fit, spent-study rerun, or forecast adoption occurred.
- `reviews/` contains task reports, independent reviews, and follow-up reviews.
  Earlier findings are retained alongside their resolutions.

## Validation and private preview

The final integration receipt records test outcomes, browser checks, source
preservation, the local checkpoint and the generated preview hashes. The
repository's supported suite is `python -B -m unittest discover -s tests`;
the separate corrected-roster checks are the three modules named in the Task 1
report. Plain `python -m unittest` has an existing sibling-import discovery
problem; the supported invocation is authoritative.

The private preview is `output/opening-night/site/index.html`, served at
`http://127.0.0.1:8769/`. The Task 1 report contains its regeneration command.
The local `output/opening-night/build_preview.py` helper additionally asserts
that removing the separately marked current injury notes recovers every byte
of the saved Fantasy panel. Saved Forecast Lab files and evidence are copied
into the private preview directory for inspection.

Browser review covers desktop 1280 px, mobile 375 px and embedded width 640 px;
no page overflow, all-column scrolling, sorting, historical snapshots, keyboard
drawer open/close and focus restoration, separate McCabe/PGO views, Fantasy
search, and Henderson OUT / Horton QUESTIONABLE source badges.

## Next game-day check

NE at SEA kicks off tonight at 8:20 p.m. Eastern. Recheck official inactive
announcements before the 7:20 p.m. T-60 checkpoint; absence of an announcement
is not permission to infer an inactive list. The exact append-only capture
command is in `reviews/task-3-report.md`. It captures evidence only: inspect the
actual announcement, verify exact team/GSIS identities and source clocks, then
prepare the separately reviewed inactive lock. Never derive it from practice
participation or the current injury-report ledger.
