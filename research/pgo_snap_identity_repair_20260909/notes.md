# Raw snap identity source audit

Latest result: **inventory COMPLETE / source qualification STOP**. The explicit
diagnostic conflict inventory covers 2013-2025, all 32 teams in every season
(416 team-seasons), and 310,475 REG snap rows. The production resolver continues
to raise on contradictory PFR IDs. Its behavior was not relaxed. Diagnostic
conflicts are counted separately from unmatched/missing observations and are
never converted into production history or training values.

`source-conflict-inventory.json` is the latest receipt. Both earlier STOP receipts
remain unchanged. All 26 pinned raw source files and the frozen receipt/context
have identical before/after hashes. There were no history walks, model fits,
source captures, or changes to model/forecast artifacts.

| All 13 seasons | Rows | Offense + defense snap volume |
| --- | ---: | ---: |
| Denominator | 310,475 | 9,957,627 |
| Old resolver matched | 299,785 | 9,635,404 |
| Final resolver matched outside conflicts | 301,899 | 9,714,193 |
| Newly matched | 2,244 | 81,088 |
| Former matches now rejected as ambiguous | 16 | 109 |
| PFR/name conflicts | 115 | 2,195 |
| Remaining unresolved, excluding conflicts | 8,461 | 241,239 |

Of the conflicts, 114 rows / 2,190 snaps were matched by the old resolver;
one row / five snaps was previously unresolved. No old identity was reassigned
to a different nonmissing player. No duplicate raw PFR keys, duplicate resolved
snap assignments, or conflicting ACT roster records were accepted. No exact ACT
duplicates required collapse in these sources. Per-season/per-team denominators
and all newly matched named examples are retained in the JSON receipt.

The seven distinct PFR conflicts are:

| Snap name | Named roster GSIS | Snap PFR | Roster PFR | Seasons / teams | Rows | Volume |
| --- | --- | --- | --- | --- | ---: | ---: |
| Damaris Johnson | 00-0029435 | JohnDa04 | JohnDe22 | 2013 PHI; 2014 HOU; 2015 NE | 30 | 632 |
| T.J. Johnson | 00-0030126 | JohnTJ00 | JohnTo20 | 2014-2017 CIN | 45 | 357 |
| Tyler Conklin | 00-0034270 | ConkTy00 | IzzoRy00 | 2023 NYJ | 17 | 772 |
| Byron Young | 00-0038978 | YounBy00 | YounBy01 | 2023 LV | 6 | 99 |
| Kwamie Lassiter II | 00-0037420 | LassKw00 | LassKw20 | 2023 CIN | 1 | 5 |
| Jonah Williams | 00-0035944 | WillJo16 | WillJo10 | 2025 NO | 15 | 319 |
| Jacoby Jones | 00-0040317 | JoneJa16 | JoneJa15 | 2025 WAS | 1 | 11 |

The complete raw snap row and named roster counterpart accompany every conflict
in the inventory. These are source disagreements; the inventory does not choose
which PFR ID is correct.

All 16 old-match-to-missing transitions are CIN `Michael Thomas / ThomMi02`,
previously GSIS `00-0028908`, rejected because the ACT roster also supplies
Michael as WR Mike Thomas's first name. No full-name priority overrides that
ambiguity. All offense counts are zero. The complete week-to-defense-count
inventory is:

| Season | Weeks and raw defense snaps | Rows | Volume |
| --- | --- | ---: | ---: |
| 2021 | W11: 0; W12: 23; W14: 0; W15: 0; W17: 2; W18: 62 | 6 | 87 |
| 2022 | W1-W8: 0 each; W9: 21; W11: 1 | 10 | 22 |

Under the final guard, all eight named Onwenu/Runyan checks pass: Onwenu
`00-0036198` W15/W16/W17/W18 offense counts 52/74/58/59; Runyan
`00-0036246` W13/W15/W17/W18 offense counts 55/68/64/75. The 2025 final diagnostic
covers 25,395 rows / 768,442 snaps: 25,342 matched / 767,561 snaps,
37 unresolved / 551 snaps, and 16 conflicting / 330 snaps. It adds 258 matched
rows / 11,829 snaps across 21 team/player identities. These completed join checks
do not override the final source qualification STOP.

Current command requires a new, nonexistent output path. `--collect-conflicts`
enables diagnostic inventory; omitting it retains the first-conflict stop:

```
python -B research/pgo_snap_identity_repair_20260909/verify_sources.py --collect-conflicts --output research/pgo_snap_identity_repair_20260909/NEW_RECEIPT.json
```

Final audited `pgo_challenger.py` SHA-256:
`0369a31a13703f2030bd930c37cd3e4087488151706968bff79f1223d9b340d8`.
Current audit script SHA-256, matching the completed inventory receipt:
`332e3a632a4aaace4bd0fb224e9e3b35c98b4b65dad1d169a041a600dc00ee8d`.

