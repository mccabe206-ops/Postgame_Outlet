# Seven PGO identity conflicts: supported corrections, bounded diagnostic PASS

The seven disputed identities are resolved by identifier-provider evidence.
Replacing only the incorrect PFR field in 115 exact copied roster rows removes
all 115 previously inventoried snap-join conflicts. The full historical join
check passed without changing any other snap assignment.

**Status: correction evidence and bounded in-memory diagnostic PASS. Original
source files remain STOP / UNADOPTED. PGO remains EXPERIMENTAL / HOLD.**

Worktree: `D:\CodexWorktrees\Postgame_Outlet-snap-identity-repair`, branch
`codex/pgo-snap-identity-repair-20260909`, base `275289e`. This resume added
research evidence and a mockup review; it changed no pre-existing code, raw
source, model, forecast or public file. All work remains local and uncommitted.

## Supported mappings

| Player | GSIS | Incorrect roster PFR | Supported PFR | Conflict rows |
| --- | --- | --- | --- | ---: |
| Damaris Johnson | 00-0029435 | JohnDe22 | JohnDa04 | 30 |
| T.J. Johnson | 00-0030126 | JohnTo20 | JohnTJ00 | 45 |
| Tyler Conklin | 00-0034270 | IzzoRy00 | ConkTy00 | 17 |
| Byron Young, Alabama | 00-0038978 | YounBy01 | YounBy00 | 6 |
| Kwamie Lassiter II | 00-0037420 | LassKw20 | LassKw00 | 1 |
| Jonah Williams, Weber State | 00-0035944 | WillJo10 | WillJo16 | 15 |
| Jacoby Jones, born 2001 | 00-0040317 | JoneJa15 | JoneJa16 | 1 |

The [provider excerpt](provider-evidence.json) records exact GSIS/PFR mappings,
birth dates, colleges, identifying fields, observation times, response hashes
and a commit-pinned provider correction file. The [early-player evidence](early-identities.md)
and [recent-player evidence](recent-identities.md) link primary provider profiles
and official biographies. Six incorrect roster PFR IDs demonstrably belong to
other people. The old `JoneJa15` owner's identity is unverified; positive exact
GSIS evidence establishes `JoneJa16` without needing to guess that history.

The current crosswalk is retrospective corroboration, not proof of historical
publication before a game's decision cutoff. Indexed PFR content was available;
direct PFR page retrieval was blocked for several profiles. These limitations
are preserved in the evidence notes.

## What was verified

[corrections.json](corrections.json) binds every correction to its original
source hash, exact full raw row, old value and provider row. The frozen inventory
normalizes team names; the ledger preserves original spelling such as `HST` and
uses the existing team normalization only for comparison. Duplicate, changed,
missing and extra correction rows fail closed.

The [diagnostic](diagnostic-validation.json) reuses the existing strict audit,
feeding corrected dictionaries only in process memory. It does not suppress
resolver conflicts or write corrected CSV files.

- All 13 seasons, 2013-2025: 310,475 regular-season snap rows, 416 team-seasons.
- Exactly 115 former conflicts resolve to the evidenced GSIS IDs, covering
  2,195 offense-plus-defense snaps.
- All 310,360 other rows retain identical strict and legacy resolver results.
- Corrected copies match 302,014 rows / 9,716,388 snaps; 8,461 rows /
  241,239 snaps remain unresolved. All team and season count changes reconcile.
- Zero remaining conflicts in this snap-join diagnostic, duplicate assignments
  or unexpected reassignments. Eight NE Onwenu / NYG Runyan examples are intact;
  16 ambiguous CIN Michael/Mike Thomas rows remain missing.
- All 451 protected file hashes match before and after; root independently
  rechecked them after completion. Source writes, history walks and model fits: 0.
- Fresh focused repair tests: 129 passed in 17.174 seconds. The new exact-row
  self-check passed two positive and eight negative cases. Independent review
  found no blocker in the bounded evidence, ledger or verifier scope.

Diagnostic receipt SHA-256:
`06a3c24c40358368f46dbc8d355213710f1592580b950068b5bed75ab63a5771`.
The receipt contains the exact ledger, verifier, provider and source pins.
Do not overwrite this receipt or alter its pinned inputs.

Read-only checks, from the worktree root:

```powershell
python -B research/pgo_snap_identity_repair_20260909/source-resolution-20260909/verify_resolution.py --self-check
python -B research/pgo_snap_identity_repair_20260909/source-resolution-20260909/verify_resolution.py --stdout
```

## Remaining source work

There are **104 additional raw roster rows** with the same seven GSIS/disputed
PFR combinations outside the exact 115 correction keys: **34 ACT and 70 other
statuses**. Their season/player/status counts are retained in the diagnostic.
They were not silently included in this correction set. An absence of a snap-join
conflict does not certify the correctness of those remaining roster fields.

The next source task is a separately versioned correction package covering the
remaining occurrences, followed by full-source qualification. Preserve these
115-row results and the original STOP receipts. The 8,461 unresolved snap rows,
the CIN ambiguity, stale-role policy, other roster metadata, and historical
publication timing are separate limits. No numerical rating impact has been
estimated. A new reconstruction or model study must not reuse the spent study
invocation or replace issued forecasts.

## McCabe theme review

The user's supplied `pgo_dashboard_mock_v2.html` was reviewed separately in
[the theme review](../../../docs/reviews/2026-09-09-mccabe-theme-review.md).
Its dark slate/Cobalt direction fits the product; responsive layout, keyboard
controls, sorting and source/methodology access need to be retained from the
existing renderer. The mock also contains substantive McCabe grade revisions,
which remain proposed content changes. Browser policy blocked the local-file
render, so the review is explicitly based on HTML/CSS and arithmetic, with no
claim of rendered visual approval. No theme or revised grades were applied.
