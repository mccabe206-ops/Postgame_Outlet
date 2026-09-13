# Offensive non-QB participation collection

This prospective descriptive study starts with newly saved offensive inventories.
The charter fixes its scope and exclusions; no model fit, injury weights,
replacement-quality values or forecast changes are authorized by collection.

`pgo_offensive_inventory.capture(state, root, checked_at, inventory_version=2)`
returns a detached version-2 observation. The season writer saves it as
`offensive_inventory`. The default version remains 1 for exact legacy replay;
normal new captures request version 2 explicitly.
Healthy status is `DESCRIPTIVE / NOT IN MODEL`; fields include `generated_at`,
`sources`, `games`, `teams[].players` and `forecast_adjustment: null`. Source
maintenance already archives roster and depth bytes; availability packages are
verified and replayed. The capture function makes no downloads or state writes.
Roster status is context, never a diagnosis. Unresolved roster identities, depth
names and official names remain explicit. Provider depth older than 24 hours is
STALE even when its source was downloaded recently.

Version 2 adds a [verified player-ID table](inventory-v2-addendum.md) because
many roster rows, including offensive linemen, do not have a PFR identifier.
The original roster controls membership and team. Exact GSIS, unique PFR
ownership, name, birthdate and available auxiliary IDs are checked before a
missing PFR can be supplied. Every player retains `usage_identity` with a
qualified `ROSTER` or `PROVIDER` link, or explicit `MISSING`/`CONFLICT` status.
The derived roster is separate; raw roster bytes and earlier captures are unchanged.

The writer refreshes the full player table independently of defensive sources
before constructing new inventories. Its real capture clock, exact bytes and
hash are archived; the source is refreshed after 24 hours. A corrupt selected
source blocks the check instead of falling back. A missing, malformed or stale
player table blocks the new offensive capture while primary grading continues.
The public display reports both overall and offensive-line ID coverage. A
qualified link does not establish health, actual playing time or injury value.

`pgo_offensive_usage_monitor.refresh_shadow(state, previous, root, checked_at)`
returns the optional `offensive_usage` result. Run it after the defender monitor
so it can reuse that monitor's latest snap-count source receipt. It writes only
immutable target/report evidence, never season state or forecasts. Target bytes
keep the existing `injury-usage/targets/<hash>/` custody path, shared by both
monitors. Offensive reports use `offensive-usage/reports/<hash>.json`.

The result exposes `status` (WAITING, READY or BLOCKED), `blocked_reason`,
`coverage_scope`, `selected_games`, `excluded_games`, `pending_games`, `games`,
`metrics`, `source`, `last_attempt` and `report` when available. Metrics count
games, cohort rows, eligible final rows, joined rows, observed zero/positive
usage, missing targets, pending target rows, coverage and invalid/unresolved
target rows. Detailed rows and exclusion reasons are in the hashed report.
`predictive_status` is always UNAVAILABLE and `forecast_adjustment` is null.

Selection uses the latest verified archive manifest strictly before T-60.
Generation time alone never qualifies an inventory. The selected inventory is
reproduced from its pinned roster/depth/availability sources and, for version 2,
its exact original player-ID table before joining
offense_snaps. An invalid chosen snapshot blocks without selecting an older one.
Saved selections and missing-inventory exclusions persist across refreshes.
Targets captured at or before the verified final are pending, not admitted.
Missing source rows never become zero; duplicate identities are counted before
filtering malformed values. PFR identities, team/opponent and supplied target
player names must agree with the saved roster or aliases from its qualified
version-2 player table. Version 1 uses only its original roster identifiers.

Run the bounded offline checks from the repository root:

```
python -m unittest tests.test_pgo_player_identity tests.test_pgo_offensive_identity_refresh tests.test_pgo_offensive_inventory tests.test_pgo_offensive_usage_monitor
```

The real-data test pins the September 12 18:55 UTC archived state, verifies its
sources and availability bytes, and performs an in-memory capture. It explicitly
rejects that old archive as prospective offensive evidence because no offensive
inventory was saved there. This engineering replay neither backfills the two
completed openers nor modifies any archive. Synthetic archive/target fixtures
write only temporary directories; network requests are mocked.
