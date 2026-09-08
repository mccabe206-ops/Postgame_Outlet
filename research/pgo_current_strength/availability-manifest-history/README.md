# Availability manifest history

The canonical `availability-20260908/manifest.json` is the exact first-generation
receipt (SHA-256 `68e72c6ef2c3dd267f9a80154f0b79035e27651a0525c01cc73cd303913ddf42`).

After that build, the generator received a repository-root import bootstrap so it
can run both as a direct script and with `python -m`. A `generator_sha256` field
was then added to the existing manifest. That metadata-only receipt is preserved
as `manifest.with-generator.json`; every one of its nine member artifact hashes
is identical to the first-generation receipt. `repair-receipt.json` records both
manifest hashes and the two byte-identical temporary CLI reproductions.
