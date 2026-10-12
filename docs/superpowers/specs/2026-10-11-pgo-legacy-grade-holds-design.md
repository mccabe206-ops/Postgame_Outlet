# PGO legacy grading holds

Approved by the user's "proceed" on the first patch in `output/pgo-qb-reconciliation-20261011/reliability-proposal.md`. Base: `26ef93be2717bd2fb5c0314827136f0197a2c2b9`. This approval includes implementation, required checks and guarded publication of the first patch only.

The season refresh currently fails when CHI–GB's verified final uses 17:00 UTC but two immutable preseason editions saved 20:25 UTC. The shared decorator attempts every legacy grade; its fallback repeats the same failing calculation. Preserve strict identity validation while isolating this legacy kickoff conflict.

The weekly model continues to use strict `record()` validation. An earlier edition with matching game/team identity but differing kickoff is held. Retain that edition's entire last verified record and the actual saved-check time of the authenticated archive supplying it. If none exists, show unavailable counts. Store the affected edition, game IDs and reason separately in `legacy_grading_check`; do not add outcome counts or silently omit the conflict. Repeated holds retain the same verified source and counts. A current weekly identity conflict, wrong-team legacy conflict, changed accepted final, corrupt archive or unverified starter remains rejected.

The independent healthy weekly grades, availability, current-lineup calculations and publishing can continue. Historical accuracy and comparisons for held editions must be explicitly unavailable, with their reason and saved record date; they must not look like current complete results. Board, Forecast Lab and existing health reporting disclose the hold.

Custody is verified at save and load: held counts exactly match an authenticated earlier state and replay against its accepted finals; the source pointer and clock are retained from the immediately preceding verified state, cannot be self/future references, and cannot be changed during repeated holds. Use the existing `pgo_season_rollover.load_archive()` archive reader rather than duplicate byte/hash validation. Sources, source clocks and immutable model snapshots remain validated.

Never revise previously accepted final scores or grades; pending forecasts may earn new grades from verified finals. Retain original issue clocks, margins, QB assumptions, confidence allocations and archived bytes. Current calculations remain excluded from locked grading. Keep experimental labels. No dependency, refit, automatic rescheduling approval, publication-queue change or Shopify-content change is part of this patch.

Acceptance: the exact kickoff mismatch saves a new valid state and renders both pages with unchanged, visibly held legacy records and refreshed valid weekly grades. Save/load rejects forged counts, pointers, clocks, missing hold declarations and wrong-team conflicts. Real refresh, required full CI, guarded publication, deployed bytes and the Opera embed must be verified before completion.
