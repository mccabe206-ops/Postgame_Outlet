# Final independent preservation check

**PASS: no source mutation drift.** Use `final-preservation-qualified.json` as the final result; the initial raw comparison and the line-ending diagnostic remain separately preserved.

- All **431** original-checkout paths in `preserved-checkpoint.json` match their recorded SHA-256 values.
- All **476** `qualification.json` protected-after paths match their recorded SHA-256 values; protected-before and protected-after maps are identical.
- All **51** tracked `docs/evidence` files match both original-checkout bytes and base Git blobs exactly.
- `docs/index.html` matches the preserved source checkout exactly: SHA-256 `2b2490159152dc54d77231b8f7460eb98f15deda8a29480a017a366e922cc434`. Its 2,129 CRLF newlines reflect the existing checkout representation. Comparing CRLF as LF reproduces the base Git bytes exactly (base SHA-256 `756c28658f4a288e33063d8fd54130ebaa87ebfd599f02b114bd7d757d5f045a`). Git reports no diff. No file was normalized or rewritten.
- Both prior snapshot entries equal base parsed entries; exactly one opening-night edition was added.
- All **32** current quarterback names and exact numeric component grades match `editorial-import.json`.
- The original Downloads mock remains SHA-256 `164f9b55a42064ef3107f4e089cb32cd99acec93ac8dd20342d9afd37ca8dae7`.

This was a fresh read-only filesystem/Git check against base `275289e71ae4d8950b621f86447fff673f84840d`. Only the requested result files under `output/opening-night/tasks` were created. No source fetch, regeneration, source edit, study or model run occurred.
