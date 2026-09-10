# Task 1 and whole-branch independent review

**HOLD pending the new Fantasy availability annotation fix. The previously frozen source/data passed the bounded static checks below, with two Minor findings.**

Reviewed base: `275289e71ae4d8950b621f86447fff673f84840d` plus the uncommitted opening-night changes and the copied prior snap repair. Root confirmed source/data freeze on September 9. This is a code/specification and evidence review; root owns rendered browser QA and the full repository suite. No publication, model fit, package rebuild, source fetch, or forecast rewrite was performed by this reviewer.

## New Important integration finding (root browser review)

The preserved Fantasy Henderson row still presents an older Sunday DNP/no-game-designation context beside its frozen projected points, although the new official report marks him Out. Preserve frozen projections, but add current source-backed availability context within the Fantasy view so that the old projection is not mistaken for current playable guidance. Root and the theme agent are implementing that bounded presentation change. This report is provisional until that delta is reviewed and source is frozen again. Task 3's independent review additionally requests the source-backed Dre Greenlaw limited/Achilles context in the SF writeup; that separate Important finding also needs closure before a whole-branch PASS.

## Minor findings

1. `generate_site.py:487-489`: the header's Updated date still comes from generation time rather than the selected edition's saved lock time. It is accurate for this September 9 preview, but regenerating the same edition on a later day can imply fresh editorial work. The approved theme review requested edition-derived freshness. Use the saved edition clock for editorial freshness, or explicitly label a separately displayed build clock.
2. `generate_site.py:396-397`, `generate_site.py:1066-1089`: team buttons preserve real button/dialog semantics, focus trapping, Escape dismissal and focus restoration, but omit the explicit `aria-controls` and expanded-state linkage requested by the theme review. This is a limited specification discrepancy, not a blocked keyboard path; link the trigger to the existing drawer and keep any expanded state synchronized with open/close if adopting that part of the review literally.

## Checked implementation

- Slate/Cobalt surfaces, stronger numeric totals, team markers, signed zero-centered bars, close-by scale labels, mobile quarterback text and the all-columns control reuse the existing renderer and vanilla JS. No new dependency or unnecessary framework was added.
- The new HTTPS Markdown links escape input first. Literal HTML and non-HTTPS link syntax remain inert. Injury status requires a complete status/source/clock tuple and rejects naive timestamps; official report time, evidence-capture time, editorial lock time and final inactive status remain distinct.
- `pgo_comparison.py:80-97` selects and validates the configured new McCabe edition against current rows. `refresh_mccabe_page` refreshes human comparison fields and recomputes explanation rank highlights while retaining the reviewed model data.
- Independently compared all 32 exact editorial component values and quarterback names with `editorial-import.json`, including San Francisco offense `0.2`. The four runnable opening-night tests also passed, including reference HTML hash and all 32 displayed arithmetic comparisons.
- Independently compared old `data/snapshots.json` entries with base Git JSON: every old entry is identical, with exactly one added edition (`Week 1 2026 - McCabe Sep 9`). Current rows validate against the new saved edition.
- Rehashed all 32 current writeups against the injury application plus the followup journal: every final file matches. The original supplied prose remains available in the pinned reference and import receipt; approved grades are unchanged by injury annotations.
- Independently compared the preview's 32 current PGO ranks/ratings and all five historical PGO model cells per archived team with `docs/index.html`: every model value remains identical. Updated human ranks are kept separate. The preview contains one current board and one explanation block, with EXPERIMENTAL / HOLD context retained.
- The preview's complete Fantasy panel equals the issued page's Fantasy panel byte for byte, and the preview contains exactly one Fantasy tab. Companion navigation and saved snapshots remain present.
- Independently rehashed all 431 paths in `preserved-checkpoint.json`: zero mismatches. The original snap-repair checkout is untouched. Reviewed the already independently passing Task 2 source-package report and the strict resolver diff: explicit reviewed-manifest selection, full-row guards, duplicate/conflict rejection and unknown usage remain in place. This review does not elevate Task 2's identity qualification into model acceptance.
- `.gitattributes` preserves research evidence and the intentionally mixed-ending pinned challenger as raw bytes; editable editorial files use explicit LF. The current challenger SHA-256 still equals the pinned `0369...` source identity.

## Checked SHA-256 values

| File | SHA-256 |
| --- | --- |
| `generate_site.py` | `b68965ca5ec414338405cdc00866d2abb8355871dd8ad15f80aac3138ca4d1dd` |
| `pgo_comparison.py` | `9143176005bc5dd68baee84ede12a126770bc602155ccb2fc5139f6dcea311e6` |
| `docs/pgo-theme.css` | `1c2b2a723f5ddfab0918358ca62986d3e53c61dfefb4fe515d7fdf96f6d1c73e` |
| `data/ratings.csv` | `3a3d88f8bbaee1d227642c27fe43a5eac101d4947dda66cc1011302a6157898d` |
| `data/config.csv` | `22ddfc3584db107f0b66030fca88684a13d4de4476a803867382eaec95b1cbd6` |
| `data/snapshots.json` | `69e74d38113d874307eab56e3489051cd1b072cb731044ced11dbcf6888bbd52` |
| `pgo_challenger.py` | `0369a31a13703f2030bd930c37cd3e4087488151706968bff79f1223d9b340d8` |
| `research/pgo_corrected_roster_candidate/adapter.py` | `e09304ea4b88bf837624ab52d678a3075d30faa3f607c956f590c2829d32f8ee` |
| `output/opening-night/site/index.html` | `c6598b98ea19b08aaea7dd3a2a0f2841c38aa18f27e5c531083690d4de81dd16` |

The HTML hash is the private pre-commit parity preview. Root plans to commit locally and regenerate it so the existing Git-based McCabe source timestamp reflects the newly adopted source. That final artifact still needs its own recorded hash and timestamp/content comparison. Task 3 source verification, the full suite and rendered desktop/mobile approval remain separate evidence owned by their assigned reviewers. No public-release approval is implied.