## Earlier attempt 1: alias-collision stop

Status: **STOP at 2021 week 11 CIN**. The 2025 audit and 2013-2020 audits completed;
2021 is incomplete, and 2022-2024 were not attempted. This is an identity-only
comparison using pinned raw sources, with ACT roster filtering before the
existing exact/status-only dedup rule and REG snap rows. No feature construction,
history walk, model fit, source refresh or forecast mutation occurred.

2025 covers all 32 teams and 544 team-weeks. Of 25,395 REG snap rows and 768,442
offense-plus-defense snaps, the old resolver matched 25,100 rows / 756,062 snaps;
the repaired resolver matched 25,358 rows / 767,891 snaps. The 258 new matches
cover 21 team/player identities and 11,829 snaps. Remaining unresolved data:
37 rows / 551 snaps. All eight previously documented Onwenu/Runyan examples now
match their expected GSIS IDs and raw offense counts. No 2025 existing match
changed; no duplicate assignments or conflicting PFR/name identities occurred.

The first stopped comparison is source-backed:

| 2021 W11 CIN ACT roster | GSIS | PFR | First name | Football name |
| --- | --- | --- | --- | --- |
| Michael Thomas, DB | 00-0028908 | blank | Michael | Michael |
| Mike Thomas, WR | 00-0033114 | ThomMi04 | Michael | Mike |

The snap row `Michael Thomas / ThomMi02 / SS` has zero offense and defense
snaps. The prior exact-full-name resolver assigns it to `00-0028908`; the new
combined alias map returns missing because both players supply `Michael Thomas`.
The WR's snap row `Mike Thomas / ThomMi04` has eight offense snaps. The audit
stopped rather than accepting the lost prior match or changing either source.

`source-verification.json` records the stopped result, complete earlier-season
and 2025 team denominators, named new matches, exact code/script hashes, and
before/after hashes for all 26 pinned roster/snap files plus the frozen receipt
and historical context. All protected hashes remained unchanged.

The first script launch failed before reading sources because of a wrong import
location for CURRENT_TEAMS. A second development run completed the 2025 joins
but failed its volume assertion because a counter label was incremented twice;
that audit-only bookkeeping was fixed before the preserved source STOP above.
Neither development error caused source changes or model execution.

The first script revision used a fixed output filename and stopped on any lost
old match. That command and policy have been superseded by the explicit output
and diagnostic mode documented above.

## Earlier attempt 2: final resolver stopped on contradictory PFR IDs

The final policy rejects competing aliases even when the older resolver had an
exact-full-name match. Such old-match-to-missing transitions are reportable
rejections; only a different nonmissing identity is a reassignment. The script
now records rejected rows, volume and identities separately, requires `--output`,
and refuses an existing output file. The original STOP receipt remains unchanged:
SHA-256 `366f005b12680f912d63362fc268ce9b15e8289c57a6785ca72b3d6d573dd86f`.

The final shared resolver also refuses a name fallback when the incoming snap
PFR ID is nonempty and the matched roster player already owns another PFR ID.
The separately issued `source-verification-final.json` records **STOP**, with no
completed season under that final code. It stopped at 2025 week 1 New Orleans:

| Source | Player | GSIS | PFR | Position | Offense snaps | Defense snaps |
| --- | --- | --- | --- | --- | --- | --- |
| ACT weekly roster | Jonah Williams | 00-0035944 | WillJo10 | DL | n/a | n/a |
| REG snap row | Jonah Williams | not supplied | WillJo16 | DE | 0 | 13 |

The exception was `Conflicting snap PFR/name identity: WillJo16`. The data contain
contradictory PFR IDs; this audit does not determine which source identity is
correct. The guard was not relaxed, no source was changed, and no retry occurred.
The previously reported 2025 totals and eight example successes belong to the
earlier resolver revision only. They are not final-code qualification. No
all-13-season totals or complete rejection inventory can be claimed from the
final stopped attempt; the eight named examples were not reached in that run.

Final audited `pgo_challenger.py` SHA-256:
`0369a31a13703f2030bd930c37cd3e4087488151706968bff79f1223d9b340d8`.
Audit script SHA-256:
`7d9a9116f359cc9067d80f16df58aa18b6f5f497d85053372b4051d3fa8471b1`.
All 26 pinned roster/snap file hashes and the frozen receipt/context hashes match
before and after. No histories, features, fits or sources were regenerated.

Final command, already executed; its output is preserved and cannot be reused:

```
python -B research/pgo_snap_identity_repair_20260909/verify_sources.py --output research/pgo_snap_identity_repair_20260909/source-verification-final.json
```
