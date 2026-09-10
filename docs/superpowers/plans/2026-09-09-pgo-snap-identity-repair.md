# PGO snap identity repair and player-value definitions

User scope: repair the demonstrated identities and missing-versus-zero handling,
then define player values. The preceding audit and explicit instruction authorize
this repair. No forecast rebuild, coefficient fit, source capture or publication.

The completed study stays at `275289e` in the league-profiles worktree. This
repair is isolated in `codex/pgo-snap-identity-repair-20260909`; copied audit files
remain byte-identical evidence of the prior state.

1. Reproduce NE Mike/Michael Onwenu and NYG Jon Runyan/Jon Runyan Jr. through the
   actual history updater. Use supplied full, first/last and football/last names;
   remove only trailing generational suffixes for matching. Never infer nicknames.
2. Share identity resolution between history construction and coverage. Reject
   ambiguous normalized names, conflicting PFR/name matches, duplicate PFR owners,
   and duplicate snap assignments. Keep matching inside one season/week/team.
3. Preserve explicit observed zero. On a present unit feed, retain the existing
   known-PFR-but-absent convention of zero. Unresolved identity or absent unit
   feed is missing, including role-model targets. Missing observations do not
   enter the four-observation history; stale-role policy remains a separate issue.
4. Run the focused and repository checks, a read-only raw 2013-2025 identity coverage
   comparison, and independent code review. Do not reconstruct the spent model.
5. Write definitions for neutral-field team/unit/player value, reference and
   replacement, role, availability, unavailable estimates and future validation.
   Definitions are the deliverable; no point estimation or component model here.

Files: shared `pgo_challenger.py`, its coverage-only consumer in the candidate
adapter, focused regression tests, and this plan plus definition/evidence notes.
The original frozen adapter and model artifacts remain in the preserved checkout.
