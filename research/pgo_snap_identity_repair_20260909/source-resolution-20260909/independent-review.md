# Independent review: identifier evidence and bounded correction diagnostic

Reviewed 2026-09-09. **PASS for the evidence, exact-row ledger and diagnostic
implementation within this scope; no unresolved review blocker.** This review
does not adopt corrected sources, qualify historical timing, reconstruct a
model, or remove EXPERIMENTAL / HOLD.

The reviewer investigated the three early identities separately, then reviewed
the other four identities and the shared provider excerpt. The only new write
in this review is this note. No full all-season snap sweep was executed by this
reviewer; the evidence below is the independent 115-conflict check and code review.

## Reviewed pins

| Artifact | SHA-256 |
| --- | --- |
| `corrections.json` | `03d4c415a9f2d3f83cd1a96763965f3cdfe536c8b2c2f78cf159bfb8623c5f5b` |
| `verify_resolution.py` | `f16f7583364bdb522198cc7ba9ccf7830e4cf67b81558deee4f6948cffb67f4e` |
| `provider-evidence.json` | `a48acc5cd40d598a41b1a247ff6e1dbeb2af03c3ec647d4e6a59b953b0e86799` |
| `recent-identities.md` | `0ffaa9e8847686b8050aa13515b48fa99630b1e2771cb8a548c04d066a9c5c2d` |
| Original conflict inventory | `c3f721962886ba77fd1ff8d45637508d2050fd294c0f3185dff77f3561a66a29` |
| Preserved production resolver | `0369a31a13703f2030bd930c37cd3e4087488151706968bff79f1223d9b340d8` |
| Preserved raw-source audit | `332e3a632a4aaace4bd0fb224e9e3b35c98b4b65dad1d169a041a600dc00ee8d` |

## Identity evidence checks

All 115 frozen conflict records match the seven selected provider rows by exact
GSIS, supported PFR, birth date and college. The four later cases also retain
matching ESB and SMART IDs, and every nonblank frozen ESPN ID matches. All 13
retained provider rows (seven targets and six opposite owners) have unique GSIS
and PFR IDs. All five retained manual-overwrite entries agree with that crosswalk.

- Conklin: 17 NYJ 2023 rows / 772 snaps. `ConkTy00` matches the 1995-07-30
  Central Michigan TE; `IzzoRy00` identifies Ryan Izzo, another GSIS and DOB.
- Alabama Byron Young: six LV 2023 rows / 99 snaps. `YounBy00` matches the
  2000-11-10 Alabama DT, draft pick 70. `YounBy01` belongs to the Tennessee
  Rams player born 1998-03-13, draft pick 77.
- Weber State Jonah Williams: 15 NO 2025 rows / 319 snaps. `WillJo16` matches
  the 1995-08-17 defensive end. `WillJo10` belongs to the Alabama offensive
  tackle born 1997-11-17, a different GSIS and draft history.
- Jacoby Jones: one WAS 2025 row / 11 snaps. Exact provider GSIS
  `00-0040317` maps to `JoneJa16`, with DOB 2001-07-18 and UCF/Ohio history.
  The note correctly leaves ownership of `JoneJa15` unknown; it does not
  falsely attribute that ID to the older player with the same name. The positive
  mapping is supported independently of the obsolete/erroneous ID's ownership.

Week lists and counts in `recent-identities.md` match every frozen record. Its
primary-source links, indexed-PFR retrieval limits, related-provider caveat and
historical-vintage limitations are retained. This review used the recorded
provider excerpt and did not repeat all remote downloads. The early investigator
separately observed the identical full crosswalk response hash.

One minor documentation issue was closed before this review pin: an optional
current PFF-ID claim was not supported by the retained selected fields. The
researcher removed that claim and retained the narrower PFR-only limitation.
No remaining unsupported GSIS-to-PFR linkage was found within the seven cases.

## Ledger and code review

The ledger covers exactly the 115 inventory-named ACT rows and seven identities.
Each correction retains the full raw row, its canonical JSON hash, original PFR,
supported PFR, provider row and source-file hash. The pre-existing team alias
normalizer reconciles raw `HST` with inventory `HOU`; the raw row is still retained
unchanged and compared in full at application time. No other row-field
normalization or nickname override is admitted.

`apply_rows` refuses duplicate corrections, duplicate affected source keys,
missing affected rows, altered full rows, altered original PFR/hash and changed
source hashes. It changes only `pfr_id` in copied dictionaries. `load_inputs`
requires exact provider/inventory/preservation pins and unchanged production
resolver/audit hashes, derives the expected correction key set from the original
conflict inventory, and rejects missing or extra correction scope.

The diagnostic temporarily wraps the source reader and resolver in its own
process. It calls the unchanged strict resolver and does not catch or convert
new identity conflicts. It compares both strict and legacy results for every
unlisted snap row, checks each former conflict's complete snap row, verifies
team/season metric deltas, retains ambiguity rejections and named regression
examples, and requires the full expected denominator. Original audit duplicate
assignment and contradictory-roster guards remain in the called path.

The CLI refuses optimized Python (the reused audit has assertions), refuses an
existing receipt or a receipt outside this directory, and opens a permitted new
receipt with exclusive creation. Read-only stdout replay is also available.
No network fetch, history updater, feature construction, model fit, source
writer, forecast writer or production adoption call occurs in the reviewed path.

## Independently executed checks

Executed with `python -B`, importing definitions without running the diagnostic:

- Final row-guard self-check: two positive cases and eight negative cases passed.
- Loaded and independently inspected all 115 ledger entries and provider matches.
- Read the pinned raw roster files for affected seasons, selected the complete
  ACT roster groups containing those 115 rows, and applied only the ledger copies.
  Row count was preserved; exactly 115 rows differed, solely in `pfr_id`.
- For every inventoried conflict, the untouched original group still raised
  `Conflicting snap PFR/name identity`. Its corrected in-memory group resolved
  the snap to the exact inventory GSIS using the `pfr` method: 115 of 115.
- All 451 files in the loaded protection set matched their expected SHA-256
  values both before and after these checks.

These checks substantiate the bounded row correction and preservation. A later
full diagnostic receipt must separately substantiate all-season unchanged-row
and denominator claims. Even a passing diagnostic remains an unadopted
source-resolution result; original STOP receipts and model gates remain intact.
