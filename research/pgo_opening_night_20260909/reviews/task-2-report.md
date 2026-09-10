# Task 2: Complete historical identity source package

**PASS: all 219 evidenced roster occurrences corrected in separately hashed CSV derivatives.**
The explicit source manifest supplies 26 verified historical inputs: nine corrected
roster CSVs, four unchanged roster sources, and all 13 unchanged snap sources.
Frozen default source selection, issued forecasts, original CSVs, and prior evidence
remain unchanged. Qualification covers strict historical identity joins only;
the statistical model remains **EXPERIMENTAL / HOLD**.

## Package and interface

Package: `research/pgo_opening_night_20260909/identity/package-complete-20260909/`.

`source-manifest.json` SHA-256:
`17f1dec348ad4992dbe32c6e5d54461ef8bd858e7e9d1775e37951385c492f2a`.

The loader requires explicit manifest selection and its reviewed hash. It returns
the existing `(source_name, season) -> pathlib.Path` interface after checking all
26 inputs, qualification, correction ledger, provider evidence, and code pins:

```python
from research.pgo_opening_night_20260909.identity.source_package import load_sources

paths = load_sources(
    "research/pgo_opening_night_20260909/identity/package-complete-20260909/source-manifest.json",
    "17f1dec348ad4992dbe32c6e5d54461ef8bd858e7e9d1775e37951385c492f2a",
)
```

This call loads historical roster/snap paths only. No automatic override of a
frozen source lock was introduced, and this task did not construct features,
walk model history, fit a model, or generate forecasts. Paths are explicitly
bound to this local checkout and the preserved raw cache; missing/moved inputs
fail verification.

## Exact correction scope

| Player | GSIS | Old PFR | Corrected PFR | Rows |
| --- | --- | --- | --- | ---: |
| Damaris Johnson | 00-0029435 | JohnDe22 | JohnDa04 | 49 |
| T.J. Johnson | 00-0030126 | JohnTo20 | JohnTJ00 | 84 |
| Tyler Conklin | 00-0034270 | IzzoRy00 | ConkTy00 | 17 |
| Kwamie Lassiter II | 00-0037420 | LassKw20 | LassKw00 | 18 |
| Byron Young | 00-0038978 | YounBy01 | YounBy00 | 17 |
| Jonah Williams | 00-0035944 | WillJo10 | WillJo16 | 17 |
| Jacoby Jones | 00-0040317 | JoneJa15 | JoneJa16 | 17 |

The 219-row ledger contains the original 115 rows plus 34 additional ACT rows
and 70 rows in other statuses. Each entry records the source hash, exact CSV
data-row number, complete original row and its canonical SHA-256, original and
corrected PFR IDs, normalized lookup key, and selected provider row. Original
team spellings such as HST remain present in the complete raw-row record.
Only the PFR field changes; all CSV field values otherwise remain identical.
No occurrence of these seven disputed GSIS/PFR pairs remains in the 13 derived
or unchanged historical roster inputs.

199 rows corroborate DOB and college. Twenty extra rows have blank source DOB:
four Damaris ACT rows and sixteen T.J. CUT rows. All twenty exactly match the
provider ESB ID, smart ID, numeric NFL ID, and college. Their DOB cells remain
blank, and their ledger entries record this alternate corroboration explicitly.

## Qualification and validation

The existing strict audit completed all 2013-2025 seasons, 416 team-seasons,
and 310,475 REG snap rows. Every strict resolver assignment and resolution
method was compared with the preserved 115-correction diagnostic behavior.
Every per-season/per-team metric and named example matched that baseline.
The additional 104 corrections changed no REG assignment or missingness result.

| Result | Rows | Offense + defense snaps |
| --- | ---: | ---: |
| Matched | 302,014 | 9,716,388 |
| Still unresolved | 8,461 | 241,239 |
| Total | 310,475 | 9,957,627 |

Zero residual identity conflicts, duplicate assignments, or unexpected
reassignments. All eight Onwenu/Runyan checks and all sixteen CIN ambiguous
rows remain unchanged. Missing observations remain missing. All 476 protected
files matched before/after hashes, including original checkout/source evidence
and copied prior repair evidence. Original raw-source qualification remains
STOP; the new, explicit corrected package has passed its identity join scope.

Commands run from `D:\CodexWorktrees\Postgame_Outlet-opening-night-20260909`:

```powershell
python -B research/pgo_opening_night_20260909/identity/source_package.py --self-check
python -B research/pgo_opening_night_20260909/identity/source_package.py --build research/pgo_opening_night_20260909/identity/package-complete-20260909
python -B research/pgo_opening_night_20260909/identity/source_package.py --verify research/pgo_opening_night_20260909/identity/package-complete-20260909/source-manifest.json --expected-sha256 17f1dec348ad4992dbe32c6e5d54461ef8bd858e7e9d1775e37951385c492f2a
```

All completed with exit 0. Self-check covers positive exact-row, manifest and
identity cases, plus six negative row guards, four negative manifest guards,
and two negative identity corroboration cases. Build output directories must
not already exist; manifest verification can be repeated without writing files.

Final evidence SHA-256:

| File | SHA-256 |
| --- | --- |
| `qualification.json` | `c00e0e756ddee65a04223746095dcd940b94a3b5f2e08ff6f2b759eafb500bfb` |
| `corrections.json` | `af1fd2751ed61c355cfa38435d657cf678e69b97c94bb6c4b83d1bc15bba2c80` |
| `source_package.used.py.txt` | `4ce04c433ff5c88000eb0f337fb07de9ab904737ec80fb02fd811cfece2b9d15` |

## Preserved first attempt

`identity/package-20260909/` is an unqualified, retained STOP attempt. Its first
strict DOB check stopped on an additional Damaris row with blank DOB before
running the full identity audit. The recorded STOP receipt hash is
`274dc401b681d86de44f0436cea71de3bdc93c1489885f571d674c51dfdf14df`.
Its exact original builder bytes were preserved as `source_package.used.py.txt`
before adding the explicit three-ID corroboration rule. That archived code hash
matches the stopped receipt. The successful package uses a separate directory;
no failed receipt or earlier 115-row evidence was overwritten.
