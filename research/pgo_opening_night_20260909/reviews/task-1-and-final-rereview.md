# Task 1 and whole-branch bounded rereview

**PASS for the local source/data implementation. Both prior Important findings are resolved; no Critical or Important findings remain.**

This report supplements, and does not overwrite, `task-1-and-final-review.md`. Its prior evidence checks still apply to unchanged files. The two earlier Minor observations about header freshness and explicit drawer trigger linkage remain nonblocking. This is source/specification approval for a private preview, not public-release, model-performance, or final-inactive approval.

## Reviewed delta

- `pgo_comparison.py:1231-1298` adds separately marked reader notes from the explicitly configured, existing reviewed injury snapshot. The existing loader validates team/player identity fields, unique rows, official HTTPS sources and statuses. The final clock guard also rejects a capture timestamp later than the ledger snapshot time using the existing timezone-aware parser. Annotation matching uses exact canonical team plus GSIS. No same-name or cross-team guessing occurs.
- Henderson's row now explicitly says `Game designation: OUT`, links the official report and displays the actual team-source capture clock. Horton's row says `QUESTIONABLE`. Practice-only observations explicitly state that no final game designation was supplied. Each note retains final inactives pending. The panel introduction explains that notes supersede older availability labels, the displayed points remain from the saved snapshot, Out players should not be started, and missing notes do not establish health.
- The shared `inject_fantasy_preview` seam covers both new Fantasy insertion and McCabe refresh. Existing annotation markers are stripped before reinsertion, preventing duplicate notes. Matching adds text inside the player header; no scoring cells, `data-inactive`, `data-base-points`, saved availability labels, scoring payload, or league calculation changes.
- Checked `fantasy_league_ui.js`: filtering and identity use row data attributes, and score/rank refreshes rewrite other cells, so the new header notes are preserved through sorting, filtering and league recalculation.
- `data/writeups/SF.md:16` now supplies the dated Greenlaw limited/Achilles note with the official source and no invented final designation. `task-3-rereview.md` independently passes this correction. Its current SHA-256 matches the append-only Greenlaw receipt, which chains to the preceding SF followup hash. Approved defense remains `+0.5`.

## Independent checks

- `python -B -m unittest tests.test_pgo_current_injury_notes -v`: all three tests passed. These cover all saved HTML bytes recoverable after stripping annotations, annotation idempotence, the strict Fantasy validator, Out/Questionable/practice distinctions, source links, a mismatched-team negative case, and a future capture-clock negative case.
- In-memory full McCabe refresh run twice with identical base input produced exactly identical output. Stripping the new annotations from the refreshed Fantasy panel recovered the issued Fantasy panel exactly. Seven fantasy player identities receive notes, including Henderson (`00-0040734`) and Horton (`00-0040648`). No model source or projection package was run or rewritten.
- The approved ratings hash remains exactly `3a3d88f8bbaee1d227642c27fe43a5eac101d4947dda66cc1011302a6157898d`.

## Current checked SHA-256 values

| File | SHA-256 |
| --- | --- |
| `generate_site.py` | `b68965ca5ec414338405cdc00866d2abb8355871dd8ad15f80aac3138ca4d1dd` |
| `pgo_comparison.py` | `3bbeb068ca4a0967343ddb54a75ef3fd84ffc7242a06251b8b64e43c38bae8ca` |
| `data/config.csv` | `39ec20b6549f96f550dd92f13e97f835b743614797396ee556c7708e38369344` |
| `data/writeups/SF.md` | `fd895249b23da561dc2bd31a3eae46263305bc927390cf2e75491cbfc77380ae` |
| `tests/test_pgo_current_injury_notes.py` | `80e3d59f5a3a77308bb64d7a14cf251ffa05db0bb049e3ca7f9cb7bb68df8138` |
| `research/pgo_opening_night_20260909/injuries/injury-source.json` | `4c4927b7bbb7469d2700e8c330f186fde1d108bacb1e44d9b8c0504d921645ac` |

Root retains responsibility for the repository-wide suite, final post-commit private HTML hash/parity/source-clock check, and rendered review of the new notes. Those checks are not claimed here. No publication authorization is implied.
