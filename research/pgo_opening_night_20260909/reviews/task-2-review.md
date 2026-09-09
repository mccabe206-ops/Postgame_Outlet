# Task 2 independent review: historical identity source package

**PASS. No Critical or Important findings.**

The package satisfies Task 2's bounded source-identity scope. This review did
not rebuild the package, rerun a study, construct features, fit a model, rewrite
an issued forecast, or change source/default-selection behavior.

## Spec and code review

- Exact-row application fails closed on duplicate/out-of-range row numbers,
  source hash drift, complete-row drift, row-hash drift, and old/new PFR drift;
  it changes only the copied `pfr_id` field
  (`research/pgo_opening_night_20260909/identity/source_package.py:48-63`).
- Blank-DOB rows require exact ESB, smart, and numeric NFL IDs plus compatible
  college; nonblank-DOB rows require exact DOB plus compatible college
  (`source_package.py:35-45`).
- The loader requires the caller-supplied reviewed manifest SHA-256, PASS/scope
  markers, the pinned qualification, all pinned evidence and inputs, and exactly
  both source types for 2013-2025 (`source_package.py:78-98`). No caller outside
  this package currently invokes it, so frozen default selection is not silently
  changed.
- Qualification compares the strict resolver result for each of 310,475 REG
  snap rows against the preserved 115-row diagnostic behavior and requires exact
  per-season/team metrics and named examples (`source_package.py:106-146`). The
  shared resolver rejects PFR/name conflicts and preserves ambiguous/unmatched
  results (`pgo_challenger.py:2237-2252`).
- Build-time guards pin the prior provider/ledger/audit/resolver inputs, hash the
  protected set before and after, write only to a new directory, and retain STOP
  on failure (`source_package.py:149-182`, `source_package.py:250-270`). The
  archived first-attempt receipt remains STOP for `2016/12271`; its builder hash
  in that receipt equals the archived builder bytes.

## Independent evidence checks

- Manifest SHA-256 is
  `17f1dec348ad4992dbe32c6e5d54461ef8bd858e7e9d1775e37951385c492f2a`.
  `--verify` exited 0 and returned `PASS`, 26 sources. `--self-check` exited 0:
  one positive/six negative exact-row cases, two positive/two negative identity
  cases, and one positive/four negative manifest cases.
- An independent row-by-row comparison loaded every original and manifest roster
  CSV. It found exactly 219 unique changed rows, all and only ledger rows, with
  `pfr_id` as the sole changed field. It found zero remaining disputed
  GSIS/old-PFR pairs. The manifest contains nine corrected roster derivatives,
  four unchanged roster inputs, and thirteen unchanged snap inputs.
- Ledger counts independently reproduce 115 original + 34 additional ACT + 70
  other-status rows. Mapping totals are 49, 84, 17, 18, 17, 17, and 17 for the
  seven documented GSIS identities. Identity checks reproduce 199 DOB/college
  rows and 20 blank-DOB alternate-corroboration rows: four Damaris ACT and
  sixteen T.J. CUT rows. Raw values, including 17 `HST` team spellings, remain
  in the complete original-row records.
- The pinned qualification reports 416 team-seasons, 310,475 REG rows,
  302,014 matched / 8,461 unresolved rows, and 9,716,388 / 241,239 respective
  snap volume (`qualification.json:5-24`). It records all eight NE/NYG examples,
  sixteen CIN ambiguous rows, no changed strict assignments for the extra 104
  corrections, zero conflicts/duplicate assignments/reassignments, and
  EXPERIMENTAL / HOLD (`qualification.json:2-28`, `qualification.json:30-125`).
- All 26 manifest source hashes and nine evidence hashes verify at their current
  paths. A fresh independent rehash of all 476 protected paths found zero
  mismatches; the receipt records equal before/after maps
  (`qualification.json:126-127`). Current `source_package.py` bytes also match
  the package's `source_package.used.py.txt` at
  `4ce04c433ff5c88000eb0f337fb07de9ab904737ec80fb02fd811cfece2b9d15`.
- `python -B -m unittest tests.test_pgo_snap_identity -v` ran five resolver
  regressions in 0.325 seconds: all passed. These cover exact source names,
  suffix ambiguity, conflict/duplicate rejection, unresolved-versus-zero usage,
  and absent-feed missingness.

The PASS is limited to the explicit strict historical identity package and its
loader. It does not qualify the original raw-source set, historical publication
timing, model performance, forecast output, adoption, or release.
