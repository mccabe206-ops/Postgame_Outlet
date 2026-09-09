# Task 3 independent review

Status: **CHANGES REQUESTED — 1 Important finding; no Critical findings.**

## Important

1. `data/writeups/SF.md:16` still presents Dre Greenlaw only as a defensive
   anchor, although the task handoff explicitly requires the dated context that
   he was limited with an Achilles issue (`output/opening-night/tasks/task-3-report.md:114`).
   The pinned NFL roundup supports that status
   (`research/pgo_opening_night_20260909/injuries/capture-20260909-fourth/nfl-sept8-roundup.html:1`).
   This omission leaves a current availability limitation out of a prioritized
   SF/LAR writeup. Add the limited/Achilles context to the Week 1 note or defense
   bullet and cite the existing September 8 NFL update. Keep the approved +0.5
   defense grade unchanged and do not imply a final game designation.

## Verified

- All 13 successful source captures match the byte counts and SHA-256 values in
  `evidence-manifest.json`; all nine recorded publication/update clock pairs are
  present in the corresponding captured HTML. The one failed Bills URL is
  disclosed without fabricated bytes.
- `pgo_injury_source.load_snapshot` accepts `injury-source.json`; it retains 32
  teams and 29 players. The raw NFL overview contains 28 `No Injuries Reported`
  placeholders, and the package consistently labels those teams unknown rather
  than healthy.
- All 29 player identities reproduce as unique normalized full-name matches on
  the same canonical team in the pinned roster, with matching GSIS IDs. The
  roster file's current SHA-256 matches the identity receipt.
- The eight reviewed annotations remain annotation-only and explicitly deny
  final-inactive status. Both Donald and Alfred Collins conflicts preserve the
  practice observation and the dated official-news evidence without inferring
  chronology from the undated league table.
- All 32 current writeups match the initial and follow-up application receipts;
  `data/ratings.csv` matches the recorded approved-ratings SHA-256. The rendered
  preview exposes the checked clock, four-team formal/practice split, 28-team
  unknown count, annotation-only treatment, and pending final inactives.

No fetch, overlay build, snapshot import, study, or model run was performed.
